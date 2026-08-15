#!/usr/bin/env python3
"""
Radar de tendencias emergentes.

Rastrea PubMed midiendo el crecimiento de publicaciones de una lista de terminos
de medicina estetica, comparando los ultimos 12 meses con los 12 anteriores.
Genera data/radar.json con los candidatos ordenados por crecimiento.

NO anade tratamientos al observatorio: solo propone. La decision de promover un
candidato a tratamiento completo (con su contenido clinico curado) es humana.

Sin clave funciona; con NCBI_API_KEY va mas rapido.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
API_KEY = os.environ.get("NCBI_API_KEY", "")
EMAIL = os.environ.get("NCBI_EMAIL", "")
TOOL = "estetica-radar"

# Universo de terminos a vigilar. Amplia esta lista para vigilar mas tecnicas.
# Cada entrada es (etiqueta legible, consulta PubMed).
TERMINOS = [
    ("Endolift / laser endodermico", "endolift OR endolaser OR (subdermal diode laser skin laxity)"),
    ("Exosomas en estetica", "exosome AND (skin OR aesthetic OR rejuvenation OR alopecia)"),
    ("Bioestimuladores PCL", "polycaprolactone AND (collagen OR aesthetic OR skin)"),
    ("Polinucleotidos / salmon DNA", "polynucleotide AND (skin OR rejuvenation OR aesthetic)"),
    ("Skinbooster", "skin booster OR (injectable hyaluronic acid hydration)"),
    ("Microtoxina / microbotox", "microbotox OR intradermal botulinum toxin"),
    ("RF microagujas", "microneedling radiofrequency OR fractional radiofrequency"),
    ("HIFU facial", "microfocused ultrasound skin OR high-intensity focused ultrasound face"),
    ("Toxina para masetero", "botulinum toxin masseter"),
    ("Rinomodelacion no quirurgica", "non-surgical rhinoplasty OR liquid rhinoplasty"),
    ("Acido deoxicolico papada", "deoxycholic acid submental fat"),
    ("Lipolisis laser", "laser lipolysis OR laser-assisted lipolysis"),
    ("Vaser / lipo ultrasonica", "vaser OR ultrasound-assisted liposuction"),
    ("Regeneracion capilar PRP", "platelet-rich plasma AND (hair OR alopecia)"),
    ("Fototerapia LED", "LED phototherapy skin OR photobiomodulation skin"),
    ("Peeling con exosomas", "exosome AND (peel OR resurfacing)"),
    ("Colageno inyectable recombinante", "recombinant collagen injectable skin"),
    ("Toxina liquida / topica", "topical botulinum toxin OR liquid botulinum toxin"),
    ("Bioregeneracion con PDRN", "PDRN AND (skin OR aesthetic OR wound)"),
    ("Ultrasonido + RF combinado", "combined ultrasound radiofrequency skin tightening"),
]


def call(endpoint, params):
    params = {**params, "tool": TOOL}
    if EMAIL:
        params["email"] = EMAIL
    if API_KEY:
        params["api_key"] = API_KEY
    url = f"{EUTILS}/{endpoint}?{urllib.parse.urlencode(params)}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            time.sleep(2 ** attempt)
    raise RuntimeError(f"E-utilities sin respuesta: {params.get('term','')[:50]}")


def throttle():
    time.sleep(0.11 if API_KEY else 0.36)


def count_range(query, start, end):
    """Publicaciones entre dos fechas YYYY/MM/DD."""
    term = f"({query}) AND ({start}[dp] : {end}[dp])"
    raw = call("esearch.fcgi", {"db": "pubmed", "term": term, "retmax": 0, "retmode": "json"})
    throttle()
    return int(json.loads(raw)["esearchresult"]["count"])


def main():
    hoy = datetime.utcnow()
    fin_reciente = hoy.strftime("%Y/%m/%d")
    ini_reciente = (hoy - timedelta(days=365)).strftime("%Y/%m/%d")
    fin_previo = (hoy - timedelta(days=366)).strftime("%Y/%m/%d")
    ini_previo = (hoy - timedelta(days=730)).strftime("%Y/%m/%d")

    # tratamientos ya en el observatorio, para marcar candidatos ya cubiertos
    cat = json.loads((DATA / "treatments.json").read_text(encoding="utf-8"))
    kw_existentes = {t["trends_kw"].lower() for t in cat["tratamientos"]}
    nombres_existentes = " ".join(t["nombre"].lower() for t in cat["tratamientos"])

    candidatos = []
    for etiqueta, query in TERMINOS:
        print(f"-> {etiqueta}")
        reciente = count_range(query, ini_reciente, fin_reciente)
        previo = count_range(query, ini_previo, fin_previo)
        base = previo or 1
        crecimiento = round((reciente - previo) / base * 100, 1)
        # heuristica simple para marcar si ya esta en el observatorio
        ya = any(k in etiqueta.lower() for k in kw_existentes if len(k) > 4)
        candidatos.append({
            "etiqueta": etiqueta,
            "query": query,
            "pubs_ultimos_12m": reciente,
            "pubs_12m_previos": previo,
            "crecimiento_pct": crecimiento,
            "ya_en_observatorio": ya,
        })
        print(f"   {previo} -> {reciente}  ({crecimiento:+.0f}%)")

    # ordenar por crecimiento, exigiendo un minimo de volumen para evitar ruido
    candidatos.sort(key=lambda c: (c["pubs_ultimos_12m"] >= 8, c["crecimiento_pct"]), reverse=True)

    salida = {
        "generado": hoy.isoformat(timespec="seconds") + "Z",
        "fuente": "PubMed E-utilities",
        "ventana_reciente": f"{ini_reciente} a {fin_reciente}",
        "ventana_previa": f"{ini_previo} a {fin_previo}",
        "nota": "Crecimiento de publicaciones ultimos 12 meses vs 12 previos. Candidatos a evaluar, no anadidos automaticamente. La promocion a tratamiento requiere contenido clinico curado.",
        "candidatos": candidatos,
    }
    (DATA / "radar.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nListo: radar.json con {len(candidatos)} candidatos")


if __name__ == "__main__":
    main()
