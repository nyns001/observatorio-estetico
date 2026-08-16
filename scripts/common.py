#!/usr/bin/env python3
"""
Utilidades compartidas para los scripts de datos.

Centraliza la logica HTTP que antes estaba duplicada en cada script, y aplica
reintentos con espera progresiva en TODAS las fuentes (antes solo PubMed y el
radar reintentaban; openFDA, EUDAMED y Trends fallaban al primer error, que es
justo donde mas fallos hay).
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UA = "Mozilla/5.0 (compatible; observatorio-estetico/1.0)"


def fetch_json(url, *, headers=None, timeout=45, intentos=4, silencioso_404=True):
    """GET que devuelve JSON. Reintenta con espera progresiva.

    Devuelve None si agota los intentos, para que el script decida si eso es
    fatal o solo un hueco en los datos.
    """
    cabeceras = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        cabeceras.update(headers)

    for intento in range(intentos):
        try:
            req = urllib.request.Request(url, headers=cabeceras)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            if e.code == 404 and silencioso_404:
                return None  # sin coincidencias, no es un error
            if e.code in (429, 500, 502, 503, 504) and intento < intentos - 1:
                time.sleep(2 ** intento)
                continue
            print(f"  HTTP {e.code}: {url[:90]}", file=sys.stderr)
            return None
        except Exception as e:  # noqa: BLE001
            if intento < intentos - 1:
                time.sleep(2 ** intento)
                continue
            print(f"  sin respuesta: {e}", file=sys.stderr)
            return None
    return None


def build_url(base, params):
    return f"{base}?{urllib.parse.urlencode(params)}"


def leer_json(nombre, por_defecto=None):
    ruta = DATA / nombre
    if not ruta.exists():
        return por_defecto
    return json.loads(ruta.read_text(encoding="utf-8"))


def escribir_json(nombre, datos):
    (DATA / nombre).write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Listo: {nombre}")


def catalogo():
    """Tratamientos del observatorio."""
    return leer_json("treatments.json")["tratamientos"]
