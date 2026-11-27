# -*- coding: utf-8 -*-
"""Volcar un pou de la ACA a la capa 231 (pous en alta), tocandolo en el mapa.

Flujo, igual que el volcador de tuberias:

  1. Selecciona el pou de registro (222) que corresponde, el medido en campo.
  2. Activa la herramienta.
  3. Clic sobre el pou de la capa `Pous` de la ACA.

Se crea el pou en alta en la POSICION DEL 222, no en la de la ACA: las
coordenadas del registro oficial suelen estar desplazadas, y un pou en alta es
un pou de registro con otro papel (en Colldejou y Pradell caen a 0,00 m de su
222). Si ya hay un 231 en ese punto, se completa en vez de duplicarlo.

De donde sale cada campo -- las mismas reglas que el paso C5 del Field
Preparer:

  * De la ACA: POU_ID, N_POU, COD_SIST y TIP_POU. El N_POU va TAL CUAL: es el
    nombre oficial y no coincide con el numero del POU_ID (en la Febro el
    DLBF-PR-0202 es el N_POU "004").
  * Del 222, porque manda lo medido en campo: PROF, Z_T, Z_FONS (o Z_T - PROF)
    y CON_BAIXA, que en el 222 se llama NUM_ESC. El CON_BAIXA de la ACA NO se
    usa: es un recuento de 2019-2022 y el campo lo cuenta hoy.
  * MUN_INE y NOM_MUN del 222 si los tiene; si no, los pone el A5.
  * El ID lo pone el A1.

(Marisa, 27/10/2026: *"una herramienta tipo la del volcador de tuberias para
los pozos en alta, para que coja los datos de la capa de la ACA y trasladarlos
a la capa 231"*.)
"""
from qgis.core import (Qgis, QgsCoordinateTransform, QgsFeature,
                       QgsFeatureRequest, QgsGeometry, QgsPointXY, QgsProject,
                       QgsRectangle, QgsWkbTypes)
from qgis.gui import QgsMapTool
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QCursor

#: Radio de busqueda del clic, en pixeles de pantalla.
TOL_PIXELES = 15

#: Un 231 a menos de esto del 222 se considera el mismo pou: se completa.
TOL_MISMO_POU = 0.05

#: Si el pou de la ACA esta mas lejos que esto del 222 seleccionado, se pide
#: confirmacion: lo normal son unos metros, no decenas.
DIST_SOSPECHOSA = 30.0

#: Lo que se toma del registro de la ACA (texto, tal cual).
CAMPOS_ACA = ("POU_ID", "N_POU", "COD_SIST", "TIP_POU")

#: Entero de 64 bits "sin asignar" que deja el formulario de campo. No es dato.
CENTINELA = -9223372036854775808


def _vacio(v):
    if v is None:
        return True
    s = str(v).strip()
    if s in ("", "NULL"):
        return True
    try:
        return int(float(s)) == CENTINELA
    except (TypeError, ValueError):
        return False


def _num(v, entero=False):
    if _vacio(v):
        return None
    try:
        return int(float(v)) if entero else round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _campos(capa):
    return [f.name() for f in capa.fields()]


def es_capa_aca_pous(capa):
    """La capa `Pous` del registro de la ACA."""
    try:
        if capa.type() != 0 or capa.geometryType() != 0:
            return False
        campos = _campos(capa)
    except Exception:
        return False
    return "POU_ID" in campos and "TIP_POU" in campos and \
        not capa.name()[:3].isdigit()


def buscar_capas():
    """(capa 231, capa 222, [capas ACA]) del proyecto."""
    c231 = c222 = None
    aca = []
    for capa in QgsProject.instance().mapLayers().values():
        try:
            nombre = capa.name()
        except Exception:
            continue
        if capa.type() != 0:
            continue
        if nombre.startswith("231") and capa.geometryType() == 0:
            c231 = capa
        elif nombre.startswith("222") and capa.geometryType() == 0:
            c222 = capa
        elif es_capa_aca_pous(capa):
            aca.append(capa)
    return c231, c222, aca


def _punto_en(capa_destino, geom, crs_origen):
    """El punto de `geom` (en `crs_origen`) llevado al CRS de la capa destino."""
    g = QgsGeometry(geom)
    if crs_origen != capa_destino.crs():
        g.transform(QgsCoordinateTransform(crs_origen, capa_destino.crs(),
                                           QgsProject.instance()))
    pt = g.asMultiPoint()[0] if g.isMultipart() else g.asPoint()
    return QgsPointXY(pt)


def _geom_para(capa, pt):
    """Geometria de punto con el tipo que pide la capa (Z, multi)."""
    g = QgsGeometry.fromPointXY(pt)
    tipo = capa.wkbType()
    if QgsWkbTypes.hasZ(tipo):
        g.get().addZValue(0)
    if QgsWkbTypes.isMultiType(tipo):
        g.convertToMultiType()
    return g


def calcular_volcado(capa231, pou222, capa222, pou_aca, capa_aca,
                     no_pisar=True):
    """Que se escribiria. Devuelve (fid_231 o None, {campo: valor}, punto, avisos).

    No escribe nada: el mismo calculo sirve para comprobarlo y para aplicarlo.
    `fid_231` es el 231 que ya hay en ese punto, o None si hay que crearlo.
    """
    avisos = []
    campos = _campos(capa231)
    pt = _punto_en(capa231, pou222.geometry(), capa222.crs())

    # Ya hay un 231 en ese pou?
    existente = None
    rect = QgsRectangle(pt.x() - TOL_MISMO_POU, pt.y() - TOL_MISMO_POU,
                        pt.x() + TOL_MISMO_POU, pt.y() + TOL_MISMO_POU)
    for f in capa231.getFeatures(QgsFeatureRequest().setFilterRect(rect)):
        existente = f
        break

    actual = {}
    if existente is not None:
        actual = {c: existente[c] for c in campos}

    nuevos = {}

    def poner(campo, valor):
        if campo not in campos or _vacio(valor):
            return
        if existente is not None and no_pisar and not _vacio(actual.get(campo)):
            if str(actual.get(campo)).strip() != str(valor).strip():
                avisos.append("%s ya tenia %s (no se pisa; la ACA/el 222 "
                              "dicen %s)" % (campo, actual.get(campo), valor))
            return
        nuevos[campo] = valor

    # De la ACA, como texto tal cual.
    for c in CAMPOS_ACA:
        v = pou_aca[c] if c in _campos(capa_aca) else None
        poner(c, None if _vacio(v) else str(v).strip())
    if _vacio(pou_aca["POU_ID"]):
        avisos.append("ese pou de la ACA NO tiene POU_ID: el CODI_XARXA de la "
                      "red no podra colgar de el")

    # Del 222: lo medido en campo.
    c222 = _campos(capa222)
    prof = _num(pou222["PROF"]) if "PROF" in c222 else None
    z_t = _num(pou222["Z_T"]) if "Z_T" in c222 else None
    z_fons = _num(pou222["Z_FONS"]) if "Z_FONS" in c222 else None
    if z_fons is None and z_t is not None and prof is not None:
        z_fons = round(z_t - prof, 2)
    poner("PROF", prof)
    poner("Z_T", z_t)
    poner("Z_FONS", z_fons)
    if "NUM_ESC" in c222:
        poner("CON_BAIXA", _num(pou222["NUM_ESC"], entero=True))
    for c in ("MUN_INE", "NOM_MUN"):
        if c in c222:
            poner(c, pou222[c])

    # Ese POU_ID ya esta puesto en OTRO 231?
    pou_id = nuevos.get("POU_ID")
    if pou_id and "POU_ID" in campos:
        for f in capa231.getFeatures():
            if existente is not None and f.id() == existente.id():
                continue
            if str(f["POU_ID"]).strip() == pou_id:
                d = f.geometry().distance(QgsGeometry.fromPointXY(pt))
                return None, None, pt, ["el POU_ID %s ya esta en otro pou de "
                                        "la 231, a %.1f m. No hago nada: "
                                        "revisa cual es el bueno"
                                        % (pou_id, d)]

    return (existente.id() if existente is not None else None), nuevos, pt, \
        avisos


def aplicar_volcado(capa231, fid, nuevos, pt):
    """Escribe el volcado. Devuelve (ok, mensaje)."""
    tenia_edicion = capa231.isEditable()
    if not tenia_edicion:
        capa231.startEditing()
    capa231.beginEditCommand("Volcar pou de la ACA a la 231")
    try:
        if fid is None:
            f = QgsFeature(capa231.fields())
            f.setGeometry(_geom_para(capa231, pt))
            for campo, valor in nuevos.items():
                f.setAttribute(campo, valor)
            if not capa231.addFeature(f):
                raise RuntimeError("la capa no acepta el elemento nuevo")
            que = "creado"
        else:
            for campo, valor in nuevos.items():
                capa231.changeAttributeValue(
                    fid, capa231.fields().indexOf(campo), valor)
            que = "completado"
        capa231.endEditCommand()
    except Exception as e:
        capa231.destroyEditCommand()
        return False, "no he podido escribirlo: %s" % e

    if tenia_edicion:
        return True, "%s (sin guardar, la capa estaba en edicion)" % que
    if capa231.commitChanges():
        return True, "%s y guardado" % que
    return False, "no se ha guardado: %s" % "; ".join(
        capa231.commitErrors()[:2])


class PousAltaMapTool(QgsMapTool):
    """Con un 222 seleccionado, clic sobre un pou de la ACA -> 231."""

    def __init__(self, canvas, plugin):
        super().__init__(canvas)
        self.canvas = canvas
        self.plugin = plugin
        self.setCursor(QCursor(Qt.CrossCursor))

    def _bar(self, level, msg):
        niveles = {"info": Qgis.Info, "warn": Qgis.Warning,
                   "ok": Qgis.Success, "err": Qgis.Critical}
        self.plugin.iface.messageBar().pushMessage(
            "Pou en alta", msg, level=niveles.get(level, Qgis.Info),
            duration=8 if level in ("warn", "err") else 5)

    def _pou_aca_bajo_clic(self, capas_aca, click_map):
        tol = self.canvas.mapUnitsPerPixel() * TOL_PIXELES
        crs_mapa = self.canvas.mapSettings().destinationCrs()
        mejor = None
        for capa in capas_aca:
            punto = click_map
            if crs_mapa != capa.crs():
                punto = QgsCoordinateTransform(
                    crs_mapa, capa.crs(), QgsProject.instance()).transform(
                        click_map)
            gp = QgsGeometry.fromPointXY(QgsPointXY(punto))
            # la tolerancia esta en unidades del mapa; si la capa esta en
            # grados se queda corta, pero la ACA viene en 25831 como el mapa
            rect = QgsRectangle(punto.x() - tol, punto.y() - tol,
                                punto.x() + tol, punto.y() + tol)
            for f in capa.getFeatures(QgsFeatureRequest().setFilterRect(rect)):
                if not f.hasGeometry():
                    continue
                d = f.geometry().distance(gp)
                if mejor is None or d < mejor[0]:
                    mejor = (d, capa, f)
        return mejor

    def canvasReleaseEvent(self, event):
        c231, c222, capas_aca = buscar_capas()
        if c231 is None or c222 is None:
            self._bar("warn", "Faltan capas en el proyecto: hace falta la 231 "
                              "y la 222.")
            return
        if not capas_aca:
            self._bar("warn", "No encuentro la capa Pous de la ACA (con "
                              "POU_ID y TIP_POU) cargada en el proyecto.")
            return

        sel = c222.selectedFeatures()
        if len(sel) != 1:
            self._bar("warn", "Selecciona antes UN pou de registro en la 222 "
                              "(ahora hay %d) y luego pulsa el pou de la ACA."
                      % len(sel))
            return
        pou222 = sel[0]

        mejor = self._pou_aca_bajo_clic(
            capas_aca, self.toMapCoordinates(event.pos()))
        if mejor is None:
            self._bar("info", "No hay ningun pou de la ACA bajo el clic.")
            return
        _d, capa_aca, pou_aca = mejor

        # Lejos del 222? Puede ser el pou equivocado.
        p222 = _punto_en(capa_aca, pou222.geometry(), c222.crs())
        dist = pou_aca.geometry().distance(QgsGeometry.fromPointXY(p222))
        if dist > DIST_SOSPECHOSA:
            from qgis.PyQt.QtWidgets import QMessageBox
            r = QMessageBox.question(
                self.canvas.window(), "Pou en alta",
                "El pou %s de la ACA esta a %.0f m del pou de registro "
                "seleccionado.\n\nLo normal son unos metros. Volcarlo igual?"
                % (pou_aca["POU_ID"], dist))
            if r != QMessageBox.Yes:
                return

        fid, nuevos, pt, avisos = calcular_volcado(
            c231, pou222, c222, pou_aca, capa_aca,
            no_pisar=getattr(self.plugin, "no_pisar", True))
        if nuevos is None:
            self._bar("err", avisos[0])
            return
        if not nuevos:
            self._bar("info", "Nada que escribir: ese 231 ya tenia todo. %s"
                      % " · ".join(avisos))
            return

        ok, msg = aplicar_volcado(c231, fid, nuevos, pt)
        if not ok:
            self._bar("err", msg)
            return
        resumen = "%s %s: %s (%s) · a %.1f m del registro ACA" % (
            nuevos.get("POU_ID") or pou_aca["POU_ID"] or "pou",
            nuevos.get("TIP_POU") or "", msg, ", ".join(sorted(nuevos)), dist)
        if avisos:
            self._bar("warn", resumen + " · OJO: " + " · ".join(avisos))
        else:
            self._bar("ok", resumen)
        c222.removeSelection()
        self.canvas.refresh()
