<!-- markdownlint-disable MD024 -->

# Changelog — Exportador de Redes Pro

Todas las versiones notables del plugin, con foco en los cambios de comportamiento.

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).
Versionado según [SemVer](https://semver.org/lang/es/).

---

## [0.17.57] — 2026-11-27 — BETA

### Corregido

- **"Preparar Archivo Base (Notas)" — grupos restaurados**: vuelve a
  verificar/crear la estructura `FieldPreparer > Revisados` en el árbol de
  capas en cada ejecución, existan o no las notas (el rediseño de la v0.17.55
  los había eliminado). Si la capa `Notas_<municipio>` ya existe se salta su
  creación pero los grupos quedan creados/verificados; la capa de notas sigue
  cargándose en la **raíz** del índice de capas, fuera de los grupos.

---

## [0.17.56] — 2026-11-23 — BETA

### Corregido

- **KML del polígono CNIG a WGS84**: la exportación a KML ahora fija `destinationCrs = EPSG:4326` explícitamente (el KML exige coordenadas geográficas; el GPKG sigue en el CRS del proyecto).
- **Margen del buffer**: `currentIndex() = -1` (combo sin selección) ya no resuelve a 10 m por indexación negativa — cae a 0 m.
- **Capa de notas — protección de datos**: si `Notas_<municipio>.gpkg` existe en disco pero la capa no está cargada en el proyecto, ahora pide confirmación antes de sobrescribir (antes borraba
  polígonos/notas guardados sin avisar).

---

## [0.17.55] — 2026-11-23 — BETA

### Cambiado

- **Capa de notas rediseñada**: "Preparar Archivo Base (Notas)" ya no crea grupos `FieldPreparer/Revisados` ni una memory layer. Ahora genera `Notas_<municipio>.gpkg` **en la carpeta del proyecto**
  (mismo nivel que el `.qgz`), lo carga como capa OGR persistente y editable en la **raíz del índice de capas**, fuera de los grupos Potable/Saneamiento. Campos: `id` (entero) + `Notas` (texto, 260
  caracteres). Mantiene el estilo `QML_NOTAS`.
- **Detección tolerante a renombres**: si ya existe una capa cuyo nombre empiece por `notas_<municipio>` (p. ej. renombrada a mano con sufijos), el plugin la detecta, avisa y **no la crea ni la
  modifica**.

---

## [0.17.54] — 2026-11-23 — BETA

### Cambiado

- **Polígono CNIG sin shapefile**: se elimina la exportación a ESRI Shapefile (generaba `.shp`/`.shx`/`.dbf`/`.prj`/`.cpg`). Ahora solo produce `<municipio>_CNIG.gpkg` (capa persistente en el
  proyecto) y `<municipio>_CNIG.kml`, manteniendo `PDFs_Exportacion/` limpia.

---

## [0.17.53] — 2026-11-23 — BETA

### Cambiado

- **Polígono CNIG persistente**: el polígono de ámbito municipal ahora sigue el mismo flujo que `RecortesPDF` — se guarda como `<municipio>_CNIG.gpkg` en `PDFs_Exportacion/` y se carga al proyecto
  como capa OGR persistente (ya no es una capa temporal en memoria). Se aplica el estilo propio `estilos/municipio_cnig.qml` si existe; como fallback se usa `recortes.qml` con las etiquetas
  desactivadas. Solo se exporta `.kml` además del GPKG (sin shapefile, para no llenar la carpeta de archivos auxiliares).

---

## [0.17.52] — 2026-11-23 — BETA

### Añadido

- **Polígono de ámbito municipal (SHP + KML)**: nueva sección en la pestaña *Cuadrícula*. Genera un único polígono rectangular que abarca todas las capas vectoriales de los grupos *Potable* y
  *Saneamiento*, con margen exterior opcional de 0, 5 o 10 m (se recuerda la última elección). Crea la capa `<municipio>_CNIG` en el proyecto (nombre del municipio detectado) y exporta
  `<municipio>_CNIG.shp` + `<municipio>_CNIG.kml` en la carpeta de exportación. Abort a propósito si el lienzo está en un CRS geográfico, para que el margen en metros sea correcto.

---

## [0.17.51] — 2026-11-20 — BETA

### Añadido

- **Dock del plugin como pestaña**: al abrirse, el panel del Exportador se agrupa como pestaña con otros docks visibles del área derecha (`tabifyDockWidget`) en lugar de apilarse como dock
  independiente.

---

## [0.17.50] — 2026-11-20 — BETA

### Corregido

- **`get_grupo_raiz` con falso positivo por nombre**: antes cualquier ancestro llamado `Potable`/`Saneamiento`/`RecortesPDF` activaba las reglas de grupo, a cualquier profundidad. Un subgrupo anidado
  llamado `saneamiento` dentro de una carpeta de datos (`2003_..._COPIA_DXF_GPKG`) mantenía todo su contenido visible al preparar el proyecto. Ahora solo cuentan los grupos **de primer nivel** del árbol
  de capas; si el proyecto no tiene ninguno en raíz se conserva el comportamiento anterior como fallback.

---

## [0.17.49] — 2026-11-20 — BETA

### Cambiado

- **Acordeón "Módulos de Exportación" plegado por defecto**: la pestaña Exportar abre compacta (botón `▶`); el usuario despliega la selección solo cuando la necesita. Mismo patrón que "Capas Extra" en
  Preparación.
- **Resumen único de capas auxiliares ocultadas**: antes se emitía un WARNING por cada capa oculta por keyword (~30 líneas de log); ahora un solo WARNING indica el total y hasta 10 nombres, con el
  recordatorio de Capas Extra.

---

## [0.17.48] — 2026-11-20 — BETA

> Nota: las entradas 0.17.0–0.17.47 solo estaban documentadas en `metadata.txt` (`changelog=`); a partir de aquí se retoma este archivo.

### Cambiado

- **Versión centralizada**: `VERSION` en `__init__.py` es ahora la única fuente; la UI (título del dock, menú, acción) la usa vía f-strings en lugar de textos hardcodeados.
- **Metadatos completados**: `email` real, `tracker` y `repository` apuntando al repo.
- **`bloquear_ui_exportacion` dinámico**: los controles a bloquear se descubren con `findChildren` en la pestaña de exportación en lugar de una lista hardcodeada de 18 nombres; controles futuros
  quedan cubiertos automáticamente.

### Añadido

- **Espejo del registro en `QgsMessageLog`**: todo `log_message()` también escribe en *Ver → Paneles → Mensajes de Log* (etiqueta "ExportadorRedes"), facilitando depurar en equipos remotos sin acceso
  al panel del plugin.

### Corregido

- **`except: pass` → warnings logueados** en conexión de señales de proyecto y escritura de settings/historial de carpetas (antes fallaban en silencio).

---

## [0.16.0] — 2026-11-03 — BETA

Release que consolida los cambios planificados para las versiones 0.15 y 0.16 en un único salto. **Breaking change de compatibilidad**: `qgisMinimumVersion` sube de 3.16 a 3.30.

### Añadido

- **Transformación de CRS** en `run_generales` y `generar_cuadricula`: soporta capas en distintos sistemas de referencia.
- **Helper `_extent_en_crs_canvas`** para transformar extents al CRS del canvas.
- **Selector de formato** de captura: PNG (recomendado) o JPG (más ligero). Persiste en `QgsSettings`.
- **Log WARNING** al ocultar capas por coincidencia de keywords (`aux_mdt` / `aux_kw`).
- **Shim `_DRAW_LABELING_FLAG`** para compatibilidad entre versiones de QGIS.

### Cambiado

- **DPI unificado**: `spin_dpi` afecta a capturas, leyendas y PDF. Antes había tres DPI incoherentes (capturas 150, leyendas 200, PDF 150).
- **Umbral de aviso de PDF pesado** ajustado según DPI (20 MB a 150, 30 MB a 200, 50 MB a 300).
- **Enums modernos**: `Qgis.MapSettingsFlag.DrawLabeling`, `QgsUnitTypes.LayoutUnit.LayoutMillimeters`, `QMetaType.Type.Int` / `.QString`.
- **Textos de UI**: "PNG" en lugar de "JPG" en botones y tooltips.

### Corregido

- **`refreshLayerSymbology()`** ahora recibe el `layer.id()` correcto (evita `TypeError`).
- **`QMetaType`** con shim defensivo para PyQt5 < 5.15.4.

### Eliminado

- **Soporte para QGIS 3.16–3.29** (por el uso de enums modernos).

---

## [0.14.26] — 2026-11-03 — RELEASE DE SEGURIDAD

Release que solo toca código donde el comportamiento era incorrecto o peligroso. Sin cambios de comportamiento visible.

### Corregido

- **Bucle infinito** en `generar_cuadricula` si `solape >= ancho` o `solape >= alto`. Ahora valida antes del bucle.
- **CRS geográfico** tratado como metros: ahora avisa y aborta si el canvas está en grados.
- **Backup de estilos perdido** si había excepción con "Mantener Copia Original". Ahora restaura el backup original en el `except`.
- **Filtro OBSERVACIO** roto con apóstrofos (`"L'escomesa"`). Ahora escapa comillas simples y usa `NOT IN` con **todas** las acometidas detectadas.
- **Inyección HTML** en la consola de log (rutas con `&`, `<`, `>`). Ahora escapa con `html.escape()`.
- **`img.save()` silencioso**: ahora devuelve `bool` y cuenta fallos de guardado.
- **`QDomDocument.setContent()`** con retorno tupla/objeto `ParseResult`. Helper `_qdom_set_content` robusto para Qt5 y Qt6.
- **Estado del proyecto corrupto** si `run_generales`/`run_individuales` fallaban. Ahora `finally` limpia `subsetString` y visibilidad de recortes.
- **Municipio autodetectado sobrescribía edición manual**. Ahora solo autocompleta si el campo está vacío.
- **`get_layer_by_prefix` no determinista**: ahora prioriza coincidencia exacta y ordena alfabéticamente el fallback por prefijo.
- **Regex de carpeta** sin `IGNORECASE` para `_Completo/WS/UD`.

---

## [0.14.25] — 2026-11-01

### Añadido

- Botón **"Preparar Archivo Base (Notas)"** que crea los grupos `FieldPreparer > Revisados`.
- **Registro dinámico**: splitter vertical arrastrable con `QSplitter`.
- **Menú interactivo de gestión de estilos** con pestañas y checkboxes.

---

## [0.14.24] — 2026-10-25

### Corregido

- Rediseño de gestión de estilos.
- Correcciones de compatibilidad con QGIS 3.40.

---

## [0.14.23] — 2026-10-18

### Añadido

- Guardado inteligente: versionado automático `v1`, `v2`, ... al guardar estilos.

---

## [0.14.22] — 2026-10-10

### Añadido

- Toggle del botón del plugin (marcar/desmarcar).

---

## [0.14.21] — 2026-10-01

### Añadido

- Estilo 222 (Pozos) discreto.
- Modo FEDER con frase legal.
- Salvaguardas varias.
