#!/usr/bin/env python3
"""
Genera data/devices.json a partir de openFDA (registro 510(k) de dispositivos
medicos de la FDA). Por cada tratamiento consulta su fda_query y devuelve los
equipos autorizados mas recientes con fabricante y fecha de decision.

API publica y gratuita. Sin clave: 1.000 peticiones/dia por IP.
Con clave gratuita (OPENFDA_API_KEY): 120.000/dia.

Aviso: el registro es estadounidense. Un equipo puede estar disponible en la UE
con marcado CE sin aparecer aqui, y viceversa. Sirve como indice tecnico de
equipos y fabricantes, no como listado de disponibilidad local.
"""

import json
import os
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import fetch_json, build_url  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ENDPOINT = "https://api.fda.gov/device/510k.json"
API_KEY = os.environ.get("OPENFDA_API_KEY", "")
POR_TRATAMIENTO = 25


def buscar(termino: str, limite: int) -> list:
    # Solo device_name (no el resumen) para evitar falsos positivos: productos
    # que solo *mencionan* el termino en su texto quedan fuera.
    params = {
        "search": f'device_name:"{termino}"',
        "limit": limite,
        "sort": "decision_date:desc",
    }
    if API_KEY:
        params["api_key"] = API_KEY
    data = fetch_json(build_url(ENDPOINT, params))
    return (data or {}).get("results", [])


def main() -> None:
    catalog = json.loads((DATA / "treatments.json").read_text(encoding="utf-8"))
    salida = {
        "generado": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "fuente": "openFDA - registro 510(k) de dispositivos medicos",
        "aviso": "Autorizaciones de EE.UU. No refleja disponibilidad ni marcado CE en Europa.",
        "por_tratamiento": {},
    }

    for treatment in catalog["tratamientos"]:
        termino = treatment.get("fda_query")
        print(f"-> {treatment['nombre']} ({termino})")
        resultados = buscar(termino, POR_TRATAMIENTO) if termino else []
        equipos, vistos = [], set()
        for item in resultados:
            nombre = (item.get("device_name") or "").strip()
            clave = nombre.lower()
            if not nombre or clave in vistos:
                continue
            vistos.add(clave)
            fecha = item.get("decision_date", "")
            equipos.append({
                "nombre": nombre,
                "fabricante": (item.get("applicant") or "").strip(),
                "k_number": item.get("k_number", ""),
                "fecha_decision": fecha,
                "ano": fecha[:4] if fecha else "",
                "pais": item.get("country_code", ""),
            })
        salida["por_tratamiento"][treatment["id"]] = equipos
        print(f"   {len(equipos)} equipos")
        time.sleep(0.3)

    (DATA / "devices.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Listo: devices.json")


if __name__ == "__main__":
    main()
