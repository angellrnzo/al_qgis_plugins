# logos_tarragona

Toolkit de scripts Python para el pipeline de descarga/procesado de escudos municipales de Tarragona. **No es un plugin QGIS** (sin `metadata.txt`).

Documentación completa del pipeline y estado de los assets: ver [`../WIKI.md`](../WIKI.md) §4.

## Uso

1. `pip install -r requirements.txt`
2. Descomprimir `logos_tarragona_assets.zip` en esta carpeta para restaurar las imágenes que los scripts esperan.
3. Ejecutar los scripts en orden (descarga → mapeo → proceso → verificación). Cada script escribe sus propios logs/archivos de estado en esta carpeta.

> Nota: `descargar_logos.py` desactiva la verificación SSL (`CERT_NONE`) para tolerar certificados inválidos de algunos ayuntamientos. Solo descargar imágenes públicas de escudos.
