import os

from qgis.core import QgsMapLayerType
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QDockWidget, QAction

VERSION = "1.4"


class TablaLateralPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None

    def initGui(self):
        self.action = QAction("Abrir Tabla en Lateral", self.iface.mainWindow())
        icon_path = os.path.join(os.path.dirname(__file__), "icon.svg")
        if os.path.exists(icon_path):
            self.action.setIcon(QIcon(icon_path))
        self.action.triggered.connect(self.ejecutar)
        self.iface.registerMainWindowAction(self.action, "Alt+T")
        self.iface.addPluginToMenu("Tabla Lateral", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        self.iface.unregisterMainWindowAction(self.action)
        self.iface.removePluginMenu("Tabla Lateral", self.action)
        self.iface.removeToolBarIcon(self.action)

    def ejecutar(self):
        capa = self.iface.activeLayer()
        if not capa or not capa.isValid() or capa.type() != QgsMapLayerType.VectorLayer:
            self.iface.messageBar().pushWarning("Aviso", "Selecciona una capa vectorial primero.")
            return

        self.iface.showAttributeTable(capa)
        dock = self._buscar_dock_tabla(capa)
        if dock:
            dock.setFloating(False)
            main = self.iface.mainWindow()
            # Agrupar como pestaña con otra tabla ya visible en el panel derecho
            for otro in main.findChildren(QDockWidget):
                if otro is dock or not otro.isVisible():
                    continue
                if main.dockWidgetArea(otro) != Qt.RightDockWidgetArea:
                    continue
                if self._capa_de_dock(otro) is not None:
                    main.tabifyDockWidget(otro, dock)
                    break
            else:
                main.addDockWidget(Qt.RightDockWidgetArea, dock)
            dock.raise_()
            dock.setFocus()

    def _capa_de_dock(self, dock):
        """Devuelve la QgsMapLayer asociada a un dock de tabla, o None."""
        for obj in (dock, dock.widget()):
            getter = getattr(obj, "layer", None)
            if callable(getter):
                try:
                    capa = getter()
                    if capa is not None:
                        return capa
                except Exception:
                    pass
        return None

    def _buscar_dock_tabla(self, capa):
        """Localiza el QDockWidget que muestra la tabla de atributos de `capa`."""
        capa_id = capa.id()
        docks = self.iface.mainWindow().findChildren(QDockWidget)

        # Primero por capa asociada (robusto ante renombrados y títulos localizados)
        for dock in docks:
            capa_dock = self._capa_de_dock(dock)
            if capa_dock is not None and capa_dock.id() == capa_id:
                return dock

        # Fallback: coincidencia por título
        for dock in docks:
            if capa.name() in dock.windowTitle():
                return dock
        return None
