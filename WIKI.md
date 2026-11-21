# 📚 al_qgis_plugins — Technical Wiki

Manual técnico de los plugins y herramientas del repositorio. Para instalación rápida ver [README.md](README.md).

---

## 📑 Índice

1. [Convenciones del Repositorio](#1-convenciones-del-repositorio)
2. [Plugin: ExportadorRedes_Beta](#2-plugin-exportadorredes_beta)
3. [Plugin: Tabla Lateral](#3-plugin-tabla-lateral)
4. [Pipeline de Logos de Tarragona](#4-pipeline-de-logos-de-tarragona)
5. [Sistema de Empaquetado (.zip)](#5-sistema-de-empaquetado-zip)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Convenciones del Repositorio

- **Un plugin = una carpeta** en la raíz, nombrada en `PascalCase_Snake` (`ExportadorRedes_Beta`).
- **Sin comprimir en el repo** — el control de versiones gestiona el código; los `.zip` son solo artefactos de test.
- **`dist/` está en `.gitignore`** — nunca commitear paquetes generados.
- **Assets pesados** (imágenes, PDFs) se consolidan en `.zip` internos antes de commitear para no inflar el árbol de trabajo.
- Cada plugin debe tener `metadata.txt` + `__init__.py` válidos para QGIS Plugin Builder.

### Formato de `metadata.txt` (QGIS)

```ini
[general]
name=Nombre visible en Plugins
qgisMinimumVersion=3.30
description=Descripción corta
version=0.17.48
changelog=Historial legible por el usuario
author=angellrnzo
email=angellrnzo@users.noreply.github.com
about=Texto "About" del diálogo de plugins
tracker=URL del issue tracker (opcional)
hasProcessingProvider=no       # sí/no si provee algoritmos Processing
```

Campos clave: `qgisMinimumVersion` controla compatibilidad; `changelog` se muestra al actualizar; `icon.png` aparece en *Manage and Install Plugins*.

---

## 2. Plugin: ExportadorRedes_Beta

**Versión:** 0.17.48 (Beta) · **Requisito:** QGIS ≥ 3.30 · **Autor:** angellrnzo

Herramienta de automatización para proyectos de redes de abastecimiento y saneamiento (DIELMO / contexto municipal).

### Estructura interna

```text
ExportadorRedes_Beta/
├── metadata.txt              # v0.17.48 — ver changelog para historial completo
├── __init__.py               # classFactory() → ExportadorPlugin
├── exportador_plugin.py      # ~3300 líneas: lógica principal
├── icon.png
├── README.md / CHANGELOG.md / LICENSE.txt
├── estilos/                  # Estilos QML de impresión (recortes.qml, 111_p, 124_p, 211_s, 222_s, 225_s)
├── logos_generales/          # logo_dielmo.png + logos_feder.png (cofinanciación FEDER)
└── logos_municipios/         # ~80 escudos numerados (01_alcover.png …) para portada de planos
```

### Funcionalidades principales (según CHANGELOG)

- Preparación automática del proyecto y generación de cuadrículas de planos.
- Exportación masiva a **PNG, JPG y PDF** con DPI independientes para planos generales, leyendas y detalles.
- Selector de idioma **CA/ES** para el texto legal de cofinanciación FEDER.
- Detección automática del logotipo municipal por atributos del proyecto.
- Historial de carpetas recientes y rutas de respaldo QML fijadas en el `.qgz`.
- Fallbacks de capas satelitales/ortofoto con aviso cuando hay múltiples.

### ⚠️ Notas técnicas conocidas

- `STYLES_WS` / `STYLES_UD` apuntan a rutas absolutas `F:\Tarragona\...` — **hardcodeadas a propósito**: el plugin se ejecuta en un equipo remoto donde los proyectos viven en esa ruta (los `.qgz` se distribuyen por Google Drive). Además `estilos/222_s.qml` referencia CSVs de virtualización en `F:/Tarragona/...`.
- La versión vive solo en `VERSION` (`__init__.py`); `exportador_plugin.py` la importa y la usa en títulos de UI. Para bump: `metadata.txt` (`version=` + `changelog=` + `name=`) + `VERSION` + entrada en `CHANGELOG.md`.
- `metadata.txt` tiene email/tracker/repository reales (repo: `angellrnzo/al_qgis_plugins`).
- `log_message()` escribe en el panel del plugin **y** en `QgsMessageLog` (etiqueta `ExportadorRedes`) → visible en *Ver → Paneles → Mensajes de Log* para depurar en remoto.
- `bloquear_ui_exportacion()` descubre los controles por `findChildren` en `tab_exportador` (excluye `btn_stop` y `btn_toggle_modulos`); `cmb_municipio`/`cmb_idioma_feder` conservan su lógica de habilitación condicional.

---

## 3. Plugin: Tabla Lateral

**Versión:** 1.2 · **Requisito:** QGIS ≥ 3.0 · **Icono:** `icon.svg`

Plugin mínimo que abre la tabla de atributos de la capa activa en el **panel lateral** como `QDockWidget` acoplado a la derecha.

```text
tabla_lateral/
├── metadata.txt   # version=1.2, changelog, about, tracker
├── __init__.py    # classFactory() → TablaLateralPlugin
├── main.py        # Lógica + VERSION = "1.2"; acción, dock, atajo Alt+T
├── icon.svg       # Icono vectorial del plugin
└── README.md      # Doc del plugin
```

**Comportamiento:** `ejecutar()` obtiene `iface.activeLayer()`, valida `isValid()` + `QgsMapLayerType.VectorLayer`, llama `iface.showAttributeTable(capa)` y re-acopla el `QDockWidget` resultante a `Qt.RightDockWidgetArea`. `_buscar_dock_tabla()` localiza el dock por `layer().id()` (robusto ante renombrados y títulos localizados) con fallback a coincidencia por título. Sin capa válida → `messageBar().pushWarning`. La `QAction` lleva `icon.svg` en toolbar.

**Atajos:** `Alt+T` (registrado vía `registerMainWindowAction`).

---

## 4. Pipeline de Logos de Tarragona

Carpeta `logos_tarragona/` — **no es un plugin instalable** (sin `metadata.txt`); es un toolkit de scripts Python + assets.

### Scripts

| Script | Propósito |
| :--- | :--- |
| `descargar_logos.py` | Descarga escudos desde fuentes abiertas (Ayuntamientos, Wikipedia, THV) |
| `proceso.py` | Renombrado normalizado (`NN_nombre.png`), recorte y conversión |
| `mapear_def.py` | Mapeo nombre-de-municipio → archivo de imagen |
| `verificar_logos.py` | Chequeo de integridad / descargas fallidas |
| `listar_archivos.py` | Inventario del estado del pipeline |
| `limpiar_todo.py` | Eliminación de temporales y duplicados |

### Estado de los assets (`logos_tarragona_assets.zip`, 351 entradas)

| Subcarpeta | Contenido | Estado |
| :--- | :--- | :--- |
| `logos_municipios/` | 250 escudos raw (variantes `_THV_ES`, históricos, DOGC) | Fuente original |
| `logos_finales/` | 82 escudos procesados finales | ✅ Resultado del pipeline |
| `logos_faltantes/` | 17 municipios recuperados | ✅ `faltantes.txt` resuelto |
| `logo_dielmo/` | `logo_dielmo.png` + `ico1.svg` | Institucional |

**Archivos de estado** (se conservan sueltos, son pequeños):
- `faltantes.txt` — 17 municipios que faltaban (ya cubiertos por `logos_faltantes/`)
- `lista_descargados.txt` — 233 URLs/archivos descargados
- `log_descarga.txt` — log de 484 líneas del proceso de descarga

> **Para re-ejecutar el pipeline:** descomprimir `logos_tarragona_assets.zip` en `logos_tarragona/` para restaurar las carpetas de imágenes que los scripts esperan.

---

## 5. Sistema de Empaquetado (.zip)

Los `.zip` de test se generan con `Tools\package-plugin.ps1` del Workspace:

```powershell
# Uso directo
powershell -File ..\Tools\package-plugin.ps1 -PluginName "ExportadorRedes_Beta"

# Uso interactivo (doble clic)
..\Tools\package-plugin.bat
```

**Salida:** `al_qgis_plugins/dist/<Plugin>-v<X.Y.Z>-<yyyyMMdd-HHmmss>.zip` — el script lee `version=` de `metadata.txt` y lo incrusta en el nombre. El zip contiene el **contenido** de la carpeta (sin la carpeta padre), que es lo que QGIS espera al instalar desde ZIP.

**Convención de versionado:**
1. Subir `version=` en `metadata.txt` + constante `VERSION` en el código de entrada.
2. Registrar el cambio en `CHANGELOG.md` / `changelog=` del metadata.
3. Generar el zip — el nombre resultante identifica el build (`-v1.1-`).
4. QGIS muestra la versión del `metadata.txt` en *Manage and Install Plugins → Installed*, por lo que cada instalación desde ZIP es trazable.

`dist/` está cubierto por `.gitignore`; los zips no se versionan.

---

## 6. Troubleshooting

| Problema | Causa | Solución |
| :--- | :--- | :--- |
| Plugin no aparece en QGIS | `metadata.txt` mal formado o `__init__.py` sin `classFactory()` | Validar con *Plugins → Show Python Error Log*; revisar encoding UTF-8 |
| Error de rutas `F:\Tarragona` | Paths hardcodeados en `exportador_plugin.py` | Ajustar `STYLES_WS`/`STYLES_UD` o crear la estructura de carpetas esperada |
| Logos municipales no cargan | Falta `logos_municipios/` dentro del plugin | Está incluido en el repo; si se instaló desde ZIP antiguo, regenerar el paquete |
| `.zip` muy grande (>100MB) | Assets sin comprimir dentro del plugin | Consolidar assets en `.zip` interno o usar Git LFS |
| Scripts de `logos_tarragona` fallan | Carpetas de imágenes comprimidas | Extraer `logos_tarragona_assets.zip` en la carpeta |

---

*Última actualización: 2026-11-20*
