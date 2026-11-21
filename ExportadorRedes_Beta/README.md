# Exportador de Redes Pro — Beta 0.17.51

Plugin QGIS que prepara el proyecto, genera cuadrículas de recortes, aplica estilos QML y exporta planos en PNG/JPG y PDF para redes de **Abastecimiento** y **Saneamiento**.

> ⚠️ **Versión BETA** — valida el flujo completo en tus proyectos reales antes de sustituir la versión de producción. Historial completo en `CHANGELOG.md`.

---

## Requisitos

| Componente | Versión mínima | Notas |
|------------|----------------|-------|
| QGIS       | **3.30**       | Probado en 3.40.2 |
| Qt         | 5.15.4+        | Incluido con QGIS 3.30+ |
| Python     | 3.9+           | Incluido con QGIS 3.30+ |
| Sistema    | Windows / Linux / macOS | Probado en Windows 10/11 |

> **Breaking change respecto a 0.14.x**: la 0.16.0 sube `qgisMinimumVersion` de 3.16 a 3.30 por el uso de enums modernos (`Qgis.MapSettingsFlag`, `QgsUnitTypes.LayoutUnit`, `QMetaType.Type`).

---

## Instalación

### Opción A — Copia manual (recomendada para pruebas)

1. Copia la carpeta `ExportadorRedes_Beta\` completa a:

C:\Users<usuario>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\

2. Cierra QGIS por completo (verifica que no quede `qgis-bin.exe` en el Administrador de tareas).
3. Abre QGIS.
4. Ve a **Complementos → Administrar e instalar complementos → Instalados**.
5. Activa **"Exportador de Redes Pro (Beta 0.17.51)"**.

### Opción B — Instalación desde ZIP

1. Genera el `.zip` con `Tools\package-plugin.bat` del Workspace (el nombre del archivo incluye la versión, p. ej. `ExportadorRedes_Beta-v0.17.51.zip`).
2. En QGIS: **Complementos → Administrar e instalar complementos → Instalar desde ZIP**.
3. Selecciona el `.zip` generado y pulsa **Instalar complemento**.
4. Activa el plugin en la pestaña **Instalados**.

---

## Uso rápido

### Flujo de trabajo

1. **Pestaña 1 — Preparación**
- Escribe el nombre del municipio.
- Pulsa **▶ PREPARAR PROYECTO** → aplica estilos, oculta capas auxiliares, configura filtros.
2. **Pestaña 2 — Cuadrícula**
- Ajusta ancho, alto y solape.
- Pulsa **Generar Capa de Recortes** → crea la capa `RecortesPDF` con la malla.
3. **Pestaña 3 — Exportar**
- Configura DPI y formato (PNG/JPG).
- **1.1** Generales e Índices (no requiere cuadrícula).
- **1.2** Planos de Detalle (requiere cuadrícula).
- **1.3** Leyendas.
- **Unificar PDF** → genera el PDF final.
4. **Pestaña 1 — Preparación**
- Pulsa **↺ RESTAURAR PROYECTO** al terminar.

Los archivos se guardan en `ExportadorRedes_Beta/`:

```text
├── metadata.txt          # Metadatos del plugin (nombre, versión=0.17.51, autor)
├── __init__.py           # Punto de entrada (classFactory + VERSION)
├── exportador_plugin.py  # Código principal (~3300 líneas)
├── README.md             # Este archivo
├── CHANGELOG.md          # Historial de versiones
├── LICENSE.txt           # Licencia
├── icon.png              # Icono de la barra de herramientas
├── estilos/              # Estilos QML de impresión (recortes, potables, saneamiento)
├── logos_generales/      # logo_dielmo.png + logos_feder.png (cofinanciación FEDER)
└── logos_municipios/     # ~80 escudos municipales para portadas de planos
```


---

## Licencia

Ver `LICENSE.txt`.