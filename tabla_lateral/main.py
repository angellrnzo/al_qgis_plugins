from qgis.core import QgsMapLayerType
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDockWidget, QAction

class TablaLateralPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None

    def initGui(self):
        self.action = QAction("Abrir Tabla en Lateral", self.iface.mainWindow())
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
        if capa and capa.type() == QgsMapLayerType.VectorLayer:
            self.iface.showAttributeTable(capa)
            for dock in self.iface.mainWindow().findChildren(QDockWidget):
                if capa.name() in dock.windowTitle():
                    dock.setFloating(False)
                    self.iface.mainWindow().addDockWidget(Qt.RightDockWidgetArea, dock)
                    break
        else:
            self.iface.messageBar().pushWarning("Aviso", "Selecciona una capa vectorial primero.")
