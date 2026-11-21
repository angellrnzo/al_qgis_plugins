import os

from qgis.core import QgsMapLayerType
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QDockWidget, QAction

VERSION = "1.3"


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
            self.iface.mainWindow().addDockWidget(Qt.RightDockWidgetArea, dock)
            dock.raise_()
            dock.setFocus()

    def _buscar_dock_tabla(self, capa):
        """Localiza el QDockWidget que muestra la tabla de atributos de `capa`."""
        capa_id = capa.id()
        docks = self.iface.mainWindow().findChildren(QDockWidget)

        # Primero por capa asociada (robusto ante renombrados y títulos localizados)
        for dock in docks:
            for obj in (dock, dock.widget()):
                getter = getattr(obj, "layer", None)
                if callable(getter):
                    try:
                        capa_dock = getter()
                        if capa_dock is not None and capa_dock.id() == capa_id:
                            return dock
                    except Exception:
                        pass

        # Fallback: coincidencia por título
        for dock in docks:
            if capa.name() in dock.windowTitle():
                return dock
        return None
