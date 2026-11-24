# al_qgis_plugins — Reglas del agente

Reglas específicas de los plugins QGIS de este workspace. Suman a las reglas
globales de `../AGENTS.md`.

## Versionado (ExportadorRedes_Beta y futuros plugins)

- **Cada cambio en el código del plugin debe ir acompañado de la pregunta al
  usuario: "¿actualizamos versión?"** — no asumir bump automático ni mantener
  la versión en silencio. El usuario decide si el cambio amerita nueva versión
  (`__init__.py` → `VERSION`, `metadata.txt` → `name`/`version`/`changelog`,
  `CHANGELOG.md` → nueva entrada) o se queda en la misma.

## Empaquetado

- Tras cambios aprobados: empaquetar con
  `powershell -ExecutionPolicy Bypass -File ..\Tools\package-plugin.ps1 -PluginName "<carpeta>"`
  → genera `dist/<Plugin>-v<X.Y.Z>.zip` (conserva los 3 builds más recientes).
- Verificación mínima tras editar Python: `python -m py_compile <archivo>`.
- **Tras empaquetar, actualizar la memoria general antes de cerrar:** la
  sección `al_qgis_plugins` de `../HANDOFF.md` (versión, nombre del zip en
  `dist/`, qué probar en QGIS). El usuario dirá "chequea" para verificar.

## Convenciones del ExportadorRedes_Beta

- Estilos QML de capas en `ExportadorRedes_Beta/estilos/` (`DIR_ESTILOS_LOCAL`).
- Salidas siempre en `<proyecto>/PDFs_Exportacion/` vía `get_output_dir()`.
- Flujos que crean capas persistentes siguen el patrón de `RecortesPDF`:
  memory layer temporal → `QgsVectorFileWriter` a GPKG → `QgsVectorLayer(uri, ..., "ogr")`
  → `addMapLayer` (la capa cargada es la persistente, no la temporal).
