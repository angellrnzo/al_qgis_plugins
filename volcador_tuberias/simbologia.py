# -*- coding: utf-8 -*-
"""Poner la simbologia de inventario a las capas del proyecto unido.

Despues de unir un municipio, las capas salen con el estilo por defecto de
QGIS: todo del mismo color y sin flechas. Para revisar el inventario hace falta
la simbologia de trabajo -- la de la capa madre con sus flechas, la de los
pous, la de las referencias --, y ponerla a mano capa por capa son diez pasos
cada vez que se abre un municipio.

Pedido por Marisa el 25/09/2026, con los estilos elegidos por ella.

⚠ Los estilos NO son los de la entrega. Los de `simbologia_entrega` son los que
ve el cliente; estos son los de trabajo, que ensenan cosas que en la entrega no
interesan (el sentido de las flechas, la calidad del GPS de cada referencia).
Son dos juegos distintos a proposito.
"""
import os

from qgis.core import QgsProject


#: Donde viven los estilos de trabajo.
ESTILOS = r"F:\Tarragona\01_Preparacion_previa\Estilos"

#: Que estilo lleva cada capa. Elegidos por Marisa, 25/09/2026.
#:
#: La clave es el principio del nombre de la capa, que es lo unico estable:
#: una capa puede llamarse `211_Trams_Sanejament` o `211_Trams_Sanejament_v2`
#: segun el municipio.
ESTILO_DE = (
    ('111', os.path.join('Potables', '111_v5.qml')),
    ('124', os.path.join('Potables', '124_v2.qml')),
    ('125', os.path.join('Potables', '125_v2.qml')),
    ('211', os.path.join('Saneamiento', '211_v4.qml')),
    ('222', os.path.join('Saneamiento', '222_v4.qml')),
    ('224', os.path.join('Saneamiento', '224.qml')),
    ('225', os.path.join('Saneamiento', '225.qml')),
    ('231', os.path.join('Saneamiento', '231_v2.qml')),
    ('Tuberias', os.path.join('Referencia', 'Tuberias_v6.qml')),
    ('Tuberías', os.path.join('Referencia', 'Tuberias_v6.qml')),
    ('Ref_Elementos', os.path.join('Topografia', 'topografia.qml')),
    ('Ref_elementos', os.path.join('Topografia', 'topografia.qml')),
)


def _estilo_para(nombre):
    """El QML que le toca a una capa, o None si no esta en la lista."""
    n = (nombre or '').strip()
    for prefijo, qml in ESTILO_DE:
        if n.lower().startswith(prefijo.lower()):
            return qml
    return None


def aplicar_simbologia(iface, log=print, carpeta=None):
    """Aplica a cada capa del proyecto el estilo de trabajo que le toca.

    Devuelve (puestos, sin_estilo, que_faltan).
    """
    base = carpeta or ESTILOS
    if not os.path.isdir(base):
        log('[ERROR] No encuentro la carpeta de estilos: %s' % base)
        return 0, 0, []

    puestos, sin_estilo, faltan = 0, 0, []
    for capa in QgsProject.instance().mapLayers().values():
        try:
            if capa.type() != capa.VectorLayer:
                continue
        except Exception:
            continue
        rel = _estilo_para(capa.name())
        if rel is None:
            sin_estilo += 1
            continue
        qml = os.path.join(base, rel)
        if not os.path.exists(qml):
            faltan.append((capa.name(), rel))
            continue
        # ⚠ `loadNamedStyle` carga el estilo GUARDADO EN EL GEOPACKAGE si la
        # capa tiene uno, no el fichero que se le pasa. Hay que decirle que
        # esto es un fichero.
        try:
            capa.loadNamedStyle(qml)
            capa.triggerRepaint()
            puestos += 1
            log('  %-38s <- %s' % (capa.name()[:38], rel))
        except Exception as e:
            log('  [AVISO] %s: %s' % (capa.name(), e))

    log('')
    if puestos:
        log('Simbologia puesta en %d capa(s).' % puestos)
    else:
        log('No he puesto ninguna. ?Es el proyecto del municipio unido?')
    if sin_estilo:
        log('  (%d capa(s) sin estilo asignado: se quedan como estaban)'
            % sin_estilo)
    for nombre, rel in faltan:
        log('  [!] %s: no existe el estilo %s' % (nombre, rel))
    if iface is not None:
        try:
            iface.mapCanvas().refreshAllLayers()
        except Exception:
            pass
    return puestos, sin_estilo, faltan
