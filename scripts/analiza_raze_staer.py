#!/usr/bin/env python3
"""Analiza razelor comerciale Staer, exclusiv din cache-uri locale.

Programul nu conține cod de rețea și nu citește chei API. Dacă un cache nu este
prezent, clienții aferenți sunt păstrați explicit ca ``Negeocodat / nerutat``.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import folium
from folium.plugins import HeatMap
from matplotlib.backends.backend_pdf import PdfPages

EXPECTED_TOTALS = {"Staer 7": 6_617, "Staer 9": 11_117, "Staer 23": 11_470}
STORE_COORDS = {"Staer 7": (44.4907, 26.1240), "Staer 9": (44.4145, 26.0224), "Staer 23": (44.3760, 26.1205)}
SOURCE_SHEET, HEADER_ROW = "Date analizate", 2
ADDRESS_COLUMNS = ["Stradă standard", "Localitate standard", "Sector atribuit", "Județ"]
PAIR_COLUMNS = ["Magazin standard", *ADDRESS_COLUMNS]
BINS = [-np.inf, 3, 5, 10, 15, 25, np.inf]
LABELS = ["0–3 km", "3–5 km", "5–10 km", "10–15 km", "15–25 km", "Peste 25 km"]
UNGEO = "Negeocodat / nerutat"
INVALID = {"", "-", "—", "n/a", "nan", "necunoscut", "necunoscută", "1191"}


def canonical_text(value: Any) -> str:
    return " ".join(str(value).strip().casefold().split())


def responsible_address_mask(frame: pd.DataFrame) -> pd.Series:
    return ~frame["Stradă standard"].isin(INVALID) & ~frame["Localitate standard"].isin(INVALID) & ~frame["Județ"].isin(INVALID)


def weighted_quantile(values: pd.Series, weights: pd.Series, q: float) -> float:
    """Nearest-rank weighted quantile (each client has equal weight)."""
    valid = values.notna() & weights.gt(0)
    if not valid.any():
        return float("nan")
    order = np.argsort(values[valid].to_numpy(), kind="stable")
    v, w = values[valid].to_numpy()[order], weights[valid].to_numpy()[order]
    return float(v[np.searchsorted(np.cumsum(w), q * w.sum(), side="left")])


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    if any(pd.isna(x) for x in (lat1, lon1, lat2, lon2)):
        return float("nan")
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def read_cache(path: Path | None) -> pd.DataFrame:
    if path is None or not path.is_file():
        return pd.DataFrame()
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".jsonl":
        return pd.read_json(path, lines=True)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("results", payload.get("rows", []))
    return pd.DataFrame(payload)


def _rename_cache_columns(frame: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "latitude": "lat", "lng": "lon", "longitude": "lon",
        "distance_km": "rutier_km", "route_distance_km": "rutier_km",
    }
    return frame.rename(columns={c: aliases.get(c.casefold(), c) for c in frame.columns})


def load_source(path: Path) -> pd.DataFrame:
    frame = pd.read_excel(path, sheet_name=SOURCE_SHEET, header=HEADER_ROW)
    frame = frame[frame["Magazin standard"].isin(EXPECTED_TOTALS)].copy()
    frame.loc[frame["Magazin original"].eq("Alis Ecomob SRL"), "Magazin standard"] = "Staer 9"
    for column in ADDRESS_COLUMNS:
        frame[column] = frame[column].map(canonical_text)
    frame["Nr. clienți"] = pd.to_numeric(frame["Nr. clienți"], errors="coerce").fillna(0)
    return frame


def prepare(source: Path, geocode_cache: Path | None, route_cache: Path | None) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = load_source(source)
    totals = raw.groupby("Magazin standard")["Nr. clienți"].sum().astype(int).to_dict()
    if totals != EXPECTED_TOTALS or sum(totals.values()) != 29_204:
        raise ValueError(f"Totalurile sursei nu se reconciliază: {totals}")
    positive = raw[raw["Nr. clienți"].gt(0)].copy()
    dims = [*PAIR_COLUMNS, "Bazin comercial"]
    data = positive.groupby(dims, as_index=False, dropna=False)["Nr. clienți"].sum()
    data["adresă eligibilă"] = responsible_address_mask(data)

    geo = _rename_cache_columns(read_cache(geocode_cache))
    geo_attempts = len(geo)
    if not geo.empty and set(ADDRESS_COLUMNS + ["lat", "lon"]).issubset(geo.columns):
        for c in ADDRESS_COLUMNS:
            geo[c] = geo[c].map(canonical_text)
        geo["lat"], geo["lon"] = pd.to_numeric(geo["lat"], errors="coerce"), pd.to_numeric(geo["lon"], errors="coerce")
        geo = geo.dropna(subset=["lat", "lon"]).drop_duplicates(ADDRESS_COLUMNS, keep="last")
        data = data.merge(geo[ADDRESS_COLUMNS + ["lat", "lon"]], on=ADDRESS_COLUMNS, how="left")
    else:
        data[["lat", "lon"]] = np.nan
    data["geocodat"] = data["lat"].notna() & data["lon"].notna()
    data["haversine_km"] = [haversine(*STORE_COORDS[s], la, lo) for s, la, lo in data[["Magazin standard", "lat", "lon"]].itertuples(index=False)]

    routes = _rename_cache_columns(read_cache(route_cache))
    route_cache_rows = len(routes)
    if not routes.empty and set(PAIR_COLUMNS + ["rutier_km"]).issubset(routes.columns):
        for c in PAIR_COLUMNS:
            routes[c] = routes[c].map(canonical_text)
        # Restore canonical store spelling after case-folding cache keys.
        routes["Magazin standard"] = routes["Magazin standard"].map({k.casefold(): k for k in EXPECTED_TOTALS})
        routes["rutier_km"] = pd.to_numeric(routes["rutier_km"], errors="coerce")
        routes = routes.dropna(subset=["rutier_km"]).drop_duplicates(PAIR_COLUMNS, keep="last")
        data = data.merge(routes[PAIR_COLUMNS + ["rutier_km"]], on=PAIR_COLUMNS, how="left")
    else:
        data["rutier_km"] = np.nan
    data.loc[~data["geocodat"], "rutier_km"] = np.nan
    data["interval rutier"] = pd.cut(data["rutier_km"], BINS, labels=LABELS, right=False).astype(object).fillna(UNGEO)
    required = int((data["geocodat"] & data["rutier_km"].isna()).sum())
    run_summary_path = geocode_cache.with_name("geocoding_run_summary.json") if geocode_cache else None
    run_summary = json.loads(run_summary_path.read_text(encoding="utf-8")) if run_summary_path and run_summary_path.is_file() else {}
    audit = {
        "totaluri_sursă": {**totals, "Total": 29_204}, "reconciliat": True,
        "apeluri_geocoding_efectuate_total": run_summary.get("apeluri_geocoding", "necunoscut"),
        "apeluri_geocoding_efectuate_în_etapa_de_analiză": 0, "rânduri_cache_geocodare_citite": geo_attempts,
        "geocodări_reușite_unice": int(geo.shape[0]) if not geo.empty and "lat" in geo else 0,
        "rânduri_cache_rutare_citite": route_cache_rows,
        "elemente_route_matrix_rămase": required,
        "în_limita_25000": required <= 25_000,
        "notă": "Etapa de analiză nu efectuează apeluri API; folosește cache-urile create separat și fără cheie API.",
    }
    return data, audit


def coverage(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for store in [*EXPECTED_TOTALS, "Total"]:
        part = data if store == "Total" else data[data["Magazin standard"].eq(store)]
        total = sum(EXPECTED_TOTALS.values()) if store == "Total" else EXPECTED_TOTALS[store]
        clients = int(part.loc[part["geocodat"], "Nr. clienți"].sum())
        addresses = int(part.loc[part["geocodat"], ADDRESS_COLUMNS].drop_duplicates().shape[0])
        pct = clients / total
        level = "Acoperire solidă" if pct >= .9 else "Analiză utilizabilă, cu limitări" if pct >= .8 else "Rezultat parțial"
        routed = part[part["rutier_km"].notna()]
        intervals = part.groupby("interval rutier", observed=True)["Nr. clienți"].sum()
        zones = part.groupby("Bazin comercial", dropna=False)["Nr. clienți"].sum().nlargest(3)
        rows.append({"Magazin": store, "Clienți totali": total, "Adrese geocodate": addresses,
                     "Clienți geocodați": clients, "Acoperire %": pct,
                     "Clienți negeocodați": total - clients, "Negeocodați %": 1-pct,
                     "Distanță medie rutieră km": np.average(routed["rutier_km"], weights=routed["Nr. clienți"]) if len(routed) else np.nan,
                     "Mediană / P50 km": weighted_quantile(routed["rutier_km"], routed["Nr. clienți"], .5),
                     "P80 km": weighted_quantile(routed["rutier_km"], routed["Nr. clienți"], .8),
                     "P90 km": weighted_quantile(routed["rutier_km"], routed["Nr. clienți"], .9),
                     "P95 km": weighted_quantile(routed["rutier_km"], routed["Nr. clienți"], .95),
                     "Interval dominant": intervals.idxmax() if len(intervals) else UNGEO,
                     "Principalele zone": ", ".join(f"{k} ({int(v):,})" for k, v in zones.items()),
                     "Nivel încredere": level})
    return pd.DataFrame(rows)


def missing_bias(data: pd.DataFrame) -> pd.DataFrame:
    records = []
    scoped = [("Magazin", "Magazin standard"), ("Sector", "Sector atribuit"), ("Județ", "Județ"), ("Bazin", "Bazin comercial")]
    volume = pd.cut(data["Nr. clienți"], [0, 1, 2, 5, 10, 25, np.inf], labels=["1", "2", "3–5", "6–10", "11–25", ">25"])
    for scope, col in scoped + [("Volum/adresă", "_vol")]:
        vals = volume if col == "_vol" else data[col].fillna("Necunoscut")
        for value in vals.unique():
            mask = vals.eq(value); total = data.loc[mask, "Nr. clienți"].sum(); missing = data.loc[mask & ~data["geocodat"], "Nr. clienți"].sum()
            records.append({"Dimensiune": scope, "Categorie": str(value), "Clienți": int(total), "Clienți negeocodați": int(missing), "Rată negeocodare %": missing / total if total else 0})
    return pd.DataFrame(records).sort_values(["Dimensiune", "Clienți negeocodați"], ascending=[True, False])


def distributions(data: pd.DataFrame) -> pd.DataFrame:
    out = []
    for store, total in [*EXPECTED_TOTALS.items(), ("Total", 29_204)]:
        part = data if store == "Total" else data[data["Magazin standard"].eq(store)]
        for label in [*LABELS, UNGEO]:
            n = int(part.loc[part["interval rutier"].eq(label), "Nr. clienți"].sum())
            out.append({"Magazin": store, "Interval": label, "Clienți": n, "% din total complet": n / total})
    return pd.DataFrame(out)


def write_outputs(output: Path, data: pd.DataFrame, audit: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    cov, bias, dist = coverage(data), missing_bias(data), distributions(data)
    with pd.ExcelWriter(output / "raza_comerciala_staer.xlsx", engine="xlsxwriter") as writer:
        cov.to_excel(writer, sheet_name="Rezumat", index=False); dist.to_excel(writer, sheet_name="Distribuții", index=False)
        data.to_excel(writer, sheet_name="Detaliu adrese", index=False); bias.to_excel(writer, sheet_name="Lipsă nealeatorie", index=False)
        pd.DataFrame([audit]).to_excel(writer, sheet_name="Control", index=False)
        for sheet in writer.sheets.values(): sheet.freeze_panes(1, 0); sheet.autofilter(0, 0, sheet.dim_rowmax, sheet.dim_colmax)
    (output / "audit_analiza_raze_staer.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

    colors = {"Staer 7": "#1769aa", "Staer 9": "#e67e22", "Staer 23": "#c62828"}
    map_obj = folium.Map(location=[44.43, 26.08], zoom_start=10, tiles="CartoDB positron")
    for store, color in colors.items():
        part = data[data["Magazin standard"].eq(store) & data["geocodat"]]
        layer = folium.FeatureGroup(name=f"Clienți {store}", show=True)
        HeatMap(part[["lat", "lon", "Nr. clienți"]].values.tolist(), radius=12, blur=16, min_opacity=.25,
                gradient={.25: "#d8ecff", .55: color, 1: "#4a0010"}).add_to(layer)
        layer.add_to(map_obj)
        lat, lon = STORE_COORDS[store]
        summary = cov[cov["Magazin"].eq(store)].iloc[0]
        folium.Marker([lat, lon], tooltip=store, popup=f"{store}<br>P80 rutier: {summary['P80 km']:.1f} km",
                      icon=folium.Icon(color="red", icon="home")).add_to(map_obj)
        folium.Circle([lat, lon], radius=float(summary["P80 km"]) * 1000, color=color, fill=False,
                      tooltip=f"{store} – cerc orientativ P80 rutier").add_to(map_obj)
    folium.LayerControl(collapsed=False).add_to(map_obj)
    title = f"""<div style='position:fixed;top:10px;left:50px;z-index:9999;background:white;padding:10px;border:1px solid #999'>
    <b>Raze comerciale Staer</b><br>29.204 clienți; acoperire geocodare {cov.iloc[-1]['Acoperire %']:.1%}.<br>
    Cercurile P80 sunt orientative; punctele lipsă rămân în rapoarte ca „{UNGEO}”.</div>"""
    map_obj.get_root().html.add_child(folium.Element(title))
    map_path = output / "harta_raze_staer.html"
    map_obj.save(map_path)
    # Folium's template emits whitespace-only suffixes; normalize the tracked
    # artifact so standard Git whitespace checks remain clean.
    map_path.write_text("\n".join(line.rstrip() for line in map_path.read_text(encoding="utf-8").splitlines()) + "\n", encoding="utf-8")

    with PdfPages(output / "rezumat_raze_staer.pdf") as pdf:
        fig, ax = plt.subplots(figsize=(11.7, 8.3)); ax.axis("off")
        ax.text(.02, .95, "Raze comerciale Staer — rezultate observate", fontsize=20, weight="bold")
        ax.text(.02, .88, "Totaluri reconfirmate: Staer 7 = 6.617 | Staer 9 = 11.117 | Staer 23 = 11.470 | Total = 29.204", fontsize=11)
        ax.text(.02, .82, "Fără extrapolare. Negeocodații sunt păstrați în numitor și raportați distinct.", color="#a33")
        cols = ["Magazin", "Clienți totali", "Clienți geocodați", "Acoperire %", "Nivel încredere"]
        shown = cov[cols].copy(); shown["Acoperire %"] = shown["Acoperire %"].map(lambda x: f"{x:.1%}")
        ax.table(cellText=shown.values, colLabels=cols, loc="center", cellLoc="center", bbox=[.02,.35,.96,.38])
        ax.text(.02,.2,f"Elemente Route Matrix rămase: {audit['elemente_route_matrix_rămase']:,}. Geocodări unice în cache: {audit['geocodări_reușite_unice']:,}.")
        pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)
        fig, axes = plt.subplots(1, 3, figsize=(11.7, 8.3))
        for ax, store in zip(axes, EXPECTED_TOTALS):
            part = dist[dist.Magazin.eq(store)]; ax.pie(part["Clienți"], labels=part["Interval"], autopct=lambda p: f"{p:.1f}%" if p else "")
            ax.set_title(store)
        fig.suptitle("Distribuții rutiere — total complet inclusiv negeocodați"); pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("analiza_bazine_clienti_staer_bucuresti.xlsx"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--geocode-cache", type=Path, default=Path("cache/geocoding_cache.jsonl"))
    parser.add_argument("--route-cache", type=Path, default=Path("cache/routes_cache.jsonl"))
    args = parser.parse_args()
    data, audit = prepare(args.input, args.geocode_cache, args.route_cache)
    write_outputs(args.output_dir, data, audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
