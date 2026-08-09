#!/usr/bin/env python3
"""Preflight and Google Maps trade-area analysis for the three Staer stores.

The preflight is deliberately a hard gate: no Google endpoint is contacted when
the reconciled source exceeds either volume ceiling requested by the brief.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


EXPECTED_TOTALS = {"Staer 7": 6_617, "Staer 9": 11_117, "Staer 23": 11_470}
GEOCODING_LIMIT = 8_000
ROUTE_MATRIX_LIMIT = 25_000
SOURCE_SHEET = "Date analizate"
HEADER_ROW = 2
ADDRESS_COLUMNS = ["Stradă standard", "Localitate standard", "Județ"]
REQUIRED_COLUMNS = [
    "Magazin original",
    "Magazin standard",
    "Stradă standard",
    "Localitate standard",
    "Județ",
    "Nr. clienți",
]


def canonical_text(value: Any) -> str:
    """Normalize only inconsequential whitespace/case for safe deduplication."""
    return " ".join(str(value).strip().casefold().split())


def find_source(requested: Path) -> tuple[Path, str | None]:
    """Resolve the supplied workbook while documenting the repository mismatch."""
    if requested.is_file() and requested.suffix.lower() == ".xlsx":
        return requested, None
    fallback = Path("analiza_bazine_clienti_staer_bucuresti.xlsx")
    if fallback.is_file():
        return fallback, (
            f"Calea solicitată {requested} nu este un workbook .xlsx valid; "
            f"a fost inspectat workbookul disponibil {fallback}."
        )
    raise FileNotFoundError(f"Workbookul nu există la {requested} și nu există fallbackul {fallback}.")


def preflight(source: Path) -> dict[str, Any]:
    frame = pd.read_excel(source, sheet_name=SOURCE_SHEET, header=HEADER_ROW)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Coloane obligatorii absente: {', '.join(missing)}")

    frame = frame[frame["Magazin standard"].isin(EXPECTED_TOTALS)].copy()
    frame.loc[frame["Magazin original"].eq("Alis Ecomob SRL"), "Magazin standard"] = "Staer 9"
    if frame[ADDRESS_COLUMNS + ["Magazin standard", "Nr. clienți"]].isna().any().any():
        raise ValueError("Există valori lipsă în câmpurile necesare controlului preliminar.")

    totals = frame.groupby("Magazin standard")["Nr. clienți"].sum().astype(int).to_dict()
    differences = {store: totals.get(store, 0) - expected for store, expected in EXPECTED_TOTALS.items()}
    reconciled = all(value == 0 for value in differences.values()) and sum(totals.values()) == 29_204

    normalized = frame.copy()
    normalized[ADDRESS_COLUMNS] = normalized[ADDRESS_COLUMNS].map(canonical_text)
    unique_addresses = int(normalized[ADDRESS_COLUMNS].drop_duplicates().shape[0])
    unique_pairs = int(
        normalized[["Magazin standard", *ADDRESS_COLUMNS]].drop_duplicates().shape[0]
    )
    geocoding_overage = max(0, unique_addresses - GEOCODING_LIMIT)
    route_overage = max(0, unique_pairs - ROUTE_MATRIX_LIMIT)
    allowed = reconciled and geocoding_overage == 0 and route_overage == 0

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_workbook": str(source),
        "source_sheet": SOURCE_SHEET,
        "header_excel_row": HEADER_ROW + 1,
        "identified_columns": {
            "magazin": "Magazin standard (Alis Ecomob SRL → Staer 9)",
            "strada": "Stradă standard",
            "localitate_sau_sector": "Localitate standard",
            "judet": "Județ",
            "pondere_clienti": "Nr. clienți",
        },
        "source_rows_analyzed": int(len(frame)),
        "api_key_environment_variable_present": bool(os.environ.get("GOOGLE_MAPS_API_KEY")),
        "totals": totals,
        "expected_totals": EXPECTED_TOTALS,
        "differences": differences,
        "general_total": int(sum(totals.values())),
        "expected_general_total": 29_204,
        "totals_reconciled": reconciled,
        "unique_geographic_addresses": unique_addresses,
        "unique_store_address_pairs": unique_pairs,
        "limits": {
            "geocoding_requests": GEOCODING_LIMIT,
            "route_matrix_elements": ROUTE_MATRIX_LIMIT,
        },
        "overages": {
            "geocoding_requests": geocoding_overage,
            "route_matrix_elements": route_overage,
        },
        "google_api_calls_made": 0,
        "analysis_allowed": allowed,
        "status": "READY" if allowed else "STOPPED_BEFORE_GOOGLE_API_CALLS",
        "stop_reason": None
        if allowed
        else (
            "Pragul de geocodare este depășit. Este necesară aprobarea explicită "
            "pentru continuare sau o regulă de reducere a universului de adrese."
            if geocoding_overage
            else "Controlul de reconciliere sau pragul Route Matrix nu a trecut."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("input/analiza_bazine_clienti_staer_bucuresti.xlsx"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    args = parser.parse_args()

    source, warning = find_source(args.input)
    report = preflight(source)
    report["source_path_warning"] = warning
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "control_preliminar_volume.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Control preliminar salvat: {report_path}")
    print(f"Adrese geografice unice: {report['unique_geographic_addresses']:,}")
    print(f"Perechi magazin–adresă: {report['unique_store_address_pairs']:,}")
    print(f"Status: {report['status']}")
    if not report["analysis_allowed"]:
        print(report["stop_reason"], file=sys.stderr)
        return 2
    print("Preflight acceptat; implementarea apelurilor Google poate continua.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
