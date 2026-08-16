#!/usr/bin/env python3
"""
Verificacion de aprobacion en la Union Europea (marcado CE) para las marcas
y productos asociados a cada tratamiento del observatorio.

Recorre el campo "dispositivos_seed" de cada tratamiento en treatments.json
(equipos y productos inyectables) y consulta el buscador publico de EUDAMED
para cada marca unica. Si existe una entrada en data/certificacion_manual.json
para esa marca, el dato manual tiene prioridad sobre el automatico.

IMPORTANTE:
  EUDAMED se despliega por fases y esta incompleto. Ausencia de resultado NO
  significa que el producto no tenga marcado CE. Todo resultado automatico
  se etiqueta "verificacion parcial - EUDAMED" y toda ausencia "a verificar
  por experto", salvo que exista un dato manual cargado por el equipo.

Genera data/eudamed.json.
"""

import json
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import fetch_json, build_url  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BASE = "https://ec.europa.eu/tools/eudamed/api/devices/udiDiData"
UA = "Mozilla/5.0 (compatible; observatorio-estetico/1.0)"


def buscar(termino, limite=8):
    params = {
        "page": 1, "pageSize": limite, "size": limite,
        "iso2Code": "en", "languageIso2Code": "en",
        "deviceStatusCode": "refdata.device-model-status.on-the-market",
        "searchText": termino,
    }
    return fetch_json(build_url(BASE, params))


def limpiar_clase(code):
    if not code:
        return ""
    return "Clase " + code.split(".")[-1].replace("class-", "").upper()


def main():
    catalog = json.loads((DATA / "treatments.json").read_text(encoding="utf-8"))

    manual_path = DATA / "certificacion_manual.json"
    if not manual_path.exists():
        manual_path.write_text(json.dumps({
            "_nota": "Estado CE indicado a mano para marcas que EUDAMED no encuentra o que quereis confirmar. Formato: 'Nombre marca': {'estado': '...', 'detalle': '...'}",
            "marcas": {}
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    manual = json.loads(manual_path.read_text(encoding="utf-8")).get("marcas", {})

    marca_a_tratamientos = {}
    for t in catalog["tratamientos"]:
        for marca in t.get("dispositivos_seed", []):
            marca_a_tratamientos.setdefault(marca, []).append(t["id"])

    por_marca = {}
    for marca in sorted(marca_a_tratamientos):
        print(f"-> EUDAMED: {marca}")

        if marca in manual:
            por_marca[marca] = {
                "encontrados_eudamed": None,
                "dispositivos": [],
                "estado": manual[marca].get("estado", "confirmado manualmente"),
                "detalle": manual[marca].get("detalle", ""),
                "fuente": "dato manual del equipo",
            }
            print("   usando dato manual")
            continue

        data = buscar(marca)
        dispositivos = []
        if data and isinstance(data.get("content"), list):
            for it in data["content"]:
                dispositivos.append({
                    "nombre_comercial": it.get("tradeName") or "",
                    "fabricante": it.get("manufacturerName") or "",
                    "clase_riesgo": limpiar_clase((it.get("riskClass") or {}).get("code")),
                    "referencia": it.get("reference") or "",
                })
        estado = "verificacion parcial - EUDAMED" if dispositivos else "a verificar por experto"
        por_marca[marca] = {
            "encontrados_eudamed": len(dispositivos),
            "dispositivos": dispositivos,
            "estado": estado,
            "detalle": "" if dispositivos else "No aparece en EUDAMED. Puede seguir teniendo marcado CE: confirmar con la Declaracion de Conformidad del fabricante.",
            "fuente": "EUDAMED - buscador publico",
        }
        print(f"   {len(dispositivos)} resultados -> {estado}")
        time.sleep(1.0)

    salida = {
        "generado": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "aviso": "Verificacion de marcado CE. EUDAMED esta incompleto (despliegue por fases): la ausencia de un producto no implica que carezca de marcado CE. Confirmar siempre con la documentacion del fabricante.",
        "por_marca": por_marca,
        "por_tratamiento": marca_a_tratamientos,
    }
    (DATA / "eudamed.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nListo: eudamed.json ({len(por_marca)} marcas)")


if __name__ == "__main__":
    main()
