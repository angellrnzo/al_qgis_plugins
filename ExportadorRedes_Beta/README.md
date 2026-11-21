# Exportador de Redes Pro — Beta 0.16

Plugin QGIS que prepara el proyecto, genera cuadrículas de recortes, aplica estilos QML y exporta planos en PNG/JPG y PDF para redes de **Abastecimiento** y **Saneamiento**.

> ⚠️ **Versión BETA** — pensada para pruebas en paralelo con la 0.14.26 estable. No sustituyas la versión de producción hasta haber validado el flujo completo en tus proyectos reales.

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
5. Activa **"Exportador de Redes Pro (Beta 0.16)"**.

### Opción B — Instalación desde ZIP

1. Genera el `.zip` con el script `build_zip.bat` (ver más abajo).
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

Los archivos se guardan en:
ExportadorRedes_Beta/
├── metadata.txt Metadatos del plugin (nombre, versión, autor)
├── init.py Punto de entrada (classFactory)
├── exportador_plugin.py Código principal (~1500 líneas)
├── README.md Este archivo
├── CHANGELOG.md Historial de versiones
├── LICENSE.txt Licencia
├── icon.png Icono de la barra de herramientas
└── logos_feder.png Logo FEDER para el modo cofinanciación


---

## Licencia

Ver `LICENSE.txt`.