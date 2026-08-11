#!/usr/bin/env python3
"""
Genera data/google_trends.json con interes de busqueda por tratamiento.

Usa pytrends, un cliente no oficial de Google Trends. Google puede cambiar el
formato sin aviso: el script escribe lo que consigue y marca como incompletos
los terminos que fallen, en lugar de abortar.

Google Trends solo admite 5 terminos por comparacion, asi que los tratamientos
se procesan en lotes de 5 anclados al primer termino de la lista para que las
escalas sean comparables entre lotes.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from pytrends.request import TrendReq
except ImportError:
    print("Falta pytrends. Instala con: pip install pytrends", file=sys.stderr)
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

PAISES = {"ES": "Espana", "MX": "Mexico", "AR": "Argentina",
          "CO": "Colombia", "US": "Estados Unidos", "BR": "Brasil"}
VENTANA = "today 5-y"
PAUSA = 4  # segundos entre peticiones, para no encadenar bloqueos


def batches(items, size, anchor):
    """Lotes de 5 terminos manteniendo el ancla en primera posicion."""
    rest = [i for i in items if i != anchor]
    for start in range(0, len(rest), size - 1):
        yield [anchor] + rest[start:start + size - 1]


def main() -> None:
    catalog = json.loads((DATA / "treatments.json").read_text(encoding="utf-8"))
    treatments = catalog["tratamientos"]
    keyword_of = {t["trends_kw"]: t["id"] for t in treatments}
    keywords = list(keyword_of)
    anchor = keywords[0]

    pytrends = TrendReq(hl="es-ES", tz=60, retries=2, backoff_factor=1.0)
    salida = {
        "generado": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "fuente": "Google Trends (cliente no oficial pytrends)",
        "ventana": VENTANA,
        "paises": PAISES,
        "interes_temporal": {},
        "interes_por_pais": {},
        "incompletos": [],
    }

    for codigo, nombre in PAISES.items():
        print(f"-> {nombre}")
        for lote in batches(keywords, 5, anchor):
            try:
                pytrends.build_payload(lote, timeframe=VENTANA, geo=codigo)
                serie = pytrends.interest_over_time()
            except Exception as error:  # noqa: BLE001
                print(f"   lote sin datos: {error}", file=sys.stderr)
                salida["incompletos"].append({"pais": codigo, "terminos": lote})
                time.sleep(PAUSA)
                continue

            if serie.empty:
                salida["incompletos"].append({"pais": codigo, "terminos": lote})
                time.sleep(PAUSA)
                continue

            fechas = [d.strftime("%Y-%m") for d in serie.index]
            pais = salida["interes_temporal"].setdefault(codigo, {"fechas": fechas, "series": {}})
            for kw in lote:
                if kw not in serie.columns:
                    continue
                valores = [int(v) for v in serie[kw].tolist()]
                tid = keyword_of[kw]
                pais["series"][tid] = valores
                media_reciente = sum(valores[-12:]) / max(len(valores[-12:]), 1)
                media_previa = sum(valores[-24:-12]) / max(len(valores[-24:-12]), 1) or 1
                salida["interes_por_pais"].setdefault(tid, {})[codigo] = {
                    "media_12m": round(media_reciente, 1),
                    "delta_anual": round((media_reciente - media_previa) / media_previa * 100, 1),
                    "pico": max(valores),
                }
            time.sleep(PAUSA)

    (DATA / "google_trends.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Listo: google_trends.json ({len(salida['incompletos'])} lotes sin datos)")


if __name__ == "__main__":
    main()
