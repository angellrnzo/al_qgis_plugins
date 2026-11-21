# logos_tarragona

Toolkit de escudos municipales de Tarragona. **No es un plugin QGIS** (sin `metadata.txt`).

Documentación completa del pipeline y estado de los assets: ver [`../WIKI.md`](../WIKI.md) §4.

## Uso

```powershell
pip install -r requirements.txt   # solo Pillow
python logos_tarragona.py
```

Un solo script con **menú interactivo** que guía todo el pipeline:

| Opción | Qué hace |
| :--- | :--- |
| 1 | Descarga escudos desde Wikimedia Commons → `logos_municipios/` |
| 2 | Procesa imágenes manuales de `logos_faltantes/` (fondo transparente + recorte + 800px) |
| 3 | Mapea y renombra → `logos_finales/` con formato `NN_municipio.png` |
| 4 | Verifica que los 82 municipios están completos |
| 5 | Limpieza de fondos blancos en lote sobre ambas carpetas |
| 6 | Genera `lista_descargados.txt` con los PNG descargados |
| 7 | **Pipeline completo guiado** — pregunta qué pasos ejecutar según el estado de las carpetas |

## Estructura

```text
logos_tarragona/
├── logos_tarragona.py          # script único (menú + pipeline completo)
├── requirements.txt            # Pillow>=10.0
├── logos_tarragona_assets.zip  # assets: logos_municipios/ + logos_finales/ + faltantes/
├── logos_municipios/           # (generada al descomprimir el zip) descargas crudas
├── logos_finales/              # (generada) 82 escudos procesados NN_municipio.png
└── logos_faltantes/            # (manual) imágenes conseguidas a mano
```

> Para re-ejecutar el pipeline: descomprimir `logos_tarragona_assets.zip` en esta carpeta para restaurar las imágenes que el script espera.
>
> Nota: la descarga desactiva la verificación SSL (`CERT_NONE`) para tolerar certificados inválidos de algunos ayuntamientos. Solo descargar imágenes públicas de escudos.
