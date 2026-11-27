# -*- coding: utf-8 -*-
"""Girar el sentido de un tram tocandolo en el mapa.

Invertir la linea a mano deja la mitad del trabajo hecho: la geometria queda
al reves y los atributos siguen apuntando al extremo de antes. El `ID_NODE1`
nombra el nodo del final, la cota de entrada pasa por ser la de salida y la
pendiente conserva el signo. **No da ningun error**: el mapa se ve bien y los
datos mienten.

Esto lo hace entero de una vez:

  * invierte la geometria;
  * intercambia los pares que van por extremo -- `ID_NODE1/2`, `Z_NODE1/2`,
    `PROF_NODE1/2`, `prof_colector1/2` y los dos valores de `prof_interp`;
  * recalcula `LONGIT` midiendo la geometria;
  * recalcula `PENDENT` con la formula del propio dato:

        PENDENT = (Z_NODE1 - Z_NODE2) / LONGIT * 1000        (por mil)

    Comprobada contra los 82 tramos de Arboli que ya la cumplian. Se redondea
    segun el tipo de la columna: entero en saneamiento, que el pliego la
    declara `N(5)`, y con dos decimales en potable.

No decide si un tram esta al reves: eso lo mira una persona con las flechas de
la capa madre delante. Esto solo ejecuta la decision sin dejarse nada.

(Marisa, 11/09/2026: *"necesito una herramienta que gire el tramo de sentido y
que ademas cambie los datos... y que la longitud la vuelva a calcular"*.)
"""
from qgis.core import (Qgis, QgsFeatureRequest, QgsGeometry, QgsPointXY,
                       QgsProject, QgsRectangle)
from qgis.gui import QgsMapTool
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QCursor

#: Capas de tramos sobre las que trabaja.
CAPAS_TRAM = ("211", "111")

#: Pares de campos que se intercambian.
PARES = (
    ("ID_NODE1", "ID_NODE2"),
    ("Z_NODE1", "Z_NODE2"),
    ("PROF_NODE1", "PROF_NODE2"),
    ("prof_colector1", "prof_colector2"),
)

SEP_INTERP = "-"

#: Radio de busqueda del clic, en pixeles de pantalla.
TOL_PIXELES = 15


def _num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _es_entero(capa, campo):
    i = capa.fields().indexOf(campo)
    if i < 0:
        return False
    return "int" in capa.fields()[i].typeName().lower()


def _gira_interp(v):
    """`prof_interp` guarda los dos valores unidos por guion."""
    if v is None or str(v).strip() in ("", "NULL"):
        return v
    partes = str(v).split(SEP_INTERP)
    if len(partes) != 2:
        return v
    try:
        float(partes[0])
        float(partes[1])
    except ValueError:
        return v
    return SEP_INTERP.join([partes[1].strip(), partes[0].strip()])


def calcular_giro(capa, feat):
    """Que quedaria al girar. Devuelve (dict de campos nuevos, geometria, aviso).

    No escribe nada: asi el mismo calculo sirve para enseñarlo antes y para
    aplicarlo despues, sin que se puedan separar.
    """
    g = feat.geometry()
    if g is None or g.isNull() or g.isEmpty():
        return None, None, "ese tram no tiene geometria"
    if g.isMultipart() and len(g.asMultiPolyline()) > 1:
        return None, None, ("ese tram es MULTIPARTE (%d lineas): eso se "
                            "arregla antes de girarlo"
                            % len(g.asMultiPolyline()))

    campos = [f.name() for f in capa.fields()]
    largo = g.length()
    nuevos = {}
    for a, b in PARES:
        if a in campos and b in campos:
            nuevos[a], nuevos[b] = feat[b], feat[a]
    if "prof_interp" in campos:
        nuevos["prof_interp"] = _gira_interp(feat["prof_interp"])
    if "LONGIT" in campos:
        nuevos["LONGIT"] = round(largo, 2)
    if "PENDENT" in campos:
        z1 = _num(nuevos.get("Z_NODE1"))
        z2 = _num(nuevos.get("Z_NODE2"))
        if z1 is not None and z2 is not None and largo > 0:
            p = (z1 - z2) / largo * 1000.0
            nuevos["PENDENT"] = (int(round(p)) if _es_entero(capa, "PENDENT")
                                 else round(p, 2))
        else:
            # Sin las dos cotas no hay pendiente que dar. Dejarla como estaba
            # seria peor: conservaria el signo de antes de girar.
            nuevos["PENDENT"] = None

    geom_nueva = QgsGeometry(g.constGet().clone().reversed())
    return nuevos, geom_nueva, None


def aplicar_giro(capa, feat, nuevos, geom_nueva):
    """Escribe el giro. Devuelve (ok, mensaje)."""
    tenia_edicion = capa.isEditable()
    if not tenia_edicion:
        capa.startEditing()
    # Un solo comando de edicion: asi el Deshacer de QGIS lo deshace entero,
    # no campo a campo.
    capa.beginEditCommand("Girar el sentido del tram")
    try:
        capa.changeGeometry(feat.id(), geom_nueva)
        for campo, valor in nuevos.items():
            idx = capa.fields().indexOf(campo)
            if idx >= 0:
                capa.changeAttributeValue(feat.id(), idx, valor)
        capa.endEditCommand()
    except Exception as e:
        capa.destroyEditCommand()
        return False, "no he podido girarlo: %s" % e

    if tenia_edicion:
        # La capa ya estaba en edicion: se deja en el buffer para que decida
        # ella cuando guardar, y para que el Deshacer siga funcionando.
        return True, "girado (queda sin guardar, la capa estaba en edicion)"
    if capa.commitChanges():
        return True, "girado y guardado"
    return False, "no se ha guardado: %s" % "; ".join(capa.commitErrors()[:2])


class GirarMapTool(QgsMapTool):
    """Clic sobre un tram -> le da la vuelta."""

    def __init__(self, canvas, plugin, buscar_capa):
        super().__init__(canvas)
        self.canvas = canvas
        self.plugin = plugin
        self._buscar_capa = buscar_capa
        self.setCursor(QCursor(Qt.CrossCursor))

    def _bar(self, level, msg):
        niveles = {"info": Qgis.Info, "warn": Qgis.Warning,
                   "ok": Qgis.Success, "err": Qgis.Critical}
        self.plugin.iface.messageBar().pushMessage(
            "Girar tram", msg, level=niveles.get(level, Qgis.Info),
            duration=6 if level in ("warn", "err") else 5)

    def _capas(self):
        out = []
        for capa in QgsProject.instance().mapLayers().values():
            try:
                nombre = capa.name()
            except Exception:
                continue
            if not nombre[:3].isdigit() or nombre[:3] not in CAPAS_TRAM:
                continue
            if capa.geometryType() != 1:      # solo lineas
                continue
            out.append(capa)
        return out

    def canvasReleaseEvent(self, event):
        capas = self._capas()
        if not capas:
            self._bar("warn", "No encuentro ninguna capa de trams (111 o 211) "
                              "cargada en el proyecto.")
            return

        click_map = self.toMapCoordinates(event.pos())
        tol = self.canvas.mapUnitsPerPixel() * TOL_PIXELES

        mejor = None
        for capa in capas:
            punto = click_map
            if self.canvas.mapSettings().destinationCrs() != capa.crs():
                from qgis.core import QgsCoordinateTransform
                xf = QgsCoordinateTransform(
                    self.canvas.mapSettings().destinationCrs(), capa.crs(),
                    QgsProject.instance())
                punto = xf.transform(click_map)
            gp = QgsGeometry.fromPointXY(QgsPointXY(punto))
            rect = QgsRectangle(punto.x() - tol, punto.y() - tol,
                                punto.x() + tol, punto.y() + tol)
            for f in capa.getFeatures(QgsFeatureRequest().setFilterRect(rect)):
                if not f.hasGeometry():
                    continue
                d = f.geometry().distance(gp)
                if mejor is None or d < mejor[0]:
                    mejor = (d, capa, f)

        if mejor is None:
            self._bar("info", "No hay ningun tram bajo el clic.")
            return

        _d, capa, feat = mejor
        ident = feat["ID"] if "ID" in [x.name() for x in capa.fields()] else feat.id()

        nuevos, geom_nueva, aviso = calcular_giro(capa, feat)
        if aviso:
            self._bar("warn", "%s: %s" % (ident, aviso))
            return

        antes_p = feat["PENDENT"] if "PENDENT" in nuevos else None
        ok, msg = aplicar_giro(capa, feat, nuevos, geom_nueva)
        if not ok:
            self._bar("err", "%s: %s" % (ident, msg))
            return

        detalle = ""
        if "PENDENT" in nuevos:
            detalle = " · PENDENT %s -> %s" % (antes_p, nuevos["PENDENT"])
        if "LONGIT" in nuevos:
            detalle += " · LONGIT %s" % nuevos["LONGIT"]
        self._bar("ok", "%s %s: %s%s"
                  % (capa.name()[:3], ident, msg, detalle))
        self.canvas.refresh()
