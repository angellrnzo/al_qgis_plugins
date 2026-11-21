# 🗺️ al_qgis_plugins

Colección de plugins y herramientas para **QGIS** desarrollados por [angellrnzo](https://github.com/angellrnzo).

Cada plugin es una **carpeta sin comprimir** en la raíz del repo. Los `.zip` de prueba se generan con timestamp en `dist/` (ignorado por git) listos para *Plugins → Install from ZIP* en QGIS.

---

## 📦 Contenido del Repo

| Carpeta | Tipo | Descripción |
| :--- | :--- | :--- |
| [`ExportadorRedes_Beta/`](ExportadorRedes_Beta/) | ✅ Plugin QGIS | Exportador automático de planos de redes (Abastecimiento y Saneamiento): preparación de proyecto, cuadrículas y exportación PNG/JPG/PDF con maquetación FEDER. **v0.17.48** |
| [`tabla_lateral/`](tabla_lateral/) | ✅ Plugin QGIS | Panel lateral con la tabla de atributos de la capa activa (icono SVG, atajo `Alt+T`). **v1.2** |
| [`logos_tarragona/`](logos_tarragona/) | 🛠️ Tooling | Scripts Python de descarga/organización de escudos municipales de Tarragona + assets comprimidos en `logos_tarragona_assets.zip` (351 archivos) |
| `dist/` | 📦 Output | `.zip` de test generados — **no commitear** |

---

## 🚀 Instalación en QGIS

1. Genera el paquete (doble clic en `Tools\package-plugin.bat` del Workspace, o manualmente comprime la carpeta del plugin).
2. En QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Requisitos: `ExportadorRedes_Beta` necesita **QGIS ≥ 3.30**; `tabla_lateral` funciona en QGIS ≥ 3.0.

> Los plugins siguen la estructura oficial: `metadata.txt` + `__init__.py` en la raíz de cada carpeta.

---

## 🗂️ Estructura de un Plugin

```text
<nombre_plugin>/
├── metadata.txt          # Metadatos QGIS (name, version, qgisMinimumVersion, author...)
├── __init__.py           # Entry point: classFactory() → instancia del plugin
├── <modulo_principal>.py # Lógica del plugin
├── icon.png              # Icono en Plugins > Manage
├── README.md             # Documentación del plugin
├── CHANGELOG.md          # Historial de versiones
├── LICENSE.txt           # Licencia
└── <assets>/             # Estilos QML, logos, recursos
```

---

## 🔄 Versionado

- La versión canónica vive en `metadata.txt` (`version=`) y como constante `VERSION` en el código de entrada.
- Cada `.zip` generado se nombra `<Plugin>-v<X.Y.Z>.zip` (versión de `metadata.txt` al final, sin timestamp) — así cada build instalado desde ZIP es identificable en QGIS (*Plugins → Installed* muestra nombre + versión del `metadata.txt*).
- Regla: **sube la versión en código antes de generar un nuevo paquete**; nunca reutilices un número.

## 🔄 Flujo de Trabajo (Workspace)

```text
Documents\Workspace\
├── al_qgis_plugins\      ← este repo
│   ├── <plugin>/         # código fuente sin comprimir
│   └── dist/             # .zip de test (gitignored)
└── Tools\
    ├── package-plugin.ps1
    └── package-plugin.bat
```

- **Empaquetar:** `Tools\package-plugin.bat` → indica el nombre del plugin → genera `dist/<plugin>-v<X.Y.Z>.zip` (la versión se lee de `metadata.txt` y va al final).
- **Commitear:** los cambios en las carpetas de plugins se suben con `git add/commit/push` normal.
- Los `.zip` de `dist/` **nunca** se commitean.

---

## 🛠️ Pipeline de Logos (`logos_tarragona/`)

Scripts de utilidad para descargar y organizar escudos municipales de la provincia de Tarragona:

| Script | Función |
| :--- | :--- |
| `descargar_logos.py` | Descarga masiva de escudos desde fuentes abiertas |
| `proceso.py` | Procesado/renombrado de imágenes descargadas |
| `mapear_def.py` | Mapeo de nombres de municipio a archivos |
| `verificar_logos.py` | Verificación de integridad de descargas |
| `listar_archivos.py` | Inventario de archivos del pipeline |
| `limpiar_todo.py` | Limpieza de archivos temporales |

**Assets:** `logos_tarragona_assets.zip` contiene 4 colecciones:
- `logos_municipios/` — 250 escudos raw descargados
- `logos_finales/` — 82 escudos procesados finales
- `logos_faltantes/` — 17 municipios que faltaban (ya resueltos)
- `logo_dielmo/` — logos institucionales DIELMO

> Para usar los scripts con las imágenes, descomprime el `.zip` en la misma carpeta.

---

## 📖 Wiki

Documentación técnica completa (arquitectura de cada plugin, pipeline de logos, formato de metadata.txt): **[WIKI.md](WIKI.md)**

---

## 👨‍💻 Autor

**Angel Lorenzo** — [GitHub](https://github.com/angellrnzo) • [LinkedIn](https://www.linkedin.com/in/angellrnzo/)
