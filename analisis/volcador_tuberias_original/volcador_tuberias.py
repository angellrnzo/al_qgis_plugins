# -*- coding: utf-8 -*-
"""Plugin QGIS — Volcador Tuberias a Trams (lote SI-014/23 Tarragona).

Flujo:
  1. Selecciona uno o varios trams en la capa 211_Trams_Sanejament.
  2. Activa el boton del plugin.
  3. Haz clic sobre una tuberia de la capa madre en el mapa.
  4. De esa tuberia se vuelcan DIAMETRE + MATERIAL a los trams seleccionados.
  5. Y de una sola pasada, a cada tram se le ponen SUS DOS profundidades:
     se buscan solas las flechas que arrancan en sus dos extremos.

Lo de las dos profundidades importa: un tram tiene un pou en cada punta y una
profundidad distinta en cada una -- esa diferencia es la pendiente. Antes
habia que pinchar las dos flechas y, si te dejabas una, el tram se quedaba a
medias sin que nada lo dijera.

Edicion automatica: si la capa destino no esta en edicion, la abre,
guarda los cambios y la cierra al terminar.
"""
import math
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon, QCursor
from qgis.PyQt.QtWidgets import QAction, QInputDialog
from qgis.core import (
    QgsProject, QgsFeatureRequest, QgsRectangle, QgsGeometry,
    QgsPointXY, Qgis, QgsWkbTypes, QgsMapLayer
)
from qgis.gui import QgsMapTool


# Configuracion: patrones de nombre de capa (case-insensitive, substring)
CAPA_DESTINO_PATTERNS = ['211_trams_sanejament', '211_trams']
CAPA_ORIGEN_PATTERNS = ['tuberias', 'tuberies', 'tuberia', 'tuberi']

import re

try:
    from .dominios import (Dominios, es_saneamiento, del_comentario,
                           prof_del_comentario, prof_del_embornal)
except (ImportError, ValueError):
    from dominios import (Dominios, es_saneamiento, del_comentario,
                          prof_del_comentario, prof_del_embornal)

#: Distancia maxima para dar por bueno que el arranque de la flecha coincide
#: con un extremo del tram. Medido en Alcover, Vilallonga y Prat de Comte: la
#: mediana es 0,00 m, asi que con medio metro sobra.
TOL_EXTREMO = 0.60

#: El campo de la madre con la profundidad medida en campo, y los dos del 211
#: donde va segun a que extremo corresponda.
CAMPO_PROF_ORIGEN = 'Profundidad'

#: Profundidad corregida en gabinete, que MANDA sobre la de campo.
#:
#: La escribe el control E31b del Field Preparer cuando sube un colector que
#: entraba por debajo del fondo de su pou. Va en columna aparte a proposito:
#: `Profundidad` es el dato de campo y no se toca nunca -- es la prueba de que
#: se midio mal --, pero si el volcador siguiera leyendo solo ese campo, cada
#: pasada desharia el arreglo sin avisar. (Idea de Marisa, 11/09/2026.)
CAMPO_PROF_CORREGIDA = 'prof_corregida'
CAMPO_PROF_1 = 'prof_colector1'      # entrada: extremo de donde sale el agua
CAMPO_PROF_2 = 'prof_colector2'      # salida:  extremo donde llega


def _carpetas_de(*capas):
    """Las carpetas donde buscar los CSV de dominio: las de las propias capas."""
    out = []
    for c in capas:
        if c is None:
            continue
        try:
            d = os.path.dirname(c.source().split('|')[0])
            if d and d not in out:
                out.append(d)
        except Exception:
            pass
    return out


def _extremos_de(geom):
    """(inicio, fin) de una linea, o (None, None)."""
    if geom is None or geom.isNull() or geom.isEmpty():
        return None, None
    try:
        partes = geom.asMultiPolyline() if geom.isMultipart() else [geom.asPolyline()]
    except Exception:
        return None, None
    partes = [p for p in partes if p and len(p) >= 2]
    if not partes:
        return None, None
    return QgsPointXY(partes[0][0]), QgsPointXY(partes[-1][-1])


def _a_que_extremo(flecha, tram):
    """¿La profundidad de esta flecha es del extremo 1 o del 2 del tram?

    La flecha se dibuja EN EL POZO donde esta el operario y sale hacia fuera,
    asi que su punto de ARRANQUE cae sobre el extremo del tram al que
    corresponde lo que anoto. Medido sobre 4.300 flechas en tres municipios: el
    arranque queda a mediana 0,00 m de un extremo de tram, y el final a la
    longitud de la flecha (2,5-3,3 m).

    Esto evita tener que interpretar el "Aguas Arriba / Aguas Abajo", que es lo
    que obligo a revisar Castello d'Empuries a mano.

    Devuelve 1, 2 o None si no esta claro.
    """
    fa, _fb = _extremos_de(flecha)
    ta, tb = _extremos_de(tram)
    if fa is None or ta is None:
        return None

    def d(p, q):
        return ((p.x() - q.x()) ** 2 + (p.y() - q.y()) ** 2) ** 0.5

    d1, d2 = d(fa, ta), d(fa, tb)
    if min(d1, d2) > TOL_EXTREMO:
        return None
    if abs(d1 - d2) < 1e-6:
        return None
    return 1 if d1 < d2 else 2



#: Angulo maximo entre la flecha y el tram para dar por hecho que la flecha
#: habla de ESE tram y no del de al lado. Un pou con tres colectores tiene
#: tres flechas que arrancan en el mismo punto: lo unico que las distingue es
#: hacia donde apuntan.
ANGULO_MAX = 1.05                     # 60 grados en radianes


def _vertices_de(geom):
    """Todos los vertices de la linea, en orden. Vale simple, multi y con Z."""
    if geom is None or geom.isNull() or geom.isEmpty():
        return []
    try:
        return [QgsPointXY(v) for v in geom.vertices()]
    except Exception:
        return []


def _rumbo(p, q):
    """Angulo del segmento p->q, en radianes."""
    return math.atan2(q.y() - p.y(), q.x() - p.x())


def _dif_angular(a, b):
    """Diferencia entre dos rumbos, siempre entre 0 y pi."""
    d = abs(a - b) % (2 * math.pi)
    return d if d <= math.pi else 2 * math.pi - d


def _prof_valida(bruto, campo=CAMPO_PROF_ORIGEN):
    """(profundidad, aviso) leyendo la COLUMNA. None si no vale.

    ⚠ Hay versiones de la plantilla en las que la columna trae **su propio
    nombre** dentro: en la madre de Mont-roig `Profundidad` vale literalmente
    "Profundidad" en las 965 flechas. Eso no es un dato ni un error del
    operario: es la columna vacia con otra cara. Se trata como vacia y en
    silencio, para no gritar 965 veces.
    """
    if bruto in (None, ''):
        return None, None
    s = str(bruto).strip()
    if not s or s.upper() in ('NULL', 'NONE'):
        return None, None
    if _norm_field(s) == _norm_field(campo):
        return None, None
    try:
        v = float(s.replace(',', '.'))
    except (TypeError, ValueError):
        return None, "no entiendo la profundidad %r" % bruto
    if not (0 < v < 10):
        return None, ("trae %.2f m, y eso no es una profundidad de colector"
                      % v)
    return v, None


def _prof_de_la_flecha(feat, idx_prof, idx_com, idx_corr=-1):
    """La profundidad de una flecha, por orden de quien manda.

      1. `prof_corregida`, si el gabinete la ha corregido;
      2. la columna `Profundidad`, si trae un numero de verdad;
      3. el `Comentario`, que es donde la escriben cuando la columna no esta
         o esta inservible.

    Marisa: *"en Mont-roig hay varias versiones de plantilla, nos podemos
    encontrar las medidas en comentario o en la otra"*. Y sobre la primera:
    *"en caso de que se vuelva a pasar el volcador que coja la segunda
    columna, la corregida"*.

    Devuelve (metros, explicacion) o (None, motivo).
    """
    if idx_corr != -1:
        v, _aviso = _prof_valida(feat[idx_corr], CAMPO_PROF_CORREGIDA)
        if v is not None:
            return v, "de la columna %s (corregida en gabinete)" % \
                CAMPO_PROF_CORREGIDA
    if idx_prof != -1:
        v, aviso = _prof_valida(feat[idx_prof])
        if v is not None:
            return v, "de la columna %s" % CAMPO_PROF_ORIGEN
        if aviso:
            return None, aviso
    if idx_com != -1:
        return prof_del_comentario(feat[idx_com])
    return None, "no hay ni columna de profundidad ni comentario"


def _flechas_de_los_extremos(capa_origen, geom_tram, idx_prof, red_ref,
                             idx_red, idx_com=-1, capa_emb=None,
                             interp=None, xf_a_madre=None, xf_a_tram=None,
                             idx_corr=-1):
    """Las profundidades de LOS DOS extremos del tram, de una sola pasada.

    Cada extremo del tram es un pou, y en cada pou el operario dibujo una
    flecha por colector. La flecha ARRANCA en el pou y sale hacia fuera
    siguiendo el colector, asi que:

      * el extremo del que habla = aquel sobre el que cae su arranque;
      * cual de las flechas del pou es la de ESTE tram = la que apunta hacia
        donde se va el tram. **Un pou con tres colectores tiene tres flechas
        saliendo del mismo punto**, y sin mirar la direccion se cogeria la del
        tram de al lado sin enterarse.

    El vertice 0 del tram es su NODE1: comprobado sobre 404 trams de
    Colldejou, el Mila y la Vilella Alta, 404 coinciden y 0 salen cruzados.

    ⚠ `geom_tram` viene en el CRS DEL TRAM (metros), no en el de la madre.
    `xf_a_madre` y `xf_a_tram` son las dos transformaciones entre ellos, y solo
    hacen falta cuando no coinciden -- lo normal, porque la madre va en 4326.

    Si se pasa `interp` -- (capa_destino, capa_cd, capa_pous,
    xf_a_madre, xf_a_tram) --,
    las puntas que
    se queden sin dato se intentan **interpolar**: ver
    `_prof_interpolada_en_cd`. Sin `interp` no se interpola nada, y asi es como
    se llama a si misma desde la interpolacion (si no, seria recursion sin fin).

    Devuelve (prof1, prof2, avisos, interpolados), donde `interpolados` son los
    indices (0 y/o 1) de las puntas cuyo valor se ha CALCULADO y no medido.
    """
    vs = _vertices_de(geom_tram)
    if len(vs) < 2:
        return None, None, ["el tram no tiene geometria utilizable"], []

    #: (punto del extremo, vertice de al lado hacia dentro del tram)
    extremos = [(vs[0], vs[1]), (vs[-1], vs[-2])]
    #: En que proyeccion estan `vs`: la del tram, que es la que se mide.
    crs_tram = interp[0].crs() if interp else None
    salida = [None, None]
    avisos = []

    for i, (pt, vecino) in enumerate(extremos):
        # ⚠ TODO ESTO SE MIDE EN METROS, en la proyeccion del tram.
        #
        # Antes se llevaba el tram a la proyeccion de la MADRE y se comparaba
        # alli. Cuando la madre esta en 4326 -- que es lo normal, la plantilla
        # la pone asi a proposito -- los 0,60 m de `TOL_EXTREMO` pasaban a ser
        # **0,60 GRADOS, unos 66 km**, y el filtro dejaba de filtrar: en
        # Vilaplana las 100 puntas tenian las 86 flechas del municipio como
        # candidatas, y en 27 de ellas la flecha elegida estaba a mas de 1 m,
        # la peor a **144 m**. Salian 50 de 50 trams "con las dos
        # profundidades" y ninguna era de fiar. (Medido el 09/09/2026.)
        #
        # Ahora la geometria del tram llega en SU proyeccion, el rectangulo de
        # busqueda se lleva a la de la madre solo para pedirle las flechas, y
        # los vertices de cada candidata se traen de vuelta a metros antes de
        # medir nada.
        rect = QgsRectangle(pt.x() - TOL_EXTREMO, pt.y() - TOL_EXTREMO,
                            pt.x() + TOL_EXTREMO, pt.y() + TOL_EXTREMO)
        if xf_a_madre is not None:
            try:
                rect = xf_a_madre.transformBoundingBox(rect)
            except Exception:
                pass
        rumbo_tram = _rumbo(pt, vecino)
        mejor, mejor_ang = None, None
        for f in capa_origen.getFeatures(
                QgsFeatureRequest().setFilterRect(rect)):
            gf = f.geometry()
            if gf is None or gf.isNull():
                continue
            if xf_a_tram is not None:
                gf = QgsGeometry(gf)
                try:
                    gf.transform(xf_a_tram)
                except Exception:
                    continue
            fv = _vertices_de(gf)
            if len(fv) < 2:
                continue
            # Tiene que ARRANCAR aqui, no solo pasar cerca.
            d = ((fv[0].x() - pt.x()) ** 2 + (fv[0].y() - pt.y()) ** 2) ** 0.5
            if d > TOL_EXTREMO:
                continue
            # Y ser de la misma red: la madre lleva potable y saneamiento
            # juntas, y en un cruce pueden arrancar las dos en el mismo punto.
            if idx_red != -1 and red_ref is not None:
                if str(f[idx_red]) != str(red_ref):
                    continue
            ang = _dif_angular(_rumbo(fv[0], fv[-1]), rumbo_tram)
            if mejor_ang is None or ang < mejor_ang:
                mejor, mejor_ang = f, ang

        if mejor is None:
            # No hay flecha: puede que el tram muera en un embornal, y el
            # embornal si trae su medida.
            v, motivo = _prof_del_embornal_en(capa_emb, pt, crs_tram)
            if v is not None:
                salida[i] = v
                avisos.append("en el extremo %d no hay flecha, pero %s"
                              % (i + 1, motivo))
            elif motivo:
                avisos.append("en el extremo %d no arranca ninguna flecha y %s"
                              % (i + 1, motivo))
            else:
                avisos.append("en el extremo %d no arranca ninguna flecha"
                              % (i + 1))
            continue
        if mejor_ang > ANGULO_MAX:
            avisos.append(
                "en el extremo %d la flecha mas parecida se va %d grados del "
                "tram, no me fio de que sea la suya"
                % (i + 1, int(round(mejor_ang * 57.2958))))
            continue
        v, motivo = _prof_de_la_flecha(mejor, idx_prof, idx_com, idx_corr)
        if v is None:
            avisos.append("extremo %d: %s" % (i + 1, motivo))
        salida[i] = v

    # -- segunda pasada: las puntas sin dato, interpoladas ---------------
    #
    # Va DESPUES del bucle a proposito: para interpolar en una punta hace falta
    # la profundidad de la OTRA, y esa no se conoce hasta terminar la primera
    # pasada.
    interpolados = []
    if interp is not None and (salida[0] is None) != (salida[1] is None):
        capa_destino, capa_cd, capa_pous, xf_a_madre, xf_a_tram = interp
        i = 0 if salida[0] is None else 1
        v, motivo = _prof_interpolada_en_cd(
            extremos[i][0], geom_tram, salida[1 - i], capa_destino,
            capa_origen, idx_prof, red_ref, idx_red, idx_com, capa_emb,
            capa_cd, capa_pous, xf_a_madre, xf_a_tram, idx_corr)
        if v is not None:
            salida[i] = v
            interpolados.append(i)
            avisos.append("extremo %d: %s" % (i + 1, motivo))
        elif motivo:
            avisos.append("extremo %d: %s" % (i + 1, motivo))

    return salida[0], salida[1], avisos, interpolados


#: Los embornals. Un tram que muere en un embornal no tiene pou, asi que no
#: tiene flecha -- pero el embornal SI trae su medida, en `Z_NODE`, y el pliego
#: define ese campo como **la cota inferior del tubo**: exactamente lo que
#: necesita el tram en esa punta. Y un embornal tiene UN solo lateral, asi que
#: no hay la ambiguedad del pou, donde entran varios colectores a distinta
#: altura (por eso la profundidad del pou no se deriva al colector).
#:
#: ⚠ Las unidades se interpretan AQUI y no se espera al paso D1 del Field
#: Preparer: ese se lanza cuando el municipio ya esta digitalizado, y el
#: volcador lo usan los chicos mientras digitalizan. (Marisa, 07/09/2026:
#: *"no puedes depender del D1 [...] a los chicos no les voy a decir que lo
#: pasen, es un mareo"*.)
CAPA_EMB_PATTERNS = ['223_embornals_sanejament', '223_embornals', '223_']
#: Donde vive la profundidad del embornal, EN ESTE ORDEN.
#:
#: ⚠ Cambia de sitio segun por donde vaya el municipio: en campo llega dentro
#: de `Z_NODE`, y el paso **D5** del Field Preparer la saca a `PROF` y deja el
#: `Z_NODE` vacio para que el A3/A4 lo calcule como `Z_T - PROF`. O sea que el
#: mismo dato esta en un campo o en otro segun si el D5 ya ha pasado.
#: (Visto en Arboli el 07/09/2026, con el D5 recien pasado: `Z_NODE` vacio y
#: `PROF` con las 36.)
CAMPOS_PROF_EMB = ('PROF', 'Z_NODE')

#: Las conexiones de saneamiento: el CD. Un tram que muere en un CD no tiene
#: pou ni embornal, asi que no hay nada que medir ahi -- por eso hasta ahora la
#: punta se quedaba vacia.
CAPA_CD_PATTERNS = ['225_connexions_sanejament', '225_connexions', '225_']

#: Donde se anota que una profundidad la ha CALCULADO la herramienta en vez de
#: medirla un operario. Vale '1', '2' o '1,2' segun la punta.
#:
#: ⚠ Columna INTERNA nuestra, como las `prof_colector`: **se borra antes de
#: entregar**. La primera version escribia esto en el `OBSERVACIO` y Marisa lo
#: paro en el sitio (09/09/2026): *"en observaciones del tramo no, porque esa
#: columna se entrega y es mucha mierda"*. Tenia razon -- el `OBSERVACIO` es un
#: campo del pliego y va al cliente; una nota nuestra ahi es basura en el
#: entregable.
#: Cual de las dos puntas lleva una profundidad CALCULADA por la herramienta
#: en un CD, en vez de medida en campo. Vale '1', '2' o **'1-2'**.
#:
#: ⚠ El separador es un GUION y no una coma. Con coma, un '1,2' se lee en
#: español como *uno coma dos*, o sea como una profundidad de 1,2 m en una
#: columna que esta al lado de dos columnas de profundidades. Lo vio Marisa el
#: 09/09/2026: *"lo de 1,2 puede inducir a error, mejor ponle guion"*.
#:
#: El valor en si va en la `prof_colector` de su punta, con los medidos; esta
#: columna solo dice cuales no se midieron.
#:
#: ⚠ Se probo lo contrario -- el valor calculado en columnas propias
#: `prof_interp1/2` y las `prof_colector` solo con lo medido -- el 09/09/2026,
#: a peticion de Marisa. Al verlo funcionando lo revirtio ella misma: *"ahora
#: entiendo el sentido de esa columna, y no me parece mala idea... quiza lo
#: cambies en Arboli a como estaba antes y asi te vale lo que tienes en el
#: resto de municipios"*. Pesaba mas no tener que repasar 140 municipios que
#: la separacion de columnas.
#:
#: ⚠ Interna: se borra antes de entregar, como las `prof_colector`.
CAMPO_INTERP = 'prof_interp'
#: Con que se separan las dos puntas cuando las dos son interpoladas.
SEP_INTERP = '-'


#: El tipo de red NO esta en la capa madre: esta en cada pou de la 222.
CAPA_POUS_PATTERNS = ['222_pous_registre_sanejament', '222_pous', '222_']
CAMPO_TIPUS = 'TIPUS_XARXA'

#: Los pous lo guardan en mayusculas ('RESIDUAL') y el 211 lo lleva con la
#: primera en mayuscula ('Residual'). No es cosmetica: el 211 es texto libre,
#: sin desplegable que lo corrija, y la forma buena es la que ya se ha
#: entregado -- 8.478 valores del lote escritos `Residual` / `Pluvial` /
#: `Unitaria` frente a un puñado de erratas.
_TIPUS_BUENOS = ('Residual', 'Pluvial', 'Unitaria')


def _tipus_normalizado(v):
    """'RESIDUAL' -> 'Residual'. Devuelve (valor, aviso)."""
    if v in (None, ''):
        return None, None
    s = str(v).strip()
    if not s or s.upper() in ('NULL', 'NONE'):
        return None, None
    for bueno in _TIPUS_BUENOS:
        if s.upper() == bueno.upper():
            return bueno, None
    return None, ("el pou dice %r, que no es Residual, Pluvial ni Unitaria: "
                  "no lo escribo" % s)


def _tipus_de_los_pous(capa_pous, geom_tram):
    """El tipo de red del tram, sacado de los pous de sus dos extremos.

    Un tram va de pou a pou, y el tipo de red es una propiedad de la red, no
    del tram: se hereda del pou. Se miran **los dos extremos**:

      * si los dos pous dicen lo mismo -> se escribe;
      * si dicen cosas distintas -> **no se escribe y se avisa**. Un tram entre
        un pou residual y uno pluvial no es un detalle: o esta mal uno de los
        dos pous, o ese tram es la union de dos redes y hay que mirarlo;
      * si solo hay pou en un extremo -> se usa ese, diciendolo.

    Devuelve (valor, explicacion) o (None, motivo).
    """
    idx = _find_field_idx(capa_pous, CAMPO_TIPUS)
    if idx == -1:
        return None, "la 222 no tiene campo %s" % CAMPO_TIPUS
    vs = _vertices_de(geom_tram)
    if len(vs) < 2:
        return None, "el tram no tiene geometria utilizable"

    encontrados = []
    for pt in (vs[0], vs[-1]):
        rect = QgsRectangle(pt.x() - TOL_EXTREMO, pt.y() - TOL_EXTREMO,
                            pt.x() + TOL_EXTREMO, pt.y() + TOL_EXTREMO)
        mejor, mejor_d = None, None
        for f in capa_pous.getFeatures(QgsFeatureRequest().setFilterRect(rect)):
            g = f.geometry()
            if g is None or g.isNull():
                continue
            p = g.asPoint()
            d = ((p.x() - pt.x()) ** 2 + (p.y() - pt.y()) ** 2) ** 0.5
            if d <= TOL_EXTREMO and (mejor_d is None or d < mejor_d):
                mejor, mejor_d = f, d
        if mejor is not None:
            encontrados.append(mejor)

    if not encontrados:
        return None, "no hay ningun pou de la 222 en los extremos del tram"

    vals, avisos = [], []
    for f in encontrados:
        v, aviso = _tipus_normalizado(f[idx])
        if aviso:
            avisos.append(aviso)
        if v:
            vals.append(v)
    if not vals:
        return None, (avisos[0] if avisos
                      else "los pous de los extremos no traen tipo de red")
    distintos = sorted(set(vals))
    if len(distintos) > 1:
        return None, ("un extremo dice %s y el otro %s: no escribo el tipo de "
                      "red hasta que se aclare cual es"
                      % (distintos[0], distintos[1]))
    if len(encontrados) == 1:
        return distintos[0], "del unico pou que hay en un extremo"
    return distintos[0], "los dos pous dicen %s" % distintos[0]


def _pt_en_capa(pt, crs_origen, capa):
    """El punto `pt`, que viene en `crs_origen`, en el CRS de `capa`.

    ⚠ Hace falta porque **la capa madre y las capas del pliego NO comparten
    proyeccion**, y no por error: la madre `Tuberias` esta a proposito en 4326
    en la plantilla, porque si no los chicos no la ven al meter inventario
    (Marisa, 12/08/2026). Las capas del pliego van en 25831.

    El volcador lleva el tram a la proyeccion de la MADRE para casar las
    flechas, asi que a partir de ahi trabaja en grados en esos municipios. Si
    con esas coordenadas se va a buscar un embornal, un CD o un pou -- que
    estan en metros -- no se encuentra nada **y no salta ningun error**: la
    busqueda simplemente vuelve vacia.

    Medido el 09/09/2026: de 29 carpetas de gabinete, **15 tienen la madre en
    4326 y los embornals en 25831**. En todas ellas la profundidad del embornal
    no se llegaba a leer nunca. Arboli funcionaba porque su madre esta en
    25831.
    """
    if capa is None:
        return None
    try:
        if crs_origen is None or capa.crs() == crs_origen:
            return pt
        xf = QgsCoordinateTransform(crs_origen, capa.crs(),
                                    QgsProject.instance())
        return xf.transform(pt)
    except Exception:
        return None


def _largo(geom):
    """El largo de una linea, en las unidades de su CRS."""
    vs = _vertices_de(geom)
    if len(vs) < 2:
        return None
    t = 0.0
    for a, b in zip(vs, vs[1:]):
        t += ((a.x() - b.x()) ** 2 + (a.y() - b.y()) ** 2) ** 0.5
    return t


def _otro_extremo(geom, pt):
    """El extremo de la linea que NO es `pt`, o None si `pt` no es un extremo."""
    vs = _vertices_de(geom)
    if len(vs) < 2:
        return None
    d0 = ((vs[0].x() - pt.x()) ** 2 + (vs[0].y() - pt.y()) ** 2) ** 0.5
    dn = ((vs[-1].x() - pt.x()) ** 2 + (vs[-1].y() - pt.y()) ** 2) ** 0.5
    if d0 <= TOL_EXTREMO and d0 <= dn:
        return vs[-1]
    if dn <= TOL_EXTREMO:
        return vs[0]
    return None


def _hay_algo_en(capa, pt, crs_origen=None):
    """Si esa capa tiene un elemento en ese punto. Informativo."""
    if capa is None:
        return False
    p = _pt_en_capa(pt, crs_origen, capa)
    if p is None:
        return False
    rect = QgsRectangle(p.x() - TOL_EXTREMO, p.y() - TOL_EXTREMO,
                        p.x() + TOL_EXTREMO, p.y() + TOL_EXTREMO)
    g = QgsGeometry.fromPointXY(p)
    for f in capa.getFeatures(QgsFeatureRequest().setFilterRect(rect)):
        gg = f.geometry()
        if gg is not None and not gg.isNull() and gg.distance(g) <= TOL_EXTREMO:
            return True
    return False


def _que_hay_en(pt, capa_cd, capa_pous, crs_origen=None):
    """Como se llama el sitio donde muere esta punta del tram.

    Tres casos distintos, con TRES acciones distintas, y hasta ahora el aviso
    los mezclaba en dos. Lo pidio Marisa el 09/09/2026 al revisar los dos que
    salian "en esta punta" en Arboli y comprobar que el pou **si estaba**: lo
    que faltaba era la flecha de campo.

      * **el CD**: no hay pou, no hay nada que medir. Normal, nada que hacer.
      * **un pou sin flecha**: el pou esta, pero nadie midio ese colector.
        Se pregunta a campo o se mira el PROF del propio pou.
      * **una punta sin nada**: puede faltar un pou por digitalizar. Eso lo
        confirma el control E10 del Field Preparer.
    """
    if _hay_algo_en(capa_cd, pt, crs_origen):
        return 'el CD'
    if _hay_algo_en(capa_pous, pt, crs_origen):
        return 'un pou SIN flecha de campo (el pou esta; falta la medida)'
    return 'una punta donde no hay ni pou ni CD (revisar con el E10)'


def _prof_interpolada_en_cd(pt_cd, tram_actual, prof_lejana, capa_destino,
                            capa_origen, idx_prof, red_ref, idx_red, idx_com,
                            capa_emb, capa_cd, capa_pous=None,
                            xf_a_madre=None, xf_a_tram=None, idx_corr=-1):
    """La profundidad en un CD, interpolada -> (metros, explicacion).

    En un CD **no hay nada que medir**: no hay pou ni embornal, asi que el
    operario no dibujo flecha y esa punta del tram se quedaba vacia. Pero el
    dato se puede deducir sin inventarlo: el colector sigue bajando, asi que la
    profundidad en el CD esta entre la del pou de un lado y la del otro, a
    prorrata de lo que hay de tuberia hasta cada uno.

        pou1 ---- tram actual ----> [CD] ---- tram vecino ----> pou2
                    L_actual                    L_vecino

        prof(CD) = p1 + (p2 - p1) * L_actual / (L_actual + L_vecino)

    Pedido por Marisa el 09/09/2026: *"quiero meterle en los tramos que cambia
    de diametro una cota interpolada donde tengo la etiqueta CD o donde termina
    el tramo"*.

    ⚠ Esto **revierte** su decision del 07/09 (*"dejaremos vacio el prof
    colector cuando termine en CD"*, *"no, lo de la cota interpolada no"*). Es
    un cambio de criterio suyo, no un despiste: queda escrito por si alguien
    ve las dos cosas y no entiende cual manda.

    ⚠ Y es un valor CALCULADO, no medido. Por eso el que llama a esto lo anota
    en el `OBSERVACIO` del tram: un numero interpolado y uno tomado con el
    metro se ven exactamente igual, y esa confusion ya ha costado disgustos con
    las cotas del MDT.

    Se NIEGA a interpolar si:
      * la punta NO muere en un CD -- ver el candado de mas abajo;
      * no se conoce la profundidad del otro extremo de este mismo tram;
      * en el CD no muere exactamente OTRO tram (si hay dos o mas, no se sabe
        por cual sigue el agua);
      * el tram vecino no tiene profundidad conocida en su extremo lejano.
    """
    if prof_lejana is None:
        return None, ("no se puede interpolar: no conozco la profundidad del "
                      "otro extremo de este tram")

    l_act = _largo(tram_actual)
    if not l_act:
        return None, "no se puede interpolar: el tram no tiene largo"

    # -- los trams que tocan el CD, menos este --------------------------
    rect = QgsRectangle(pt_cd.x() - TOL_EXTREMO, pt_cd.y() - TOL_EXTREMO,
                        pt_cd.x() + TOL_EXTREMO, pt_cd.y() + TOL_EXTREMO)
    vecinos = []
    for f in capa_destino.getFeatures(QgsFeatureRequest().setFilterRect(rect)):
        g = f.geometry()
        if g is None or g.isNull() or g.isEmpty():
            continue
        # Los vecinos vienen de la misma capa que el tram, asi que ya estan
        # en la proyeccion en la que se mide: no se reproyecta nada.
        gg = QgsGeometry(g)
        if _otro_extremo(gg, pt_cd) is None:
            continue                      # solo pasa cerca, no muere aqui
        if gg.equals(tram_actual):
            continue                      # es el nuestro
        vecinos.append((f, gg))

    crs_org = capa_destino.crs() if capa_destino is not None else None
    donde = _que_hay_en(pt_cd, capa_cd, capa_pous, crs_org)

    # ⚠⚠ SOLO SE INTERPOLA EN UN CD. Regla dura de Marisa (09/09/2026):
    #
    #     *"ese pozo no tiene flechas porque no se pudo abrir, por lo tanto si
    #      no tiene flechas, o si tiene flechas pero no se ha medido la prof,
    #      no se mete nada interpolado ni de ninguna manera"*.
    #
    # La diferencia es de fondo, no de forma:
    #
    #   * en un **CD** no hay pou, no hay nada que medir y nunca lo habra: el
    #     valor interpolado es la mejor descripcion posible de la realidad.
    #   * en un **pou** si hay algo que medir. Si no esta medido es porque no
    #     se pudo abrir la tapa (Porrera y Cornudella enteros, con losa de
    #     piedra) o porque se paso. Poner un numero ahi **tapa un dato que
    #     falta**, y ese hueco tiene que llegar al informe, no desaparecer.
    #
    # Asi que si en la punta hay un pou -- o no hay nada, que puede ser un pou
    # sin digitalizar -- no se escribe nada y se dice por que.
    if 'el CD' not in donde:
        return None, ("no interpolo: esta punta muere en %s, y ahi la "
                      "profundidad es un dato que FALTA, no uno que se pueda "
                      "calcular" % donde)
    if not vecinos:
        return None, ("no se puede interpolar: en %s no muere ningun otro "
                      "tram" % donde)
    if len(vecinos) > 1:
        return None, ("no se puede interpolar: en %s mueren %d trams y no se "
                      "por cual sigue el agua" % (donde, len(vecinos)))

    f_vec, g_vec = vecinos[0]
    l_vec = _largo(g_vec)
    if not l_vec:
        return None, "no se puede interpolar: el tram vecino no tiene largo"

    # -- la profundidad del vecino en SU extremo lejano -----------------
    pv1, pv2, _, _ = _flechas_de_los_extremos(
        capa_origen, g_vec, idx_prof, red_ref, idx_red, idx_com, capa_emb,
        None, xf_a_madre, xf_a_tram, idx_corr)
    lejano = _otro_extremo(g_vec, pt_cd)
    vs = _vertices_de(g_vec)
    # `_flechas_de_los_extremos` devuelve (vertice 0, ultimo vertice)
    d0 = ((vs[0].x() - lejano.x()) ** 2 + (vs[0].y() - lejano.y()) ** 2) ** 0.5
    p_vec = pv1 if d0 <= TOL_EXTREMO else pv2
    if p_vec is None:
        return None, ("no se puede interpolar: el tram vecino tampoco tiene "
                      "profundidad en su otro extremo")

    t = l_act / (l_act + l_vec)
    v = prof_lejana + (p_vec - prof_lejana) * t
    return (round(v, 2),
            "interpolada en %s: %.2f m (entre %.2f y %.2f, a %.0f%% del "
            "recorrido)" % (donde, v, prof_lejana, p_vec, t * 100))


def _prof_del_embornal_en(capa_emb, pt, crs_origen=None):
    """La profundidad del embornal que haya en ese punto -> (metros, motivo)."""
    if capa_emb is None:
        return None, None
    pt = _pt_en_capa(pt, crs_origen, capa_emb)
    if pt is None:
        return None, None
    idx, campo = -1, None
    for c in CAMPOS_PROF_EMB:
        i = _find_field_idx(capa_emb, c)
        if i != -1:
            idx, campo = i, c
            break
    if idx == -1:
        return None, None
    rect = QgsRectangle(pt.x() - TOL_EXTREMO, pt.y() - TOL_EXTREMO,
                        pt.x() + TOL_EXTREMO, pt.y() + TOL_EXTREMO)
    g = QgsGeometry.fromPointXY(pt)
    mejor, mejor_d = None, None
    for f in capa_emb.getFeatures(QgsFeatureRequest().setFilterRect(rect)):
        gg = f.geometry()
        if gg is None or gg.isNull():
            continue
        d = gg.distance(g)
        if d <= TOL_EXTREMO and (mejor_d is None or d < mejor_d):
            mejor, mejor_d = f, d
    if mejor is None:
        return None, None
    # El campo elegido puede estar vacio justo en este embornal: se prueban
    # todos antes de darse por vencido.
    ultimo = None
    for c in CAMPOS_PROF_EMB:
        i = _find_field_idx(capa_emb, c)
        if i == -1:
            continue
        v, motivo = prof_del_embornal(mejor[i])
        if v is not None:
            return v, motivo
        ultimo = motivo
    return None, ultimo


def asegurar_columnas_prof(capa, avisar=None, en_seco=False):
    """Crea `prof_colector1/2` y `prof_interp` en el 211 si no estan.

    UNA sola implementacion para los dos caminos: el volcado en lote (B6) y
    el clic sobre un tram suelto. Antes solo las creaba el lote, y pulsar
    sobre un tram en un municipio recien montado no escribia nada: avisaba
    por la barra de mensajes, que se va sola a los pocos segundos, asi que
    parecia que la herramienta no hacia nada (Marisa, 07/10/2026, La Galera).

    `en_seco=True` no toca la estructura: solo dice que faltan.
    Devuelve la lista de nombres creados (o los que faltan, en seco).
    """
    from qgis.PyQt.QtCore import QVariant
    from qgis.core import QgsField
    necesarias = ((CAMPO_PROF_1, QVariant.Double, 0),
                  (CAMPO_PROF_2, QVariant.Double, 0),
                  (CAMPO_INTERP, QVariant.String, 20))
    faltan = [(n, tp, ln) for n, tp, ln in necesarias
              if _find_field_idx(capa, n) == -1]
    if not faltan:
        return []
    nombres = [n for n, _, _ in faltan]
    if en_seco:
        if avisar:
            avisar('faltan columnas (%s). En seco no las creo; se crean al '
                   'volcar de verdad.' % ', '.join(nombres))
        return nombres
    # ⚠ Anadir campos exige cerrar la sesion de edicion, pero hay que
    # DEVOLVERLA como estaba. Sin esto, al pulsar sobre un tram el volcador
    # abria la edicion, esta funcion se la cerraba, y el `commitChanges()`
    # del final reventaba con un error de Python. Y de paso guardaba lo que
    # la tecnica tuviera a medias sin preguntar (Marisa, 07/10/2026).
    estaba_editando = capa.isEditable()
    try:
        if estaba_editando:
            capa.commitChanges()
        capa.dataProvider().addAttributes(
            [QgsField(n, tp, len=ln) if ln else QgsField(n, tp)
             for n, tp, ln in faltan])
        capa.updateFields()
    except Exception as exc:
        if avisar:
            avisar('no he podido crear las columnas: %s' % exc)
        if estaba_editando and not capa.isEditable():
            capa.startEditing()
        return []
    if estaba_editando and not capa.isEditable():
        capa.startEditing()
        if avisar:
            avisar('ojo: para anadir las columnas he tenido que guardar la '
                   'capa. Lo que tuvieras a medias en el 211 ha quedado '
                   'guardado.')
    if avisar:
        avisar('he creado las columnas que faltaban: %s' % ', '.join(nombres))
    return nombres


def _nombre_de(feat, capa):
    """El ID del tram si lo tiene, y si no su fid."""
    try:
        if 'ID' in [f.name() for f in capa.fields()]:
            v = feat['ID']
            if v not in (None, ''):
                return str(v).split('.')[0]
    except Exception:
        pass
    return str(feat.id())


def _t_int(val):
    """'150 mm' / '150' / 150.0 -> 150. Vacio o None -> None."""
    if val is None: return None
    s = str(val).strip()
    if not s or s.upper() in ('NULL', 'NONE'): return None
    m = re.search(r'-?\d+', s)
    return int(m.group()) if m else None


def _t_code_paren(val):
    """'PVC LISO (PC)' -> 'PC'. 'PVC' -> 'PVC'. None -> None."""
    if val is None: return None
    s = str(val).strip()
    if not s or s.upper() in ('NULL', 'NONE'): return None
    m = re.search(r'\(([^)]+)\)', s)
    if m: return m.group(1).strip()
    return s


def _t_passthrough(val):
    return val


# Mapeo de campos origen -> (destino, transform)
# La capa origen "Tuberias" usa nombres en castellano (Diametro, Material)
# La capa destino "211_Trams_Sanejament" usa nombres en catalan/PPT (DIAMETRE, MATERIAL)
# La busqueda es case-insensitive y tolera acentos.
FIELD_MAPPING = {
    # origen (Tuberias):  (destino (211_Trams),   transform)
    'Diametro':            ('DIAMETRE',           _t_int),
    # Para Material pasamos el texto completo ('HORMIGON (HO)') porque el desplegable
    # de 211 tiene nombres complets ('hormigón'). El resolver del desplegable hara
    # el match por substring/sin-acentos.
    'Material':            ('MATERIAL',           _t_passthrough),
}


def _norm_field(s):
    """Normaliza un nombre de campo para comparar (sin acentos, minusculas, sin espacios)."""
    import unicodedata
    s = unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('ascii')
    return s.lower().replace(' ', '').replace('_', '')


def _find_field_idx(layer, name):
    """Busca el indice de un campo en una capa de forma tolerante (case + acentos)."""
    target = _norm_field(name)
    for i, f in enumerate(layer.fields()):
        if _norm_field(f.name()) == target:
            return i
    return -1


def _stored_to_label(layer, field_name, stored_value):
    """Dado un valor crudo (stored) de un campo con desplegable,
    devuelve su label visible. Si no tiene desplegable o no encuentra
    el stored, devuelve el valor original.
    """
    vmap = _get_widget_value_map(layer, field_name)
    if not vmap:
        return stored_value
    if stored_value is None:
        return None
    target = str(stored_value).strip()
    for label, stored in vmap.items():
        if stored is not None and str(stored).strip() == target:
            return label
    return stored_value


def _get_widget_value_map(layer, field_name):
    """Si el campo tiene widget ValueMap o ValueRelation, devuelve dict {label: stored_value}.

    Devuelve None si no tiene widget de lista, o {} si tiene pero esta vacio.
    """
    idx = _find_field_idx(layer, field_name)
    if idx == -1:
        return None
    setup = layer.editorWidgetSetup(idx)
    wtype = setup.type()
    config = setup.config()

    if wtype == 'ValueMap':
        m = config.get('map')
        result = {}
        if isinstance(m, list):
            for item in m:
                if isinstance(item, dict):
                    for k, v in item.items():
                        result[str(k)] = str(v) if v is not None else None
        elif isinstance(m, dict):
            for k, v in m.items():
                result[str(k)] = str(v) if v is not None else None
        return result

    if wtype == 'ValueRelation':
        layer_id = config.get('Layer')
        key_field = config.get('Key')
        value_field = config.get('Value')
        if not (layer_id and key_field and value_field):
            return None
        ref = QgsProject.instance().mapLayer(layer_id)
        if not ref:
            return None
        result = {}
        ki = _find_field_idx(ref, key_field)
        vi = _find_field_idx(ref, value_field)
        if ki == -1 or vi == -1:
            return None
        for f in ref.getFeatures():
            label = f[vi]
            stored = f[ki]
            if label is not None:
                result[str(label)] = stored
        return result

    return None


def _resolve_through_dropdown(layer, field_name, raw_value):
    """Si el campo destino tiene desplegable, intenta resolver `raw_value` a
    uno de los stored_values validos.

    Estrategia:
      1. Si raw esta entre los stored_values, ok.
      2. Si raw esta entre los labels (case-insensitive sin acentos), devolver su stored.
      3. Si raw aparece como substring case-insensitive en algun label, devolver su stored.
      4. Si no, devolver raw tal cual (el usuario vera el aviso si no cabe).
    """
    vmap = _get_widget_value_map(layer, field_name)
    if not vmap:
        return raw_value, None  # sin desplegable, sin info extra
    stored_values = {str(v) for v in vmap.values() if v is not None}
    labels = {k: v for k, v in vmap.items()}

    if raw_value is None:
        return None, "(NULL)"

    raw_str = str(raw_value).strip()

    # Estrategia: devolvemos siempre el LABEL del desplegable que matchea,
    # no el stored value. Esto funciona si la columna acepta texto plano
    # como hacen las filas existentes ya rellenadas.

    # 1) si raw ya coincide con algun label exacto, devolverlo tal cual
    for label in labels.keys():
        if str(label).strip() == raw_str:
            return label, f"label_exact:{label}"

    # 2) si raw coincide con un stored value (numerico o codigo), devolver el LABEL asociado
    for label, stored in labels.items():
        if stored is not None and str(stored).strip() == raw_str:
            return label, f"stored->label:{stored}->{label}"

    # 3) match exacto contra label normalizado (sin acentos, mayus/min)
    target = _norm_field(raw_str)
    for label in labels.keys():
        if _norm_field(label) == target:
            return label, f"label_norm:{label}"

    # 4) substring bidireccional contra labels
    best_match = None
    best_len = 0
    for label in labels.keys():
        nlabel = _norm_field(label)
        if not nlabel: continue
        if (target and (nlabel in target or target in nlabel)):
            if len(nlabel) > best_len:
                best_len = len(nlabel)
                best_match = label
    if best_match:
        return best_match, f"substring:{best_match}"

    # 5) match por tokens compartidos (para 'FUNDICION (FD)' -> 'fundición dúctil')
    def _tokens(s):
        import unicodedata
        s = unicodedata.normalize('NFD', str(s)).encode('ascii','ignore').decode('ascii').lower()
        s = re.sub(r'\([^)]*\)', ' ', s)
        return set(t for t in re.split(r'[^a-z0-9]+', s) if t and len(t) > 2)
    raw_tokens = _tokens(raw_str)
    best_overlap = 0
    best_token_match = None
    for label in labels.keys():
        lt = _tokens(label)
        ov = raw_tokens & lt
        if ov and len(ov) > best_overlap:
            best_overlap = len(ov)
            best_token_match = (label, ov)
    if best_token_match:
        l, ov = best_token_match
        return l, f"tokens:{l} (compartidos:{','.join(ov)})"

    # 6) no match
    valid_str = ", ".join(sorted(str(s) for s in labels.keys())[:8])
    return raw_value, f"NO_MATCH (validos: {valid_str}...)"


def _is_line_layer(layer):
    return (
        layer.type() == QgsMapLayer.VectorLayer
        and layer.geometryType() == QgsWkbTypes.LineGeometry
    )


def find_layer_by_name(patterns):
    """Busca capa por nombre (case-insensitive, substring)."""
    for layer in QgsProject.instance().mapLayers().values():
        n = layer.name().lower()
        for p in patterns:
            if p in n:
                return layer
    return None


#: Candidatas de la ultima busqueda, para poder decir cuales eran cuando hay
#: empate y no se puede decidir.
ULTIMAS_CANDIDATAS = []


def _sin_tildes(s):
    """Minusculas y sin acentos, para comparar nombres de capa.

    ⚠ La capa madre se llama `Tuberias` **CON TILDE**, y los patrones estaban
    todos sin ella: `'tuberi' in 'tuberias'` es False. Resultado: la madre no
    se encontraba por nombre, se caia al plan B --buscar por campos-- y ahi la
    cartografia del Ayuntamiento tambien vale, porque tiene `material` y
    `diametro`. En Mont-roig habia CINCO candidatas.
    """
    import unicodedata
    s = unicodedata.normalize('NFD', str(s))
    s = s.encode('ascii', 'ignore').decode('ascii')
    return s.lower()


def es_capa_madre(layer):
    """¿Esta capa es la capa madre `Tuberias` y no otra cosa parecida?"""
    if layer is None:
        return False
    n = _sin_tildes(layer.name())
    return any(p in n for p in CAPA_ORIGEN_PATTERNS)


def find_source_layer(required_origin_fields):
    """Busca capa de origen filtrando SOLO capas de lineas.

    Estrategia:
      1) por nombre (patrones) + tipo linea.
      2) por campos + tipo linea (TODOS los campos origen presentes).
    Excluye la capa destino 211 en ambos casos.
    """
    destino = find_layer_by_name(CAPA_DESTINO_PATTERNS)
    destino_id = destino.id() if destino else None

    # 1) por nombre + es capa de lineas
    for layer in QgsProject.instance().mapLayers().values():
        if not _is_line_layer(layer):
            continue
        if layer.id() == destino_id:
            continue
        n = _sin_tildes(layer.name())
        # excluir dominios (CSVs de catalogo aunque tengan 'tuberias' en el nombre)
        if 'dominio' in n or 'domini' in n:
            continue
        for p in CAPA_ORIGEN_PATTERNS:
            if p in n:
                return layer

    # 2) por campos + es capa de lineas
    candidatos = []
    for layer in QgsProject.instance().mapLayers().values():
        if not _is_line_layer(layer):
            continue
        if layer.id() == destino_id:
            continue
        n = _sin_tildes(layer.name())
        if 'dominio' in n or 'domini' in n:
            continue
        if all(_find_field_idx(layer, rf) != -1 for rf in required_origin_fields):
            candidatos.append(layer)

    global ULTIMAS_CANDIDATAS
    ULTIMAS_CANDIDATAS = [c.name() for c in candidatos]

    # La madre manda siempre, aunque haya otras que tambien encajen. La
    # cartografia del Ayuntamiento (`Col.lectors`, `Tubs`, `colectors_pluv`...)
    # tiene los mismos nombres de campo y en Mont-roig salieron CINCO
    # candidatas: sin esta preferencia se cogia una cualquiera.
    madres = [c for c in candidatos if es_capa_madre(c)]
    if len(madres) == 1:
        return madres[0]
    if len(madres) > 1:
        return madres[0]

    # ⚠ REGLA DURA (Marisa, 07/09/2026): *"que lea siempre del Tuberias madre,
    # es obvio"*. Si la madre no esta, NO se vuelca. Antes habia un plan B que
    # aceptaba cualquier capa de lineas con los campos `Diametro` y `Material`,
    # y la cartografia del Ayuntamiento los tiene: en Mont-roig habia CINCO
    # candidatas y se colo `Col.lectors`, cuyo material 'FOR' ni siquiera esta
    # en el desplegable del pliego.
    return None


class VolcadorMapTool(QgsMapTool):
    """Map tool: clic sobre una tuberia -> vuelca atributos a trams seleccionados."""

    def __init__(self, canvas, plugin):
        super().__init__(canvas)
        self.canvas = canvas
        self.plugin = plugin
        self.setCursor(QCursor(Qt.CrossCursor))

    def _bar(self, level, msg):
        """Mensaje en la barra de QGIS."""
        bar = self.plugin.iface.messageBar()
        if level == 'info':
            bar.pushMessage("Volcador", msg, level=Qgis.Info, duration=4)
        elif level == 'warn':
            bar.pushMessage("Volcador", msg, level=Qgis.Warning, duration=6)
        elif level == 'ok':
            bar.pushMessage("Volcador", msg, level=Qgis.Success, duration=4)
        else:
            bar.pushMessage("Volcador", msg, level=Qgis.Critical, duration=8)

    def canvasReleaseEvent(self, event):
        capa_destino = find_layer_by_name(CAPA_DESTINO_PATTERNS)
        capa_origen = find_source_layer(list(FIELD_MAPPING.keys()))

        if not capa_destino:
            self._bar('warn', "No encuentro la capa 211_Trams_Sanejament.")
            return
        if not capa_origen:
            extra = ""
            if ULTIMAS_CANDIDATAS:
                extra = (" Hay capas de lineas con esos campos, pero ninguna "
                         "es la madre: %s." % ", ".join(ULTIMAS_CANDIDATAS))
            self._bar('warn',
                "No encuentro la capa madre 'Tuberias' en el proyecto, asi que "
                "no vuelco nada.%s" % extra)
            return

        # Verificar seleccion en destino
        sel = list(capa_destino.selectedFeatures())
        if not sel:
            self._bar('warn', "Selecciona primero al menos un tram en 211.")
            return

        # Convertir clic a coordenadas del CRS de la capa origen
        click_map = self.toMapCoordinates(event.pos())
        if self.canvas.mapSettings().destinationCrs() != capa_origen.crs():
            from qgis.core import QgsCoordinateTransform
            xform = QgsCoordinateTransform(
                self.canvas.mapSettings().destinationCrs(),
                capa_origen.crs(),
                QgsProject.instance()
            )
            click_layer = xform.transform(click_map)
        else:
            click_layer = click_map

        # Tolerancia de busqueda: 15 pixeles convertidos a unidades de mapa
        tol_pix = 15
        tol_map = self.canvas.mapUnitsPerPixel() * tol_pix
        rect = QgsRectangle(
            click_layer.x() - tol_map, click_layer.y() - tol_map,
            click_layer.x() + tol_map, click_layer.y() + tol_map
        )

        req = QgsFeatureRequest().setFilterRect(rect)
        encontrados = list(capa_origen.getFeatures(req))
        if not encontrados:
            self._bar('info',
                f"No hay features en '{capa_origen.name()}' bajo el clic "
                f"({click_layer.x():.1f}, {click_layer.y():.1f}) tol={tol_map:.2f}m. "
                f"CRS capa: {capa_origen.crs().authid()}, "
                f"CRS canvas: {self.canvas.mapSettings().destinationCrs().authid()}."
            )
            return

        # Si hay varias, coger la mas cercana
        target_point = QgsGeometry.fromPointXY(QgsPointXY(click_layer))
        if len(encontrados) > 1:
            origen = min(
                encontrados,
                key=lambda f: f.geometry().distance(target_point) if f.hasGeometry() else float('inf')
            )
        else:
            origen = encontrados[0]

        # Los CSV de dominio, buscados junto a las propias capas.
        dom = Dominios(_carpetas_de(capa_origen, capa_destino))
        for aviso in dom.avisos:
            self._bar('warn', "Dominios: %s" % aviso)

        # La madre lleva LAS DOS REDES. El mismo numero de material significa
        # cosas distintas en una y en otra, asi que hay que saber cual es.
        red_flecha = None
        idx_red = _find_field_idx(capa_origen, 'Red')
        if idx_red != -1:
            red_flecha = origen[idx_red]
            if es_saneamiento(red_flecha) is False:
                self._bar('warn',
                    "Ojo: la tuberia que has pinchado es de POTABLE (Red=%s) y "
                    "estas volcando al 211 de saneamiento." % red_flecha)

        # ── Lo que los chicos escriben en el comentario ───────────────
        #
        # Marisa: *"a veces no hay diametro y material porque debe ser que no
        # esta en el dominio y los chicos lo escriben en la columna
        # comentario"*. Escriben "DN100", "DN220. ESCOMBRO", "DN300 HORMIGON",
        # "PE de 140", "30 mm"... y tambien avisan de cuando NO se puede medir:
        # "NO SE PUEDE TOMAR DN", "ESCOMBRO", "TUBO ROTO".
        #
        # Solo se usa para RELLENAR HUECOS: si la columna trae el dato, manda
        # la columna. Y se dice siempre que el valor sale del comentario.
        com = {"diametro": None, "material": None, "no_medible": False,
               "avisos": []}
        idx_com = _find_field_idx(capa_origen, 'Comentario')
        if idx_com != -1:
            com = del_comentario(origen[idx_com])
            for av in com["avisos"]:
                self._bar('warn', av)

        # Leer valores de la capa origen segun el mapeo
        # valores: {nombre_destino: valor_transformado}
        valores = {}
        faltan_origen = []
        faltan_destino = []
        for campo_origen, dest in FIELD_MAPPING.items():
            if isinstance(dest, tuple):
                campo_destino, transform = dest
            else:
                campo_destino, transform = dest, _t_passthrough
            idx_o = _find_field_idx(capa_origen, campo_origen)
            if idx_o == -1:
                faltan_origen.append(campo_origen)
                continue
            idx_d = _find_field_idx(capa_destino, campo_destino)
            if idx_d == -1:
                faltan_destino.append(campo_destino)
                continue
            raw = origen[idx_o]

            # ── Primero, el CSV de dominio ────────────────────────────────
            #
            # La madre guarda estos campos como CODIGOS. Antes se traducian con
            # _stored_to_label(), o sea usando la configuracion del desplegable
            # de la capa en QGIS; cuando esa configuracion no esta -- proyecto
            # montado de otra forma, capa de dominio sin cargar -- la
            # traduccion no ocurria, no saltaba ningun error y se escribia EL
            # CODIGO CRUDO en el 211. Ese era el "algunos materiales fallaban".
            #
            # El CSV esta al lado del GPKG y no depende de como este montado el
            # proyecto, asi que manda el. El camino viejo se queda de reserva y
            # se dice cuando se ha tenido que usar.
            v_final, via = None, None
            n_campo = _norm_field(campo_origen)
            if n_campo == 'material' and dom is not None:
                v_final, via = dom.material(raw, red_flecha)
            elif n_campo == 'diametro' and dom is not None:
                v_final, via = dom.diametro(raw)

            # Si la columna no da nada, mirar lo que escribieron a mano.
            if v_final is None and n_campo in ('material', 'diametro'):
                del_com = com.get(n_campo)
                if del_com is not None:
                    if n_campo == 'material':
                        v2, info = _resolve_through_dropdown(
                            capa_destino, campo_destino, del_com)
                        v_final = del_com if (info or '').startswith('NO_MATCH') else v2
                    else:
                        v_final = del_com
                    self._bar('info',
                        f"{campo_destino}: no venia en su columna, lo he "
                        f"sacado del COMENTARIO -> {v_final}")
                    via = None
                else:
                    # NUNCA se escribe el texto del comentario en el campo:
                    # ahi solo va un numero o un material del dominio. Si no se
                    # ha podido sacar, se dice y se deja el hueco, con el
                    # comentario delante para que se mire a mano.
                    texto = ''
                    if idx_com != -1 and origen[idx_com] not in (None, ''):
                        texto = str(origen[idx_com]).strip()
                    if com.get('no_medible'):
                        self._bar('warn',
                            f"{campo_destino}: en campo no se pudo medir "
                            f'("{texto[:60]}"). Lo dejo vacio.')
                    elif texto:
                        self._bar('warn',
                            f"{campo_destino}: no viene en su columna y no lo "
                            f"se sacar del comentario. METER A MANO desde "
                            f'Comentario: "{texto[:60]}"')
                    continue

            if v_final is None:
                if via:
                    self._bar('warn', f"{campo_destino}: {via}. Tiro del "
                                      f"desplegable de la capa.")
                raw_label = _stored_to_label(capa_origen, campo_origen, raw)
                try:
                    v_transformado = transform(raw_label)
                except Exception as e:
                    self._bar('warn', f"Transform fallo en {campo_origen}={raw_label}: {e}")
                    continue
                v_final, info = _resolve_through_dropdown(
                    capa_destino, campo_destino, v_transformado)
                if info and info.startswith('NO_MATCH'):
                    self._bar('warn',
                        f"{campo_destino}: valor '{v_transformado}' no esta en "
                        f"el desplegable. {info}")
            else:
                if via and 'SIN casar' in via:
                    self._bar('warn', f"{campo_destino}: {via}")
                if n_campo == 'diametro':
                    try:
                        v_final = transform(str(v_final))
                    except Exception:
                        pass
                else:
                    v2, info = _resolve_through_dropdown(
                        capa_destino, campo_destino, v_final)
                    if not (info and info.startswith('NO_MATCH')):
                        v_final = v2

            valores[campo_destino] = v_final

        if faltan_origen:
            self._bar('warn', f"Faltan en origen: {', '.join(faltan_origen)}")
        if faltan_destino:
            self._bar('warn', f"Faltan en destino: {', '.join(faltan_destino)}")
        if not valores:
            return

        # Escribir
        ya_editable = capa_destino.isEditable()
        if not ya_editable:
            capa_destino.startEditing()

        # ── Las profundidades de campo, LAS DOS ─────────────────
        #
        # Un tram tiene un pou en cada punta y una profundidad distinta en
        # cada una: esa diferencia ES la pendiente. Antes habia que pinchar
        # las dos flechas, una por punta, y si te dejabas una el tram se
        # quedaba con medio dato y NADA lo avisaba.
        #
        # Ahora, con un solo clic, para cada tram seleccionado se buscan las
        # flechas que arrancan en sus dos extremos y se escriben las dos.
        idx_prof = _find_field_idx(capa_origen, CAMPO_PROF_ORIGEN)
        # La corregida en gabinete manda sobre la de campo. Puede no
        # existir: la crea el control E31b solo donde hace falta.
        idx_corr = _find_field_idx(capa_origen, CAMPO_PROF_CORREGIDA)
        # Si el municipio no trae las columnas de trabajo, se crean aqui
        # mismo. Antes solo se avisaba, y el aviso sale en la barra de
        # mensajes, que se va sola a los pocos segundos: desde fuera parecia
        # que pulsar sobre el tram no hacia nada (Marisa, 07/10/2026, La
        # Galera). Es el mismo helper que usa el volcado en lote.
        _creadas = asegurar_columnas_prof(capa_destino)
        if _creadas:
            self._bar('info', 'He anadido al 211 las columnas que le '
                              'faltaban: %s' % ', '.join(_creadas))
        idx_p1 = _find_field_idx(capa_destino, CAMPO_PROF_1)
        idx_p2 = _find_field_idx(capa_destino, CAMPO_PROF_2)
        idx_interp = _find_field_idx(capa_destino, CAMPO_INTERP)
        #: Lista de un elemento para poder marcarla desde dentro del bucle.
        sin_columna = [False]
        # La medida puede venir en la columna o en el comentario, segun la
        # version de plantilla del municipio: con cualquiera de las dos vale.
        hacer_prof = ((idx_prof != -1 or idx_com != -1)
                      and idx_p1 != -1 and idx_p2 != -1)
        if (idx_prof != -1 or idx_com != -1) and not hacer_prof:
            self._bar('warn',
                "Este 211 no tiene %s / %s y no he podido crearlas, asi que "
                "las profundidades no se vuelcan."
                % (CAMPO_PROF_1, CAMPO_PROF_2))

        # ⚠ La madre y el 211 casi nunca comparten proyeccion, y NO es un
        # error del proyecto: la plantilla pone `Tuberias` en 4326 a proposito,
        # porque si no los chicos no la ven al meter inventario (Marisa,
        # 12/08/2026). Asi que aqui no se avisa de nada: se preparan las dos
        # transformaciones y se mide siempre en METROS, en la proyeccion del
        # 211. Ver el comentario largo dentro de `_flechas_de_los_extremos`.
        xf_a_madre = xf_a_tram = None
        if hacer_prof and capa_destino.crs() != capa_origen.crs():
            from qgis.core import QgsCoordinateTransform
            xf_a_madre = QgsCoordinateTransform(
                capa_destino.crs(), capa_origen.crs(), QgsProject.instance())
            xf_a_tram = QgsCoordinateTransform(
                capa_origen.crs(), capa_destino.crs(), QgsProject.instance())

        # -- los embornals, para los trams que mueren en uno -------------
        capa_emb = find_layer_by_name(CAPA_EMB_PATTERNS)

        # -- los CD, solo para poder nombrarlos en el aviso --------------
        capa_cd = find_layer_by_name(CAPA_CD_PATTERNS)

        # -- el tipo de red, que hay que ir a buscarlo a los pous --------
        capa_pous = find_layer_by_name(CAPA_POUS_PATTERNS)
        idx_tipus = _find_field_idx(capa_destino, CAMPO_TIPUS)
        xf_pous = None
        if capa_pous is not None and idx_tipus == -1:
            self._bar('warn', "El 211 no tiene campo %s." % CAMPO_TIPUS)
            capa_pous = None
        if capa_pous is not None and capa_pous.crs() != capa_destino.crs():
            from qgis.core import QgsCoordinateTransform
            xf_pous = QgsCoordinateTransform(
                capa_destino.crs(), capa_pous.crs(), QgsProject.instance())
        if capa_pous is None and idx_tipus != -1:
            self._bar('warn',
                "No encuentro la 222 de pous, asi que el tipo de red no se "
                "vuelca. Cargala en el proyecto.")

        cnt = 0
        n_dos = n_una = n_cero = n_tipus = n_interp = 0
        pegas = []
        #: Lo que se ha escrito en cada tram, para poder ENSENARLO. La tabla
        #: de atributos abierta no se refresca sola cuando un plugin escribe
        #: en el buffer de edicion, asi que el dato esta puesto y no se ve --
        #: y eso hace creer que la herramienta no ha hecho nada. (Marisa,
        #: 07/09/2026: *"por lo menos que se vea escrito el texto en la
        #: casilla, para comprobar que este bien, eso es importante"*.)
        escritos = []
        no_pisar = bool(getattr(self.plugin, 'no_pisar', True))
        respetados = []

        def _escribir(tram, idx, val, nombre):
            """Escribe respetando lo que ya haya, si asi esta configurado."""
            if idx == -1:
                return False
            if no_pisar:
                tenia = tram[idx]
                if tenia not in (None, '', 'NULL'):
                    try:
                        igual = abs(float(tenia) - float(val)) < 0.005
                    except (TypeError, ValueError):
                        igual = str(tenia).strip() == str(val).strip()
                    if not igual:
                        respetados.append('%s %s: se queda %s (la madre dice %s)'
                                          % (_nombre_de(tram, capa_destino),
                                             nombre, tenia, val))
                    return False
            capa_destino.changeAttributeValue(tram.id(), idx, val)
            _escrito_ahora[nombre] = val
            return True

        _escrito_ahora = {}
        for tram in sel:
            _escrito_ahora.clear()
            tv, p1, p2 = None, None, None
            for campo_destino, val in valores.items():
                fidx = _find_field_idx(capa_destino, campo_destino)
                _escribir(tram, fidx, val, campo_destino)

            if capa_pous is not None:
                gp = tram.geometry()
                if xf_pous is not None and gp is not None and not gp.isNull():
                    gp = QgsGeometry(gp)
                    gp.transform(xf_pous)
                tv, tmot = _tipus_de_los_pous(capa_pous, gp)
                if tv is not None:
                    if _escribir(tram, idx_tipus, tv, CAMPO_TIPUS):
                        n_tipus += 1
                    else:
                        n_tipus += 1      # ya lo tenia: cuenta como puesto
                else:
                    pegas.append("tram %s: %s"
                                 % (_nombre_de(tram, capa_destino), tmot))

            if hacer_prof:
                # La geometria va TAL CUAL, en la proyeccion del 211: es la
                # que se mide. Reproyectarla aqui era lo que convertia los
                # 0,60 m de tolerancia en 0,60 grados.
                g = tram.geometry()
                p1, p2, avisos, interp_i = _flechas_de_los_extremos(
                    capa_origen, g, idx_prof, red_flecha, idx_red, idx_com,
                    capa_emb,
                    (capa_destino, capa_cd, capa_pous, xf_a_madre, xf_a_tram),
                    xf_a_madre, xf_a_tram, idx_corr)
                if p1 is not None:
                    _escribir(tram, idx_p1, p1, CAMPO_PROF_1)
                if p2 is not None:
                    _escribir(tram, idx_p2, p2, CAMPO_PROF_2)

                # Un valor interpolado NO es un valor medido, y se ve igual.
                # Queda marcado en una columna INTERNA -- nunca en el
                # OBSERVACIO, que se entrega.
                if interp_i:
                    n_interp += len(interp_i)
                    if idx_interp != -1:
                        capa_destino.changeAttributeValue(
                            tram.id(), idx_interp,
                            SEP_INTERP.join(str(i + 1) for i in interp_i))
                    else:
                        sin_columna[0] = True
                puestas = (p1 is not None) + (p2 is not None)
                if puestas == 2:
                    n_dos += 1
                elif puestas == 1:
                    n_una += 1
                else:
                    n_cero += 1
                if avisos:
                    pegas.append("tram %s: %s"
                                 % (_nombre_de(tram, capa_destino),
                                    "; ".join(avisos)))
            # Lo que se anuncia es lo que se ha ESCRITO, no lo que se
            # habia calculado. Antes se armaba con `valores` y, con "no pisar"
            # activado, decia "DIAMETRE=400" mientras en la tabla seguia el
            # 450 de antes: el mensaje contradecia al dato y uno se fia del
            # mensaje (Marisa, 06/10/2026).
            puesto = dict(_escrito_ahora)
            escritos.append((_nombre_de(tram, capa_destino), puesto))
            if puesto:
                cnt += 1

        if capa_pous is not None and n_tipus < cnt:
            self._bar('warn',
                "Tipo de red: puesto en %d de %d tram(s)." % (n_tipus, cnt))
        if respetados:
            self._bar('warn',
                "NO he tocado %d campo(s) que ya tenian valor distinto al de "
                "la madre. El primero: %s. Si quieres que los pise, quita la "
                "marca de 'No pisar lo que ya tenga valor' en el menu "
                "Tarragona." % (len(respetados), respetados[0]))
        if n_interp:
            self._bar('info',
                "%d profundidad(es) INTERPOLADAS en un CD: no estan medidas, "
                "las ha calculado la herramienta." % n_interp)
        if sin_columna[0]:
            self._bar('warn',
                "Esta 211 no tiene la columna %s, asi que la profundidad "
                "interpolada esta escrita pero SIN MARCAR. Que te la anadan "
                "antes de seguir: si no, dentro de un mes no se sabra cual se "
                "midio y cual se calculo." % CAMPO_INTERP)
        if hacer_prof and (n_una or n_cero):
            self._bar('warn',
                "Profundidades: %d tram(s) con las DOS, %d con una sola y %d "
                "sin ninguna. Los que van a medias hay que mirarlos."
                % (n_dos, n_una, n_cero))
        for p in pegas[:4]:
            self._bar('warn', p)
        if len(pegas) > 4:
            self._bar('warn', "...y %d tram(s) mas con pegas."
                              % (len(pegas) - 4))

        # Si nosotros abrimos la edicion, la cerramos guardando.
        # Si ya estaba editable, dejamos que el usuario guarde manualmente: no
        # se le comprometen otros cambios que tenga a medias sin preguntarle.
        # ⚠ Pero hay que DECIRLO: si no, el dato esta escrito y no se ve en la
        # tabla, y parece que la herramienta no ha hecho nada. (Lo vio Marisa,
        # 07/09/2026.)
        if ya_editable:
            self._bar('info',
                "La capa ya estaba en edicion, asi que NO lo he guardado: "
                "dale a guardar para que aparezca en la tabla.")
        if not ya_editable:
            ok = capa_destino.commitChanges()
            if not ok:
                self._bar('err', f"Error al guardar: {capa_destino.commitErrors()}")
                return

        # Que se vea sin tener que guardar: se avisa a las vistas abiertas
        # (la tabla de atributos escucha `dataChanged`) y ademas se ESCRIBE en
        # el mensaje lo que ha quedado en cada tram, que es el unico canal del
        # que se puede depender.
        capa_destino.triggerRepaint()
        try:
            capa_destino.dataChanged.emit()
        except Exception:
            pass

        if escritos:
            orden = [CAMPO_TIPUS, 'DIAMETRE', 'MATERIAL', CAMPO_PROF_1,
                     CAMPO_PROF_2]
            def _fmt(d):
                trozos = []
                for k in orden:
                    if k in d and d[k] is not None:
                        v = d[k]
                        trozos.append('%s=%s' % (
                            k.replace('prof_colector', 'prof'),
                            ('%.2f' % v) if isinstance(v, float) else v))
                for k in sorted(d):
                    if k not in orden and d[k] is not None:
                        trozos.append('%s=%s' % (k, d[k]))
                return ', '.join(trozos) if trozos else 'nada'
            if len(escritos) <= 3:
                for nom, d in escritos:
                    self._bar('ok', 'tram %s: %s' % (nom, _fmt(d)))
            else:
                self._bar('ok', 'tram %s: %s   (y %d tram(s) mas)'
                          % (escritos[0][0], _fmt(escritos[0][1]),
                             len(escritos) - 1))

        msg_vals = ", ".join(f"{k}={v}" for k, v in valores.items())
        # DEBUG: mostrar tambien fid de la tuberia origen, columna usada y valores raw/label
        raw_info = []
        for campo_origen in FIELD_MAPPING.keys():
            io = _find_field_idx(capa_origen, campo_origen)
            if io != -1:
                real_name = capa_origen.fields()[io].name()
                raw_val = origen[io]
                label_val = _stored_to_label(capa_origen, campo_origen, raw_val)
                if str(raw_val) != str(label_val):
                    raw_info.append(f"{real_name}={raw_val!r}->'{label_val}'")
                else:
                    raw_info.append(f"{real_name}={raw_val!r}")
        self._bar('ok',
            f"Volcado desde '{capa_origen.name()}' fid={origen.id()} "
            f"raw=({', '.join(raw_info)}) -> a {cnt} tram(s): {msg_vals}"
            + (f" | profundidades: {n_dos} completos" if hacer_prof else "")
            + (f" | tipo de red: {n_tipus}" if capa_pous is not None else "")
        )


class VolcadorTuberias:
    """Plugin entrypoint."""

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.action_cfg = None
        self.action_no_pisar = None
        self.tool = None
        #: Si NO se pisa lo que ya tenga valor. Por defecto SI se respeta.
        #:
        #: ⚠ Hasta la 1.5.4 la herramienta reescribia siempre el DIAMETRE, el
        #: MATERIAL, el TIPUS_XARXA y las profundidades, tuvieran valor o no.
        #: En un municipio recien digitalizado da igual, porque estan vacios --
        #: y para eso se hizo. Pero en uno ya hecho **borra las correcciones a
        #: mano**: lo pregunto Marisa el 09/09/2026 (*"si ahora uso la
        #: herramienta, me meteria las prof si el resto de datos ya los tengo
        #: metidos?"*) y la respuesta era que si, y de paso le pisaba lo
        #: corregido. En Arboli eso habria devuelto el diametro de la madre a
        #: los trams que ella habia arreglado.
        # Se recuerda entre sesiones: antes volvia a marcarse en cada
        # arranque de QGIS y habia que desmarcarlo otra vez para seguir
        # trabajando igual que el dia anterior (Marisa, 06/10/2026).
        from qgis.PyQt.QtCore import QSettings
        self.no_pisar = QSettings().value(
            'volcador_tuberias/no_pisar', True, type=bool)

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        icon = QIcon(icon_path) if os.path.isfile(icon_path) else QIcon()

        # boton principal: activar herramienta
        self.action = QAction(icon, "Volcar Tuberia a Tram (211)", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.setToolTip(
            "1) Selecciona tram(s) en 211. 2) Activa esta herramienta. "
            "3) Clic sobre una tuberia: vuelca DIAMETRE+MATERIAL."
        )
        self.action.triggered.connect(self._toggle)

        # boton: girar el sentido de un tram
        #
        # Invertir la linea a mano deja los atributos apuntando al extremo de
        # antes y no da ningun error: el mapa se ve bien y los datos mienten.
        # Esto gira geometria y datos a la vez.
        self.action_girar = QAction(
            QIcon(), "Girar el sentido de un tram (111/211)",
            self.iface.mainWindow())
        self.action_girar.setCheckable(True)
        self.action_girar.setToolTip(
            "Clic sobre un tram y le da la vuelta ENTERA: geometria, "
            "ID_NODE1/2, Z_NODE1/2, PROF_NODE1/2 y prof_colector1/2 "
            "intercambiados, LONGIT medida otra vez y PENDENT recalculada "
            "con el signo nuevo."
            + chr(10) + chr(10) +
            "No decide si un tram esta al reves: eso lo miras tu con las "
            "flechas de la capa madre delante."
            + chr(10) +
            "Si la capa ya estaba en edicion, el cambio se queda sin guardar "
            "y lo puedes deshacer con Ctrl+Z.")
        self.action_girar.triggered.connect(self._toggle_girar)

        # boton: volcar un pou de la ACA a la 231 (pous en alta)
        #
        # Marisa, 27/10/2026: lo mismo que el volcador pero para los pous en
        # alta, cogiendo los datos de la capa Pous de la ACA.
        self.action_pous_alta = QAction(
            QIcon(), "Volcar pou de la ACA a la 231 (pous en alta)",
            self.iface.mainWindow())
        self.action_pous_alta.setCheckable(True)
        self.action_pous_alta.setToolTip(
            "1) Selecciona el pou de registro (222) medido en campo. "
            "2) Activa esta herramienta. 3) Clic sobre el pou de la capa Pous "
            "de la ACA." + chr(10) + chr(10) +
            "Crea el pou en alta (231) en la posicion del 222, o lo completa "
            "si ya hay uno ahi." + chr(10) +
            "De la ACA: POU_ID, N_POU, COD_SIST, TIP_POU." + chr(10) +
            "Del 222 (manda campo): PROF, Z_T, Z_FONS y CON_BAIXA (= NUM_ESC).")
        self.action_pous_alta.triggered.connect(self._toggle_pous_alta)

        # boton: volcar el municipio entero, sin pulsar tram a tram
        #
        # Para los municipios que se digitalizaron antes de que existiera el
        # volcador: Marca 380 flechas con profundidad, Maspujols 430,
        # L'Aleixar 276, Vilaplana 90. A mano es una tarde por municipio.
        # Escribe solo donde no hay nada que decidir y saca el resto a una
        # capa de dudosos. (Marisa, 15/09/2026.)
        self.action_lote = QAction(
            QIcon(), "Volcar TODO el municipio (deja capa de dudosos)",
            self.iface.mainWindow())
        self.action_lote.setToolTip(
            "Recorre el 211 entero con la misma regla que el volcador y "
            "rellena prof_colector1/2 SOLO donde no hay duda." + chr(10) +
            "Una punta se da por buena si la flecha le gana por angulo a la "
            "segunda con holgura Y el diametro y el material del tram cuadran "
            "con los de esa flecha." + chr(10) +
            "Todo lo demas se queda como esta y sale en la capa "
            "DUDOSO_prof_colector, para resolverlo pulsando encima." + chr(10) +
            chr(10) +
            "Pregunta antes si quieres una pasada en seco, que no escribe "
            "nada y solo cuenta.")
        self.action_lote.triggered.connect(self._volcar_lote)

        # boton: la simbologia de trabajo del inventario
        #
        # Al unir un municipio las capas salen con el estilo por defecto de
        # QGIS y hay que ponerles el de trabajo una a una, diez veces, cada
        # vez que se abre. (Marisa, 25/09/2026.)
        self.action_simbologia = QAction(
            QIcon(), "Poner la simbologia de inventario",
            self.iface.mainWindow())
        self.action_simbologia.setToolTip(
            "Aplica a las capas del proyecto los estilos de TRABAJO, los de "
            "F:/Tarragona/01_Preparacion_previa/Estilos." + chr(10) +
            "Toca el 111, 124, 125, 211, 222, 224, 225, 231, la capa madre "
            "Tuberias y Ref_Elementos." + chr(10) + chr(10) +
            "No son los estilos de la entrega: aquellos son los que ve el "
            "cliente y estos ensenan lo que hace falta para revisar -- el "
            "sentido de las flechas, la calidad del GPS de cada referencia.")
        self.action_simbologia.triggered.connect(self._poner_simbologia)

        # boton secundario: configurar campos
        self.action_cfg = QAction(QIcon(), "Configurar campos a volcar...", self.iface.mainWindow())
        self.action_cfg.triggered.connect(self._configurar)

        # interruptor: respetar lo que ya esta escrito
        self.action_no_pisar = QAction(
            QIcon(), "No pisar lo que ya tenga valor",
            self.iface.mainWindow())
        self.action_no_pisar.setCheckable(True)
        self.action_no_pisar.setChecked(self.no_pisar)
        self.action_no_pisar.setToolTip(
            "Marcado (lo normal): solo rellena lo que este vacio. Es lo que "
            "hace falta en un municipio ya digitalizado, para no borrar las "
            "correcciones hechas a mano."
            + chr(10) +
            "Sin marcar: reescribe siempre con lo que diga la capa madre.")
        self.action_no_pisar.toggled.connect(self._set_no_pisar)

        self.iface.addPluginToMenu("Tarragona", self.action)
        self.iface.addPluginToMenu("Tarragona", self.action_girar)
        self.iface.addPluginToMenu("Tarragona", self.action_pous_alta)
        self.iface.addPluginToMenu("Tarragona", self.action_lote)
        self.iface.addPluginToMenu("Tarragona", self.action_simbologia)
        self.iface.addPluginToMenu("Tarragona", self.action_cfg)
        self.iface.addPluginToMenu("Tarragona", self.action_no_pisar)
        self.iface.addToolBarIcon(self.action)
        self.iface.addToolBarIcon(self.action_girar)
        self.iface.addToolBarIcon(self.action_pous_alta)
        # Tambien en la barra: estaba solo en el menu y Marisa lo
        # busco dos veces entre los botones sin encontrarlo
        # (01/10/2026). Se usa al abrir cada municipio, asi que a
        # mano.
        self.iface.addToolBarIcon(self.action_simbologia)

    def _poner_simbologia(self):
        """Pone a cada capa del proyecto su estilo de trabajo."""
        from .simbologia import aplicar_simbologia
        from qgis.core import QgsMessageLog, Qgis

        def _log(m):
            QgsMessageLog.logMessage(str(m), 'Volcador', Qgis.Info)

        _log(chr(9552) * 3 + ' Simbologia de inventario ' + chr(9552) * 3)
        puestos, _sin, faltan = aplicar_simbologia(self.iface, _log)
        if faltan:
            self.iface.messageBar().pushWarning(
                'Simbologia',
                'Puesta en %d capa(s). Faltan %d estilo(s): mira el registro.'
                % (puestos, len(faltan)))
        elif puestos:
            self.iface.messageBar().pushSuccess(
                'Simbologia', 'Puesta en %d capa(s).' % puestos)
        else:
            self.iface.messageBar().pushInfo(
                'Simbologia',
                'Ninguna capa reconocida. Abre el proyecto del municipio.')

    def _volcar_lote(self):
        """Pasa el volcador por todo el municipio, con capa de dudosos."""
        from qgis.PyQt.QtWidgets import QMessageBox
        from .lote import volcar_lote, CAPA_DUDOSOS

        # Botones que dicen lo que hacen. Antes era Si/No con 'SI = hacerlo
        # de verdad' y 'NO = pasada en seco' escrito en el cuerpo: quien
        # queria la prueba pulsaba Si -- '¿si, hazla?' -- y escribia en firme.
        # Le paso a Marisa el 05/10/2026.
        dlg = QMessageBox(self.iface.mainWindow())
        dlg.setWindowTitle('Volcar todo el municipio')
        dlg.setIcon(QMessageBox.Question)
        dlg.setText('Voy a recorrer el 211 entero y rellenar '
                    'prof_colector1/2 donde no haya duda.')
        dlg.setInformativeText(
            'Pasada en seco: cuenta lo que haria, sin escribir nada. Puede '
            'ademas COMPARAR contra lo que ya este puesto, para ver si la '
            'herramienta acierta.' + chr(10) + chr(10) +
            'Volcar de verdad: escribe. Por defecto respeta lo que ya tenga '
            'valor; te preguntare si quieres PISARLO.')
        b_seco = dlg.addButton('Pasada en seco',
                               QMessageBox.AcceptRole)
        b_real = dlg.addButton('Volcar de verdad',
                               QMessageBox.DestructiveRole)
        b_canc = dlg.addButton('Cancelar', QMessageBox.RejectRole)
        dlg.setDefaultButton(b_seco)
        dlg.exec_()
        pulsado = dlg.clickedButton()
        if pulsado is b_canc or pulsado is None:
            return
        dry = (pulsado is b_seco)

        comparar = False
        if dry:
            c = QMessageBox.question(
                self.iface.mainWindow(), 'Pasada en seco',
                '¿Comparo tambien con las profundidades que YA estan puestas?'
                + chr(10) + chr(10) +
                'SI = modo validacion: dice en cuantas coincide y en cuantas '
                'no. Sirve para comprobar la herramienta en un municipio ya '
                'volcado a mano.' + chr(10) +
                'NO = solo mira lo que esta vacio, que es lo que hay que '
                'rellenar. Lo ya resuelto no se toca ni sale en los dudosos.',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            comparar = (c == QMessageBox.Yes)

        # Pisar lo ya escrito: no es el modo normal, pero cuando una
        # pasada anterior del propio volcador dejo valores malos,
        # repetirla es la forma natural de arreglarlo. Alcover,
        # 05/10/2026: corregirlos a mano uno por uno no es viable.
        pisar = False
        if not dry:
            q = QMessageBox.question(
                self.iface.mainWindow(), 'Volcar todo el municipio',
                '¿PISO las profundidades que YA estan puestas?'
                + chr(10) + chr(10) +
                'NO  = lo normal. Solo rellena lo que esta vacio y no '
                'toca nada de lo que ya hay.' + chr(10) + chr(10) +
                'SI  = recalcula TODO y sobreescribe. Ademas corrige el '
                'DIAMETRE y el MATERIAL del tram cuando no cuadran con la '
                'flecha de la madre, en vez de mandarlo a dudosos.' + chr(10) +
                chr(10) +
                'OJO: si alguien ha corregido valores A MANO, se '
                'pierden. Si no estas segura, pasa primero en seco con '
                'la comparacion, que te dice en cuantas difiere.',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            pisar = (q == QMessageBox.Yes)

        res = volcar_lote(self, self.iface, dry_run=dry,
                          comparar=comparar, pisar=pisar)
        if 'error' in res:
            self.iface.messageBar().pushWarning('Volcador', res['error'])
            return

        cab = 'PASADA EN SECO (no se ha escrito nada)' if dry else 'Volcado'
        lin = ['%s: %d trams' % (cab, res['trams']),
               '  profundidades que pondria: %d' % res['escritas']
               if dry else '  profundidades puestas: %d' % res['escritas'],
               '  dudosas, sin tocar: %d' % res['dudosas']]
        # En seco, lo que ya estaba puesto A MANO no se salta: se compara.
        # Es la unica forma de saber si el automatico coge lo mismo.
        if dry and comparar and (res.get('cmp_ok') or res.get('cmp_mal')
                    or res.get('cmp_nosabe')):
            tot = res['cmp_ok'] + res['cmp_mal'] + res['cmp_nosabe']
            lin.append('')
            lin.append('  CONTRA LO QUE YA ESTABA PUESTO A MANO (%d):' % tot)
            lin.append('     coinciden:        %d' % res['cmp_ok'])
            lin.append('     DIFIEREN:         %d' % res['cmp_mal'])
            lin.append('     no sabria ponerlo: %d' % res['cmp_nosabe'])
            if res.get('cd'):
                lin.append('     (aparte: %d puntas acaban en un CD, que no '
                           'lleva flecha)' % res['cd'])
            if res['cmp_mal']:
                lin.append('     Los que difieren estan en la capa de dudosos, '
                           'con los dos valores.')
        else:
            if res.get('pisadas'):
                lin.append('  ya tenian valor y se han PISADO: %d'
                           % res['pisadas'])
            if res.get('corr_diametro') or res.get('corr_material'):
                lin.append('')
                lin.append('  CORREGIDO del tram con lo que dice la flecha:')
                if res.get('corr_diametro'):
                    lin.append('     DIAMETRE: %d' % res['corr_diametro'])
                if res.get('corr_material'):
                    lin.append('     MATERIAL: %d' % res['corr_material'])
                for c in (res.get('correcciones') or [])[:10]:
                    lin.append('     %s' % c)
                if len(res.get('correcciones') or []) > 10:
                    lin.append('     ... y %d mas (estan en la consola)'
                               % (len(res['correcciones']) - 10))
            lin.append('  ya tenian valor, respetadas: %d'
                       % res['ya_tenian'])
        if res['sin_corroborar']:
            lin.append('  de las puestas, %d sin poder comprobar diametro ni '
                       'material (el tram no los tenia)'
                       % res['sin_corroborar'])
        for m, n in sorted(res['motivos'].items(), key=lambda x: -x[1]):
            lin.append('     %-46s %d' % (m, n))
        if res['dudosas']:
            # El numero que se da tiene que ser el que luego se ve en la
            # capa. Las puntas repetidas se dicen aparte, no se suman: si no,
            # el mensaje dice 36 y la capa trae 25 (Marisa, 07/10/2026).
            lin.append('  Las dudosas estan en la capa %s (%d filas).'
                       % (CAPA_DUDOSOS, res['dudosas']))
            if res.get('dudosas_repetidas'):
                lin.append('  (%d puntas mas caian en el mismo punto y por el '
                           'mismo motivo: una sola fila cada una)'
                           % res['dudosas_repetidas'])
        if res.get('diag'):
            lin.append('')
            lin.append('  QUE HE MIRADO:')
            for x in res['diag']:
                lin.append('     ' + x)
        texto = chr(10).join(lin)
        for l in lin:
            print(l)
        QMessageBox.information(self.iface.mainWindow(),
                                'Volcado del municipio', texto)
        if not dry:
            self.iface.messageBar().pushInfo(
                'Volcador',
                '%d profundidades puestas, %d dudosas sin tocar. Los cambios '
                'estan SIN GUARDAR: revisalos y guarda la capa.'
                % (res['escritas'], res['dudosas']))

    def unload(self):
        if self.tool:
            self.iface.mapCanvas().unsetMapTool(self.tool)
            self.tool = None
        if getattr(self, 'action_lote', None):
            self.iface.removePluginMenu("Tarragona", self.action_lote)
        if self.action:
            self.iface.removePluginMenu("Tarragona", self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None
        if getattr(self, 'tool_girar', None):
            self.iface.mapCanvas().unsetMapTool(self.tool_girar)
            self.tool_girar = None
        if getattr(self, 'action_girar', None):
            self.iface.removePluginMenu("Tarragona", self.action_girar)
            self.iface.removeToolBarIcon(self.action_girar)
            self.action_girar = None
        if getattr(self, 'tool_pous_alta', None):
            self.iface.mapCanvas().unsetMapTool(self.tool_pous_alta)
            self.tool_pous_alta = None
        if getattr(self, 'action_pous_alta', None):
            self.iface.removePluginMenu("Tarragona", self.action_pous_alta)
            self.iface.removeToolBarIcon(self.action_pous_alta)
            self.action_pous_alta = None
        if getattr(self, 'action_simbologia', None):
            self.iface.removePluginMenu(
                "Tarragona", self.action_simbologia)
            self.iface.removeToolBarIcon(self.action_simbologia)
            self.action_simbologia = None
        if self.action_cfg:
            self.iface.removePluginMenu("Tarragona", self.action_cfg)
            self.action_cfg = None
        if self.action_no_pisar:
            self.iface.removePluginMenu("Tarragona", self.action_no_pisar)
            self.action_no_pisar = None

    def _toggle(self, checked):
        if checked:
            self.tool = VolcadorMapTool(self.iface.mapCanvas(), self)
            # Sin setAction el boton se quedaba marcado al pasar a otra
            # herramienta (Marisa, 06/11/2026). Igual que el de pous en alta.
            self.tool.setAction(self.action)
            self.iface.mapCanvas().setMapTool(self.tool)
        else:
            if self.tool:
                self.iface.mapCanvas().unsetMapTool(self.tool)
                self.tool = None

    def _toggle_girar(self, checked):
        if checked:
            from .girar import GirarMapTool
            self.tool_girar = GirarMapTool(self.iface.mapCanvas(), self, None)
            self.tool_girar.setAction(self.action_girar)
            self.iface.mapCanvas().setMapTool(self.tool_girar)
        else:
            if getattr(self, 'tool_girar', None):
                self.iface.mapCanvas().unsetMapTool(self.tool_girar)
                self.tool_girar = None

    def _toggle_pous_alta(self, checked):
        if checked:
            from .pous_alta import PousAltaMapTool
            self.tool_pous_alta = PousAltaMapTool(self.iface.mapCanvas(), self)
            self.tool_pous_alta.setAction(self.action_pous_alta)
            self.iface.mapCanvas().setMapTool(self.tool_pous_alta)
        else:
            if getattr(self, 'tool_pous_alta', None):
                self.iface.mapCanvas().unsetMapTool(self.tool_pous_alta)
                self.tool_pous_alta = None

    def _set_no_pisar(self, activo):
        self.no_pisar = bool(activo)
        from qgis.PyQt.QtCore import QSettings
        QSettings().setValue('volcador_tuberias/no_pisar', self.no_pisar)
        self.iface.messageBar().pushMessage(
            "Volcador",
            ("Solo se rellenara lo que este VACIO."
             if self.no_pisar else
             "Se reescribira todo, tenga valor o no."),
            level=0, duration=4)

    def _configurar(self):
        """Permite cambiar el mapeo de campos en tiempo de ejecucion (no persiste).

        Formato: "origen->destino, origen2->destino2, ..."
        Si solo se pone un nombre, se asume que es igual en ambas capas.
        """
        global FIELD_MAPPING
        def dest_name(v):
            return v[0] if isinstance(v, tuple) else v
        actual = ", ".join(f"{o}->{dest_name(d)}" for o, d in FIELD_MAPPING.items())
        text, ok = QInputDialog.getText(
            self.iface.mainWindow(),
            "Mapeo de campos a volcar",
            "Formato:  origen->destino, origen2->destino2\n"
            "(las transformaciones Diametro->int y Material->codigo se preservan)",
            text=actual,
        )
        if ok and text.strip():
            nuevo = {}
            for parte in text.split(","):
                parte = parte.strip()
                if not parte: continue
                if "->" in parte:
                    o, d = parte.split("->", 1)
                    o, d = o.strip(), d.strip()
                else:
                    o = d = parte
                # preservar transform si ya existia para ese origen
                if o in FIELD_MAPPING and isinstance(FIELD_MAPPING[o], tuple):
                    transform = FIELD_MAPPING[o][1]
                    nuevo[o] = (d, transform)
                else:
                    nuevo[o] = (d, _t_passthrough)
            FIELD_MAPPING = nuevo
            self.iface.messageBar().pushSuccess(
                "Volcador",
                f"Mapeo: {', '.join(f'{o}->{dest_name(d)}' for o,d in FIELD_MAPPING.items())}"
            )
