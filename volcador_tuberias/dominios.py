# -*- coding: utf-8 -*-
"""Resolucion de codigos de dominio para el volcador de tuberias.

POR QUE ESTO EXISTE
-------------------
La capa madre `Tuberias` guarda `Material` y `Diametro` como CODIGOS, no como
texto: 11, 152, 133, 7... El volcador los traducia con `_stored_to_label()`, o
sea **usando la configuracion del desplegable de la capa en QGIS**. Cuando esa
configuracion no esta -- proyecto montado de otra forma, capa de dominio sin
cargar, widget perdido -- la traduccion no ocurre, no salta ningun error, y se
escribe **el codigo crudo** en el 211. Ahi estaba el "algunos materiales
fallaban" que reporto Marisa, y por eso fallaba de forma intermitente.

Este modulo lee los CSV de dominio, que estan al lado del GPKG y no dependen de
como este montado el proyecto.

LOS DOS FICHEROS
----------------
`dominio_material_tuberias.csv`  ->  cod_red ; red ; cod_mat ; mat

    ⚠️ El MISMO NUMERO significa cosas distintas segun la red:

        200 Saneamiento:  1 PVC LISO · 10 PVC CORRUGADO · 11 HORMIGON
                         12 Otro     · 14 PRFVC
        100 Potable:      1 PVC LISO · 2 Polietileno · 3 Fibrocemento
                          4 PP · 5 Fundicion · 6 Plomo · 7 Acero
                          8 Otro · 13 PRFVC

    Y la capa madre lleva LAS DOS REDES -- tiene columna `Red`. El volcador
    ignoraba `Red` por completo.

`dominio_tuberias_.csv`  ->  cod_mat ; mat ; cod_ele ; ele

    El `cod_ele` es un indice GLOBAL de 1 a 247 que no se repite entre
    materiales, asi que basta el numero para resolver el diametro:

        cod_ele 7   -> PVC LISO       150 mm
        cod_ele 127 -> PVC CORRUGADO  150 mm
        cod_ele 133 -> PVC CORRUGADO  350 mm
        cod_ele 152 -> HORMIGON       200 mm
        cod_ele 225 -> PRFVC          300 mm

⚠️ NO TODOS LOS CSV USAN COMA: en Prat de Comte van con punto y coma, y leerlos
suponiendo la coma deja el diccionario vacio sin dar ningun error. El separador
se saca de la cabecera.
"""
import csv
import io
import os
import re
import unicodedata


def _norm(txt):
    """Minusculas sin acentos ni signos, para comparar."""
    t = unicodedata.normalize("NFD", str(txt or ""))
    t = t.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", t.lower())


def _sep(ruta):
    """El separador que use la cabecera. No todos usan coma."""
    with io.open(ruta, encoding="utf-8-sig", errors="replace") as f:
        cab = f.readline()
    return ";" if cab.count(";") > cab.count(",") else ","


def _leer(ruta):
    with io.open(ruta, encoding="utf-8-sig", errors="replace") as f:
        return list(csv.DictReader(f, delimiter=_sep(ruta)))


def _buscar(carpetas, nombre):
    for c in carpetas:
        if not c:
            continue
        p = os.path.join(c, nombre)
        if os.path.isfile(p):
            return p
        for dp, _dn, fn in os.walk(c):
            if nombre in fn:
                return os.path.join(dp, nombre)
    return None


class Dominios(object):
    """Los dos diccionarios, leidos del disco.

    `avisos` recoge lo que no se ha podido hacer, para que el volcador lo diga
    en vez de degradarse en silencio -- que es justo el fallo que se arregla.
    """

    def __init__(self, carpetas):
        self.materiales = {}        # (cod_red, cod_mat) -> texto
        self.por_material = {}      # cod_mat -> texto  (cuando no hay red)
        self.diametros = {}         # cod_ele -> mm (int)
        self.avisos = []

        f = _buscar(carpetas, "dominio_material_tuberias.csv")
        if not f:
            self.avisos.append("no encuentro dominio_material_tuberias.csv")
        else:
            try:
                for r in _leer(f):
                    red = str(r.get("cod_red", "")).strip()
                    cod = str(r.get("cod_mat", "")).strip()
                    mat = (r.get("mat") or "").strip()
                    if cod and mat:
                        self.materiales[(red, cod)] = mat
                        self.por_material.setdefault(cod, mat)
                if not self.materiales:
                    self.avisos.append(
                        "dominio_material_tuberias.csv esta ahi pero no he "
                        "sacado ninguna fila (¿separador raro?)")
            except Exception as e:
                self.avisos.append("no puedo leer %s: %s"
                                   % (os.path.basename(f), e))

        f = _buscar(carpetas, "dominio_tuberias_.csv")
        if not f:
            self.avisos.append("no encuentro dominio_tuberias_.csv")
        else:
            try:
                for r in _leer(f):
                    cod = str(r.get("cod_ele", "")).strip()
                    ele = (r.get("ele") or "").strip()
                    m = re.search(r"\d+", ele)
                    if cod and m:
                        self.diametros[cod] = int(m.group())
                if not self.diametros:
                    self.avisos.append(
                        "dominio_tuberias_.csv esta ahi pero no he sacado "
                        "ninguna fila (¿separador raro?)")
            except Exception as e:
                self.avisos.append("no puedo leer %s: %s"
                                   % (os.path.basename(f), e))

    # -- resolucion --------------------------------------------------------

    def material(self, valor, red=None):
        """codigo -> texto. Devuelve (texto, explicacion) o (None, motivo)."""
        if valor in (None, ""):
            return None, "vacio en la madre"
        cod = str(valor).strip()
        if cod.endswith(".0"):
            cod = cod[:-2]
        r = str(red).strip() if red not in (None, "") else None
        if r and r.endswith(".0"):
            r = r[:-2]
        if r and (r, cod) in self.materiales:
            return self.materiales[(r, cod)], "dominio red %s codigo %s" % (r, cod)
        if cod in self.por_material:
            texto = self.por_material[cod]
            if r:
                return texto, ("dominio codigo %s, pero SIN casar con la red %s"
                               % (cod, r))
            return texto, "dominio codigo %s (la madre no dice la red)" % cod
        # Puede que ya venga en texto
        if not cod.isdigit():
            return cod, "ya venia en texto"
        return None, ("el codigo %s no esta en dominio_material_tuberias.csv%s"
                      % (cod, (" para la red %s" % r) if r else ""))

    def diametro(self, valor):
        """cod_ele -> mm. Devuelve (mm, explicacion) o (None, motivo)."""
        if valor in (None, ""):
            return None, "vacio en la madre"
        cod = str(valor).strip()
        if cod.endswith(".0"):
            cod = cod[:-2]
        if cod in self.diametros:
            return self.diametros[cod], "dominio cod_ele %s" % cod
        m = re.search(r"\d+", cod)
        if m:
            n = int(m.group())
            # Si ya viene en mm no hay nada que resolver. Un cod_ele va de 1 a
            # 247, asi que por encima de eso es seguro que ya son milimetros.
            if n > 247:
                return n, "ya venia en milimetros"
            return None, ("%s podria ser un codigo de dominio o unos "
                          "milimetros y no esta en dominio_tuberias_.csv: no "
                          "me la juego" % n)
        return None, "no entiendo el valor %r" % valor


def es_saneamiento(red):
    """La madre lleva las dos redes: 100 potable, 200 saneamiento."""
    r = str(red or "").strip()
    if r.endswith(".0"):
        r = r[:-2]
    if r == "200":
        return True
    if r == "100":
        return False
    return None if not r else _norm(r).startswith("sane") or None


# --------------------------------------------------------------------------
# Cuando el dato no esta en su columna sino escrito en el comentario
# --------------------------------------------------------------------------
#
# Marisa (05/09/2026): *"en la capa tuberias a veces no hay diametro y material
# porque debe ser que no esta en el dominio y los chicos lo escriben en la
# columna comentario"*.
#
# Mirados los comentarios reales de los 82 municipios, escriben asi:
#
#     DN100 · DN 850 · DN220. ESCOMBRO · TUBO DEFORMADO. DN 180
#     ESCOMBRO. DN330 · DN300 HORMIGON · DN50 PE · PE de 140 · 30 mm
#
# Y tambien dicen cuando NO se puede medir, que es informacion igual de util:
#
#     NO SE PUEDE TOMAR DN · NO ES POSIBLE MEDICION · ESCOMBRO
#     TUBO DEFORMADO · TUBO ROTO · NO SE APRECIA MATERIAL · DN DIFICIL DE TOMAR
#
# ⚠️ Dos trampas que hay que esquivar:
#
#   * `NO SE PUEDE TOMAR DN` lleva "DN" pero sin numero detras. Un patron que
#     busque "DN" a secas y luego el primer numero de la linea se traeria un
#     numero de otro sitio.
#   * `NO TUBO, "GALERIA" 350x300` es una SECCION RECTANGULAR, no un diametro.
#     Coger el 350 seria inventarse un tubo redondo que no existe.
#
# Regla: solo se lee lo inequivoco, y **siempre se dice que el valor sale del
# comentario y no de su columna**.

_RE_RECT = re.compile(r"(\d{2,5})\s*[x\u00d7*]\s*(\d{2,5})", re.I)
_RE_DN = re.compile(r"\bDN\s*[.:]?\s*(\d{2,4})\b", re.I)
_RE_MM = re.compile(r"\b(\d{2,4})\s*mm\b", re.I)
_RE_DE = re.compile(r"\bde\s+(\d{2,4})\b", re.I)

#: Frases con las que dicen que no se pudo medir.
_NO_MEDIBLE = ("no se puede", "no sw puede", "no es posible", "no se aprecia",
               "no puedo tomar", "no pudo", "dificil de tomar",
               "no se puede tomar", "imposible", "no medible")

#: Abreviaturas que usan para el material, con el texto del dominio al que van.
_MATERIALES_TEXTO = (
    ("hormigon", "HORMIGON"),
    ("pvc corrugado", "PVC CORRUGADO"),
    ("corrugado", "PVC CORRUGADO"),
    ("pvc liso", "PVC LISO"),
    ("pvc", "PVC"),
    ("fibrocemento", "Fibrocemento"),
    ("uralita", "Fibrocemento"),
    ("fundicion", "Fundicion"),
    ("polietileno", "Polietileno"),
    ("prfv", "PRFVC"),
    ("gres", "Gres"),
    ("ladrillo", "Otro"),
    ("obra", "Otro"),
)
#: Siglas sueltas: solo valen como palabra entera, que si no "PE" sale dentro
#: de cualquier palabra.
_MATERIALES_SIGLA = (("pe", "Polietileno"), ("ho", "HORMIGON"),
                     ("fc", "Fibrocemento"), ("fu", "Fundicion"),
                     ("pead", "Polietileno"))


#: Como escriben la profundidad en el comentario. Son tres formas para la
#: misma medida --la profundidad desde la tapa hasta la solera del tubo-- y en
#: Mont-roig aparecen las tres en la misma capa:
#:     "PROFUNDIDAD 1.50M"   "ALT. 0.9M"   "COTA 1.20"   y el numero a secas.
#: Entre la palabra y el numero puede colarse un calificativo: escriben
#: "COTA INTERIOR 0.57M" tanto como "COTA 1.20". Sin admitirlo se perdian.
_RE_PROF_ETIQUETA = re.compile(
    r"\b(?:PROFUNDIDAD|PROFUNDIDA|PROFUND|PROF|ALTURA|ALT|COTA)\s*[.:]?\s*"
    r"(?:(?:INTERIOR|INFERIOR|INT|INF|DEL\s+TUBO|DE\s+TUBO|TUBO)\s*[.:]?\s*){0,2}"
    r"(\d{1,2}[.,]\d{1,3}|\d{1,2})\s*M?\b", re.I)
#: El numero a secas SOLO cuenta si trae decimales: "1.544" es una
#: profundidad, "300" es un diametro. Sin esa condicion se confunden.
_RE_PROF_SOLA = re.compile(r"^\s*(\d{1,2}[.,]\d{1,3})\s*M?\s*$", re.I)

#: Por encima de esto no es una profundidad de colector: en las capas madre
#: hay un 1447 y un 109.
PROF_MAX = 10.0


#: Umbrales para leer una profundidad capturada. **Copiados** de
#: `field_preparer/core/layer_utils.py`, donde vive el original
#: (`interpretar_profundidad`). Se copian y no se importan porque el volcador
#: tiene que funcionar sin que el Field Preparer este instalado -- lo usan los
#: chicos mientras digitalizan. Si alli cambian, hay que cambiarlos aqui.
PROF_MAX_M = 20.0
PROF_AMBIGUA = (5.0, PROF_MAX_M)


def interpretar_profundidad(valor):
    """Una profundidad capturada -> (metros, unidad) o (None, motivo).

        777    -> (0.78, 'mm')
        1.67   -> (1.67, 'm')
        8.0    -> (None, 'ambigua')     ni 8 m ni 8 mm tienen sentido
        None/0 -> (None, 'sin dato')

    No se convierte a ciegas porque **las unidades cambian de un municipio a
    otro**: en la Vilella Alta, Pradell y la Vilella Baixa venian en metros y
    en la Bisbal de Falset en milimetros.
    """
    if valor is None:
        return (None, 'sin dato')
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return (None, 'no es un numero')
    if v == 0.0:
        return (None, 'sin dato')
    if v < 0:
        return (None, 'negativa')
    if PROF_AMBIGUA[0] <= v < PROF_AMBIGUA[1]:
        return (None, 'ambigua')
    if v >= PROF_MAX_M:
        return (round(v / 1000.0, 2), 'mm')
    return (round(v, 2), 'm')


#: Banda de sensatez para la profundidad de un embornal. NO basta con
#: `interpretar_profundidad`: a un 36 le aplica la regla de los milimetros y
#: devuelve **0,04 m**, que son cuatro centimetros -- un numero creible y
#: falso, que es lo peor que puede pasar. En Alcover hay justo un 36 asi (y
#: 309 valores buenos de 311). Fuera de esta banda no se escribe y se avisa,
#: para que lo mire una persona: Marisa lee ese 36 como un 0,36, pero eso hay
#: que verlo, no adivinarlo.
PROF_EMB_MIN = 0.10
PROF_EMB_MAX = 3.00


def prof_del_embornal(valor):
    """La profundidad utilizable de un embornal -> (metros, explicacion)."""
    m, u = interpretar_profundidad(valor)
    if m is None:
        return None, "el embornal trae %r y %s" % (valor, u)
    if not (PROF_EMB_MIN <= m <= PROF_EMB_MAX):
        return None, ("el embornal trae %r, que interpretado en %s da %.2f m: "
                      "fuera de lo creible para un embornal (%.2f-%.2f), no lo "
                      "escribo" % (valor, u, m, PROF_EMB_MIN, PROF_EMB_MAX))
    return m, ("del embornal (%s%s)"
               % (valor, ", leido en mm" if u == "mm" else ""))


def prof_del_comentario(texto):
    """La profundidad que el operario escribio en el comentario.

    Devuelve (metros, explicacion) o (None, motivo).

    Se coge **el valor etiquetado**, que es el bueno: un comentario corregido
    dice "PROFUNDIDAD 1.50M (corregida: se midio 0.90 a la generatriz
    superior, sumado DN 600)" y ahi el dato es 1,50 -- no el 0,90 ni el 600.
    """
    if texto in (None, ""):
        return None, "comentario vacio"
    t = str(texto).strip()
    if not t or t.upper() == "NULL":
        return None, "comentario vacio"

    m = _RE_PROF_ETIQUETA.search(t)
    como = "etiquetada"
    if not m:
        m = _RE_PROF_SOLA.match(t)
        como = "el numero a secas"
    if not m:
        return None, "el comentario no trae ninguna profundidad"

    try:
        v = float(m.group(1).replace(",", "."))
    except (TypeError, ValueError):
        return None, "no entiendo %r" % m.group(1)
    if not (0 < v < PROF_MAX):
        return None, ("el comentario da %.2f m, y eso no es una profundidad "
                      "de colector" % v)
    return v, "del comentario (%s)" % como


def del_comentario(texto):
    """Saca diametro y material de un comentario de campo.

    Devuelve un dict con `diametro`, `material`, `no_medible` y `avisos`.
    Lo que no se pueda leer con seguridad se queda a None: es preferible dejar
    el hueco a inventarse un dato.
    """
    out = {"diametro": None, "material": None, "no_medible": False,
           "avisos": []}
    if texto in (None, ""):
        return out
    t = str(texto).strip()
    if not t or t.upper() == "NULL":
        return out
    bajo = _norm(t)
    plano = t.lower()

    if any(f.replace(" ", "") in bajo for f in _NO_MEDIBLE):
        out["no_medible"] = True

    # -- seccion rectangular: no es un diametro -------------------------
    m = _RE_RECT.search(t)
    if m:
        out["avisos"].append(
            'el comentario dice "%s", que es una seccion rectangular de %sx%s '
            "y no un diametro: no lo escribo" % (t[:40], m.group(1), m.group(2)))
    else:
        m = _RE_DN.search(t) or _RE_MM.search(t) or _RE_DE.search(t)
        if m:
            n = int(m.group(1))
            if 20 <= n <= 3000:
                out["diametro"] = n
            else:
                out["avisos"].append(
                    "el comentario da %d mm de diametro, que no es creible" % n)

    for clave, valor in _MATERIALES_TEXTO:
        if clave in plano or clave.replace(" ", "") in bajo:
            out["material"] = valor
            break
    if out["material"] is None:
        for sigla, valor in _MATERIALES_SIGLA:
            if re.search(r"\b%s\b" % sigla, plano, re.I):
                out["material"] = valor
                break

    return out
