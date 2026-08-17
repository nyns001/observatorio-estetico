#!/usr/bin/env python3
"""
Validador de esquema de datos.

Comprueba que los ficheros JSON que generan los scripts tienen la estructura que
el dashboard (index.html) espera leer. Existe porque un desajuste silencioso de
nombres de campo (p.ej. el dashboard leyendo 'por_ano' cuando el script escribe
'conteos') deja secciones vacias sin ningun error visible.

Uso:
    python scripts/check_schema.py

Devuelve codigo 0 si todo cuadra, 1 si hay algun problema. Pensado para correr
en local antes de subir cambios, o como paso opcional del workflow.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

errores = []
avisos = []


def cargar(nombre):
    ruta = DATA / nombre
    if not ruta.exists():
        avisos.append(f"{nombre}: no existe todavia (se genera en el workflow)")
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errores.append(f"{nombre}: JSON invalido ({e})")
        return None


def check_treatments():
    data = cargar("treatments.json")
    if not data:
        errores.append("treatments.json es obligatorio y falta o esta roto")
        return
    if "tratamientos" not in data:
        errores.append("treatments.json: falta la clave 'tratamientos'")
        return
    campos = ["id", "nombre", "familia", "categoria", "zonas", "recuperacion",
              "cuidados", "pubmed_query", "trends_kw", "fda_query",
              "dispositivos_seed", "usa_maquinaria"]
    for t in data["tratamientos"]:
        for c in campos:
            if c not in t:
                errores.append(f"treatments.json: '{t.get('id','?')}' sin campo '{c}'")
        rec = t.get("recuperacion", {})
        for c in ["efecto_visible", "duracion", "detalle", "downtime"]:
            if c not in rec:
                errores.append(f"treatments.json: '{t.get('id','?')}' recuperacion sin '{c}'")


def check_pubmed():
    data = cargar("pubmed_trends.json")
    if not data:
        return
    # el dashboard lee: S.trends.anos  y  S.trends.series[id].conteos / .total / .delta_3a
    if "anos" not in data:
        errores.append("pubmed_trends.json: falta 'anos' (el dashboard lo usa para el eje X)")
    if "series" not in data:
        errores.append("pubmed_trends.json: falta 'series'")
        return
    for tid, s in data["series"].items():
        for c in ["conteos", "total", "delta_3a"]:
            if c not in s:
                errores.append(f"pubmed_trends.json: serie '{tid}' sin '{c}'")
        if "conteos" in s and "anos" in data and len(s["conteos"]) != len(data["anos"]):
            avisos.append(f"pubmed_trends.json: '{tid}' tiene {len(s['conteos'])} conteos "
                          f"pero hay {len(data['anos'])} anos")


def check_radar():
    data = cargar("radar.json")
    if not data:
        return
    if "candidatos" not in data:
        errores.append("radar.json: falta 'candidatos'")
        return
    # el dashboard lee: etiqueta, crecimiento_pct, pubs_ultimos_12m, pubs_12m_previos, query
    for c in data["candidatos"]:
        for campo in ["etiqueta", "crecimiento_pct", "pubs_ultimos_12m", "pubs_12m_previos"]:
            if campo not in c:
                errores.append(f"radar.json: candidato sin '{campo}'")
                break


def check_eudamed():
    data = cargar("eudamed.json")
    if not data:
        return
    if "por_marca" not in data:
        errores.append("eudamed.json: falta 'por_marca'")


def check_devices():
    data = cargar("devices.json")
    if not data:
        return
    if "por_tratamiento" not in data:
        errores.append("devices.json: falta 'por_tratamiento'")


def check_trends():
    data = cargar("google_trends.json")
    if not data:
        return
    if "interes_por_pais" not in data:
        errores.append("google_trends.json: falta 'interes_por_pais'")


def check_radar_market():
    data = cargar("radar_market.json")
    if not data:
        return
    # estructura de la vista Radar (mercado/local). Vacia es valida (usa demo).
    for clave in ["tecnologias", "fabricantes", "geografia_poblacion",
                  "geografia_maquinaria", "madrid", "barcelona"]:
        if clave not in data:
            errores.append(f"radar_market.json: falta '{clave}'")
    if "madrid" in data and not isinstance(data["madrid"].get("tratamientos"), list):
        errores.append("radar_market.json: madrid.tratamientos debe ser lista")
    if "barcelona" in data and not isinstance(data["barcelona"].get("noticias"), list):
        errores.append("radar_market.json: barcelona.noticias debe ser lista")


def main():
    check_treatments()
    check_pubmed()
    check_radar()
    check_eudamed()
    check_devices()
    check_trends()
    check_radar_market()

    if avisos:
        print("AVISOS:")
        for a in avisos:
            print(f"  - {a}")
    if errores:
        print("\nERRORES:")
        for e in errores:
            print(f"  x {e}")
        print(f"\n{len(errores)} error(es) de esquema.")
        sys.exit(1)
    print("\nEsquema correcto: los JSON coinciden con lo que el dashboard espera.")
    sys.exit(0)


if __name__ == "__main__":
    main()
