#!/usr/bin/env python3
"""Construiește incremental cache-urile Google, fără a salva cheia API.

Rulează geocodarea o singură dată pentru fiecare adresă unică și reia în
siguranță după întreruperi. Rutarea folosește doar coordonatele din cache și
verifică limita de 25.000 de elemente înainte de primul apel Routes API.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from analiza_raze_staer import ADDRESS_COLUMNS, PAIR_COLUMNS, EXPECTED_TOTALS, canonical_text

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
ROUTES_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"


def existing_keys(path: Path, columns: list[str]) -> set[tuple[str, ...]]:
    if not path.exists():
        return set()
    keys = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
                keys.add(tuple(canonical_text(row.get(c, "")) for c in columns))
            except (json.JSONDecodeError, TypeError):
                continue
    return keys


def completed_geocode_keys(path: Path) -> set[tuple[str, ...]]:
    """Exclude transient failures so a resumed run can retry them."""
    if not path.exists():
        return set()
    completed = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status") in {"OK", "ZERO_RESULTS", "INVALID_REQUEST"}:
                completed.add(tuple(canonical_text(row.get(c, "")) for c in ADDRESS_COLUMNS))
    return completed


def append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def geocode_one(row: dict, api_key: str) -> dict:
    query = f"{row['Stradă standard']}, {row['Localitate standard']}, {row['Județ']}, România"
    url = GEOCODE_URL + "?" + urllib.parse.urlencode({"address": query, "region": "ro", "language": "ro", "key": api_key})
    result = {c: row[c] for c in ADDRESS_COLUMNS}
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.load(response)
        result["status"] = payload.get("status", "UNKNOWN")
        if result["status"] == "OK" and payload.get("results"):
            best = payload["results"][0]
            location = best["geometry"]["location"]
            result.update(lat=location["lat"], lon=location["lng"], formatted_address=best.get("formatted_address"),
                          location_type=best.get("geometry", {}).get("location_type"), partial_match=bool(best.get("partial_match", False)))
        elif payload.get("error_message"):
            result["error"] = payload["error_message"]
    except Exception as exc:  # response failures must be cached and auditable
        result.update(status="REQUEST_ERROR", error=f"{type(exc).__name__}: {exc}")
    return result


def run_geocoding(source_csv: Path, cache: Path, api_key: str, workers: int) -> None:
    frame = pd.read_csv(source_csv).drop_duplicates(ADDRESS_COLUMNS)
    for column in ADDRESS_COLUMNS:
        frame[column] = frame[column].map(canonical_text)
    done = completed_geocode_keys(cache)
    rows = [row for row in frame[ADDRESS_COLUMNS].to_dict("records") if tuple(row[c] for c in ADDRESS_COLUMNS) not in done]
    print(f"Adrese unice: {len(frame)}; deja în cache: {len(done)}; apeluri necesare: {len(rows)}")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(geocode_one, row, api_key) for row in rows]
        buffer = []
        for index, future in enumerate(as_completed(futures), 1):
            buffer.append(future.result())
            if len(buffer) >= 25:
                append_jsonl(cache, buffer); buffer.clear()
            if index % 250 == 0:
                print(f"Geocodare: {index}/{len(rows)}")
        if buffer:
            append_jsonl(cache, buffer)


def route_batch(store: str, rows: list[dict], api_key: str) -> list[dict]:
    origin_lat, origin_lon = {
        "Staer 7": (44.4907, 26.1240), "Staer 9": (44.4145, 26.0224), "Staer 23": (44.3760, 26.1205)
    }[store]
    body = {
        "origins": [{"waypoint": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lon}}}}],
        "destinations": [{"waypoint": {"location": {"latLng": {"latitude": r["lat"], "longitude": r["lon"]}}}} for r in rows],
        "travelMode": "DRIVE", "routingPreference": "TRAFFIC_UNAWARE",
    }
    request = urllib.request.Request(ROUTES_URL, data=json.dumps(body).encode(), method="POST", headers={
        "Content-Type": "application/json", "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "originIndex,destinationIndex,distanceMeters,duration,status,condition",
    })
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)
    output = []
    for item in payload:
        idx = item.get("destinationIndex", 0); source = rows[idx]
        record = {c: source[c] for c in PAIR_COLUMNS}
        record.update(status=item.get("condition", item.get("status", {}).get("code", "UNKNOWN")))
        if "distanceMeters" in item:
            record["rutier_km"] = item["distanceMeters"] / 1000
        if "duration" in item:
            record["durată"] = item["duration"]
        output.append(record)
    return output


def run_routes(source_csv: Path, geo_cache: Path, route_cache: Path, api_key: str) -> None:
    pairs = pd.read_csv(source_csv)
    geo = pd.read_json(geo_cache, lines=True).dropna(subset=["lat", "lon"]).drop_duplicates(ADDRESS_COLUMNS, keep="last")
    pairs = pairs.merge(geo[ADDRESS_COLUMNS + ["lat", "lon"]], on=ADDRESS_COLUMNS, how="inner")
    done = existing_keys(route_cache, PAIR_COLUMNS)
    rows = [r for r in pairs.to_dict("records") if tuple(canonical_text(r[c]) for c in PAIR_COLUMNS) not in done]
    print(f"Elemente Route Matrix exacte rămase: {len(rows)}")
    if len(rows) > 25_000:
        raise RuntimeError("Limita de 25.000 de elemente ar fi depășită; nu s-a efectuat niciun apel Routes API.")
    for store in EXPECTED_TOTALS:
        store_rows = [r for r in rows if r["Magazin standard"] == store]
        for start in range(0, len(store_rows), 100):
            batch = store_rows[start:start + 100]
            for attempt in range(6):
                try:
                    append_jsonl(route_cache, route_batch(store, batch, api_key))
                    break
                except urllib.error.HTTPError as exc:
                    detail = exc.read().decode(errors="replace")
                    if exc.code != 429 or attempt == 5:
                        raise RuntimeError(f"Routes API HTTP {exc.code}: {detail[:500]}") from exc
                    wait = 20 * (attempt + 1)
                    print(f"Cotă temporar epuizată; reîncercare în {wait}s.")
                    time.sleep(wait)
            print(f"Rutare {store}: {min(start + 100, len(store_rows))}/{len(store_rows)}")
            time.sleep(2.2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("etapă", choices=["geocode", "routes"])
    parser.add_argument("--source", type=Path, default=Path("output/adrese_magazin_agregate.csv"))
    parser.add_argument("--geocode-cache", type=Path, default=Path("cache/geocoding_cache.jsonl"))
    parser.add_argument("--route-cache", type=Path, default=Path("cache/routes_cache.jsonl"))
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not key:
        raise RuntimeError("Variabila GOOGLE_MAPS_API_KEY nu este setată.")
    if args.etapă == "geocode":
        run_geocoding(args.source, args.geocode_cache, key, args.workers)
    else:
        run_routes(args.source, args.geocode_cache, args.route_cache, key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
