# -*- coding: utf-8 -*-
"""
Plugin QGIS: Exportador de Redes Pro
Prepara el proyecto, genera cuadrículas, aplica estilos QML (QGIS 3.40)
y exporta planos PNG/PDF de Abastecimiento y Saneamiento.
Versión 0.17.47 - BETA. Logotipo municipal dinámico.
Requiere QGIS 3.30+.
"""

import os
import json
import time
import re
import html
import unicodedata
from datetime import datetime

from qgis.PyQt.QtWidgets import (
    QAction, QDockWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QSpinBox, QFrame, QFileDialog, QComboBox, QCheckBox,
    QTabWidget, QWidget, QProgressBar, QGroupBox, QTextEdit, QSizePolicy, QScrollArea,
    QDialog, QDialogButtonBox, QListWidget, QListWidgetItem
)
from qgis.PyQt.QtCore import (
    QSize, Qt, QRectF, QMarginsF, QRect, QUrl, QMetaType, QStandardPaths,
)
from qgis.PyQt.QtGui import (
    QImage, QPainter, QColor, QIcon, QFont,
    QPdfWriter, QPageSize, QPageLayout, QDesktopServices, QTextCursor
)
from qgis.PyQt.QtXml import QDomDocument
from qgis.core import (
    QgsProject, QgsApplication, QgsMapRendererCustomPainterJob,
    QgsRectangle, QgsMapSettings, QgsSettings, QgsVectorLayer,
    QgsFeature, QgsGeometry, QgsField, QgsFeatureRequest,
    QgsReadWriteContext, QgsPrintLayout,
    QgsLayoutItemLegend, QgsLayoutExporter, QgsLayoutSize, QgsUnitTypes,
    QgsLayerTreeLayer, QgsLayerTreeGroup,
    QgsCoordinateTransform,
    QgsMapLayer, Qgis, QgsVectorFileWriter, QgsSpatialIndex,
    QgsMapLayerLegendUtils,
)

# ============================================================
# SHIMS DE COMPATIBILIDAD Qt5/Qt6 Y QGIS
# ============================================================
try:
    TYPE_INT = QMetaType.Type.Int
    TYPE_QSTRING = QMetaType.Type.QString
except AttributeError:
    TYPE_INT = QMetaType.Int
    TYPE_QSTRING = QMetaType.QString

try:
    _DRAW_LABELING_FLAG = Qgis.MapSettingsFlag.DrawLabeling
except AttributeError:
    _DRAW_LABELING_FLAG = QgsMapSettings.DrawLabeling

try:
    _PAGE_SIZE_A4 = QPageSize.PageSizeId.A4
    _ORIENT_PORTRAIT = QPageLayout.Orientation.Portrait
    _ORIENT_LANDSCAPE = QPageLayout.Orientation.Landscape
    _UNIT_MILLIMETER = QPageLayout.Unit.Millimeter
except AttributeError:
    _PAGE_SIZE_A4 = QPageSize.A4
    _ORIENT_PORTRAIT = QPageLayout.Portrait
    _ORIENT_LANDSCAPE = QPageLayout.Landscape
    _UNIT_MILLIMETER = QPageLayout.Millimeter

try:
    _LAYOUT_UNIT_MM = QgsUnitTypes.LayoutUnit.LayoutMillimeters
except AttributeError:
    _LAYOUT_UNIT_MM = QgsUnitTypes.LayoutMillimeters

# ============================================================
# CONSTANTES DE FILTROS Y CAPAS AUXILIARES
# ============================================================
LAYERS_HIDE_POTABLE = ('121_', '124_')
LAYERS_HIDE_SANEA = ('221_', '223_', '225_', '231_')

POINT_LABEL_HIDE_CODES = {
    '123', '125', '131', '133', '134', '135',
    '222', '224', '226', '227', '236',
}

MDT_KEYWORDS = ('mdt', 'lidar', 'hdt', 'modelo digital', 'terreno')

AUX_KEYWORDS = (
    'referencia', 'ref_elemento', 'tuberia', 'nota', 'duda', 'borrador',
    'dominio', 'bases_topografica', 'pigss', '_aca', 'aca_',
    'revisar', 'as built', 'inspeccion', 'dominios', 'catastro', 'catastre',
    'parcela', 'parcel.la', 'notas_'
)

ORTO_KEYWORDS = ('google satellite', 'ortofoto', 'orto icgc', 'pnoa', 'satellite', 'satelite', 'ortoimagen', 'ign')

ACOMETIDA_KEYWORDS = {
    'escomesa', 'acometida', 'escomeses',
    'connexio', 'connexion', 'connexions',
}

STYLES_WS = r'F:\Tarragona\01_Preparacion_previa\Estilos\Potables'
STYLES_UD = r'F:\Tarragona\01_Preparacion_previa\Estilos\Saneamiento'
DIR_ESTILOS_LOCAL = os.path.join(os.path.dirname(__file__), 'estilos')
QML_111 = '111_v5.qml'
QML_211 = '211_v4.qml'

FRASES_FEDER = {
    "CA": (
        "L'objecte d'aquest contracte està cofinançat per la Unió Europea, a través "
        "del Fons Europeu de Desenvolupament Regional (FEDER), en el marc del "
        "Programa FEDER de Catalunya 2021-2027. Operació Territori Rural "
        "Resilient (RURAL-AIGUA). Codi comptable 2026.0000006."
    ),
    "ES": (
        "El objeto de este contrato está cofinanciado por la Unión Europea, a través "
        "del Fondo Europeo de Desarrollo Regional (FEDER), en el marco del "
        "Programa FEDER de Cataluña 2021-2027. Operación Territorio Rural "
        "Resiliente (RURAL-AIGUA). Código contable 2026.0000006."
    ),
}

# RUTAS DE LOGOS ACTUALIZADAS
DIR_PLUGIN = os.path.dirname(__file__)
LOGOS_FEDER = os.path.join(DIR_PLUGIN, 'logos_generales', 'logos_feder.png')
LOGOS_DIELMO = os.path.join(DIR_PLUGIN, 'logos_generales', 'logo_dielmo.png')
CARPETA_MUNICIPIOS = os.path.join(DIR_PLUGIN, 'logos_municipios')

# ============================================================
# ESTILOS QML
# ============================================================

QML_NOTAS = r"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis hasScaleBasedVisibilityFlag="0" maxScale="0" autoRefreshTime="0" symbologyReferenceScale="-1" simplifyAlgorithm="0" styleCategories="AllStyleCategories" simplifyLocal="1" minScale="100000000" labelsEnabled="0" simplifyDrawingHints="1" simplifyDrawingTol="1" version="3.40.2-Bratislava" simplifyMaxScale="1" autoRefreshMode="Disabled" readOnly="0">
  <renderer-v2 referencescale="-1" enableorderby="0" symbollevels="0" type="singleSymbol" forceraster="0">
    <symbols>
      <symbol name="0" is_animated="0" frame_rate="10" force_rhr="0" type="fill" alpha="1" clip_to_extent="1">
        <data_defined_properties>
          <Option type="Map">
            <Option name="name" type="QString" value=""/>
            <Option name="properties"/>
            <Option name="type" type="QString" value="collection"/>
          </Option>
        </data_defined_properties>
        <layer locked="0" class="SimpleFill" enabled="1" id="{96f99494-3867-4f36-92d8-ea869a6bdec8}" pass="0">
          <Option type="Map">
            <Option name="border_width_map_unit_scale" type="QString" value="3x:0,0,0,0,0,0"/>
            <Option name="color" type="QString" value="0,0,255,255,rgb:0,0,1,1"/>
            <Option name="joinstyle" type="QString" value="bevel"/>
            <Option name="offset" type="QString" value="0,0"/>
            <Option name="offset_map_unit_scale" type="QString" value="3x:0,0,0,0,0,0"/>
            <Option name="offset_unit" type="QString" value="MM"/>
            <Option name="outline_color" type="QString" value="51,171,208,255,hsv:0.53863888888888889,0.75475700007629509,0.81515220874341954,1"/>
            <Option name="outline_style" type="QString" value="solid"/>
            <Option name="outline_width" type="QString" value="1"/>
            <Option name="outline_width_unit" type="QString" value="MM"/>
            <Option name="style" type="QString" value="dense7"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>"""

# Los estilos de capas (111_p, 124_p, 211_s, 222_s, 225_s, recortes)
# se cargan dinámicamente desde la subcarpeta 'estilos/'.


# ============================================================
# DIÁLOGO INTERACTIVO PARA GESTIÓN DE ESTILOS
# ============================================================
class StyleSelectionDialog(QDialog):
    def __init__(self, titulo, datos_por_pestaña, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumSize(450, 400)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.listas = {}

        for nombre_pestaña, items in datos_por_pestaña.items():
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            lista = QListWidget()
            for item_texto, item_data in items:
                list_item = QListWidgetItem(item_texto)
                list_item.setData(Qt.UserRole, item_data)
                list_item.setFlags(list_item.flags() | Qt.ItemIsUserCheckable)
                list_item.setCheckState(Qt.Unchecked)
                lista.addItem(list_item)
            tab_layout.addWidget(lista)
            self.listas[nombre_pestaña] = lista
            self.tabs.addTab(tab, nombre_pestaña)

        layout.addWidget(self.tabs)

        btn_layout = QHBoxLayout()

        btn_marcar_todo = QPushButton("Marcar Todo")
        btn_marcar_todo.clicked.connect(self.marcar_todo)
        btn_layout.addWidget(btn_marcar_todo)

        btn_marcar_potable = QPushButton("Marcar Potable")
        btn_marcar_potable.clicked.connect(lambda: self.marcar_pestaña("Potable"))
        btn_layout.addWidget(btn_marcar_potable)

        btn_marcar_saneamiento = QPushButton("Marcar Saneamiento")
        btn_marcar_saneamiento.clicked.connect(lambda: self.marcar_pestaña("Saneamiento"))
        btn_layout.addWidget(btn_marcar_saneamiento)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

    def marcar_todo(self):
        for lista in self.listas.values():
            for i in range(lista.count()):
                lista.item(i).setCheckState(Qt.Checked)

    def marcar_pestaña(self, nombre_pestaña):
        if nombre_pestaña in self.listas:
            lista = self.listas[nombre_pestaña]
            for i in range(lista.count()):
                lista.item(i).setCheckState(Qt.Checked)

    def get_selected(self):
        seleccionados = []
        for lista in self.listas.values():
            for i in range(lista.count()):
                item = lista.item(i)
                if item.checkState() == Qt.Checked:
                    seleccionados.append(item.data(Qt.UserRole))
        return seleccionados


# ============================================================
# WIDGET PRINCIPAL
# ============================================================
class ExportadorRedesDockWidget(QDockWidget):

    def __init__(self, iface):
        super().__init__("Plugin Exportador v0.17.47 (Beta)", iface.mainWindow())
        self.iface = iface
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setMinimumWidth(400)

        self.NOMBRE_CAPA = "RecortesPDF"
        self.GRUPO_POTABLE = "Potable"
        self.GRUPO_SANEA = "Saneamiento"
        self._cancelar = False

        self.estilos_originales = {
            "111_Trams_Potable": None,
            "211_Trams_Sanejament": None,
            "222_Pous_Registre_Sanejament": None,
            "124_Connexions_Potables": None,
            "225_Connexions_Sanejament": None,
            "RecortesPDF": None,
        }
        self._visibilidad_backup = []
        self._opacidad_backup = []
        self._point_labels_backup = {}
        self._filtros_backup = {}

        self.settings = QgsSettings()

        try:
            QgsProject.instance().readProject.connect(self._on_proyecto_leido)
            QgsProject.instance().cleared.connect(self._on_proyecto_limpiado)
        except Exception:
            pass

        self.tabs = QTabWidget()
        self.tab_estatus = QWidget()
        self.tab_generador = QWidget()
        self.tab_exportador = QWidget()

        self.tabs.addTab(self.tab_estatus, "1. Preparación")
        self.tabs.addTab(self.tab_generador, "2. Cuadrícula")
        self.tabs.addTab(self.tab_exportador, "3. Exportar")

        self.setup_tab_estatus()
        self.setup_tab_generador()
        self.setup_tab_exportador()

        log_widget = self.setup_log_panel()
        log_widget.setFixedHeight(150)

        central_widget = QWidget()
        layout_principal = QVBoxLayout()
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)
        layout_principal.addWidget(self.tabs, 1)
        layout_principal.addWidget(log_widget, 0)
        central_widget.setLayout(layout_principal)
        self.setWidget(central_widget)
        self.validar_campos()

    @staticmethod
    def _qdom_set_content(doc, content):
        try:
            result = doc.setContent(content)
        except Exception:
            return False
        if isinstance(result, tuple):
            return bool(result[0]) if result else False
        if hasattr(result, 'errorLine'):
            return bool(result)
        if hasattr(result, 'success'):
            return bool(result.success)
        return bool(result)

    @staticmethod
    def _aplicar_dom_style(capa, doc):
        """Aplica un QDomDocument de estilo a una capa QGIS con firma PyQGIS correcta."""
        ctx = QgsReadWriteContext()
        try:
            res = capa.readStyle(doc.documentElement(), "", ctx)
        except TypeError:
            res = capa.readStyle(doc.documentElement(), ctx)
        if isinstance(res, tuple):
            ok = bool(res[0])
            err = str(res[1]).strip() if len(res) > 1 and res[1] is not None else ""
            return ok, err
        return bool(res), ""

    def _leer_ruta_proyecto(self):
        try:
            val, _ok = QgsProject.instance().readEntry("ExportadorRedes", "carpeta_respaldos", "")
            return val or ""
        except Exception:
            return ""

    def _escribir_ruta_proyecto(self, ruta):
        try:
            QgsProject.instance().writeEntry("ExportadorRedes", "carpeta_respaldos", ruta)
            return True
        except Exception as exc:
            self.log_message(f"No se pudo guardar la carpeta en el proyecto: {exc}", "WARNING")
            return False

    def _leer_historial(self):
        raw = self.settings.value("PluginExportador/respaldos_historial", "[]", type=str)
        try:
            data = json.loads(raw) if raw else []
            return data if isinstance(data, list) else []
        except (ValueError, TypeError):
            return []

    def _escribir_historial(self, lista):
        try:
            self.settings.setValue("PluginExportador/respaldos_historial", json.dumps(lista[:5]))
        except Exception:
            pass

    def _registrar_ruta(self, ruta, en_proyecto=True):
        if not ruta:
            return
        try:
            self.settings.setValue("PluginExportador/respaldos_ultima_ruta", ruta)
        except Exception:
            pass

        historial = self._leer_historial()
        if ruta in historial:
            historial.remove(ruta)
        historial.insert(0, ruta)
        self._escribir_historial(historial)

        if en_proyecto:
            self._escribir_ruta_proyecto(ruta)

        self._refrescar_combo_historial(historial)

    def _refrescar_combo_historial(self, historial=None):
        if not hasattr(self, 'cmb_historial_respaldos'):
            return
        if historial is None:
            historial = self._leer_historial()
        self.cmb_historial_respaldos.blockSignals(True)
        self.cmb_historial_respaldos.clear()
        self.cmb_historial_respaldos.addItem("🕘 Ver carpetas recientes…", "")
        for ruta in historial:
            nombre = os.path.basename(ruta.rstrip("\\/")) or ruta
            self.cmb_historial_respaldos.addItem(nombre, ruta)
            idx = self.cmb_historial_respaldos.count() - 1
            self.cmb_historial_respaldos.setItemData(idx, ruta, Qt.ToolTipRole)
        self.cmb_historial_respaldos.setCurrentIndex(0)
        self.cmb_historial_respaldos.blockSignals(False)

    def _cargar_ruta_inicial(self):
        if not hasattr(self, 'txt_carpeta_respaldos'):
            return
        ruta_proyecto = self._leer_ruta_proyecto()
        ruta_global = self.settings.value("PluginExportador/respaldos_ultima_ruta", "", type=str)
        ruta = ruta_proyecto or ruta_global or ""
        self.txt_carpeta_respaldos.blockSignals(True)
        self.txt_carpeta_respaldos.setText(ruta)
        self.txt_carpeta_respaldos.blockSignals(False)

    def _on_proyecto_leido(self, dom):
        try:
            self._reiniciar_estado_proyecto()
            if hasattr(self, 'txt_carpeta_respaldos'):
                ruta_proyecto = self._leer_ruta_proyecto()
                if ruta_proyecto:
                    self.txt_carpeta_respaldos.blockSignals(True)
                    self.txt_carpeta_respaldos.setText(ruta_proyecto)
                    self.txt_carpeta_respaldos.blockSignals(False)
                else:
                    self._cargar_ruta_inicial()
            self.verificar_proyecto_actual(forzar=True)
            self._refrescar_lista_extra(conservar_seleccion=False)
        except Exception:
            pass

    def _on_proyecto_limpiado(self):
        try:
            self._reiniciar_estado_proyecto()
            if hasattr(self, 'txt_municipio'):
                self.txt_municipio.clear()
            if hasattr(self, 'cmb_municipio'):
                self.cmb_municipio.setCurrentIndex(0)
            if hasattr(self, 'lista_capas_extra'):
                self.lista_capas_extra.clear()
            self.validar_campos()
        except Exception:
            pass

    def _reiniciar_estado_proyecto(self):
        self.estilos_originales = {
            "111_Trams_Potable": None,
            "211_Trams_Sanejament": None,
            "222_Pous_Registre_Sanejament": None,
            "124_Connexions_Potables": None,
            "225_Connexions_Sanejament": None,
            "RecortesPDF": None,
        }
        self._visibilidad_backup.clear()
        self._opacidad_backup.clear()
        self._point_labels_backup.clear()
        self._filtros_backup.clear()

    def _on_texto_carpeta_changed(self, texto):
        texto = (texto or "").strip()
        if texto and os.path.isdir(texto):
            self._registrar_ruta(texto, en_proyecto=True)

    def _examinar_carpeta(self):
        actual = ""
        if hasattr(self, 'txt_carpeta_respaldos'):
            actual = self.txt_carpeta_respaldos.text().strip()
        if actual and os.path.isdir(actual):
            inicio = actual
        elif actual:
            inicio = os.path.dirname(actual)
        else:
            inicio = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)

        carpeta = QFileDialog.getExistingDirectory(
            self, "Elige la carpeta donde se guardan los estilos (respaldos)", inicio,
        )
        if carpeta:
            self.txt_carpeta_respaldos.setText(carpeta)
            self._registrar_ruta(carpeta, en_proyecto=True)
            self.log_message(f"Carpeta de respaldos: {carpeta}", "SUCCESS")

    def _al_elegir_historial(self, idx):
        if idx <= 0:
            return
        ruta = self.cmb_historial_respaldos.itemData(idx, Qt.UserRole)
        if ruta:
            self.txt_carpeta_respaldos.setText(ruta)
            self._registrar_ruta(ruta, en_proyecto=True)
            self.cmb_historial_respaldos.setCurrentIndex(0)

    def _fijar_ruta_al_proyecto(self):
        ruta = self.txt_carpeta_respaldos.text().strip() if hasattr(self, 'txt_carpeta_respaldos') else ""
        if not ruta:
            QMessageBox.information(
                self, "Falta la carpeta",
                "Primero escribe o elige una carpeta de respaldos.\n\nPuedes hacerlo con el botón 'Examinar…' de al lado.",
            )
            return
        if not os.path.isdir(ruta):
            QMessageBox.warning(
                self, "La carpeta no existe",
                f"La carpeta indicada no existe o no es accesible:\n\n{ruta}\n\nComprueba la ruta y vuelve a intentarlo.",
            )
            return
        ok = self._escribir_ruta_proyecto(ruta)
        self._registrar_ruta(ruta, en_proyecto=False)
        if ok:
            self.log_message(f"Carpeta guardada en el proyecto: {ruta}", "SUCCESS")
            QMessageBox.information(
                self, "Guardado en el proyecto",
                "Listo. Esta carpeta quedará asociada al proyecto actual.\n\nLa próxima vez que abras este mismo proyecto en QGIS, la carpeta aparecerá ya rellena.",
            )
        else:
            QMessageBox.warning(
                self, "No se pudo guardar",
                "La carpeta se ha configurado correctamente, pero no se pudo guardar dentro del archivo del proyecto.\n\nPuedes seguir usándola mientras el proyecto esté abierto. Si quieres que se recuerde, guarda el proyecto con Archivo → Guardar.",
            )

    def _carpeta_respaldos_actual(self):
        base_folder = ""
        if hasattr(self, 'txt_carpeta_respaldos'):
            base_folder = self.txt_carpeta_respaldos.text().strip()

        if base_folder and os.path.isdir(base_folder):
            return base_folder

        if base_folder:
            inicio = (base_folder if os.path.isdir(base_folder) else os.path.dirname(base_folder))
        else:
            inicio = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)

        base_folder = QFileDialog.getExistingDirectory(self, "Elige la carpeta donde se guardan los estilos (.qml)", inicio)
        if not base_folder:
            return ""
        self.txt_carpeta_respaldos.setText(base_folder)
        self._registrar_ruta(base_folder, en_proyecto=True)
        return base_folder

    def setup_log_panel(self):
        log_widget = QWidget()
        lay_log = QVBoxLayout()
        lay_log.setContentsMargins(5, 2, 5, 5)
        lay_log.setSpacing(2)

        lay_header = QHBoxLayout()
        lay_header.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel("📋 <b>Registro:</b> <i>(Arrastra el borde superior para cambiar el tamaño)</i>")
        lbl.setStyleSheet("font-size: 11px; color: #444;")
        lay_header.addWidget(lbl)
        lay_header.addStretch()

        self.btn_copy_log = QPushButton("📋 Copiar")
        self.btn_copy_log.setFixedSize(70, 22)
        self.btn_copy_log.setStyleSheet("font-size: 10px; background-color: #E0E0E0; border: 1px solid #CCC; border-radius: 3px;")
        self.btn_copy_log.setToolTip("Copiar todo el texto del registro al portapapeles.")
        self.btn_copy_log.clicked.connect(self.copiar_log)
        lay_header.addWidget(self.btn_copy_log)

        self.btn_clear_log = QPushButton("🗑️ Limpiar")
        self.btn_clear_log.setFixedSize(70, 22)
        self.btn_clear_log.setStyleSheet("font-size: 10px; background-color: #E0E0E0; border: 1px solid #CCC; border-radius: 3px;")
        self.btn_clear_log.setToolTip("Borrar todo el historial de la consola.")
        self.btn_clear_log.clicked.connect(self.limpiar_log)
        lay_header.addWidget(self.btn_clear_log)
        lay_log.addLayout(lay_header)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMinimumHeight(30)
        self.txt_log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.txt_log.setStyleSheet(
            "background-color: #FAFAFA; font-family: Consolas, monospace; "
            "font-size: 10px; border: 1px solid #DDD; border-radius: 4px; padding: 2px;"
        )
        lay_log.addWidget(self.txt_log)
        log_widget.setLayout(lay_log)
        return log_widget

    def log_message(self, msg, level="INFO"):
        color_map = {"INFO": "#333333", "SUCCESS": "#2E7D32", "WARNING": "#E65100", "ERROR": "#C62828"}
        color = color_map.get(level, "#333333")
        msg_escapado = html.escape(str(msg))
        cursor = self.txt_log.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.txt_log.setTextCursor(cursor)
        self.txt_log.insertHtml(f'<span style="color:{color};"><b>[{level}]</b> {msg_escapado}</span><br>')
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

    def copiar_log(self):
        from qgis.PyQt.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.txt_log.toPlainText())
        self.log_message("Registro copiado al portapapeles.", "SUCCESS")

    def limpiar_log(self):
        self.txt_log.clear()
        self.log_message("Consola limpiada. Esperando acciones...", "INFO")

    def showEvent(self, event):
        self.verificar_proyecto_actual(forzar=False)
        self._cargar_ruta_inicial()
        self._refrescar_lista_extra(conservar_seleccion=True)
        super().showEvent(event)

    def _nombre_municipio_carpeta(self):
        carpetas_genericas = {
            'gis', 'qgis', 'proyecto', 'proyectos', 'project', 'projects',
            'cartografia', 'planos', 'datos', 'data', 'src', 'export', 'pdfs_exportacion'
        }
        candidato = ""
        path = QgsProject.instance().absolutePath()
        if path:
            carpeta = os.path.basename(os.path.normpath(path))
            if carpeta and carpeta.lower() not in carpetas_genericas:
                candidato = carpeta

        if not candidato:
            base = QgsProject.instance().baseName()
            if base:
                candidato = base

        if candidato:
            candidato = re.sub(r'_(Completo|WS|UD|v\d+)$', '', candidato, flags=re.IGNORECASE)
            candidato = re.sub(r'^\d+[_\-\s]+', '', candidato)
            candidato = candidato.replace('_', ' ').strip()

        return self._formatear_nombre_municipio(candidato) or "Municipio"

    def _formatear_nombre_municipio(self, texto):
        t = re.sub(r'\s+', ' ', str(texto or '')).strip()
        if not t:
            return ""
        m = re.match(r"^(?P<base>.+?),\s*(?P<art>el|la|els|les|los|las|l'|l’)$", t, flags=re.IGNORECASE)
        if m:
            base = m.group('base').strip()
            art = m.group('art').strip()
            if art.lower() in ("l'", "l’"):
                t = f"L'{base}"
            else:
                t = f"{art.capitalize()} {base}"
        return t

    def _obtener_municipio_archivo(self):
        bruto = self.txt_municipio.text().strip() if hasattr(self, 'txt_municipio') else ""
        formateado = self._formatear_nombre_municipio(bruto)
        if not formateado:
            return "Municipio"
        limpio = formateado.replace(' ', '_')
        limpio = re.sub(r'[\\/:*?"<>|,]', '_', limpio)
        limpio = re.sub(r'_+', '_', limpio).strip('_')
        return limpio or "Municipio"

    def verificar_proyecto_actual(self, forzar=False):
        mun_detectado = self._nombre_municipio_carpeta()
        campos_muni = ('NOM_MUN', 'MUNICIPI', 'MUNICIPIO', 'NOM_MUNICIPI')

        for prefijo in ("111_Trams_Potable", "211_Trams_Sanejament"):
            lyr = self.get_layer_by_prefix(prefijo)
            if not lyr:
                continue
            fields = lyr.fields()
            idx = -1
            for campo in campos_muni:
                idx = fields.lookupField(campo)
                if idx != -1:
                    break
            if idx == -1:
                continue

            req = QgsFeatureRequest()
            req.setFlags(QgsFeatureRequest.NoGeometry)
            req.setSubsetOfAttributes([idx])
            req.setLimit(50)
            encontrado = None
            for feat in lyr.getFeatures(req):
                val = feat.attributes()[idx]
                if val is not None and str(val).strip() and str(val).strip().upper() != 'NULL':
                    encontrado = self._formatear_nombre_municipio(str(val))
                    break
            if encontrado:
                mun_detectado = encontrado
                break

        if hasattr(self, 'txt_municipio'):
            actual = self.txt_municipio.text().strip()
            if forzar or not actual or actual == "Municipio":
                self.txt_municipio.setText(mun_detectado)
        self._auto_seleccionar_municipio()
        self.validar_campos()

    def _normalizar_nombre(self, texto):
        t = str(texto).lower().strip()
        t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
        t = t.replace('ç', 'c')
        t = re.sub(r'[^a-z0-9]', '', t)
        return t

    def _auto_seleccionar_municipio(self):
        if not hasattr(self, 'txt_municipio') or not hasattr(self, 'cmb_municipio'):
            return
        texto_muni = self._formatear_nombre_municipio(self.txt_municipio.text())
        if not texto_muni:
            self.cmb_municipio.setCurrentIndex(0)
            return

        norm_muni = self._normalizar_nombre(texto_muni)
        if not norm_muni:
            self.cmb_municipio.setCurrentIndex(0)
            return

        for i in range(1, self.cmb_municipio.count()):
            norm_item = self._normalizar_nombre(self.cmb_municipio.itemText(i))
            if norm_muni == norm_item:
                self.cmb_municipio.setCurrentIndex(i)
                self.chk_municipio.setChecked(True)
                return

        if len(norm_muni) >= 4:
            for i in range(1, self.cmb_municipio.count()):
                norm_item = self._normalizar_nombre(self.cmb_municipio.itemText(i))
                if norm_muni in norm_item or (len(norm_item) >= 4 and norm_item in norm_muni):
                    self.cmb_municipio.setCurrentIndex(i)
                    self.chk_municipio.setChecked(True)
                    return

        self.cmb_municipio.setCurrentIndex(0)

    def get_output_dir(self, subfolder=None):
        project_path = QgsProject.instance().absolutePath()
        if not project_path:
            return None
        base = os.path.join(project_path, 'PDFs_Exportacion')
        if subfolder:
            base = os.path.join(base, subfolder)
        os.makedirs(base, exist_ok=True)
        return base

    def get_layer_by_prefix(self, prefix):
        lyrs = QgsProject.instance().mapLayersByName(prefix)
        if lyrs:
            return lyrs[0]
        if '_' not in prefix:
            return None
        prefix_code = prefix.split('_')[0] + "_"
        candidatos = sorted(
            (l for l in QgsProject.instance().mapLayers().values() if l.name().startswith(prefix_code)),
            key=lambda l: l.name()
        )
        if len(candidatos) > 1:
            self.log_message(
                f"Múltiples capas con prefijo '{prefix_code}': {[c.name() for c in candidatos]}. Se usa '{candidatos[0].name()}'.",
                "WARNING"
            )
        return candidatos[0] if candidatos else None

    def _extent_en_crs_canvas(self, capa, crs_canvas):
        try:
            ext = capa.extent()
            if not ext or ext.isEmpty():
                return None
            if capa.crs() == crs_canvas:
                return QgsRectangle(ext)
            xform = QgsCoordinateTransform(capa.crs(), crs_canvas, QgsProject.instance())
            return xform.transformBoundingBox(ext)
        except Exception as exc:
            self.log_message(f"No se pudo transformar extent de {capa.name()}: {exc}", "WARNING")
            try:
                return QgsRectangle(capa.extent()) if capa.extent() else None
            except Exception:
                return None

    def setup_tab_estatus(self):
        outer_layout = QVBoxLayout(self.tab_estatus)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        lay_datos = QVBoxLayout()
        lay_datos.addWidget(QLabel("Nombre del Municipio:"))
        self.txt_municipio = QLineEdit()
        self.txt_municipio.setToolTip("Escribe el nombre del municipio. Se usará para nombrar las carpetas y los archivos (los espacios se convertirán en guiones bajos).")
        self.txt_municipio.textChanged.connect(self.validar_campos)
        self.txt_municipio.textChanged.connect(self._auto_seleccionar_municipio)
        lay_datos.addWidget(self.txt_municipio)
        layout.addLayout(lay_datos)

        grupo_inst = QGroupBox("Instrucciones - Paso 1")
        lay_inst = QVBoxLayout()
        lbl_inst = QLabel(
            "<b>Flujo de trabajo:</b><br>"
            "1. Haz clic en <b>Preparar Proyecto</b>.<br>"
            "2. Ve a la pestaña Cuadrícula si necesitas los recortes.<br>"
            "3. Ve a Exportar para generar PNGs y PDF.<br>"
            "4. Vuelve aquí y haz clic en <b>Restaurar</b> al terminar."
        )
        lbl_inst.setWordWrap(True)
        lay_inst.addWidget(lbl_inst)
        grupo_inst.setLayout(lay_inst)
        layout.addWidget(grupo_inst)

        grupo_acciones = QGroupBox("Acciones Principales")
        lay_acciones = QVBoxLayout()
        lay_acciones.setSpacing(10)

        self.btn_preparar = QPushButton("▶ PREPARAR PROYECTO")
        self.btn_preparar.setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 12px; border-radius: 4px; }")
        self.btn_preparar.setToolTip("Aplica los estilos QML, oculta capas innecesarias (MDT, LIDAR, etc.) y enciende solo lo necesario para las capturas.")
        self.btn_preparar.clicked.connect(self.preparar_proyecto_completo)
        lay_acciones.addWidget(self.btn_preparar)

        linea = QFrame()
        linea.setFrameShape(QFrame.HLine)
        linea.setFrameShadow(QFrame.Sunken)
        lay_acciones.addWidget(linea)

        self.btn_restaurar = QPushButton("↺ RESTAURAR PROYECTO")
        self.btn_restaurar.setStyleSheet("QPushButton { background-color: #D32F2F; color: white; font-weight: bold; padding: 12px; border-radius: 4px; }")
        self.btn_restaurar.setToolTip("Revierte todos los cambios (estilos, capas ocultas, filtros) a como estaban antes de preparar el proyecto.")
        self.btn_restaurar.clicked.connect(self.restaurar_proyecto_completo)
        lay_acciones.addWidget(self.btn_restaurar)

        grupo_acciones.setLayout(lay_acciones)
        layout.addWidget(grupo_acciones)

        # --- Botón de acordeón para Capas Extra ---
        self.btn_toggle_extra = QPushButton("▶ Mostrar Capas Extra (Opcional)")
        self.btn_toggle_extra.setStyleSheet(
            "QPushButton { text-align: left; font-weight: bold; background-color: #F0F0F0; border: 1px solid #CCC; padding: 6px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #E0E0E0; }"
        )
        self.btn_toggle_extra.clicked.connect(self._toggle_capas_extra)
        layout.addWidget(self.btn_toggle_extra)

        # --- Contenedor desplegable (oculto por defecto) ---
        self.widget_capas_extra = QWidget()
        lay_extra = QVBoxLayout(self.widget_capas_extra)
        lay_extra.setContentsMargins(10, 5, 10, 5)

        lbl_extra = QLabel("Marca las capas que quieres que salgan siempre en los planos y que el plugin no oculte.")
        lbl_extra.setWordWrap(True)
        lbl_extra.setStyleSheet("color: #666; font-size: 11px;")
        lay_extra.addWidget(lbl_extra)

        self.lista_capas_extra = QListWidget()
        self.lista_capas_extra.setMinimumHeight(80)
        self.lista_capas_extra.setMaximumHeight(120)
        lay_extra.addWidget(self.lista_capas_extra)

        btn_refrescar_extra = QPushButton("🔄 Refrescar lista de capas")
        btn_refrescar_extra.clicked.connect(self._refrescar_lista_extra)
        lay_extra.addWidget(btn_refrescar_extra)

        self.widget_capas_extra.setVisible(False)
        layout.addWidget(self.widget_capas_extra)

        grupo_estilos = QGroupBox("Gestión Avanzada de Estilos (Opcional)")
        lay_estilos = QVBoxLayout()
        lay_estilos.setSpacing(8)

        lbl_estilos = QLabel("<i>Estas acciones son adicionales y no forman parte del flujo normal.</i>")
        lbl_estilos.setWordWrap(True)
        lbl_estilos.setStyleSheet("color: #666; font-size: 11px;")
        lay_estilos.addWidget(lbl_estilos)

        lbl_carpeta = QLabel("Carpeta donde se guardan las copias de estilos:")
        lbl_carpeta.setStyleSheet("font-weight: bold; margin-top: 6px;")
        lay_estilos.addWidget(lbl_carpeta)

        row_carpeta = QHBoxLayout()
        row_carpeta.setSpacing(4)
        self.txt_carpeta_respaldos = QLineEdit()
        self.txt_carpeta_respaldos.setMinimumWidth(50)
        self.txt_carpeta_respaldos.setPlaceholderText("Sin carpeta configurada. Pulsa 📁 para elegir una.")
        self.txt_carpeta_respaldos.setToolTip(
            "Carpeta donde se guardan los archivos .qml con los colores y símbolos de las capas.\n\n"
            "• Se recuerda automáticamente para este proyecto.\n"
            "• Si abres otro proyecto que no tenga carpeta guardada, se usará la última que hayas elegido.\n"
            "• Puedes cambiarla cuando quieras."
        )
        self.txt_carpeta_respaldos.textChanged.connect(self._on_texto_carpeta_changed)
        row_carpeta.addWidget(self.txt_carpeta_respaldos, 1)

        self.btn_examinar_respaldos = QPushButton("📁")
        self.btn_examinar_respaldos.setToolTip("Examinar carpetas para elegir la carpeta de respaldos.")
        self.btn_examinar_respaldos.setFixedWidth(32)
        self.btn_examinar_respaldos.setMinimumHeight(26)
        self.btn_examinar_respaldos.clicked.connect(self._examinar_carpeta)
        row_carpeta.addWidget(self.btn_examinar_respaldos)
        lay_estilos.addLayout(row_carpeta)

        row_historial = QHBoxLayout()
        row_historial.setSpacing(4)
        self.cmb_historial_respaldos = QComboBox()
        self.cmb_historial_respaldos.setMinimumWidth(50)
        self.cmb_historial_respaldos.setToolTip("Carpetas usadas recientemente. Elige una para volver a usarla sin tener que buscarla de nuevo.")
        self.cmb_historial_respaldos.currentIndexChanged.connect(self._al_elegir_historial)
        row_historial.addWidget(self.cmb_historial_respaldos, 1)

        self.btn_fijar_ruta = QPushButton("📌")
        self.btn_fijar_ruta.setToolTip(
            "Fijar carpeta al proyecto.\n\n"
            "Guarda la carpeta actual dentro del archivo del proyecto (.qgz).\n\n"
            "Normalmente no hace falta: el plugin ya la guarda sola cuando la eliges. Este botón sirve si quieres asegurarte de que queda guardada ahora mismo."
        )
        self.btn_fijar_ruta.setFixedWidth(32)
        self.btn_fijar_ruta.setMinimumHeight(26)
        self.btn_fijar_ruta.clicked.connect(self._fijar_ruta_al_proyecto)
        row_historial.addWidget(self.btn_fijar_ruta)
        lay_estilos.addLayout(row_historial)

        lbl_nota = QLabel("💡 <i>La carpeta se recuerda sola: no tienes que volver a elegirla cada vez que abras el mismo proyecto.</i>")
        lbl_nota.setWordWrap(True)
        lbl_nota.setStyleSheet("color: #555; font-size: 10px; margin-top: 2px; padding-bottom: 8px;")
        lay_estilos.addWidget(lbl_nota)
        lay_estilos.addSpacing(4)

        try:
            self._refrescar_combo_historial()
            self._cargar_ruta_inicial()
        except Exception:
            pass

        estilo_btn_sec = (
            "QPushButton { padding: 6px 10px; border: 1px solid #CCC; border-radius: 4px; background-color: #F8F8F8; text-align: left; padding-left: 10px; font-weight: normal; }"
            "QPushButton:hover { background-color: #E8E8E8; }"
            "QPushButton:pressed { background-color: #D8D8D8; }"
        )

        self.btn_save_qml = QPushButton("💾 Guardar Copia de Estilos (.qml)")
        self.btn_save_qml.setToolTip("Guarda los estilos de las capas en una carpeta con versionado (v1, v2...).")
        self.btn_save_qml.setStyleSheet(estilo_btn_sec)
        self.btn_save_qml.clicked.connect(self.save_styles_to_folder)
        lay_estilos.addWidget(self.btn_save_qml)

        self.btn_load_qml = QPushButton("📂 Cargar Copia de Estilos (.qml)")
        self.btn_load_qml.setToolTip("Carga estilos desde una carpeta externa y los aplica a las capas del proyecto.")
        self.btn_load_qml.setStyleSheet(estilo_btn_sec)
        self.btn_load_qml.clicked.connect(self.load_styles_from_folder)
        lay_estilos.addWidget(self.btn_load_qml)

        self.btn_restore_original_qml = QPushButton("🔄 Restaurar Estilos Originales (Ruta Fija)")
        self.btn_restore_original_qml.setToolTip("Carga los QML originales (111_v5 y 211_v4) desde las rutas configuradas.")
        self.btn_restore_original_qml.setStyleSheet(estilo_btn_sec)
        self.btn_restore_original_qml.clicked.connect(self.restore_original_styles_from_path)
        lay_estilos.addWidget(self.btn_restore_original_qml)

        self.btn_preparar_notas = QPushButton("🗂️ Preparar Archivo Base (Notas)")
        self.btn_preparar_notas.setToolTip("Crea la capa 'Notas' y los grupos 'FieldPreparer' > 'Revisados' al inicio del proyecto.")
        self.btn_preparar_notas.setStyleSheet(estilo_btn_sec)
        self.btn_preparar_notas.clicked.connect(self.preparar_archivo_notas)
        lay_estilos.addWidget(self.btn_preparar_notas)

        grupo_estilos.setLayout(lay_estilos)
        layout.addWidget(grupo_estilos)

        layout.addStretch()
        scroll.setWidget(content_widget)
        outer_layout.addWidget(scroll)

    def _toggle_modulos_exportacion(self):
        visible = self.widget_modulos_exportacion.isVisible()
        self.widget_modulos_exportacion.setVisible(not visible)
        if not visible:
            self.btn_toggle_modulos.setText("▼ Módulos de Exportación (Selección)")
        else:
            self.btn_toggle_modulos.setText("▶ Módulos de Exportación (Selección)")

    def _toggle_capas_extra(self):
        visible = self.widget_capas_extra.isVisible()
        self.widget_capas_extra.setVisible(not visible)
        if not visible:
            self.btn_toggle_extra.setText("▼ Ocultar Capas Extra")
        else:
            self.btn_toggle_extra.setText("▶ Mostrar Capas Extra (Opcional)")

    def _refrescar_lista_extra(self, conservar_seleccion=True):
        if not hasattr(self, 'lista_capas_extra'):
            return
        ids_previos = set(self._obtener_capas_extra_ids()) if conservar_seleccion else set()
        self.lista_capas_extra.clear()
        for lyr in QgsProject.instance().mapLayers().values():
            if lyr.type() == QgsMapLayer.VectorLayer:
                item = QListWidgetItem(lyr.name())
                item.setData(Qt.UserRole, lyr.id())
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if lyr.id() in ids_previos else Qt.Unchecked)
                self.lista_capas_extra.addItem(item)

    def _obtener_capas_extra_ids(self):
        ids = []
        for i in range(self.lista_capas_extra.count()):
            item = self.lista_capas_extra.item(i)
            if item.checkState() == Qt.Checked:
                ids.append(item.data(Qt.UserRole))
        return ids

    def _sin_acentos(self, txt):
        t = unicodedata.normalize('NFKD', str(txt))
        return ''.join(c for c in t if not unicodedata.combining(c))

    def preparar_archivo_notas(self):
        root = QgsProject.instance().layerTreeRoot()
        existe_capa_nota = False
        for child in root.children():
            if isinstance(child, QgsLayerTreeLayer):
                nombre = child.name().lower()
                if nombre == "notas" or nombre.startswith("nota"):
                    existe_capa_nota = True
                    self.log_message(f"Capa similar encontrada: '{child.name()}'. No se creará una nueva.", "INFO")
                    break

        if root.findGroup('FieldPreparer'):
            QMessageBox.warning(self, "Ya existe", "El grupo 'FieldPreparer' ya está en el proyecto.")
            return

        grupo_principal = QgsLayerTreeGroup('FieldPreparer')
        subgrupo_revisados = QgsLayerTreeGroup('Revisados')

        if not existe_capa_nota:
            self.log_message("No se encontró capa existente. Creando nueva capa 'Notas'...", "INFO")
            for lyr in QgsProject.instance().mapLayersByName("Notas"):
                QgsProject.instance().removeMapLayer(lyr.id())

            crs = self.iface.mapCanvas().mapSettings().destinationCrs().authid()
            capa_notas = QgsVectorLayer(f"Polygon?crs={crs}", "Notas", "memory")
            pr = capa_notas.dataProvider()
            pr.addAttributes([QgsField("id", TYPE_INT), QgsField("Notas", TYPE_QSTRING)])
            capa_notas.updateFields()

            doc = QDomDocument()
            if self._qdom_set_content(doc, QML_NOTAS):
                ok_st, err_st = self._aplicar_dom_style(capa_notas, doc)
                if not ok_st and err_st:
                    self.log_message(f"Aviso aplicando estilo QML_NOTAS: {err_st}", "WARNING")
            else:
                self.log_message("QML_NOTAS inválido, capa creada sin estilo.", "WARNING")

            QgsProject.instance().addMapLayer(capa_notas, False)
            subgrupo_revisados.addChildNode(QgsLayerTreeLayer(capa_notas))
        else:
            self.log_message("Se mantiene la capa existente donde está. Los grupos se crearán vacíos.", "INFO")

        grupo_principal.addChildNode(subgrupo_revisados)
        root.insertChildNode(0, grupo_principal)

        self.iface.mapCanvas().refreshAllLayers()
        QMessageBox.information(self, "Éxito", "Estructura 'FieldPreparer/Revisados' preparada correctamente.")

    def preparar_proyecto_completo(self):
        backup_existe = any(v is not None for v in self.estilos_originales.values()) or len(self._visibilidad_backup) > 0
        actualizar_backup = True

        if backup_existe:
            msg = QMessageBox(self)
            msg.setWindowTitle("⚠️ Ya existe una copia de seguridad")
            msg.setIcon(QMessageBox.Warning)
            msg.setText(
                "Ya hay una copia de seguridad guardada en memoria de una preparación anterior.\n\n"
                "¿Seguro que quieres SOBRESCRIBIRLA con el estado actual del proyecto?"
            )
            msg.setInformativeText(
                "Si eliges «Sobrescribir»:\n"
                "  • El respaldo actual se perderá para siempre.\n"
                "  • El estado ACTUAL del proyecto pasa a ser el nuevo respaldo.\n"
                "  • Si luego pulsas «Restaurar», volverás al estado de AHORA, "
                "no al de la primera preparación.\n\n"
                "💡 Antes de continuar, si has hecho cambios en los estilos (QML) que quieras "
                "conservar, ve a «Guardar Copia de Estilos (.qml)» y guárdalos primero.\n\n"
                "Si eliges «Mantener Copia Original»:\n"
                "  • Se conserva el respaldo de la PRIMERA preparación.\n"
                "  • «Restaurar» seguirá devolviéndote a ese estado inicial."
            )
            btn_keep = msg.addButton("Mantener Copia Original", QMessageBox.YesRole)
            btn_update = msg.addButton("Sí, sobrescribir respaldo", QMessageBox.DestructiveRole)
            btn_cancel = msg.addButton("Cancelar", QMessageBox.RejectRole)
            msg.setDefaultButton(btn_cancel)
            msg.exec_()

            if msg.clickedButton() == btn_cancel:
                self.log_message("Preparación cancelada por el usuario (no se ha tocado el respaldo).", "WARNING")
                return
            elif msg.clickedButton() == btn_update:
                actualizar_backup = True
                self.log_message("Usuario confirma SOBRESCRIBIR el respaldo anterior.", "WARNING")
            elif msg.clickedButton() == btn_keep:
                actualizar_backup = False
                self.log_message("Se mantiene el respaldo original sin tocarlo.", "INFO")

        self.log_message("Iniciando preparación del proyecto...", "INFO")

        old_visibilidad = list(self._visibilidad_backup)
        old_opacidad = list(self._opacidad_backup)
        old_labels = dict(self._point_labels_backup)
        old_filtros = dict(self._filtros_backup)

        self._visibilidad_backup.clear()
        self._opacidad_backup.clear()
        self._point_labels_backup.clear()
        self._filtros_backup.clear()

        if actualizar_backup:
            self.estilos_originales = {
                "111_Trams_Potable": None,
                "211_Trams_Sanejament": None,
                "222_Pous_Registre_Sanejament": None,
                "124_Connexions_Potables": None,
                "225_Connexions_Sanejament": None,
                "RecortesPDF": None,
            }
            if backup_existe:
                self.log_message("Sobrescribiendo copia de seguridad con el estado actual...", "INFO")
            else:
                self.log_message("Creando copia de seguridad nueva (no había ninguna guardada)...", "INFO")
        else:
            self.log_message("Manteniendo copia de seguridad original (no se sobrescribirá).", "INFO")

        restaurar_old_en_excepcion = not actualizar_backup

        try:
            root = QgsProject.instance().layerTreeRoot()

            def save_tree_state(node):
                self._visibilidad_backup.append((node, node.itemVisibilityChecked()))
                if isinstance(node, QgsLayerTreeGroup):
                    for child in node.children():
                        save_tree_state(child)

            save_tree_state(root)

            def set_visible(nodo, visible):
                if nodo.itemVisibilityChecked() != visible:
                    nodo.setItemVisibilityChecked(visible)

            def asegurar_ancestros_visibles(nodo):
                p = nodo.parent()
                while p and p != root:
                    set_visible(p, True)
                    p = p.parent()

            def es_nombre_orto(nombre):
                n = self._sin_acentos(nombre).lower()
                if any(k in n for k in ORTO_KEYWORDS if k != 'ign'):
                    return True
                if 'ortho' in n or re.search(r'\bign\b', n):
                    return True
                return False

            def clasificar(nombre):
                n = self._sin_acentos(nombre).lower()
                if any(k in n for k in MDT_KEYWORDS):
                    return 'aux_mdt'
                if es_nombre_orto(nombre):
                    return 'orto'
                if any(k in n for k in AUX_KEYWORDS):
                    return 'aux_kw'
                return 'normal'

            def get_grupo_raiz(nodo):
                p = nodo.parent()
                while p:
                    if p.name() in ('Potable', 'Saneamiento', 'RecortesPDF'):
                        return p.name()
                    p = p.parent()
                return None

            capas_extra_ids = self._obtener_capas_extra_ids()

            # Detectar todas las capas satelitales / ortofoto reales del proyecto
            nodos_orto = [
                n for n in root.findLayers()
                if n.layer() and get_grupo_raiz(n) is None and es_nombre_orto(n.name())
            ]
            tiene_google_sat = any(n.name().strip().lower() == 'google satellite' for n in nodos_orto)
            hay_varias_orto = len(nodos_orto) > 1
            nombres_orto_apagadas = []

            for nodo in root.findGroups(recursive=True) + root.findLayers():
                nombre = nodo.name()
                es_capa = hasattr(nodo, 'layer') and nodo.layer() is not None

                # Si la capa está en la lista de extras, forzar visible y no tocarla
                if es_capa and nodo.layer().id() in capas_extra_ids:
                    set_visible(nodo, True)
                    asegurar_ancestros_visibles(nodo)
                    self.log_message(f"Capa extra mantenida visible: '{nombre}'", "INFO")
                    continue

                grupo_raiz = get_grupo_raiz(nodo)
                tipo = clasificar(nombre)

                if tipo == 'orto' and grupo_raiz is None:
                    if not es_capa:
                        set_visible(nodo, True)
                        continue

                    es_google_sat = (nombre.strip().lower() == 'google satellite')
                    debe_encender = es_google_sat or (not tiene_google_sat and len(nodos_orto) == 1)

                    if debe_encender:
                        set_visible(nodo, True)
                        asegurar_ancestros_visibles(nodo)
                        try:
                            r = nodo.layer().renderer()
                            if r and abs(r.opacity() - 0.6) > 0.001:
                                self._opacidad_backup.append((nodo.layer(), r.opacity()))
                                r.setOpacity(0.6)
                                nodo.layer().triggerRepaint()
                        except Exception:
                            pass
                        self.log_message(f"Capa satelital/ortofoto activada al 60%: '{nombre}'", "INFO")
                    else:
                        set_visible(nodo, False)
                        if not tiene_google_sat:
                            nombres_orto_apagadas.append(nombre)
                    continue

                    if len(nodos_orto) > 1:
                        set_visible(nodo, False)
                        nombres_orto_apagadas.append(nombre)
                    else:
                        set_visible(nodo, True)
                        asegurar_ancestros_visibles(nodo)
                        try:
                            r = nodo.layer().renderer()
                            if r and abs(r.opacity() - 0.6) > 0.001:
                                self._opacidad_backup.append((nodo.layer(), r.opacity()))
                                r.setOpacity(0.6)
                                nodo.layer().triggerRepaint()
                        except Exception:
                            pass
                        self.log_message(f"Capa satelital/ortofoto activada al 60%: '{nombre}'", "INFO")
                    continue

                    if len(nodos_orto) > 1:
                        set_visible(nodo, False)
                        nombres_orto_apagadas.append(nombre)
                    else:
                        set_visible(nodo, True)
                        asegurar_ancestros_visibles(nodo)
                        try:
                            r = nodo.layer().renderer()
                            if r and abs(r.opacity() - 0.6) > 0.001:
                                self._opacidad_backup.append((nodo.layer(), r.opacity()))
                                r.setOpacity(0.6)
                                nodo.layer().triggerRepaint()
                        except Exception:
                            pass
                        self.log_message(f"Capa satelital/ortofoto activada al 60%: '{nombre}'", "INFO")
                    continue

                if nombre in ('RecortesPDF', 'Potable', 'Saneamiento'):
                    set_visible(nodo, True)
                    asegurar_ancestros_visibles(nodo)
                    continue

                if grupo_raiz:
                    should_be_on = True
                    if tipo in ('aux_mdt', 'aux_kw'):
                        should_be_on = False
                    elif grupo_raiz == 'Potable':
                        if nombre.startswith(LAYERS_HIDE_POTABLE) or nombre.strip().upper() == 'FONT':
                            should_be_on = False
                    elif grupo_raiz == 'Saneamiento':
                        if nombre.startswith(LAYERS_HIDE_SANEA):
                            should_be_on = False

                    set_visible(nodo, should_be_on)

                    m_pref = re.match(r'^(\d{3})', nombre)
                    prefix = m_pref.group(1) if m_pref else nombre.split('_')[0]
                    if prefix in POINT_LABEL_HIDE_CODES and es_capa:
                        lyr = nodo.layer()
                        if lyr.type() == QgsMapLayer.VectorLayer and lyr.labelsEnabled():
                            self._point_labels_backup[lyr.id()] = True
                            lyr.setLabelsEnabled(False)
                            lyr.triggerRepaint()
                    continue

                set_visible(nodo, False)

                if tipo in ('aux_mdt', 'aux_kw'):
                    self.log_message(
                        f"Capa ocultada por keyword ({tipo}): '{nombre}'. Si no debía ocultarse, revisa AUX_KEYWORDS/MDT_KEYWORDS.",
                        "WARNING"
                    )

            # Filtro de acometidas en tuberías principales
            for layer_name in ('111_Trams_Potable', '211_Trams_Sanejament'):
                lyr = self.get_layer_by_prefix(layer_name)
                if not lyr or lyr.type() != QgsMapLayer.VectorLayer:
                    continue

                idx_obs = lyr.fields().lookupField('OBSERVACIO')
                if idx_obs == -1:
                    continue
                campo_obs_real = lyr.fields().field(idx_obs).name()

                if lyr.id() not in self._filtros_backup:
                    self._filtros_backup[lyr.id()] = lyr.subsetString()

                vals = set()
                try:
                    req = QgsFeatureRequest()
                    req.setFlags(QgsFeatureRequest.NoGeometry)
                    req.setSubsetOfAttributes([idx_obs])
                    for f in lyr.getFeatures(req):
                        val_raw = f.attributes()[idx_obs]
                        if val_raw is not None and str(val_raw).strip():
                            vals.add(str(val_raw).strip())
                except Exception:
                    continue

                ac_vals = sorted({
                    v for v in vals
                    if self._sin_acentos(v).lower() in ACOMETIDA_KEYWORDS
                })
                if ac_vals:
                    lista_escaped = ", ".join("'" + v.replace("'", "''") + "'" for v in ac_vals)
                    lyr.setSubsetString(f'"{campo_obs_real}" IS NULL OR "{campo_obs_real}" NOT IN ({lista_escaped})')
                    self.log_message(f"Filtro de acometidas aplicado a {layer_name}: {ac_vals}", "INFO")

            # --- INYECCIÓN DE LOS 6 ESTILOS DESDE LA CARPETA 'estilos' ---
            qmls_locales = {
                "RecortesPDF": "recortes.qml",
                "111_Trams_Potable": "111_p.qml",
                "211_Trams_Sanejament": "211_s.qml",
                "124_Connexions_Potables": "124_p.qml",
                "222_Pous_Registre_Sanejament": "222_s.qml",
                "225_Connexions_Sanejament": "225_s.qml"
            }

            for capa_nom, archivo in qmls_locales.items():
                ruta_qml = os.path.join(DIR_ESTILOS_LOCAL, archivo)

                if os.path.exists(ruta_qml):
                    try:
                        with open(ruta_qml, "r", encoding="utf-8") as f:
                            contenido_qml = f.read()
                        self.aplicar_estilo_a_capa(capa_nom, contenido_qml)
                    except Exception as e:
                        self.log_message(f"Error al leer {archivo}: {e}. La capa {capa_nom} no tendrá estilo.", "ERROR")
                else:
                    self.log_message(f"Archivo '{archivo}' no encontrado en 'estilos'. La capa {capa_nom} no tendrá estilo.", "WARNING")

            if not actualizar_backup:
                self._visibilidad_backup = old_visibilidad
                self._opacidad_backup = old_opacidad
                self._point_labels_backup = old_labels
                self._filtros_backup = old_filtros
                self.log_message("Copia de seguridad original conservada.", "SUCCESS")

            aviso_orto = ""
            if nombres_orto_apagadas:
                lista_orto_txt = ", ".join(nombres_orto_apagadas)
                self.log_message(
                    f"Se detectaron {len(nombres_orto_apagadas)} capas satelitales/ortofoto ({lista_orto_txt}). "
                    "Se han apagado todas; marca manualmente en el panel de capas la que desees usar.",
                    "WARNING"
                )
                aviso_orto = (
                    "\n\n⚠️ AVISO DE CAPAS SATELITALES:\n"
                    f"Se detectaron {len(nombres_orto_apagadas)} capas satelitales/ortofoto ({lista_orto_txt}) "
                    "y se han apagado todas.\n"
                    "Marca manualmente en el panel de capas de QGIS la satelital que quieras usar antes de exportar."
                )

            self.log_message("Proyecto preparado con éxito. Estilos y capas configurados.", "SUCCESS")
            QMessageBox.information(
                self, "Preparación Completada",
                "Lógica aplicada correctamente.\n"
                "Potable: ON excepto 121, 124 y FONT.\n"
                "Saneamiento: ON excepto 221, 223, 225 y 231.\n"
                "Pozos (222): estilo discreto aplicado."
                + aviso_orto
            )
        except Exception as e:
            if restaurar_old_en_excepcion:
                self._visibilidad_backup = old_visibilidad
                self._opacidad_backup = old_opacidad
                self._point_labels_backup = old_labels
                self._filtros_backup = old_filtros
                self.log_message("ERROR durante la preparación. Copia de seguridad original restaurada.", "WARNING")
            self.log_message(f"Error al preparar proyecto: {str(e)}", "ERROR")
            QMessageBox.critical(self, "Error", f"Ocurrió un error al preparar:\n{str(e)}")

    def restaurar_proyecto_completo(self):
        self.log_message("Iniciando restauración del proyecto...", "INFO")
        try:
            for nodo, estado in self._visibilidad_backup:
                try:
                    nodo.setItemVisibilityChecked(estado)
                except Exception:
                    pass
            self._visibilidad_backup.clear()

            for lyr, op in self._opacidad_backup:
                try:
                    r = lyr.renderer()
                    r.setOpacity(op)
                    lyr.triggerRepaint()
                except Exception:
                    pass
            self._opacidad_backup.clear()

            for lyr_id, was_enabled in self._point_labels_backup.items():
                lyr = QgsProject.instance().mapLayer(lyr_id)
                if lyr:
                    lyr.setLabelsEnabled(was_enabled)
                    lyr.triggerRepaint()
            self._point_labels_backup.clear()

            for lyr_id, filtro in self._filtros_backup.items():
                lyr = QgsProject.instance().mapLayer(lyr_id)
                if lyr:
                    lyr.setSubsetString(filtro)
            self._filtros_backup.clear()

            for nombre_capa, estilo_xml in self.estilos_originales.items():
                if not estilo_xml:
                    continue
                lyr = (
                    self.get_layer_by_prefix(nombre_capa)
                    or (QgsProject.instance().mapLayersByName(nombre_capa)[0] if QgsProject.instance().mapLayersByName(nombre_capa) else None)
                )
                if lyr:
                    try:
                        doc = QDomDocument()
                        if self._qdom_set_content(doc, estilo_xml):
                            ok_st, err_st = self._aplicar_dom_style(lyr, doc)
                            if not ok_st and err_st:
                                self.log_message(f"Aviso restaurando estilo de {nombre_capa}: {err_st}", "WARNING")
                            lyr.triggerRepaint()
                            self.iface.layerTreeView().refreshLayerSymbology(lyr.id())
                    except Exception as exc_st:
                        self.log_message(f"No se pudo restaurar estilo de {nombre_capa}: {exc_st}", "WARNING")
                    self.estilos_originales[nombre_capa] = None

            self.log_message("Proyecto restaurado a su estado original.", "SUCCESS")
            QMessageBox.information(self, "Restauración", "Proyecto devuelto a su estado original.")
        except Exception as e:
            self.log_message(f"Error al restaurar proyecto: {str(e)}", "ERROR")

    def aplicar_estilo_a_capa(self, nombre_capa, qml_str):
        capa = (
            self.get_layer_by_prefix(nombre_capa)
            or (QgsProject.instance().mapLayersByName(nombre_capa)[0] if QgsProject.instance().mapLayersByName(nombre_capa) else None)
        )
        if not capa:
            self.log_message(f"Capa no encontrada para aplicar estilo: {nombre_capa}", "WARNING")
            return False

        if self.estilos_originales.get(nombre_capa) is None:
            try:
                doc_stash = QDomDocument()
                capa.exportNamedStyle(doc_stash)
                self.estilos_originales[nombre_capa] = doc_stash.toString()
            except Exception:
                self.estilos_originales[nombre_capa] = ""

        doc = QDomDocument()
        if not self._qdom_set_content(doc, qml_str):
            self.log_message(f"QML inválido para capa: {nombre_capa}", "ERROR")
            QMessageBox.warning(self, "QML inválido", f"No se pudo aplicar el estilo a {nombre_capa}.")
            return False

        ok_style, msg_error = self._aplicar_dom_style(capa, doc)
        capa.triggerRepaint()
        self.iface.layerTreeView().refreshLayerSymbology(capa.id())

        try:
            labels_on = capa.labelsEnabled() if capa.type() == QgsMapLayer.VectorLayer else False
            renderer_tipo = capa.renderer().type() if capa.renderer() else "None"
        except Exception:
            labels_on, renderer_tipo = "?", "?"

        msg_error_str = str(msg_error).strip().lower()
        es_error_real = (not ok_style) or (msg_error and msg_error_str not in ('', 'true', 'false', 'none'))

        if es_error_real:
            self.log_message(
                f"AVISO estilo '{nombre_capa}': readStyle devolvió '{msg_error}' "
                f"(ok={ok_style}, labels={labels_on}, renderer={renderer_tipo})",
                "WARNING",
            )
            return False
        else:
            self.log_message(
                f"Estilo aplicado a capa: {nombre_capa}  "
                f"(labels={labels_on}, renderer={renderer_tipo})",
                "INFO",
            )
            return True

    def save_styles_to_folder(self):
        folder_names = {"Potable": "01_Potable", "Saneamiento": "02_Saneamiento"}
        root = QgsProject.instance().layerTreeRoot()

        base_folder = self._carpeta_respaldos_actual()
        if not base_folder:
            self.log_message("Guardado de estilos cancelado.", "WARNING")
            return

        self.log_message(f"Carpeta raíz: {base_folder}", "INFO")

        def get_all_layers_in_group(tree_group):
            layers = []
            for child in tree_group.children():
                if isinstance(child, QgsLayerTreeLayer):
                    layers.append(child)
                elif isinstance(child, QgsLayerTreeGroup):
                    layers.extend(get_all_layers_in_group(child))
            return layers

        datos_por_pestaña = {}
        for group_name, folder_name in folder_names.items():
            group = root.findGroup(group_name)
            items = []
            if group:
                for tree_layer in get_all_layers_in_group(group):
                    layer = tree_layer.layer()
                    if layer and layer.isValid():
                        m = re.match(r"^(\d+)", layer.name())
                        if m:
                            items.append((layer.name(), (group_name, layer)))
            datos_por_pestaña[group_name] = items

        dlg = StyleSelectionDialog("Seleccionar capas para GUARDAR", datos_por_pestaña, self)
        if dlg.exec_() != QDialog.Accepted:
            return

        capas_a_guardar = dlg.get_selected()
        if not capas_a_guardar:
            QMessageBox.information(self, "Sin selección", "No has marcado ninguna capa.")
            return

        self.log_message(f"=== GUARDANDO {len(capas_a_guardar)} capas seleccionadas ===", "INFO")
        guardadas = []

        for group_name, layer in capas_a_guardar:
            folder_name = folder_names.get(
                group_name,
                folder_names[self.GRUPO_POTABLE] if layer.name().startswith(('1',)) else folder_names[self.GRUPO_SANEA]
            )
            group_folder = os.path.join(base_folder, folder_name)
            os.makedirs(group_folder, exist_ok=True)

            m = re.match(r"^(\d+)", layer.name())
            prefix = m.group(1).zfill(3)

            existing_files = [
                f for f in os.listdir(group_folder)
                if re.match(rf"^{re.escape(prefix)}_v\d+\.qml$", f, re.IGNORECASE)
            ]

            if existing_files:
                existing_files.sort(key=lambda x: int(re.search(r"_v(\d+)\.qml$", x).group(1)))
                ultimo_num = int(re.search(r"_v(\d+)\.qml$", existing_files[-1]).group(1))
                ver = f"v{ultimo_num + 1}"
            else:
                ver = "v1"

            qml_path = os.path.join(group_folder, f"{prefix}_{ver}.qml")

            try:
                success, err_msg = layer.saveNamedStyle(qml_path)
                if success:
                    self.log_message(f"  [OK {ver}] {layer.name()}", "SUCCESS")
                    guardadas.append((layer, qml_path, existing_files))
                else:
                    self.log_message(f"  [FAIL] {layer.name()}: {err_msg}", "ERROR")
            except Exception as e:
                self.log_message(f"  [FAIL] {layer.name()}: {str(e)}", "ERROR")

        self.log_message(f"Guardadas {len(guardadas)} capas.", "SUCCESS")

        con_anteriores = [g for g in guardadas if g[2]]
        if con_anteriores:
            resp = QMessageBox.question(
                self, "¿Borrar versiones anteriores?",
                f"Se han guardado {len(guardadas)} capas.\nDe ellas, {len(con_anteriores)} ya tenían versiones anteriores.\n\n¿Quieres BORRAR todas las versiones ANTERIORES de esas capas?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if resp == QMessageBox.Yes:
                borradas = 0
                for layer, qml_path, old_files in con_anteriores:
                    for old_file in old_files:
                        old_path = os.path.join(os.path.dirname(qml_path), old_file)
                        try:
                            os.remove(old_path)
                            borradas += 1
                        except Exception:
                            pass
                self.log_message(f"Borradas {borradas} versiones anteriores.", "SUCCESS")

    def load_styles_from_folder(self):
        folder_names = {"Potable": "01_Potable", "Saneamiento": "02_Saneamiento"}
        base_folder = self._carpeta_respaldos_actual()
        if not base_folder:
            self.log_message("Carga de estilos cancelada.", "WARNING")
            return

        pattern = re.compile(r"^(\d{3})_v(\d+)\.qml$", re.IGNORECASE)
        index = {}
        for folder_name in folder_names.values():
            folder = os.path.join(base_folder, folder_name)
            if not os.path.isdir(folder):
                continue
            for fname in os.listdir(folder):
                m = pattern.match(fname)
                if not m:
                    continue
                prefix = m.group(1)
                ver = int(m.group(2))
                path = os.path.join(folder, fname)
                index.setdefault(prefix, []).append((ver, path))

        if not index:
            QMessageBox.warning(self, "Sin .qml", f"No se encontró ningún archivo en:\n{base_folder}")
            return

        datos_por_pestaña = {}
        for group_name, _ in folder_names.items():
            group = QgsProject.instance().layerTreeRoot().findGroup(group_name)
            items = []
            if group:
                for tree_layer in group.findLayers():
                    layer = tree_layer.layer()
                    if layer and layer.isValid():
                        m = re.match(r"^(\d+)", layer.name())
                        if m:
                            prefix = m.group(1)[:3].zfill(3)
                            if prefix in index:
                                index[prefix].sort()
                                ultima_ver, _ = index[prefix][-1]
                                texto = f"{layer.name()} (Aplicar v{ultima_ver})"
                                items.append((texto, layer))
            datos_por_pestaña[group_name] = items

        dlg = StyleSelectionDialog("Seleccionar capas para CARGAR", datos_por_pestaña, self)
        if dlg.exec_() != QDialog.Accepted:
            return

        capas_a_cargar = dlg.get_selected()
        if not capas_a_cargar:
            return

        self.log_message(f"=== CARGANDO {len(capas_a_cargar)} capas seleccionadas ===", "INFO")
        for layer in capas_a_cargar:
            m = re.match(r"^(\d+)", layer.name())
            prefix = m.group(1)[:3].zfill(3)
            ver, path = index[prefix][-1]

            try:
                _, ok_style = layer.loadNamedStyle(path)
                if ok_style:
                    layer.triggerRepaint()
                    self.log_message(f"[OK] {layer.name()}  ←  {os.path.basename(path)}", "SUCCESS")
                else:
                    self.log_message(f"[FAIL] {layer.name()}", "ERROR")
            except Exception as e:
                self.log_message(f"[ERR] {layer.name()}: {e}", "ERROR")

        view = self.iface.layerTreeView()
        for lyr in QgsProject.instance().mapLayers().values():
            try:
                view.refreshLayerSymbology(lyr.id())
            except Exception:
                pass

    def restore_original_styles_from_path(self):
        self.log_message("=== RESTAURANDO ESTILOS ORIGINALES DESDE RUTA FIJA ===", "INFO")

        qml_111_path = os.path.join(STYLES_WS, QML_111)
        qml_211_path = os.path.join(STYLES_UD, QML_211)

        if not os.path.exists(qml_111_path) or not os.path.exists(qml_211_path):
            self.log_message("Las rutas configuradas no son accesibles en este equipo.", "WARNING")
            msg = QMessageBox(self)
            msg.setWindowTitle("Ruta no encontrada")
            msg.setText(
                "No se han encontrado los QMLs originales en las rutas por defecto:\n"
                f"{STYLES_WS}\n{STYLES_UD}\n\n"
                "¿Quieres seleccionar manualmente la carpeta donde se encuentran?"
            )
            btn_yes = msg.addButton("Seleccionar carpeta", QMessageBox.YesRole)
            btn_no = msg.addButton("Cancelar", QMessageBox.RejectRole)
            msg.exec_()

            if msg.clickedButton() == btn_no:
                return

            base = QFileDialog.getExistingDirectory(self, "Selecciona la carpeta 'Estilos'")
            if not base:
                return

            if os.path.exists(os.path.join(base, 'Potables', QML_111)):
                qml_111_path = os.path.join(base, 'Potables', QML_111)
                qml_211_path = os.path.join(base, 'Saneamiento', QML_211)
            elif os.path.exists(os.path.join(base, QML_111)):
                qml_111_path = os.path.join(base, QML_111)
                qml_211_path = os.path.join(base, QML_211)
            else:
                QMessageBox.warning(self, "Error", "No se encuentran los archivos 111_v5.qml y 211_v4.qml.")
                return

        count = 0
        lyr_111 = self.get_layer_by_prefix("111_Trams_Potable")
        if lyr_111 and os.path.exists(qml_111_path):
            lyr_111.loadNamedStyle(qml_111_path)
            lyr_111.triggerRepaint()
            self.log_message(f"Estilo 111 restaurado desde: {qml_111_path}", "SUCCESS")
            count += 1
        else:
            self.log_message("[!] No se pudo restaurar 111", "ERROR")

        lyr_211 = self.get_layer_by_prefix("211_Trams_Sanejament")
        if lyr_211 and os.path.exists(qml_211_path):
            lyr_211.loadNamedStyle(qml_211_path)
            lyr_211.triggerRepaint()
            self.log_message(f"Estilo 211 restaurado desde: {qml_211_path}", "SUCCESS")
            count += 1
        else:
            self.log_message("[!] No se pudo restaurar 211", "ERROR")

        if count > 0:
            view = self.iface.layerTreeView()
            for lyr in QgsProject.instance().mapLayers().values():
                try:
                    view.refreshLayerSymbology(lyr.id())
                except Exception:
                    pass
            QMessageBox.information(self, "Restauración Original", f"Se han restaurado {count} estilos originales.")

    def setup_tab_generador(self):
        outer_layout = QVBoxLayout(self.tab_generador)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        grupo_inst = QGroupBox("Instrucciones - Paso 2")
        lay_inst = QVBoxLayout()
        texto_inst = (
            "Genera la malla de recortes estándar para los planos de detalle."
            + chr(10)
            + "Si el proyecto ya tiene la capa 'RecortesPDF', puedes omitir esto."
        )
        lay_inst.addWidget(QLabel(texto_inst))
        grupo_inst.setLayout(lay_inst)
        layout.addWidget(grupo_inst)

        grupo_params = QGroupBox("Parámetros de la Malla")
        lay_grid = QGridLayout()
        lay_grid.setSpacing(10)

        lay_grid.addWidget(QLabel("Ancho (m):"), 0, 0)
        self.spin_ancho = QSpinBox()
        self.spin_ancho.setRange(10, 5000)
        self.spin_ancho.setValue(250)
        lay_grid.addWidget(self.spin_ancho, 0, 1)

        lay_grid.addWidget(QLabel("Alto (m):"), 1, 0)
        self.spin_alto = QSpinBox()
        self.spin_alto.setRange(10, 5000)
        self.spin_alto.setValue(150)
        lay_grid.addWidget(self.spin_alto, 1, 1)

        lay_grid.addWidget(QLabel("Solape (m):"), 2, 0)
        self.spin_solape = QSpinBox()
        self.spin_solape.setValue(15)
        lay_grid.addWidget(self.spin_solape, 2, 1)

        lay_grid.addWidget(QLabel("Margen de la captura (%):"), 3, 0)
        self.spin_margen = QSpinBox()
        self.spin_margen.setRange(0, 200)
        self.spin_margen.setValue(80)
        self.spin_margen.setToolTip("Contexto alrededor del recorte. 80% es el valor estándar.")
        lay_grid.addWidget(self.spin_margen, 3, 1)

        lay_grid.addWidget(QLabel("Tamaño del número en el recorte (px):"), 4, 0)
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(10, 100)
        self.spin_font_size.setValue(40)
        self.spin_font_size.setToolTip("Tamaño del número de captura en la capa de recortes.")
        lay_grid.addWidget(self.spin_font_size, 4, 1)

        grupo_params.setLayout(lay_grid)
        layout.addWidget(grupo_params)

        btn_generar = QPushButton("Generar Capa de Recortes")
        btn_generar.setToolTip("Crea y añade al proyecto una nueva capa con la cuadrícula de recortes.")
        btn_generar.setStyleSheet("QPushButton { background-color: #9C27B0; color: white; font-weight: bold; padding: 10px; border-radius: 4px; }")
        btn_generar.clicked.connect(self.generar_cuadricula)
        layout.addWidget(btn_generar)
        layout.addStretch()

        scroll.setWidget(content_widget)
        outer_layout.addWidget(scroll)

    def _guardar_capa_en_disco(self, layer, nombre_archivo=None):
        if not layer:
            return False

        base_dir = self.get_output_dir()
        if not base_dir:
            QMessageBox.warning(
                self, "Proyecto no guardado",
                "Debes guardar el proyecto de QGIS primero para poder guardar la capa en la carpeta de exportación."
            )
            return False

        if nombre_archivo:
            path = os.path.join(base_dir, nombre_archivo)
        else:
            path = os.path.join(base_dir, f"{layer.name()}.gpkg")

        if not path.lower().endswith('.gpkg'):
            path += '.gpkg'

        try:
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.fileEncoding = "UTF-8"
            transform_context = QgsProject.instance().transformContext()
            res = QgsVectorFileWriter.writeAsVectorFormatV3(layer, path, transform_context, options)

            if isinstance(res, tuple):
                err_code = res[0]
                err_msg = res[1] if len(res) > 1 else ""
            else:
                err_code = res
                err_msg = ""

            if err_code == QgsVectorFileWriter.NoError:
                self.log_message(f"Capa guardada automáticamente: {os.path.basename(path)}", "SUCCESS")
                return True
            else:
                self.log_message(f"Error al guardar capa: {err_msg} ({err_code})", "ERROR")
                return False
        except Exception as e:
            self.log_message(f"Error al guardar capa: {e}", "ERROR")
            return False

    def generar_cuadricula(self):
        ancho = self.spin_ancho.value()
        alto = self.spin_alto.value()
        solape = self.spin_solape.value()

        if solape >= ancho or solape >= alto:
            self.log_message(f"Parámetros inválidos: solape={solape} >= ancho={ancho} o alto={alto}", "ERROR")
            QMessageBox.warning(
                self, "Parámetros inválidos",
                "El solape debe ser menor que el ancho y el alto.\n\n"
                f"Solape actual: {solape} m\nAncho: {ancho} m\nAlto: {alto} m"
            )
            return

        crs_canvas = self.iface.mapCanvas().mapSettings().destinationCrs()
        if crs_canvas.isGeographic():
            self.log_message("CRS geográfico detectado. La cuadrícula debe generarse en metros.", "ERROR")
            QMessageBox.warning(
                self, "CRS geográfico",
                "El proyecto está en un CRS geográfico (grados).\nLas dimensiones de la cuadrícula se interpretan como metros, por lo que el resultado será incorrecto.\n\nCambia a un CRS proyectado (p. ej. EPSG:25831) antes de continuar."
            )
            return

        self.log_message(f"Iniciando generación de malla ({ancho}x{alto}m, solape {solape}m)...", "INFO")

        viejas = QgsProject.instance().mapLayersByName(self.NOMBRE_CAPA)
        if viejas:
            msg = QMessageBox(self)
            msg.setWindowTitle("La capa de recortes ya existe")
            msg.setIcon(QMessageBox.Question)
            msg.setText(f"La capa '{self.NOMBRE_CAPA}' ya está cargada en el proyecto.\n\n¿Qué deseas hacer con ella antes de generar la nueva?")
            msg.setInformativeText("Se eliminará del mapa para liberar el archivo en el disco y evitar errores de bloqueo.")

            btn_save = msg.addButton("Guardar copia y Regenerar", QMessageBox.ActionRole)
            btn_delete = msg.addButton("Sobrescribir (Borrar actual)", QMessageBox.DestructiveRole)
            btn_cancel = msg.addButton("Cancelar", QMessageBox.RejectRole)
            msg.exec_()

            if msg.clickedButton() == btn_cancel:
                self.log_message("Generación de malla cancelada.", "WARNING")
                return

            if msg.clickedButton() == btn_save:
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    nombre_backup = f"{self.NOMBRE_CAPA}_backup_{timestamp}.gpkg"
                    self._guardar_capa_en_disco(viejas[0], nombre_backup)
                except Exception as e:
                    self.log_message(f"No se pudo guardar el backup de la capa anterior: {e}", "WARNING")

            for v_lyr in viejas:
                QgsProject.instance().removeMapLayer(v_lyr.id())
            self.log_message(f"Capa antigua '{self.NOMBRE_CAPA}' eliminada del proyecto.", "INFO")
            QgsApplication.processEvents()
            time.sleep(0.3)

        try:
            root = QgsProject.instance().layerTreeRoot()
            crs = crs_canvas.authid()

            capa_tmp = QgsVectorLayer(f"Polygon?crs={crs}", "RecortesPDF_tmp", "memory")
            pr = capa_tmp.dataProvider()
            pr.addAttributes([QgsField("id", TYPE_INT), QgsField("N Captura", TYPE_QSTRING), QgsField("Tipo", TYPE_QSTRING)])
            capa_tmp.updateFields()

            features_a_crear = []
            id_global = 1

            self.lbl_status.setText("Estado: Analizando datos y construyendo índice espacial...")
            QgsApplication.processEvents()

            for nombre_grupo, tipo_attr in [(self.GRUPO_POTABLE, "POTABLE"), (self.GRUPO_SANEA, "SANEA")]:
                grupo = root.findGroup(nombre_grupo)
                if not grupo:
                    continue

                capas_validas = [n.layer() for n in grupo.findLayers() if n.layer() and n.layer().type() == 0]
                if not capas_validas:
                    continue

                ext_total = QgsRectangle()
                ext_total.setMinimal()
                for c in capas_validas:
                    ext_t = self._extent_en_crs_canvas(c, crs_canvas)
                    if ext_t:
                        ext_total.combineExtentWith(ext_t)

                if ext_total.isEmpty():
                    continue

                spatial_index = QgsSpatialIndex()
                geometrias_grupo = []

                for c in capas_validas:
                    req = QgsFeatureRequest()
                    req.setNoAttributes()
                    req.setFilterRect(ext_total)
                    req.setDestinationCrs(crs_canvas, QgsProject.instance().transformContext())
                    for f in c.getFeatures(req):
                        if f.hasGeometry():
                            geom_f = QgsGeometry(f.geometry())
                            if not geom_f.isEmpty():
                                idx_unico = len(geometrias_grupo)
                                geometrias_grupo.append(geom_f)
                                f_idx = QgsFeature(idx_unico)
                                f_idx.setGeometry(geom_f)
                                spatial_index.addFeature(f_idx)

                contador_red = 1
                y_actual = ext_total.yMaximum()
                total_filas = max(1, int((ext_total.height()) / (alto - solape)) + 1)
                fila_actual = 0

                while y_actual > ext_total.yMinimum():
                    x_actual = ext_total.xMinimum()
                    while x_actual < ext_total.xMaximum():
                        rect = QgsRectangle(x_actual, y_actual - alto, x_actual + ancho, y_actual)
                        feat_ids = spatial_index.intersects(rect)

                        if feat_ids:
                            geom = QgsGeometry.fromRect(rect)
                            tiene_datos = False
                            for fid in feat_ids:
                                if geom.intersects(geometrias_grupo[fid]):
                                    tiene_datos = True
                                    break

                            if tiene_datos:
                                feat = QgsFeature()
                                feat.setGeometry(geom)
                                feat.setAttributes([id_global, str(contador_red), tipo_attr])
                                features_a_crear.append(feat)
                                contador_red += 1
                                id_global += 1

                        x_actual += (ancho - solape)

                    y_actual -= (alto - solape)
                    fila_actual += 1

                    if fila_actual % 10 == 0:
                        progreso = min(100, int((fila_actual / total_filas) * 100))
                        self.lbl_status.setText(f"Estado: Generando malla {nombre_grupo} ({progreso}%)...")
                        QgsApplication.processEvents()

            if not features_a_crear:
                self.log_message("No se encontraron datos para generar la cuadrícula.", "WARNING")
                self.lbl_status.setText("Estado: Listo para exportar.")
                return QMessageBox.warning(self, "Error", "No se encontraron datos.")

            self.lbl_status.setText("Estado: Aplicando estilo y guardando archivo...")
            QgsApplication.processEvents()

            pr.addFeatures(features_a_crear)

            font_size = self.spin_font_size.value()
            ruta_recortes = os.path.join(DIR_ESTILOS_LOCAL, "recortes.qml")
            qml_custom = ""

            if os.path.exists(ruta_recortes):
                try:
                    with open(ruta_recortes, "r", encoding="utf-8") as f:
                        contenido = f.read()
                        qml_custom = re.sub(r'fontSize="[\d.]+"', f'fontSize="{font_size}"', contenido, count=1)
                except Exception as e:
                    self.log_message(f"Error al leer recortes.qml: {e}", "ERROR")

            doc = QDomDocument()
            if qml_custom and self._qdom_set_content(doc, qml_custom):
                self._aplicar_dom_style(capa_tmp, doc)

            base_dir = self.get_output_dir()
            if not base_dir:
                QMessageBox.warning(self, "Proyecto no guardado", "Debes guardar el proyecto de QGIS primero.")
                return

            gpkg_path = os.path.join(base_dir, f"{self.NOMBRE_CAPA}.gpkg")

            if os.path.exists(gpkg_path):
                try:
                    os.remove(gpkg_path)
                except Exception as e:
                    self.log_message(f"No se pudo borrar el archivo físico bloqueado: {e}", "ERROR")
                    QMessageBox.warning(self, "Archivo bloqueado", "El archivo está siendo usado por otro programa. Cierra QGIS y vuelve a intentarlo.")
                    return

            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = self.NOMBRE_CAPA
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
            options.fileEncoding = "UTF-8"

            transform_context = QgsProject.instance().transformContext()
            res = QgsVectorFileWriter.writeAsVectorFormatV3(capa_tmp, gpkg_path, transform_context, options)

            if isinstance(res, tuple):
                err_code, err_msg = res[0], res[1] if len(res) > 1 else ""
            else:
                err_code, err_msg = res, ""

            if err_code != QgsVectorFileWriter.NoError:
                self.log_message(f"Error al guardar el archivo GPKG: {err_msg} ({err_code})", "ERROR")
                QMessageBox.critical(self, "Error", f"No se pudo guardar la malla en el disco:\n{err_msg}")
                QgsProject.instance().addMapLayer(capa_tmp)
                return

            uri = f"{gpkg_path}|layername={self.NOMBRE_CAPA}"
            capa_grid = QgsVectorLayer(uri, self.NOMBRE_CAPA, "ogr")

            if capa_grid.isValid():
                if qml_custom and self._qdom_set_content(doc, qml_custom):
                    self._aplicar_dom_style(capa_grid, doc)

                QgsProject.instance().addMapLayer(capa_grid)
                self.log_message(f"Malla generada y guardada: {os.path.basename(gpkg_path)}", "SUCCESS")
                self.lbl_status.setText("Estado: Listo para exportar.")
                QMessageBox.information(self, "Éxito", f"Malla generada con {id_global - 1} capturas.\nGuardada correctamente.")
            else:
                self.log_message("Error al cargar la capa desde el GPKG.", "WARNING")
                QgsProject.instance().addMapLayer(capa_tmp)
                self.lbl_status.setText("Estado: Listo para exportar.")

        except Exception as e:
            self.log_message(f"Error al generar cuadrícula: {str(e)}", "ERROR")
            QMessageBox.critical(self, "Error", f"Ocurrió un error:\n{str(e)}")

    def setup_tab_exportador(self):
        outer_layout = QVBoxLayout(self.tab_exportador)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        grupo_rutas = QGroupBox("Destino de Exportación (Automático)")
        lay_rutas = QVBoxLayout()
        self.lbl_ruta_auto = QLabel("Guardando en:" + chr(10) + "[Debes guardar el proyecto primero]")
        self.lbl_ruta_auto.setStyleSheet("color: #1976D2; font-weight: bold;")
        self.lbl_ruta_auto.setWordWrap(True)
        lay_rutas.addWidget(self.lbl_ruta_auto)
        grupo_rutas.setLayout(lay_rutas)
        layout.addWidget(grupo_rutas)

        # --- Resoluciones independientes ---
        grid_dpi = QGridLayout()
        grid_dpi.setSpacing(5)

        self.spin_dpi_gen = QSpinBox()
        self.spin_dpi_gen.setRange(72, 600)
        self.spin_dpi_gen.setValue(int(self.settings.value("PluginExportador/dpi_gen", 150)))
        self.spin_dpi_gen.setToolTip("Resolución para los planos Generales e Índices.")
        grid_dpi.addWidget(QLabel("DPI Generales/Índices:"), 0, 0)
        grid_dpi.addWidget(self.spin_dpi_gen, 0, 1)

        self.spin_dpi_leg = QSpinBox()
        self.spin_dpi_leg.setRange(72, 600)
        self.spin_dpi_leg.setValue(int(self.settings.value("PluginExportador/dpi_leg", 150)))
        self.spin_dpi_leg.setToolTip("Resolución para las leyendas.")
        grid_dpi.addWidget(QLabel("DPI Leyendas:"), 1, 0)
        grid_dpi.addWidget(self.spin_dpi_leg, 1, 1)

        self.spin_dpi_rec = QSpinBox()
        self.spin_dpi_rec.setRange(72, 600)
        self.spin_dpi_rec.setValue(int(self.settings.value("PluginExportador/dpi_rec", 300)))
        self.spin_dpi_rec.setToolTip("Resolución para los planos de Detalle (Recortes)." + chr(10) + "A mayor valor, más nítido. 300 es el recomendado.")
        grid_dpi.addWidget(QLabel("DPI Detalle (Recortes):"), 2, 0)
        grid_dpi.addWidget(self.spin_dpi_rec, 2, 1)

        layout.addLayout(grid_dpi)

        self.cmb_formato = QComboBox()
        self.cmb_formato.addItems(["PNG (recomendado)", "JPG (más ligero)"])
        try:
            idx_fmt = int(self.settings.value("PluginExportador/formato", 0))
            if 0 <= idx_fmt < self.cmb_formato.count():
                self.cmb_formato.setCurrentIndex(idx_fmt)
        except (ValueError, TypeError):
            pass

        row_fmt = QHBoxLayout()
        row_fmt.addWidget(QLabel("Formato de captura:"))
        row_fmt.addWidget(self.cmb_formato)
        layout.addLayout(row_fmt)

        # --- Botón de acordeón para Módulos de Exportación ---
        self.btn_toggle_modulos = QPushButton("▼ Módulos de Exportación (Selección)")
        self.btn_toggle_modulos.setStyleSheet(
            "QPushButton { text-align: left; font-weight: bold; background-color: #F0F0F0; border: 1px solid #CCC; padding: 6px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #E0E0E0; }"
        )
        self.btn_toggle_modulos.clicked.connect(self._toggle_modulos_exportacion)
        layout.addWidget(self.btn_toggle_modulos)

        self.widget_modulos_exportacion = QWidget()
        lay_modulos = QVBoxLayout(self.widget_modulos_exportacion)
        lay_modulos.setContentsMargins(10, 5, 10, 5)

        self.chk_exp_gen = QCheckBox("1. Generales e Índices")
        self.chk_exp_gen.setChecked(True)
        lay_modulos.addWidget(self.chk_exp_gen)

        self.chk_exp_rec = QCheckBox("2. Planos de Detalle (Recortes)")
        self.chk_exp_rec.setChecked(True)
        lay_modulos.addWidget(self.chk_exp_rec)

        self.chk_exp_leg = QCheckBox("3. Leyendas")
        self.chk_exp_leg.setChecked(True)
        lay_modulos.addWidget(self.chk_exp_leg)

        self.chk_exp_pdf = QCheckBox("4. Unificar PDF Final")
        self.chk_exp_pdf.setChecked(True)
        lay_modulos.addWidget(self.chk_exp_pdf)

        self.btn_run_all = QPushButton("▶ EJECUTAR EXPORTACIÓN SELECCIONADA")
        self.btn_run_all.setStyleSheet("QPushButton { background-color: #2E7D32; color: white; font-weight: bold; padding: 12px; border-radius: 4px; margin-top: 6px; }")
        self.btn_run_all.clicked.connect(self.run_modulos)
        lay_modulos.addWidget(self.btn_run_all)

        self.widget_modulos_exportacion.setVisible(True)
        layout.addWidget(self.widget_modulos_exportacion)

        grupo_img = QGroupBox("Pasos Individuales")
        lay_img = QVBoxLayout()
        lay_img.setSpacing(8)

        self.btn_gen = QPushButton("1.1 Exportar Generales e Índices")
        self.btn_gen.setToolTip("Genera los planos generales y los índices de ambas redes. No requieren la cuadrícula.")
        self.btn_gen.clicked.connect(self.run_generales)
        lay_img.addWidget(self.btn_gen)

        self.btn_indiv = QPushButton("1.2 Exportar Planos de Detalle")
        self.btn_indiv.setToolTip("Genera una imagen por cada recorte de la cuadrícula.")
        self.btn_indiv.clicked.connect(self.run_individuales)
        lay_img.addWidget(self.btn_indiv)

        self.btn_leyendas = QPushButton("1.3 Generar Leyendas")
        self.btn_leyendas.setToolTip("Exporta una imagen de leyenda de colores para cada red.")
        self.btn_leyendas.clicked.connect(self.generar_leyendas)
        lay_img.addWidget(self.btn_leyendas)

        grupo_img.setLayout(lay_img)
        layout.addWidget(grupo_img)

        grupo_pdf = QGroupBox("2. Compilar Documento")
        lay_pdf = QVBoxLayout()
        lay_pdf.setSpacing(8)

        row_feder = QHBoxLayout()
        self.chk_feder = QCheckBox("Incluir Logos y Frase FEDER:")
        self.chk_feder.setToolTip("Añade la cabecera de cofinanciación FEDER a cada página del PDF.")
        self.chk_feder.setChecked(True)
        row_feder.addWidget(self.chk_feder)

        self.cmb_idioma_feder = QComboBox()
        self.cmb_idioma_feder.addItem("Catalán", "CA")
        self.cmb_idioma_feder.addItem("Español", "ES")
        self.cmb_idioma_feder.setToolTip("Selecciona el idioma del texto legal de cofinanciación FEDER.")
        try:
            idx_idioma = int(self.settings.value("PluginExportador/idioma_feder", 0))
            if 0 <= idx_idioma < self.cmb_idioma_feder.count():
                self.cmb_idioma_feder.setCurrentIndex(idx_idioma)
        except (ValueError, TypeError):
            pass
        self.cmb_idioma_feder.currentIndexChanged.connect(
            lambda idx: self.settings.setValue("PluginExportador/idioma_feder", idx)
        )
        self.chk_feder.toggled.connect(self.cmb_idioma_feder.setEnabled)
        row_feder.addWidget(self.cmb_idioma_feder)
        lay_pdf.addLayout(row_feder)

        self.chk_dielmo = QCheckBox("Incluir Logo DIELMO (Cabecera)")
        self.chk_dielmo.setToolTip("Añade el logo de DIELMO en la parte superior.")
        self.chk_dielmo.setChecked(True)
        lay_pdf.addWidget(self.chk_dielmo)

        # --- Selector de Logo Municipal ---
        row_muni = QHBoxLayout()
        self.chk_municipio = QCheckBox("Incluir Logo Municipal:")
        self.chk_municipio.setChecked(True)
        self.chk_municipio.toggled.connect(lambda checked: self.cmb_municipio.setEnabled(checked))
        row_muni.addWidget(self.chk_municipio)

        self.cmb_municipio = QComboBox()
        self.cmb_municipio.addItem("Sin logo municipal", "")

        if os.path.exists(CARPETA_MUNICIPIOS):
            archivos_muni = sorted([f for f in os.listdir(CARPETA_MUNICIPIOS) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))])
            for f in archivos_muni:
                nombre_base = os.path.splitext(f)[0]
                match = re.match(r'^\d+_(.+)$', nombre_base)
                if match:
                    nombre_limpio = match.group(1).replace('_', ' ').title()
                else:
                    nombre_limpio = nombre_base.replace('_', ' ').title()
                self.cmb_municipio.addItem(nombre_limpio, os.path.join(CARPETA_MUNICIPIOS, f))

        row_muni.addWidget(self.cmb_municipio)
        lay_pdf.addLayout(row_muni)

        self.btn_pdf = QPushButton("Unificar todo en un solo PDF")
        self.btn_pdf.setToolTip("Toma todas las imágenes generadas, las ordena y las une en un único PDF.")
        self.btn_pdf.setStyleSheet("QPushButton { background-color: #E91E63; color: white; font-weight: bold; padding: 12px; border-radius: 4px; }")
        self.btn_pdf.clicked.connect(self.unificar_pdf)
        lay_pdf.addWidget(self.btn_pdf)

        self.btn_abrir_pdf = QPushButton("📂 Abrir PDF Generado")
        self.btn_abrir_pdf.setToolTip("Abre el PDF final en tu visor de documentos predeterminado.")
        self.btn_abrir_pdf.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 10px; border-radius: 4px; }")
        self.btn_abrir_pdf.setEnabled(False)
        self.btn_abrir_pdf.clicked.connect(self.abrir_pdf)
        lay_pdf.addWidget(self.btn_abrir_pdf)

        grupo_pdf.setLayout(lay_pdf)
        layout.addWidget(grupo_pdf)

        grupo_control = QGroupBox("Estado del Proceso")
        lay_control = QVBoxLayout()
        lay_control.setSpacing(8)

        self.lbl_status = QLabel("Estado: Listo para exportar.")
        self.lbl_status.setStyleSheet("color: #555; font-style: italic;")
        lay_control.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        lay_control.addWidget(self.progress_bar)

        self.btn_stop = QPushButton("⏹ DETENER EXPORTACIÓN")
        self.btn_stop.setStyleSheet("QPushButton { background-color: #F44336; color: white; font-weight: bold; padding: 10px; border-radius: 4px; }")
        self.btn_stop.setToolTip("Cancela el proceso de captura en curso.")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.detener_exportacion)
        lay_control.addWidget(self.btn_stop)

        grupo_control.setLayout(lay_control)
        layout.addWidget(grupo_control)

        layout.addStretch()

        scroll.setWidget(content_widget)
        outer_layout.addWidget(scroll)

    def detener_exportacion(self):
        self._cancelar = True
        self.lbl_status.setText("Estado: Deteniendo exportación...")
        self.log_message("Solicitud de detención recibida. Finalizando captura actual...", "WARNING")
        self.btn_stop.setEnabled(False)

    def bloquear_ui_exportacion(self, bloquear, boton_activo=None):
        if bloquear and boton_activo is None:
            remitente = self.sender()
            if isinstance(remitente, QPushButton):
                boton_activo = remitente

        controles_bloquear = [
            'btn_gen', 'btn_indiv', 'btn_leyendas', 'btn_pdf', 'btn_run_all',
            'chk_exp_gen', 'chk_exp_rec', 'chk_exp_leg', 'chk_exp_pdf',
            'spin_dpi_gen', 'spin_dpi_leg', 'spin_dpi_rec', 'cmb_formato',
            'chk_feder', 'cmb_idioma_feder', 'chk_dielmo', 'chk_municipio', 'cmb_municipio',
            'btn_abrir_pdf'
        ]

        for nombre_w in controles_bloquear:
            w = getattr(self, nombre_w, None)
            if w is None:
                continue
            if nombre_w == 'cmb_municipio':
                w.setEnabled((not bloquear) and self.chk_municipio.isChecked())
            elif nombre_w == 'cmb_idioma_feder':
                w.setEnabled((not bloquear) and self.chk_feder.isChecked())
            else:
                w.setEnabled(not bloquear)

            if isinstance(w, QPushButton):
                if bloquear:
                    if not hasattr(w, "_texto_original"):
                        w._texto_original = w.text()
                    if boton_activo is not None and w is boton_activo:
                        w.setText("⏳ Procesando...")
                else:
                    if hasattr(w, "_texto_original"):
                        w.setText(w._texto_original)

        if hasattr(self, 'btn_stop'):
            self.btn_stop.setEnabled(bloquear)

        if not bloquear:
            self.validar_campos()

    def validar_campos(self):
        proyecto_guardado = bool(QgsProject.instance().absolutePath())
        listo = bool(self.txt_municipio.text().strip()) and proyecto_guardado

        if proyecto_guardado:
            self.lbl_ruta_auto.setText("Directorio:\n.../PDFs_Exportacion/")
            muni = self._obtener_municipio_archivo()
            if muni:
                base_dir = self.get_output_dir()
                if base_dir:
                    pdf_path = os.path.join(base_dir, f"{muni}_Planos_Completos.pdf")
                    self.btn_abrir_pdf.setEnabled(os.path.exists(pdf_path))
        else:
            self.lbl_ruta_auto.setText("⚠️ Guarda tu proyecto de QGIS para habilitar la exportación.")
            self.btn_abrir_pdf.setEnabled(False)

        if not self.btn_stop.isEnabled():
            for btn in [self.btn_gen, self.btn_indiv, self.btn_leyendas, self.btn_pdf, self.btn_run_all]:
                if btn is not None:
                    btn.setEnabled(listo)

    def abrir_pdf(self):
        muni = self._obtener_municipio_archivo()
        base_dir = self.get_output_dir()
        if not base_dir:
            return
        out_path = os.path.join(base_dir, f"{muni}_Planos_Completos.pdf")
        if os.path.exists(out_path):
            self.log_message(f"Abriendo PDF: {os.path.basename(out_path)}", "INFO")
            QDesktopServices.openUrl(QUrl.fromLocalFile(out_path))
        else:
            self.log_message("El archivo PDF no existe todavía.", "WARNING")

    def preparar_entorno(self):
        if not QgsProject.instance().absolutePath():
            self.log_message("Error: El proyecto de QGIS no ha sido guardado.", "ERROR")
            QMessageBox.warning(self, "Error", "Debes guardar el proyecto de QGIS primero.")
            return False

        self.root = QgsProject.instance().layerTreeRoot()
        self.nodo_potable = self.root.findGroup(self.GRUPO_POTABLE)
        self.nodo_sanea = self.root.findGroup(self.GRUPO_SANEA)
        capas = QgsProject.instance().mapLayersByName(self.NOMBRE_CAPA)

        if not capas or not self.nodo_sanea or not self.nodo_potable:
            self.log_message("Faltan capas requeridas (Potable, Saneamiento o RecortesPDF).", "ERROR")
            QMessageBox.critical(self, "Falta información", "No se encontró el grupo Potable, Saneamiento o la capa RecortesPDF.")
            return False

        self.capa_recortes = capas[0]
        self.nodo_recortes = self.root.findLayer(self.capa_recortes.id())
        if not self.nodo_recortes:
            self.log_message("La capa RecortesPDF no está en el panel de capas. Se ignorará su visibilidad.", "WARNING")
        self.canvas = self.iface.mapCanvas()
        self.municipio = self._obtener_municipio_archivo()

        self.DPI_GEN = self.spin_dpi_gen.value()
        self.DPI_LEG = self.spin_dpi_leg.value()
        self.DPI_REC = self.spin_dpi_rec.value()

        self.settings.setValue("PluginExportador/dpi_gen", self.DPI_GEN)
        self.settings.setValue("PluginExportador/dpi_leg", self.DPI_LEG)
        self.settings.setValue("PluginExportador/dpi_rec", self.DPI_REC)
        self.settings.setValue("PluginExportador/formato", self.cmb_formato.currentIndex())
        return True

    def _ext_captura(self):
        return ".png" if self.cmb_formato.currentIndex() == 0 else ".jpg"

    def _formato_captura(self):
        return "PNG" if self.cmb_formato.currentIndex() == 0 else "JPG"

    def _capas_visibles_actuales(self):
        root = QgsProject.instance().layerTreeRoot()
        set_visibles = {lyr.id() for lyr in root.checkedLayers() if lyr and lyr.isValid()}
        return [lyr for lyr in root.layerOrder() if lyr.id() in set_visibles]

    def tomar_captura(self, nombre, ext, ruta_dir, dpi, apagar_etiq=False, capas_override=None):
        if self._cancelar:
            return False

        QgsApplication.processEvents()
        if self._cancelar:
            return False

        cfg = QgsMapSettings(self.canvas.mapSettings())
        if capas_override is not None:
            cfg.setLayers(capas_override)
        cfg.setOutputDpi(dpi)
        cfg.setFlag(_DRAW_LABELING_FLAG, not apagar_etiq)
        cfg.setExtent(ext)

        ratio = ext.width() / ext.height() if ext.height() > 0 else 1.0
        base_pixels = 1920

        if ratio >= 1.0:
            out_w = base_pixels
            out_h = int(base_pixels / ratio)
        else:
            out_h = base_pixels
            out_w = int(base_pixels * ratio)

        factor = dpi / 150.0
        out_w = max(1, int(out_w * factor))
        out_h = max(1, int(out_h * factor))

        cfg.setOutputSize(QSize(out_w, out_h))

        img = QImage(cfg.outputSize(), QImage.Format_ARGB32_Premultiplied)
        img.fill(QColor(255, 255, 255).rgb())
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        job = QgsMapRendererCustomPainterJob(cfg, p)
        job.start()
        job.waitForFinished()
        p.end()

        extension = self._ext_captura()
        ruta_img = os.path.join(ruta_dir, f"{nombre}{extension}")
        calidad = -1 if extension == ".png" else 88
        ok = img.save(ruta_img, self._formato_captura(), calidad)
        if not ok:
            self.log_message(f"No se pudo guardar la imagen: {ruta_img}", "ERROR")
            return False
        return True

    def run_modulos(self):
        boton_pulsado = self.sender() if isinstance(self.sender(), QPushButton) else None
        if not self.preparar_entorno():
            return

        extent_original = self.canvas.extent()
        inicio_tiempo = time.time()
        total_pasos = sum([
            self.chk_exp_gen.isChecked(),
            self.chk_exp_rec.isChecked(),
            self.chk_exp_leg.isChecked(),
            self.chk_exp_pdf.isChecked()
        ])

        if total_pasos == 0:
            QMessageBox.warning(self, "Nada seleccionado", "Marca al menos un módulo para exportar.")
            return

        self._cancelar = False
        self.bloquear_ui_exportacion(True, boton_pulsado)
        paso_actual = 0
        try:
            if self.chk_exp_gen.isChecked():
                paso_actual += 1
                self.lbl_status.setText(f"Estado: Paso {paso_actual}/{total_pasos} - Generales...")
                QgsApplication.processEvents()
                self.run_generales(silencioso=True)
                if self._cancelar:
                    return

            if self.chk_exp_rec.isChecked():
                paso_actual += 1
                self.lbl_status.setText(f"Estado: Paso {paso_actual}/{total_pasos} - Detalles...")
                QgsApplication.processEvents()
                self.run_individuales(silencioso=True)
                if self._cancelar:
                    return

            if self.chk_exp_leg.isChecked():
                paso_actual += 1
                self.lbl_status.setText(f"Estado: Paso {paso_actual}/{total_pasos} - Leyendas...")
                QgsApplication.processEvents()
                self.generar_leyendas(silencioso=True)
                if self._cancelar:
                    return

            if self.chk_exp_pdf.isChecked():
                paso_actual += 1
                self.lbl_status.setText(f"Estado: Paso {paso_actual}/{total_pasos} - Unificando PDF...")
                QgsApplication.processEvents()
                self.unificar_pdf(silencioso=True)

            if not self._cancelar:
                tiempo_total = int(time.time() - inicio_tiempo)
                mins, segs = divmod(tiempo_total, 60)
                msg = f"Todos los módulos seleccionados han finalizado.\nTiempo total: {mins}m {segs}s"
                QMessageBox.information(self, "Proceso Completado", msg)
            else:
                QMessageBox.warning(self, "Cancelado", "La exportación por módulos fue detenida.")

        finally:
            self.canvas.setExtent(extent_original)
            self.canvas.refresh()
            self.lbl_status.setText("Estado: Listo para exportar.")
            self.bloquear_ui_exportacion(False)

    def run_generales(self, silencioso=False):
        boton_pulsado = self.sender() if (not silencioso and isinstance(self.sender(), QPushButton)) else None
        if not self.preparar_entorno():
            return
        extent_original = self.canvas.extent()
        vis_pot_orig = self.nodo_potable.itemVisibilityChecked()
        vis_san_orig = self.nodo_sanea.itemVisibilityChecked()

        self.log_message("Iniciando exportación de Generales e Índices...", "INFO")
        if not silencioso:
            self.bloquear_ui_exportacion(True, boton_pulsado)
            self._cancelar = False
        self.progress_bar.setMaximum(4)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Estado: Exportando Generales e Índices...")

        self.canvas.waitWhileRendering()
        self.canvas.freeze(True)
        try:
            dir_potable = self.get_output_dir('Abastecimiento')
            dir_sanea = self.get_output_dir('Saneamiento')

            crs_canvas = self.iface.mapCanvas().mapSettings().destinationCrs()
            xform_rec = None
            if self.capa_recortes.crs() != crs_canvas:
                xform_rec = QgsCoordinateTransform(self.capa_recortes.crs(), crs_canvas, QgsProject.instance())

            ext_p, ext_s = QgsRectangle(), QgsRectangle()
            ext_p.setMinimal()
            ext_s.setMinimal()

            for nc in self.nodo_potable.findLayers():
                lyr = nc.layer()
                if lyr and lyr.type() == 0:
                    ext_t = self._extent_en_crs_canvas(lyr, crs_canvas)
                    if ext_t:
                        ext_p.combineExtentWith(ext_t)

            for nc in self.nodo_sanea.findLayers():
                lyr = nc.layer()
                if lyr and lyr.type() == 0:
                    ext_t = self._extent_en_crs_canvas(lyr, crs_canvas)
                    if ext_t:
                        ext_s.combineExtentWith(ext_t)

            ext_p_r, ext_s_r = QgsRectangle(), QgsRectangle()
            ext_p_r.setMinimal()
            ext_s_r.setMinimal()
            for ft in self.capa_recortes.getFeatures():
                g = ft.geometry()
                if not g or g.isEmpty():
                    continue
                bbox = xform_rec.transformBoundingBox(g.boundingBox()) if xform_rec else g.boundingBox()
                if str(ft["Tipo"]).strip().upper() == "POTABLE":
                    ext_p_r.combineExtentWith(bbox)
                else:
                    ext_s_r.combineExtentWith(bbox)

            ext_p.scale(1.1)
            ext_s.scale(1.1)
            ext_p_r.scale(1.1)
            ext_s_r.scale(1.1)

            pasos = [
                (self.nodo_potable, self.nodo_sanea, False, None, ext_p, dir_potable, f"{self.municipio}_Abastecimiento_General", True),
                (self.nodo_sanea, self.nodo_potable, False, None, ext_s, dir_sanea, f"{self.municipio}_Saneamiento_General", True),
                (self.nodo_potable, self.nodo_sanea, True, "\"Tipo\" = 'POTABLE'", ext_p_r, dir_potable, f"{self.municipio}_Abastecimiento_Indice", False),
                (self.nodo_sanea, self.nodo_potable, True, "\"Tipo\" != 'POTABLE'", ext_s_r, dir_sanea, f"{self.municipio}_Saneamiento_Indice", False),
            ]

            for i, (n_on, n_off, r_on, filt, e, d_out, nom, etiq_off) in enumerate(pasos):
                if self._cancelar:
                    break
                if e.isEmpty():
                    self.log_message(f"Omitido {nom}: extensión vacía.", "WARNING")
                    self.progress_bar.setValue(i + 1)
                    continue

                self.log_message(f"Generando: {nom}...", "INFO")
                n_on.setItemVisibilityChecked(True)
                n_off.setItemVisibilityChecked(False)
                if self.nodo_recortes:
                    self.nodo_recortes.setItemVisibilityChecked(r_on)

                for extra_id in self._obtener_capas_extra_ids():
                    extra_node = self.root.findLayer(extra_id)
                    if extra_node:
                        extra_node.setItemVisibilityChecked(True)
                if filt:
                    self.capa_recortes.setSubsetString(filt)
                else:
                    self.capa_recortes.setSubsetString("")

                capas_render = self._capas_visibles_actuales()
                self.tomar_captura(nom, e, d_out, self.DPI_GEN, etiq_off, capas_override=capas_render)
                self.progress_bar.setValue(i + 1)

            if self._cancelar:
                self.log_message("Exportación de Generales cancelada.", "WARNING")
                self.lbl_status.setText("Estado: Exportación cancelada.")
                if not silencioso:
                    QMessageBox.warning(self, "Cancelado", "La exportación de Generales fue detenida.")
            else:
                self.log_message("Generales e Índices exportados correctamente.", "SUCCESS")
                self.lbl_status.setText("Estado: Generales exportados con éxito.")
                if not silencioso:
                    QMessageBox.information(self, "Fin", "Generales e Índices exportados.")
        except Exception as e:
            self.log_message(f"Error en exportación de Generales: {str(e)}", "ERROR")
            QMessageBox.critical(self, "Error", f"Ocurrió un error:\n{str(e)}")
        finally:
            self.canvas.freeze(False)
            try:
                self.capa_recortes.setSubsetString("")
                self.nodo_potable.setItemVisibilityChecked(vis_pot_orig)
                self.nodo_sanea.setItemVisibilityChecked(vis_san_orig)
                if self.nodo_recortes:
                    self.nodo_recortes.setItemVisibilityChecked(True)
                if not silencioso:
                    self.canvas.setExtent(extent_original)
                    self.canvas.refresh()
            except Exception:
                pass
            if not silencioso:
                self.bloquear_ui_exportacion(False)

    def run_individuales(self, silencioso=False):
        boton_pulsado = self.sender() if (not silencioso and isinstance(self.sender(), QPushButton)) else None
        if not self.preparar_entorno():
            return
        extent_original = self.canvas.extent()
        vis_pot_orig = self.nodo_potable.itemVisibilityChecked()
        vis_san_orig = self.nodo_sanea.itemVisibilityChecked()

        fts = list(self.capa_recortes.getFeatures())
        self.log_message(f"Iniciando exportación de {len(fts)} planos de detalle...", "INFO")
        if not silencioso:
            self.bloquear_ui_exportacion(True, boton_pulsado)
            self._cancelar = False
        self.progress_bar.setMaximum(max(1, len(fts)))
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Estado: Iniciando exportación de Detalles...")

        fallos = 0
        self.canvas.waitWhileRendering()
        self.canvas.freeze(True)
        try:
            dir_potable = self.get_output_dir('Abastecimiento')
            dir_sanea = self.get_output_dir('Saneamiento')
            extra_ids = self._obtener_capas_extra_ids()

            crs_canvas = self.iface.mapCanvas().mapSettings().destinationCrs()
            xform_rec = None
            if self.capa_recortes.crs() != crs_canvas:
                xform_rec = QgsCoordinateTransform(self.capa_recortes.crs(), crs_canvas, QgsProject.instance())

            if self.nodo_recortes:
                self.nodo_recortes.setItemVisibilityChecked(False)
            for extra_id in extra_ids:
                extra_node = self.root.findLayer(extra_id)
                if extra_node:
                    extra_node.setItemVisibilityChecked(True)

            self.nodo_potable.setItemVisibilityChecked(True)
            self.nodo_sanea.setItemVisibilityChecked(False)
            capas_potable = self._capas_visibles_actuales()

            self.nodo_potable.setItemVisibilityChecked(False)
            self.nodo_sanea.setItemVisibilityChecked(True)
            capas_sanea = self._capas_visibles_actuales()

            factor_margen = 1.0 + (self.spin_margen.value() / 100.0)
            inicio_tiempo = time.time()

            for i, ft in enumerate(fts):
                if self._cancelar:
                    break

                transcurrido = time.time() - inicio_tiempo
                restante = int((transcurrido / (i + 1)) * (len(fts) - i - 1)) if i > 0 else 0
                mins, segs = divmod(restante, 60)

                self.lbl_status.setText(f"Estado: Exportando captura {i+1} de {len(fts)} (Tiempo restante: {mins}m {segs}s)...")
                tp = str(ft["Tipo"]).strip().upper()
                num = "".join(c for c in str(ft["N Captura"]).strip() if c.isalnum() or c in (' ', '_', '-')).rstrip() or str(ft.id())
                if tp == "POTABLE":
                    nom = f"{self.municipio}_Abastecimiento_{num}"
                    r_dir = dir_potable
                    capas_render = capas_potable
                else:
                    nom = f"{self.municipio}_Saneamiento_{num}"
                    r_dir = dir_sanea
                    capas_render = capas_sanea

                g = ft.geometry()
                if g and not g.isEmpty():
                    r = xform_rec.transformBoundingBox(g.boundingBox()) if xform_rec else g.boundingBox()
                    r.scale(factor_margen)
                    if not self.tomar_captura(nom, r, r_dir, self.DPI_REC, capas_override=capas_render):
                        fallos += 1
                self.progress_bar.setValue(i + 1)

            if self._cancelar:
                self.log_message(f"Exportación cancelada tras {self.progress_bar.value()} capturas.", "WARNING")
                self.lbl_status.setText("Estado: Exportación cancelada.")
                if not silencioso:
                    QMessageBox.warning(self, "Cancelado", f"Se detuvo tras {self.progress_bar.value()} capturas.")
            elif fallos:
                self.log_message(f"Detalles exportados con {fallos} fallos de guardado.", "WARNING")
                self.lbl_status.setText(f"Estado: Detalles exportados ({fallos} fallos).")
                if not silencioso:
                    QMessageBox.warning(self, "Con fallos", f"Algunas capturas no se pudieron guardar ({fallos}). Revisa el log.")
            else:
                self.log_message("Planos de detalle exportados correctamente.", "SUCCESS")
                self.lbl_status.setText("Estado: Detalles exportados con éxito.")
                if not silencioso:
                    QMessageBox.information(self, "Fin", "Planos individuales exportados.")
        except Exception as e:
            self.log_message(f"Error en exportación de Detalles: {str(e)}", "ERROR")
            QMessageBox.critical(self, "Error", f"Ocurrió un error:\n{str(e)}")
        finally:
            self.canvas.freeze(False)
            try:
                self.nodo_potable.setItemVisibilityChecked(vis_pot_orig)
                self.nodo_sanea.setItemVisibilityChecked(vis_san_orig)
                if self.nodo_recortes:
                    self.nodo_recortes.setItemVisibilityChecked(True)
                if not silencioso:
                    self.canvas.setExtent(extent_original)
                    self.canvas.refresh()
            except Exception:
                pass
            if not silencioso:
                self.bloquear_ui_exportacion(False)

    def generar_leyendas(self, silencioso=False):
        boton_pulsado = self.sender() if (not silencioso and isinstance(self.sender(), QPushButton)) else None
        muni = self._obtener_municipio_archivo()
        if not QgsProject.instance().absolutePath():
            self.log_message("Error: Guarda el proyecto antes de generar leyendas.", "ERROR")
            return QMessageBox.warning(self, "Error", "Guarda el proyecto.")

        self.log_message("Iniciando generación de leyendas...", "INFO")
        if not silencioso:
            self.bloquear_ui_exportacion(True, boton_pulsado)
            self._cancelar = False
        self.progress_bar.setMaximum(2)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Estado: Generando leyendas...")
        QgsApplication.processEvents()

        try:
    
            grupos_leg = [
                ("Leyenda Abastecimiento", self.GRUPO_POTABLE, 'Abastecimiento'),
                ("Leyenda Saneamiento", self.GRUPO_SANEA, 'Saneamiento'),
            ]
            for idx_leg, (titulo, grupo_nombre, folder) in enumerate(grupos_leg):
                if self._cancelar:
                    break
                self.log_message(f"Generando {titulo}...", "INFO")
                self.lbl_status.setText(f"Estado: Generando {titulo}...")
                QgsApplication.processEvents()

                grupo = QgsProject.instance().layerTreeRoot().findGroup(grupo_nombre)
                if not grupo:
                    self.log_message(f"Grupo {grupo_nombre} no encontrado.", "WARNING")
                    self.progress_bar.setValue(idx_leg + 1)
                    continue
                ruta_out = self.get_output_dir(folder)

                layout = QgsPrintLayout(QgsProject.instance())
                layout.initializeDefaults()
                layout.pageCollection().pages()[0].setPageSize(QgsLayoutSize(140, 250, _LAYOUT_UNIT_MM))

                leg = QgsLayoutItemLegend(layout)
                layout.addLayoutItem(leg)
                leg.attemptSetSceneRect(QRectF(2, 2, 136, 246))
                leg.setTitle(titulo)
                leg.setAutoUpdateModel(False)

                root_group = leg.model().rootGroup()
                root_group.clear()

                estado_previo = {}

                def guardar_visibilidad(nodo):
                    estado_previo[nodo] = nodo.itemVisibilityChecked()
                    if hasattr(nodo, 'children'):
                        for c in nodo.children():
                            guardar_visibilidad(c)

                guardar_visibilidad(grupo)

                def forzar_visible(nodo):
                    nodo.setItemVisibilityChecked(True)
                    if hasattr(nodo, 'children'):
                        for c in nodo.children():
                            forzar_visible(c)

                forzar_visible(grupo)

                nodos_a_colapsar = []

                def add_nodes_to_legend(legend_group, tree_group):
                    for child in tree_group.children():
                        if isinstance(child, QgsLayerTreeLayer):
                            if child.layer() and child.name().strip().upper() != 'FONT':
                                nuevo_nodo = legend_group.addLayer(child.layer())
                                if child.name().startswith(('124_', '225_')):
                                    nodos_a_colapsar.append(nuevo_nodo)
                        elif isinstance(child, QgsLayerTreeGroup):
                            sub = legend_group.addGroup(child.name())
                            add_nodes_to_legend(sub, child)

                add_nodes_to_legend(root_group, grupo)

                leg.updateLegend()
                layout.refresh()
                QgsApplication.processEvents()

                modelo = leg.model()
                for nombre_capa in ('124_', '225_'):
                    for lyr in QgsProject.instance().mapLayers().values():
                        if lyr.name().startswith(nombre_capa):
                            nodo_capa = modelo.rootGroup().findLayer(lyr)
                            if nodo_capa:
                                QgsMapLayerLegendUtils.setLegendNodeOrder(nodo_capa, [])
                                self.log_message(
                                    f"Leyenda: subclasificaciones de '{lyr.name()}' ocultas para el PDF.",
                                    "INFO",
                                )

                for nodo in nodos_a_colapsar:
                    nodo.setExpanded(False)
                    nodo.setCustomProperty("legend/expandable", "false")
                layout.refresh()

                extension = self._ext_captura()
                out_path = os.path.join(ruta_out, f"{muni}_{folder}_Leyenda{extension}")
                exp = QgsLayoutExporter(layout)
                s = QgsLayoutExporter.ImageExportSettings()
                s.dpi = self.spin_dpi_leg.value()
                exp.exportToImage(out_path, s)

                for nodo, estado in estado_previo.items():
                    try:
                        nodo.setItemVisibilityChecked(estado)
                    except Exception:
                        pass
                self.progress_bar.setValue(idx_leg + 1)
                QgsApplication.processEvents()

            if self._cancelar:
                self.log_message("Generación de leyendas cancelada.", "WARNING")
                self.lbl_status.setText("Estado: Exportación cancelada.")
            else:
                self.log_message("Leyendas generadas con éxito.", "SUCCESS")
                self.lbl_status.setText("Estado: Leyendas generadas con éxito.")
                if not silencioso:
                    QMessageBox.information(self, "Éxito", "Leyendas generadas correctamente en PDFs_Exportacion.")
        except Exception as e:
            self.log_message(f"Error al generar leyendas: {str(e)}", "ERROR")
            QMessageBox.critical(self, "Error", f"Ocurrió un error:\n{str(e)}")
        finally:
            if not silencioso:
                self.bloquear_ui_exportacion(False)

    def unificar_pdf(self, silencioso=False):
        boton_pulsado = self.sender() if (not silencioso and isinstance(self.sender(), QPushButton)) else None
        muni = self._obtener_municipio_archivo()
        base_dir = self.get_output_dir()
        if not base_dir:
            self.log_message("Error: Directorio de salida no encontrado.", "ERROR")
            return QMessageBox.warning(self, "Error", "Guarda el proyecto primero.")

        self.log_message("Iniciando unificación de PDF...", "INFO")
        if not silencioso:
            self.bloquear_ui_exportacion(True, boton_pulsado)
            self._cancelar = False
        self.lbl_status.setText("Estado: Preparando imágenes para PDF...")
        QgsApplication.processEvents()

        out_path = os.path.join(base_dir, f"{muni}_Planos_Completos.pdf")
        ext_preferida = self._ext_captura().lower()

        def orden_captura(ruta_archivo):
            n = os.path.basename(ruta_archivo).lower()
            m = re.search(r'_(\d+)\.[a-z]+$', n)
            if m:
                return (1, int(m.group(1)), n)
            if 'general' in n or 'completo' in n:
                return (0, 0, n)
            if 'indice' in n:
                return (0, 1, n)
            return (1, float('inf'), n)

        def filtrar_por_muni_y_ext(lista_rutas):
            pref = f"{muni.lower()}_"
            del_muni = [r for r in lista_rutas if os.path.basename(r).lower().startswith(pref)]
            base = del_muni if del_muni else lista_rutas
            # Si hay duplicados con distinta extensión (.png y .jpg), priorizar la seleccionada
            por_stem = {}
            for r in base:
                stem = os.path.splitext(os.path.basename(r))[0].lower()
                ext = os.path.splitext(r)[1].lower()
                if stem not in por_stem or ext == ext_preferida:
                    por_stem[stem] = r
            return list(por_stem.values())

        painter = None
        try:
            leg_abast = None
            leg_sanea = None
            redes_capturas = []

            for nombre, sub in [('ABASTECIMIENTO', 'Abastecimiento'), ('SANEAMIENTO', 'Saneamiento')]:
                ruta = self.get_output_dir(sub)
                if os.path.isdir(ruta):
                    archivos = [
                        os.path.join(ruta, f) for f in os.listdir(ruta)
                        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
                    ]
                    archivos = filtrar_por_muni_y_ext(archivos)
                    leyendas = sorted([f for f in archivos if 'leyenda' in os.path.basename(f).lower()])
                    capturas = sorted(
                        [f for f in archivos if 'leyenda' not in os.path.basename(f).lower()],
                        key=orden_captura
                    )
                    if nombre == 'ABASTECIMIENTO' and leyendas:
                        leg_abast = leyendas[0]
                    elif nombre == 'SANEAMIENTO' and leyendas:
                        leg_sanea = leyendas[0]
                    if capturas:
                        redes_capturas.append((nombre, capturas))

            if not leg_abast and not leg_sanea and not redes_capturas:
                self.log_message("No se encontraron imágenes en las carpetas para generar el PDF.", "WARNING")
                self.lbl_status.setText("Estado: Error al unificar.")
                return QMessageBox.warning(self, "Error", "No se encontraron imágenes en las carpetas para generar el PDF.")

            if redes_capturas and not (leg_abast and leg_sanea):
                self.log_message("[!] Faltan leyendas en una de las redes. El PDF se generará sin ellas.", "WARNING")
                QMessageBox.warning(self, "Leyendas Faltantes", "Falta la leyenda de Abastecimiento o Saneamiento. El PDF se generará igualmente.")

            feder = self.chk_feder.isChecked()
            codigo_idioma = self.cmb_idioma_feder.currentData() or "CA"
            texto_feder = FRASES_FEDER.get(codigo_idioma, FRASES_FEDER["CA"])
            dielmo = self.chk_dielmo.isChecked()
            usar_muni = self.chk_municipio.isChecked()

            logos = QImage(LOGOS_FEDER) if feder else None
            if feder and (logos is None or logos.isNull()):
                self.log_message(f"Error: No se encuentra el archivo {LOGOS_FEDER}.", "ERROR")
                return QMessageBox.critical(self, "Error FEDER", "Has activado el modo FEDER pero falta 'logos_feder.png'.\n\nEl PDF no se ha generado.")
            elif feder:
                self.log_message("Modo FEDER activado.", "INFO")

            logo_dielmo = QImage(LOGOS_DIELMO) if dielmo else None
            if dielmo and (logo_dielmo is None or logo_dielmo.isNull()):
                self.log_message(f"[!] No se encuentra {LOGOS_DIELMO}. El PDF se generará sin el logo de DIELMO.", "WARNING")
                logo_dielmo = None

            ruta_muni = self.cmb_municipio.currentData() if usar_muni else None
            logo_muni = QImage(ruta_muni) if ruta_muni else None
            if ruta_muni and logo_muni.isNull():
                self.log_message(f"[!] Error al cargar el logo municipal: {ruta_muni}", "WARNING")
                logo_muni = None
            elif logo_muni:
                self.log_message(f"Logo municipal cargado: {os.path.basename(ruta_muni)}", "INFO")

            total_imgs = sum(len(caps) for _, caps in redes_capturas) + (1 if (leg_abast or leg_sanea) else 0)
            self.progress_bar.setMaximum(max(1, total_imgs))
            self.progress_bar.setValue(0)

            writer = QPdfWriter(out_path)
            writer.setResolution(150)

            has_legends = bool(leg_abast or leg_sanea)
            first_orient = _ORIENT_PORTRAIT

            if has_legends:
                first_orient = _ORIENT_LANDSCAPE
            elif redes_capturas and redes_capturas[0][1]:
                first_img = QImage(redes_capturas[0][1][0])
                if not first_img.isNull() and first_img.width() > first_img.height():
                    first_orient = _ORIENT_LANDSCAPE

            layout = QPageLayout(QPageSize(_PAGE_SIZE_A4), first_orient, QMarginsF(8, 8, 8, 8), _UNIT_MILLIMETER)
            writer.setPageLayout(layout)

            painter = QPainter()
            if not painter.begin(writer):
                self.log_message("No se pudo abrir el archivo PDF para escritura (puede estar abierto en otro programa).", "ERROR")
                self.lbl_status.setText("Estado: Error al escribir PDF.")
                return QMessageBox.critical(
                    self, "Archivo PDF bloqueado",
                    f"No se pudo guardar el archivo:\n{out_path}\n\nComprueba que no lo tengas abierto en otro visor de PDF y vuelve a intentarlo."
                )
            paginas = 0
            is_first_page = True

            def draw_header_logos(rect):
                alto_logo = int(rect.height() * 0.08)
                y_header = rect.y() + 10
                hay_logo = False

                if dielmo and logo_dielmo is not None and not logo_dielmo.isNull():
                    w_dielmo = int(rect.width() * 0.25)
                    e_dielmo = logo_dielmo.scaled(w_dielmo, alto_logo, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    painter.drawImage(int(rect.x() + 10), int(y_header), e_dielmo)
                    hay_logo = True

                if usar_muni and logo_muni is not None and not logo_muni.isNull():
                    w_muni = int(rect.width() * 0.20)
                    e_muni = logo_muni.scaled(w_muni, alto_logo, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    x_muni = rect.x() + rect.width() - e_muni.width() - 10
                    painter.drawImage(int(x_muni), int(y_header), e_muni)
                    hay_logo = True

                if hay_logo:
                    return QRect(rect.x(), y_header + alto_logo + 10, rect.width(), rect.height() - alto_logo - 20)
                return rect

            def draw_feder_footer(rect, first_page):
                if not feder:
                    return rect

                alto_banda = int(rect.height() * 0.07)
                y0 = rect.y() + rect.height() - alto_banda

                if feder and logos and not logos.isNull():
                    e = logos.scaled(int(rect.width() * 0.45), alto_banda, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                    if first_page:
                        x_pos = rect.x()
                        painter.drawImage(int(x_pos), int(y0 + (alto_banda - e.height()) // 2), e)

                        f = QFont('Arial', 7)
                        painter.setFont(f)
                        painter.setPen(QColor(60, 60, 60))
                        x_txt = x_pos + e.width() + int(rect.width() * 0.02)
                        painter.drawText(
                            QRectF(x_txt, y0, rect.x() + rect.width() - x_txt, alto_banda),
                            int(Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap),
                            texto_feder
                        )
                        painter.setPen(QColor(0, 0, 0))
                    else:
                        x_pos = rect.x() + (rect.width() - e.width()) / 2
                        painter.drawImage(int(x_pos), int(y0 + (alto_banda - e.height()) // 2), e)

                return QRect(rect.x(), rect.y(), rect.width(), rect.height() - alto_banda)

            if has_legends:
                self.log_message("Añadiendo página de Leyendas (Horizontal)...", "INFO")
                r = writer.pageLayout().paintRectPixels(writer.resolution())
                r = QRect(0, 0, r.width(), r.height())
                r = draw_header_logos(r)
                r = draw_feder_footer(r, True)
                f = QFont('Arial', 16)
                f.setBold(True)
                painter.setFont(f)
                painter.drawText(QRectF(r.x(), r.y(), r.width(), 50), Qt.AlignHCenter, "LEYENDAS DE REDES")

                half_w = r.width() / 2
                zona_img = QRectF(r.x(), r.y() + 60, half_w - 20, r.height() - 100)

                if leg_abast:
                    img_a = QImage(leg_abast)
                    if not img_a.isNull():
                        esc_a = img_a.scaled(int(zona_img.width()), int(zona_img.height()), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        painter.drawImage(
                            int(zona_img.x() + (zona_img.width() - esc_a.width()) / 2),
                            int(zona_img.y() + (zona_img.height() - esc_a.height()) / 2),
                            esc_a
                        )

                if leg_sanea:
                    img_s = QImage(leg_sanea)
                    if not img_s.isNull():
                        esc_s = img_s.scaled(int(zona_img.width()), int(zona_img.height()), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        painter.drawImage(
                            int(r.x() + half_w + (zona_img.width() - esc_s.width()) / 2),
                            int(zona_img.y() + (zona_img.height() - esc_s.height()) / 2),
                            esc_s
                        )

                paginas += 1
                is_first_page = False
                self.progress_bar.setValue(paginas)
                QgsApplication.processEvents()

            for titulo_red, capturas in redes_capturas:
                if self._cancelar:
                    break
                for img_path in capturas:
                    if self._cancelar:
                        break
                    self.lbl_status.setText(f"Estado: Añadiendo página {paginas + 1} de {total_imgs} al PDF...")
                    QgsApplication.processEvents()

                    img = QImage(img_path)
                    if img.isNull():
                        continue
                    if img.width() > 3500:
                        img = img.scaledToWidth(3500, Qt.SmoothTransformation)

                    orient = _ORIENT_PORTRAIT if img.height() > img.width() else _ORIENT_LANDSCAPE

                    is_first = is_first_page
                    if not is_first_page:
                        layout = QPageLayout(QPageSize(_PAGE_SIZE_A4), orient, QMarginsF(8, 8, 8, 8), _UNIT_MILLIMETER)
                        writer.setPageLayout(layout)
                        writer.newPage()
                    else:
                        is_first_page = False

                    r = writer.pageLayout().paintRectPixels(writer.resolution())
                    r = QRect(0, 0, r.width(), r.height())
                    r = draw_header_logos(r)
                    r = draw_feder_footer(r, is_first)

                    f = QFont('Arial', 14)
                    f.setBold(True)
                    painter.setFont(f)
                    painter.drawText(QRectF(r.x(), r.y(), r.width(), 50), Qt.AlignHCenter, titulo_red)

                    zona_img = QRectF(r.x(), r.y() + 60, r.width(), r.height() - 100)
                    img_esc = img.scaled(int(zona_img.width()), int(zona_img.height()), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    painter.drawImage(
                        int(zona_img.x() + (zona_img.width() - img_esc.width()) / 2),
                        int(zona_img.y() + (zona_img.height() - img_esc.height()) / 2),
                        img_esc,
                    )

                    f_pie = QFont('Arial', 8)
                    painter.setFont(f_pie)
                    painter.drawText(QRectF(r.x(), r.y() + r.height() - 30, r.width(), 30), Qt.AlignHCenter, os.path.basename(img_path))
                    paginas += 1
                    self.progress_bar.setValue(paginas)

            painter.end()
            painter = None

            if self._cancelar:
                self.log_message("Unificación de PDF cancelada por el usuario.", "WARNING")
                self.lbl_status.setText("Estado: PDF cancelado.")
                return

            mb = os.path.getsize(out_path) / (1024 * 1024)
            umbral_mb = {150: 20, 200: 30, 300: 50}.get(self.spin_dpi_rec.value(), 30)
            if mb > umbral_mb:
                self.log_message(f"El PDF final pesa {mb:.1f} MB. Podría no entrar por correo.", "WARNING")
                QMessageBox.warning(self, "PDF Pesado", f"El PDF generado pesa {mb:.1f} MB. Ten cuidado si lo envías por correo electrónico.")

            self.log_message(f"PDF generado con éxito ({paginas} páginas, {mb:.1f} MB).", "SUCCESS")
            self.lbl_status.setText("Estado: PDF generado con éxito.")
            self.validar_campos()
            if not silencioso:
                QMessageBox.information(self, "PDF Generado", f"PDF finalizado con {paginas} páginas en:\n{out_path}")
        except Exception as e:
            if painter is not None and painter.isActive():
                try:
                    painter.end()
                except Exception:
                    pass
            self.log_message(f"Error al unificar PDF: {str(e)}", "ERROR")
            QMessageBox.critical(self, "Error", f"Ocurrió un error:\n{str(e)}")
        finally:
            if not silencioso:
                self.bloquear_ui_exportacion(False)


# ============================================================
# PLUGIN PRINCIPAL
# ============================================================
class ExportadorRedesPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.dock = None
        self.action = None

    def initGui(self):
        from qgis.PyQt.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            self._old_app_style = app.styleSheet()
            app.setStyleSheet(self._old_app_style + '''
                QToolTip {
                    background-color: #FFFFFF;
                    color: #333333;
                    border: 1px solid #AAAAAA;
                    border-radius: 4px;
                    padding: 2px 4px;
                }
            ''')

        self.menu_name = "&Exportador de Redes (Beta 0.17.47)"
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self.action = QAction(icon, "Exportador v0.17.47 (Beta)", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(self.menu_name, self.action)


    def unload(self):
        if self.dock:
            try:
                QgsProject.instance().readProject.disconnect(self.dock._on_proyecto_leido)
            except Exception:
                pass
            try:
                QgsProject.instance().cleared.disconnect(self.dock._on_proyecto_limpiado)
            except Exception:
                pass
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
        if self.action:
            self.iface.removePluginMenu(getattr(self, 'menu_name', "&Exportador de Redes (Beta 0.17.47)"), self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None
        if hasattr(self, '_old_app_style'):
            from qgis.PyQt.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.setStyleSheet(self._old_app_style)



    def run(self):
        if self.dock is None:
            self.dock = ExportadorRedesDockWidget(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
            self.dock.visibilityChanged.connect(self._on_dock_visibility)
            self.dock.show()
        else:
            if self.dock.isVisible():
                self.dock.hide()
            else:
                self.dock.show()

    def _on_dock_visibility(self, visible):
        if self.action:
            self.action.setChecked(visible)


# ============================================================
# FUNCIÓN OBLIGATORIA PARA QGIS
# ============================================================
def classFactory(iface):
    return ExportadorRedesPlugin(iface)