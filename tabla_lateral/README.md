# Tabla Lateral

**Versión:** 1.4 · **Requisito:** QGIS ≥ 3.0 · **Autor:** [angellrnzo](https://github.com/angellrnzo)

Plugin minimalista que abre la **tabla de atributos** de la capa vectorial activa directamente en el **panel lateral** de QGIS, como `QDockWidget` acoplado a la derecha — sin ventana flotante que tape el lienzo.

---

## ¿Por qué?

- Tablas anchas o con muchas columnas se aprovechan mejor en un panel fijo.
- En monitores pequeños o portátiles, una ventana flotante siempre acaba tapando el mapa.
- El panel lateral se puede re-acoplar, redimensionar o pasar a flotante desde su propia barra de título.

---

## Instalación

**Opción A — Desde ZIP:**
1. Genera el paquete con `Tools\package-plugin.bat` del Workspace (o comprime la carpeta manualmente). El zip se nombra `tabla_lateral-v1.4.zip`.
2. En QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**.

**Opción B — Manual:**
1. Copia `tabla_lateral\` a `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`.
2. Reinicia QGIS y activa **Tabla Lateral** en *Manage and Install Plugins → Installed*.

---

## Uso

1. Selecciona una **capa vectorial** en el panel de capas.
2. Menú **Plugins → Tabla Lateral → Abrir Tabla en Lateral** (o el botón de la barra de herramientas).
3. La tabla se abre acoplada a la derecha. Si ya estaba abierta como ventana flotante, se re-acopla automáticamente.
4. **Atajo de teclado:** `Alt + T`.

> Solo funciona con capas vectoriales (`QgsMapLayerType.VectorLayer`). Con raster o sin selección activa muestra un aviso en la barra de mensajes.

---

## Estructura

```text
tabla_lateral/
├── metadata.txt   # name, version=1.4, qgisMinimumVersion=3.0, changelog
├── __init__.py    # classFactory() → TablaLateralPlugin
├── main.py        # Lógica: acción, dock widget, atajo Alt+T
└── icon.svg       # Icono del plugin (barra de herramientas y gestor)
```

## Versionado

La versión canónica vive en `metadata.txt` (`version=`) y como constante `VERSION` en `main.py`. El `.zip` generado incluye la versión en el nombre del archivo para identificar builds.

## Licencia

Ver `al_qgis_plugins` repo — uso personal/educativo.
