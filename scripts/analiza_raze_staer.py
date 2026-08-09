#!/usr/bin/env python3
"""Deterministic, API-free volume gate for the Staer Google Maps analysis.

This command deliberately performs no network requests.  It reconciles the
workbook, removes non-billable/unsafe rows, aggregates duplicates, inspects
local caches, and writes the exact billable universe used by the later stage.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


EXPECTED_TOTALS = {"Staer 7": 6_617, "Staer 9": 11_117, "Staer 23": 11_470}
GEOCODING_LIMIT = 8_000
ROUTE_MATRIX_LIMIT = 25_000
MONTHLY_FREE_USAGE = 10_000
PRICE_PER_THOUSAND_USD = 5.00
SOURCE_SHEET = "Date analizate"
HEADER_ROW = 2
ADDRESS_COLUMNS = [
    "Stradă standard",
    "Localitate standard",
    "Sector atribuit",
    "Județ",
]
PAIR_COLUMNS = ["Magazin standard", *ADDRESS_COLUMNS]
REQUIRED_COLUMNS = ["Magazin original", *PAIR_COLUMNS, "Nr. clienți"]
INVALID_STREETS = {"", "-", "—", "n/a", "nan", "necunoscut", "necunoscută", "1191"}
INVALID_LOCALITIES = INVALID_STREETS
INVALID_COUNTIES = {"", "-", "—", "n/a", "nan", "necunoscut", "necunoscută"}


def canonical_text(value: Any) -> str:
    """Normalize inconsequential whitespace and case without fuzzy merging."""
    return " ".join(str(value).strip().casefold().split())


def find_source(requested: Path) -> tuple[Path, str | None]:
    """Use the explicit repository-root workbook, never the invalid input path."""
    root_workbook = Path("analiza_bazine_clienti_staer_bucuresti.xlsx")
    if root_workbook.is_file():
        warning = None
        if requested != root_workbook:
            warning = f"Calea invalidă {requested} a fost ignorată; sursa validată este {root_workbook}."
        return root_workbook, warning
    raise FileNotFoundError(f"Workbookul valid nu există: {root_workbook}")


def responsible_address_mask(frame: pd.DataFrame) -> pd.Series:
    """Select rows that contain enough information for responsible geocoding."""
    return (
        ~frame["Stradă standard"].isin(INVALID_STREETS)
        & ~frame["Localitate standard"].isin(INVALID_LOCALITIES)
        & ~frame["Județ"].isin(INVALID_COUNTIES)
    )


def _cache_keys(path: Path | None, key_columns: Iterable[str]) -> set[tuple[str, ...]]:
    """Read JSON, JSONL, or CSV caches without ever reading an API key."""
    if path is None or not path.is_file():
        return set()
    if path.suffix.lower() == ".csv":
        cached = pd.read_csv(path)
    elif path.suffix.lower() == ".jsonl":
        cached = pd.read_json(path, lines=True)
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("results", payload) if isinstance(payload, dict) else payload
        cached = pd.DataFrame(rows)
    columns = list(key_columns)
    if not set(columns).issubset(cached.columns):
        return set()
    for column in columns:
        cached[column] = cached[column].map(canonical_text)
    return set(cached[columns].itertuples(index=False, name=None))


def _cost(events: int) -> dict[str, Any]:
    gross = events / 1_000 * PRICE_PER_THOUSAND_USD
    after_free = max(0, events - MONTHLY_FREE_USAGE) / 1_000 * PRICE_PER_THOUSAND_USD
    return {
        "currency": "USD",
        "gross_max": round(gross, 3),
        "after_monthly_free_threshold_if_unused": round(after_free, 3),
        "monthly_free_threshold": MONTHLY_FREE_USAGE,
        "account_usage_already_consumed_unknown": True,
        "rate_per_1000": PRICE_PER_THOUSAND_USD,
    }


def preflight(
    source: Path,
    geocode_cache: Path | None = None,
    route_cache: Path | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    frame = pd.read_excel(source, sheet_name=SOURCE_SHEET, header=HEADER_ROW)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Coloane obligatorii absente: {', '.join(missing)}")

    frame = frame[frame["Magazin standard"].isin(EXPECTED_TOTALS)].copy()
    frame.loc[frame["Magazin original"].eq("Alis Ecomob SRL"), "Magazin standard"] = "Staer 9"
    totals = frame.groupby("Magazin standard")["Nr. clienți"].sum().astype(int).to_dict()
    differences = {store: totals.get(store, 0) - expected for store, expected in EXPECTED_TOTALS.items()}
    reconciled = all(value == 0 for value in differences.values()) and sum(totals.values()) == 29_204

    normalized = frame.copy()
    normalized[ADDRESS_COLUMNS] = normalized[ADDRESS_COLUMNS].map(canonical_text)
    before_dedup = int(normalized[ADDRESS_COLUMNS].drop_duplicates().shape[0])
    positive = normalized[normalized["Nr. clienți"] > 0].copy()
    eligible = positive[responsible_address_mask(positive)].copy()

    # One row per store/address retains store-specific client weight.  Geocoding
    # is counted separately on ADDRESS_COLUMNS, so an address shared by stores is
    # geocoded only once.
    aggregated = (
        eligible.groupby(PAIR_COLUMNS, as_index=False, dropna=False)["Nr. clienți"]
        .sum()
        .sort_values(PAIR_COLUMNS, kind="stable")
        .reset_index(drop=True)
    )
    addresses = aggregated[ADDRESS_COLUMNS].drop_duplicates()
    address_keys = set(addresses.itertuples(index=False, name=None))
    pair_keys = set(aggregated[PAIR_COLUMNS].itertuples(index=False, name=None))
    cached_address_keys = address_keys & _cache_keys(geocode_cache, ADDRESS_COLUMNS)
    cached_pair_keys = pair_keys & _cache_keys(route_cache, PAIR_COLUMNS)
    geocoding_required = len(address_keys - cached_address_keys)
    routes_required = len(pair_keys - cached_pair_keys)
    allowed = reconciled and geocoding_required <= GEOCODING_LIMIT and routes_required <= ROUTE_MATRIX_LIMIT

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "validated_source_path": str(source),
        "source_sheet": SOURCE_SHEET,
        "header_excel_row": HEADER_ROW + 1,
        "existing_files_reviewed": [
            "analiza_bazine_clienti_staer_bucuresti.xlsx",
            "scripts/analiza_raze_staer.py",
            "tests/test_preflight.py",
            "output/control_preliminar_volume.json",
        ],
        "source_rows_analyzed": int(len(frame)),
        "rows_with_zero_clients_excluded": int((frame["Nr. clienți"] <= 0).sum()),
        "rows_with_insufficient_address_excluded": int(len(positive) - len(eligible)),
        "eligible_rows_before_store_address_aggregation": int(len(eligible)),
        "aggregated_store_address_rows": int(len(aggregated)),
        "client_totals": totals,
        "client_total": int(sum(totals.values())),
        "client_totals_reconciled": reconciled,
        "differences": differences,
        "unique_addresses_before_deduplication": before_dedup,
        "unique_addresses_after_deduplication": len(address_keys),
        "cached_geocodes": len(cached_address_keys),
        "cached_route_matrix_elements": len(cached_pair_keys),
        "geocoding_requests_required": geocoding_required,
        "route_matrix_elements_required": routes_required,
        "billable_events_remaining": {
            "geocoding_requests": geocoding_required,
            "route_matrix_elements": routes_required,
        },
        "limits": {"geocoding_requests": GEOCODING_LIMIT, "route_matrix_elements": ROUTE_MATRIX_LIMIT},
        "estimated_geocoding_cost": _cost(geocoding_required),
        "estimated_route_matrix_cost": _cost(routes_required),
        "pricing_basis": "Google Maps Platform list pricing inspected 2026-08-09; Essentials, first paid tier",
        "google_api_calls_made": 0,
        "analysis_allowed": allowed,
        "recommended_option": "analiza completă" if allowed else "distanțe Haversine înainte de Route Matrix",
        "status": "READY_FOR_GOOGLE_ANALYSIS" if allowed else "STOPPED_BEFORE_GOOGLE_API_CALLS",
    }
    return report, aggregated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("analiza_bazine_clienti_staer_bucuresti.xlsx"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--geocode-cache", type=Path)
    parser.add_argument("--route-cache", type=Path)
    args = parser.parse_args()

    source, warning = find_source(args.input)
    report, aggregated = preflight(source, args.geocode_cache, args.route_cache)
    report["source_path_warning"] = warning
    args.output_dir.mkdir(parents=True, exist_ok=True)
    aggregated.to_csv(args.output_dir / "adrese_magazin_agregate.csv", index=False)
    (args.output_dir / "control_preliminar_volume.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["analysis_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
