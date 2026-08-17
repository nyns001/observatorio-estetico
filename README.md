# Observatorio estetico — MVP

Dashboard de investigacion en medicina y cosmetica estetica. Reune evidencia publicada,
interes de busqueda y equipos autorizados, tratamiento por tratamiento.

## Que hace cada fuente

| Seccion | Fuente | Coste | Frecuencia |
|---|---|---|---|
| Publicaciones recientes | PubMed E-utilities, llamada desde el navegador | Gratis | En vivo, en cada visita |
| Banda de evidencia (volumen anual) | PubMed E-utilities via GitHub Actions | Gratis | Semanal |
| Equipos citados en la evidencia | Mineria de abstracts de PubMed | Gratis | Semanal |
| Autorizaciones de equipos | openFDA 510(k) | Gratis | Semanal |
| Interes de busqueda | Google Trends via pytrends (cliente no oficial) | Gratis | Semanal |
| Recuperacion, cuidados, combinaciones | `data/treatments.json`, curado a mano | — | Manual |

Fuera de este MVP, previsto para v2: clinicas, doctores, precios, TikTok e Instagram.
Ninguna de esas cinco tiene hoy una fuente publica y gratuita; las tres primeras exigen
curacion propia y las dos ultimas, un proveedor de datos de pago.

## Puesta en marcha

1. Crea un repositorio en GitHub y sube estos ficheros.
2. En **Settings → Pages**, elige *Deploy from a branch*, rama `main`, carpeta `/ (root)`.
   El dashboard queda publicado en `https://TU-USUARIO.github.io/TU-REPO/`.
3. En **Settings → Actions → General**, marca *Read and write permissions* en
   *Workflow permissions*. Sin esto el workflow no puede guardar los datos.
4. Ve a **Actions → Actualizar datos → Run workflow** para la primera carga.
   Tarda unos minutos. Hasta que termine, el panel muestra las secciones vacias
   con la instruccion correspondiente: es el comportamiento esperado, no un error.

### Claves opcionales

Ninguna es obligatoria. En **Settings → Secrets and variables → Actions**:

- `NCBI_API_KEY` — sube el limite de PubMed de 3 a 10 peticiones/segundo. Gratis desde tu cuenta NCBI.
- `NCBI_EMAIL` — cortesia recomendada por NCBI para identificar el origen de las consultas.
- `OPENFDA_API_KEY` — sube openFDA de 1.000 a 120.000 peticiones/dia. Gratis.

## Ejecutar en local

```bash
pip install -r requirements.txt
python scripts/update_pubmed.py
python scripts/update_devices.py
python scripts/update_google_trends.py
python -m http.server 8000     # abre http://localhost:8000
```

Sirve la carpeta con un servidor: abrir `index.html` con doble clic bloquea la carga
de los ficheros de `data/` por politica de origen del navegador.

## Anadir un tratamiento

Todo el catalogo vive en `data/treatments.json`. Anade una entrada con estos campos y
los scripts la recogen en la siguiente ejecucion:

- `pubmed_query` — sintaxis de busqueda de PubMed. Pruebala primero en pubmed.ncbi.nlm.nih.gov;
  una consulta demasiado amplia infla el volumen con literatura no relacionada.
- `trends_kw` — como lo busca la gente, no como se llama en la literatura.
- `fda_query` — termino generico del dispositivo, en ingles.
- `zonas`, `recuperacion`, `cuidados`, `complementarios` — contenido curado.

Para ampliar la deteccion de equipos, anade pares `(etiqueta, patron)` a `DEVICE_LEXICON`
en `scripts/update_pubmed.py`.

## Limites que conviene tener presentes

- Google Trends no tiene API oficial. `pytrends` funciona bien pero Google puede bloquear
  o cambiar el formato sin aviso; por eso el workflow lo ejecuta con `continue-on-error`.
- El registro 510(k) es estadounidense: no refleja marcado CE ni disponibilidad en Europa.
- El volumen de publicaciones mide actividad investigadora, no eficacia ni seguridad.
- Los campos clinicos son orientativos y deben ser revisados y firmados por un medico
  colegiado antes de publicar el panel de cara al publico.
