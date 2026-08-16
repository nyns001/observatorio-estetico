#!/usr/bin/env python3
"""
Consulta la API E-utilities de NCBI y genera dos ficheros:

  data/pubmed_trends.json   volumen de publicaciones por ano y tratamiento
  data/device_mentions.json equipos y marcas citados en los abstracts recientes

No requiere clave. Si defines NCBI_API_KEY subes de 3 a 10 peticiones/segundo.
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

API_KEY = os.environ.get("NCBI_API_KEY", "")
EMAIL = os.environ.get("NCBI_EMAIL", "")
TOOL = "estetica-research-dashboard"

FIRST_YEAR = 2015
LAST_YEAR = datetime.utcnow().year
ABSTRACTS_PER_TREATMENT = 120

# Lexico de equipos y marcas de medicina estetica que buscamos en los abstracts.
# Ampliable: cada entrada es (etiqueta mostrada, patron regex).
DEVICE_LEXICON = [
    ("Ultherapy", r"ulthera(?:py)?"),
    ("Sofwave", r"sofwave"),
    ("Morpheus8", r"morpheus\s?8"),
    ("Potenza", r"\bpotenza\b"),
    ("Secret RF", r"secret\s?rf"),
    ("Genius RF", r"genius\s?rf"),
    ("Thermage", r"thermage"),
    ("Fraxel", r"fraxel"),
    ("UltraPulse", r"ultrapulse"),
    ("CoolSculpting", r"coolsculpt(?:ing)?"),
    ("Emsculpt", r"emsculpt(?:\s?neo)?"),
    ("Cellactor", r"cellactor"),
    ("Nd:YAG 1064 nm", r"nd:?\s?yag"),
    ("Alexandrita 755 nm", r"alexandrite"),
    ("Diodo 808 nm", r"diode laser"),
    ("Er:YAG 2940 nm", r"er:?\s?yag"),
    ("Pico laser", r"picosecond laser"),
    ("IPL", r"\bintense pulsed light\b|\bIPL\b"),
    ("Laser CO2 fraccionado", r"fractional (?:carbon dioxide|CO2) laser"),
    ("Radiofrecuencia monopolar", r"monopolar radiofrequency"),
    ("HIFU", r"microfocused ultrasound|high-intensity focused ultrasound|\bHIFU\b"),
    ("HIFEM", r"\bHIFEM\b|high-intensity focused electromagnetic"),
    ("Microagujas", r"microneedl\w+"),
    ("Criolipolisis", r"cryolipolysis"),
    ("Eufoton / Endolift", r"eufoton|endolift"),
    ("Vaser", r"\bvaser\b"),
    ("Sculptra (PLLA)", r"sculptra"),
    ("Radiesse (CaHA)", r"radiesse"),
    ("Ellanse (PCL)", r"ellanse|ellanse"),
    ("Profhilo", r"profhilo"),
    ("Belkyra / Kybella", r"belkyra|kybella|deoxycholic"),
    ("Fibra optica laser", r"optical fiber|fiber optic laser|bare fiber"),
    ("Laser 1470 nm", r"1470\s?nm"),
    ("Laser 1064 nm", r"1064\s?nm"),
    ("Onda / RF fraccionada", r"fractional radiofrequency"),
    ("Exosomas", r"exosome"),
    ("PDRN / polinucleotidos", r"polynucleotide|pdrn"),
    ("PRP", r"platelet-rich plasma|\bPRP\b"),
    ("LED / fotobiomodulacion", r"led phototherapy|photobiomodulation"),
]


def call(endpoint: str, params: dict) -> str:
    params = {**params, "tool": TOOL}
    if EMAIL:
        params["email"] = EMAIL
    if API_KEY:
        params["api_key"] = API_KEY
    url = f"{EUTILS}/{endpoint}?{urllib.parse.urlencode(params)}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as error:  # noqa: BLE001
            wait = 2 ** attempt
            print(f"  reintento {attempt + 1} en {wait}s ({error})", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"E-utilities no respondio: {endpoint} {params.get('term', '')[:60]}")


def throttle() -> None:
    time.sleep(0.11 if API_KEY else 0.36)


def count_for_year(query: str, year: int) -> int:
    term = f"({query}) AND {year}[dp]"
    raw = call("esearch.fcgi", {"db": "pubmed", "term": term, "retmax": 0, "retmode": "json"})
    throttle()
    try:
        return int(json.loads(raw)["esearchresult"]["count"])
    except (KeyError, ValueError, TypeError):
        return 0  # Si la respuesta no tiene la estructura esperada, asumir 0


def recent_abstracts(query: str, limit: int) -> str:
    raw = call("esearch.fcgi", {
        "db": "pubmed", "term": query, "retmax": limit,
        "sort": "date", "retmode": "json",
    })
    throttle()
    try:
        ids = json.loads(raw)["esearchresult"]["idlist"]
    except (KeyError, TypeError):
        return ""
    if not ids:
        return ""
    text = call("efetch.fcgi", {
        "db": "pubmed", "id": ",".join(ids), "retmode": "text", "rettype": "abstract",
    })
    throttle()
    return text


def main() -> None:
    catalog = json.loads((DATA / "treatments.json").read_text(encoding="utf-8"))
    treatments = catalog["tratamientos"]

    trends = {"generado": datetime.utcnow().isoformat(timespec="seconds") + "Z",
              "anos": list(range(FIRST_YEAR, LAST_YEAR + 1)),
              "series": {}}
    mentions = {"generado": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "fuente": "Menciones detectadas en abstracts recientes de PubMed",
                "por_tratamiento": {}}

    for treatment in treatments:
        tid, query = treatment["id"], treatment["pubmed_query"]
        print(f"-> {treatment['nombre']}")

        counts = [count_for_year(query, year) for year in trends["anos"]]
        total = sum(counts)
        recent = sum(counts[-3:]) or 1
        previous = sum(counts[-6:-3]) or 1
        trends["series"][tid] = {
            "categoria": treatment["categoria"],
            "conteos": counts,
            "total": total,
            "delta_3a": round((recent - previous) / previous * 100, 1),
        }
        print(f"   {total} publicaciones {FIRST_YEAR}-{LAST_YEAR}")

        text = recent_abstracts(query, ABSTRACTS_PER_TREATMENT).lower()
        found = Counter()
        for label, pattern in DEVICE_LEXICON:
            hits = len(re.findall(pattern, text, flags=re.IGNORECASE))
            if hits:
                found[label] = hits
        mentions["por_tratamiento"][tid] = [
            {"equipo": label, "menciones": n} for label, n in found.most_common(12)
        ]
        print(f"   {len(found)} equipos citados")

    (DATA / "pubmed_trends.json").write_text(
        json.dumps(trends, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "device_mentions.json").write_text(
        json.dumps(mentions, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Listo: pubmed_trends.json y device_mentions.json")


if __name__ == "__main__":
    main()
