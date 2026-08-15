#!/usr/bin/env python3
"""
Verificacion de certificacion en EUDAMED (base europea de productos sanitarios).

Usa el endpoint del buscador publico de EUDAMED (el mismo que emplea la web
oficial). NO es una API oficial documentada: es el endpoint interno de la UI,
mapeado por la comunidad (OpenRegulatory). Puede cambiar sin aviso.

Para cada termino de busqueda (marca o fabricante que definas en
data/verify_targets.json) consulta EUDAMED y guarda los dispositivos que
encuentra con su fabricante, clase de riesgo y estado.

IMPORTANTE - leer antes de confiar en el resultado:
  EUDAMED se volvio obligatorio en mayo de 2026 pero NO esta completo: el
  registro se despliega por fases hasta ~2027. Un dispositivo legitimo y
  certificado CE puede NO aparecer aqui todavia. Por eso todo resultado se
  etiqueta como VERIFICACION PARCIAL y debe confirmarse con la documentacion
  del fabricante (Declaracion de Conformidad y certificado del Organismo
  Notificado).

Genera data/eudamed.json.
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BASE = "https://ec.europa.eu/tools/eudamed/api/devices/udiDiData"
UA = "Mozilla/5.0 (compatible; observatorio-estetico/1.0)"


def buscar(termino, limite=10):
    params = {
        "page": 1,
        "pageSize": limite,
        "size": limite,
        "iso2Code": "en",
        "languageIso2Code": "en",
        "deviceStatusCode": "refdata.device-model-status.on-the-market",
        "searchText": termino,
    }
    url = f"{BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"  sin respuesta para '{termino}': {e}", file=sys.stderr)
        return None


def limpiar_clase(code):
    # "refdata.risk-class.class-iii" -> "Clase III"
    if not code:
        return ""
    tail = code.split(".")[-1].replace("class-", "").upper()
    return f"Clase {tail}"


def main():
    targets_path = DATA / "verify_targets.json"
    if not targets_path.exists():
        # semilla inicial: marcas de las fichas comerciales
        targets_path.write_text(json.dumps({
            "nota": "Marcas o fabricantes a verificar en EUDAMED. Anade los que necesites.",
            "terminos": ["Eufoton", "Vaser", "Sculptra", "Radiesse", "Profhilo", "Ellanse"]
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    targets = json.loads(targets_path.read_text(encoding="utf-8"))["terminos"]

    salida = {
        "generado": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "fuente": "EUDAMED - buscador publico (endpoint no oficial)",
        "aviso": "VERIFICACION PARCIAL. EUDAMED aun se despliega por fases; la ausencia de un dispositivo NO significa que no este certificado. Confirmar siempre con la Declaracion de Conformidad y el certificado del Organismo Notificado del fabricante.",
        "por_termino": {},
    }

    for termino in targets:
        print(f"-> EUDAMED: {termino}")
        data = buscar(termino)
        dispositivos = []
        if data and isinstance(data.get("content"), list):
            for d in data["content"]:
                dispositivos.append({
                    "nombre_comercial": d.get("tradeName") or "",
                    "fabricante": d.get("manufacturerName") or "",
                    "representante_ue": d.get("authorisedRepresentativeName") or "",
                    "clase_riesgo": limpiar_clase((d.get("riskClass") or {}).get("code")),
                    "estado": (d.get("deviceStatusType") or {}).get("code", "").split(".")[-1],
                    "referencia": d.get("reference") or "",
                    "srn_fabricante": d.get("manufacturerSrn") or "",
                })
        salida["por_termino"][termino] = {
            "encontrados": len(dispositivos),
            "dispositivos": dispositivos,
            "estado_verificacion": "parcial - confirmar con documentacion del fabricante",
        }
        print(f"   {len(dispositivos)} dispositivos en EUDAMED")
        time.sleep(1.0)

    (DATA / "eudamed.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Listo: eudamed.json")


if __name__ == "__main__":
    main()
