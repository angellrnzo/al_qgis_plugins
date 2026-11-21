# -*- coding: utf-8 -*-
"""
Exportador de Redes Pro (Beta 0.16)
Plugin QGIS para automatizar la preparación, recorte y exportación
de planos de Abastecimiento y Saneamiento.
"""


def classFactory(iface):
    """Punto de entrada obligatorio para QGIS."""
    from .exportador_plugin import ExportadorRedesPlugin
    return ExportadorRedesPlugin(iface)