# 🗺️ Roadmap — al_qgis_plugins

Features planeadas con **spec implementable** (anclas de código verificadas). Estado: nada de esto está implementado — es backlog documentado. Fuente de verdad de versiones: `metadata.txt` + constante
`VERSION` de cada plugin.

> ⛔ **Regla de oro del proyecto:** las rutas `F:\Tarragona\...` hardcodeadas en `ExportadorRedes_Beta` (`STYLES_WS`/`STYLES_UD`, `estilos/222_s.qml` y CSVs de virtualización) **NO se tocan** mientras
> dure el inventario de redes de Tarragona — el plugin corre en un equipo remoto donde esa estructura es fija. Ver E1.

---

## ExportadorRedes_Beta (`exportador_plugin.py`, ~3334 líneas)

### E1 — Rutas de estilos configurables 🗄️ ARCHIVADO

**Estado:** descartado — las rutas `F:\Tarragona` son fijas mientras dure el inventario de redes y, al terminar el proyecto, el plugin probablemente se archive tal cual. **No implementar.**

**Referencias por si algún día resurge:** `STYLES_WS`/`STYLES_UD` (~L107-108), `estilos/222_s.qml` con CSVs `F:/Tarragona/...`, persistencia de rutas en
`_leer_ruta_proyecto()`/`_escribir_ruta_proyecto()` (~L337-344).

### E2 — Guardar log a archivo

**Qué:** botón "Guardar log" en el panel de log que exporta todo el contenido a `.txt`.

**Anclas:** `setup_log_panel()` (~L535), `log_message()` (~L576), `copiar_log()` (~L595 — ya copia al portapapeles, replicar patrón con `QFileDialog.getSaveFileName` + `QFile`), `limpiar_log()`
(~L601).

**Spec:** `QFileDialog.getSaveFileName(self.dock, "Guardar log", get_output_dir(), "Log (*.log *.txt)")` → escribir contenido del `QTextEdit`/`QPlainTextEdit` del panel precedido de cabecera
`ExportadorRedes v{VERSION} — {fecha}`. Incluir en `get_output_dir('logs')`.

### E3 — Progreso y cancelación real en exportación masiva

**Qué:** barra de progreso por recorte/lámina durante `run_modulos`, `run_generales`, `run_individuales`, `generar_leyendas` y `unificar_pdf` (~L2505, L2571, L2697, L2806, L2939).

**Anclas:** ya existe `detener_exportacion()` (~L2337) y `bloquear_ui_exportacion()` (~L2343) con `btn_stop` excluido del bloqueo — el flag de cancelación ya está cableado; falta el `QProgressDialog`
con `setValue(i/total*100)` dentro de los bucles de captura (`tomar_captura` ~L2456) y comprobación del flag entre iteraciones.

### E4 — Plantillas de cuadrícula guardadas

**Qué:** presets de ancho/alto/solape del generador de recortes (~L1890 `generar_cuadricula`, controles en `setup_tab_generador` ~L1774).

**Cómo:** combo "Plantilla" + botones guardar/cargar; persistir en `QSettings("angellrnzo","ExportadorRedes")` o como `.json` en `get_output_dir()`. Reutilizar el patrón
`_leer_historial()`/`_escribir_historial()` (~L352-360) que ya persiste rutas recientes.

---

## Tabla Lateral (`main.py`, 84 líneas — plugin mínimo)

> Diseño deliberado: ~84 líneas, una sola responsabilidad. Cualquier feature que la infle >150 líneas debe replantearse como plugin aparte o funcionalidad nativa de QGIS.

### T1 — Abrir tabla filtrada por la selección actual

**Qué:** si la capa activa tiene features seleccionados, abrir la tabla mostrando solo esos (checkbox en menú o comportamiento por defecto con modificador).

**Anclas:** `ejecutar()` (~L31) ya obtiene `iface.activeLayer()`; `iface.showAttributeTable(capa)` acepta `features=` (iterable de `QgsFeature`) en la firma de QGIS — pasar `capa.selectedFeatures()`
cuando `capa.selectedFeatureCount() > 0`.

### T2 — "Abrir tablas de todas las capas seleccionadas"

**Qué:** acción adicional que itera las capas seleccionadas en el árbol (`iface.layerTreeView().selectedLayers()`) y abre una por una con la misma lógica de `ejecutar()` + `tabifyDockWidget` (~L49) —
quedan agrupadas como pestañas automáticamente.

### T3 — Recordar última capa abierta

**Qué:** persistir `layer.id()` en `QSettings`; al ejecutar sin selección previa, reintentar con la última capa si sigue válida. Bajo valor — evaluar si merece la complejidad en un plugin de 84
líneas.

---

## Repo / Tooling (Workspace)

### R1 — Validador de metadata.txt

**Qué:** script `Tools\check-plugin.ps1` (o `.py`) que por cada carpeta de plugin verifique: `version=` existe y coincide con la constante `VERSION` del código, `qgisMinimumVersion` presente,
`metadata.txt` referenciado `icon` existe en disco, `CHANGELOG.md` menciona la versión actual. Ejecutable antes de generar el zip — detecta bumps incompletos.

### R2 — Changelog automático en el empaquetador

**Qué:** `package-plugin.ps1` podría comprobar que `CHANGELOG.md` contiene la versión de `metadata.txt` antes de generar el zip (aviso amarillo, no bloqueo — mismo estilo que la rotación de backups).

---

## Completado recientemente (referencia)

- **tabla_lateral v1.4** — agrupación de docks de tabla como pestañas (`tabifyDockWidget`).
- **ExportadorRedes_Beta v0.17.51** — su dock entra como pestaña en el grupo del panel derecho.
- **tabla_lateral v1.3** — búsqueda del dock por `layer().id()` + fallback por título.

---

*Última actualización: 2026-11-22*
