"""Volcar la profundidad de colector a TODO el municipio, de una pasada.

Por que existe
--------------
El volcador se usa tram a tram, pulsando encima. Eso esta bien mientras se
digitaliza, pero deja un problema con los municipios que se hicieron antes de
que existiera: Marca tiene 380 flechas con profundidad, Maspujols 430,
L'Aleixar 276 y Vilaplana 90. A mano es una tarde por municipio.

Y automatico del todo saldria mal, que es lo que dijo Marisa el 15/09/2026:
*"yo se que si se hace automatico va a salir mal"*. Tiene razon: en un pou con
tres colectores hay tres flechas arrancando del mismo punto, y elegir la
equivocada **no da ningun error** -- escribe una profundidad plausible en el
extremo equivocado.

Asi que esto escribe **solo donde no hay nada que decidir**, y lo demas lo saca
a una capa de dudosos para resolverlo pulsando con el volcador de siempre.

Como se elige la flecha de cada punta
-------------------------------------
Por orden. Los criterios de arriba son datos que escribio quien midio; el
angulo es una deduccion geometrica mia, y por eso va el ultimo.

1. **La punta esta en un CD (225)** -> fuera. Un tram que muere en un CD no
   lleva flecha; no se cuenta ni como duda.
2. **La punta esta en un imbornal** -> manda el imbornal. Tiene UN solo
   lateral, asi que su medida no tiene la ambiguedad de las flechas de un pou,
   y el pliego guarda ahi la cota inferior del tubo. Gana aunque arranque una
   flecha.
3. **Las flechas que van hacia el otro lado** (mas de `ANGULO_CONTRARIO`) se
   descartan, siempre que quede alguna por debajo.
4. **Tandas**, y se decide dentro de la primera que tenga algo:
   1. sentido correcto Y diametro Y material cuadrando
   2. sentido correcto
   3. diametro y material cuadrando
   4. las que no son auxiliares
   5. todas
5. **Una sola candidata en la tanda** -> esa es, sin mirar el angulo. Varias ->
   decide el angulo, con `MARGEN_ANG` de margen sobre la segunda.

El **sentido**: extremo 1 = por donde el agua SALE del pou (`Aguas Abajo`);
extremo 2 = por donde LLEGA (`Aguas Arriba`). Si el tram es el lateral de un
imbornal, es `Imbornales` **en sus dos puntas**.

⚠ El sentido no es infalible: **hay trams dibujados al reves del agua**. Por eso
el filtro de las flechas contrarias va ANTES que el.

⚠ La madre guarda el diametro y el material como **codigos de dominio**
(`Diametro='130'`), no como valores. Se traducen con `Dominios` -- el mismo CSV
que usa el volcador para escribir -- antes de compararlos. Compararlos en crudo
tumbaba 103 de 160 puntas buenas.

Lo que NO hace
--------------
* **Nunca** pisa lo que ya este escrito, pase lo que pase con el
  interruptor del menu: rellena huecos y nada mas. Lo que tiene valor no se
  evalua ni sale en los dudosos. Reescribir un valor concreto se hace pulsando
  encima con el volcador, que es donde se ve lo que se cambia.
* No interpola en los CD. El volcador si lo hace, pero un valor calculado no es
  un valor medido, y en una pasada masiva no se distingue.
* No toca la capa madre.

La pasada en seco COMPARA
-------------------------
No se salta lo que ya tiene valor: lo compara y dice en cuantas coincide,
difiere o no sabria decidir. Los municipios ya volcados a mano son la unica
verdad disponible, y asi se valido esto contra las **121 puntas de Arboli**:
de 0 aciertos en la primera version a **114**. Ver
`decision_como_elige_el_b6_la_flecha_de_cada_punta` en la memoria del proyecto.
"""
import math

from qgis.core import (QgsFeature, QgsFeatureRequest, QgsField, QgsGeometry,
                       QgsPointXY, QgsProject, QgsRectangle,
                       QgsVectorLayer, QgsCoordinateTransform)
from qgis.PyQt.QtCore import QVariant

from .dominios import Dominios, del_comentario
from .volcador_tuberias import (ANGULO_MAX, CAPA_CD_PATTERNS,
                                asegurar_columnas_prof,
                                CAPA_POUS_PATTERNS, CAMPO_INTERP,
                                SEP_INTERP, _prof_interpolada_en_cd,
                                CAPA_EMB_PATTERNS,
                                CAMPO_PROF_1, CAMPO_PROF_2,
                                CAMPO_PROF_CORREGIDA, CAMPO_PROF_ORIGEN,
                                CAPA_DESTINO_PATTERNS, FIELD_MAPPING,
                                TOL_EXTREMO, _dif_angular, _find_field_idx,
                                _nombre_de, _prof_de_la_flecha, _rumbo,
                                _vertices_de, _carpetas_de,
                                _hay_algo_en, _prof_del_embornal_en,
                                find_layer_by_name,
                                find_source_layer)

#: Cuanto tiene que ganarle la mejor flecha a la segunda para fiarse de ella.
#: 25 grados. Por debajo de eso, dos colectores que salen del mismo pou apuntan
#: demasiado parecido como para distinguirlos por el rumbo.
MARGEN_ANG = 0.44

#: Lo que tiene que separarse un vertice del extremo para que el segmento
#: sirva de rumbo. Por debajo de esto se pasa al siguiente: un vertice repetido
#: da un segmento de longitud cero y un angulo sin significado.
MIN_SEGMENTO = 0.05

#: Una flecha que se va mas de esto del rumbo del tram va hacia el otro
#: lado: no puede ser su colector. Se descarta SIEMPRE QUE haya alguna
#: por debajo -- si todas van fuera, se deja decidir como antes.
ANGULO_CONTRARIO = 1.5708      # 90 grados

#: El campo de la madre que dice si el colector entra o sale del pou.
CAMPO_TIPO_COLECTOR = 'Tipo colector'

#: Que sentido corresponde a cada punta del tram. El extremo 1 es por donde el
#: agua SALE del pou hacia el tram; el 2, por donde LLEGA.
SENTIDO = {1: 'aguas abajo', 2: 'aguas arriba'}

#: Y si el tram muere en un imbornal, su lateral va asi en la madre.
TIPO_IMBORNAL = 'Imbornales'

#: Nombre de la capa de dudosos que se deja en el proyecto.
CAPA_DUDOSOS = 'DUDOSO_prof_colector'

#: Cuanto se admite entre lo puesto a mano y lo automatico para darlo por
#: la MISMA respuesta. No se compara el decimal: se comprueba si se ha
#: elegido la misma flecha. Elegir la equivocada se va de decimetros.
TOL_COMPARA = 0.011


def _norm(v):
    """Texto comparable: sin acentos, sin espacios, en minusculas."""
    import unicodedata
    if v is None:
        return ''
    s = unicodedata.normalize('NFD', str(v)).encode('ascii', 'ignore')
    s = s.decode('ascii').lower()
    return ''.join(c for c in s if c.isalnum())


def _mismo_material(a, b):
    """Si dos materiales son el mismo, tolerando como se escriba cada uno.

    La madre guarda 'HORMIGON (HO)' y el tram 'hormigón'; tambien aparece solo
    el codigo. Se comparan normalizados y por contencion en los dos sentidos.
    """
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return None                      # no se puede comparar
    if na == nb or na in nb or nb in na:
        return True
    # El pliego NO distingue el PVC liso del corrugado: los dos se entregan
    # como `PVC` y la diferencia va al OBSERVACIO (decision del 22/09/2026).
    # Si la madre dice corrugado y el tram liso, NO es una discrepancia de
    # material: es la misma tuberia. Sacarlo a dudosos obliga a resolver a
    # mano algo que ya resuelve el control E34 (Marisa, 07/10/2026).
    if 'pvc' in na and 'pvc' in nb:
        _lis = lambda s: 'lis' in s
        _cor = lambda s: 'corrug' in s
        if (_lis(na) and _cor(nb)) or (_cor(na) and _lis(nb)):
            return True
    # el codigo entre parentesis: 'HORMIGON (HO)' -> 'ho'
    for x, y in ((a, nb), (b, na)):
        if x and '(' in str(x) and ')' in str(x):
            cod = _norm(str(x).split('(')[-1].split(')')[0])
            if cod and (cod == y or y.endswith(cod)):
                return True
    return False


def _mismo_diametro(a, b):
    """Si dos diametros son el mismo. None si alguno no es un numero."""
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return None
    if fa <= 0 or fb <= 0:
        return None
    return abs(fa - fb) < 0.5


def _candidatas(capa_origen, pt, vecino, red_ref, idx_red,
                xf_a_madre, xf_a_tram):
    """Las flechas que ARRANCAN en `pt`, ordenadas por angulo contra el tram.

    Devuelve [(feature, angulo), ...]. Mismo criterio que el volcador: tiene
    que arrancar ahi -- no solo pasar cerca -- y ser de la misma red.
    """
    rect = QgsRectangle(pt.x() - TOL_EXTREMO, pt.y() - TOL_EXTREMO,
                        pt.x() + TOL_EXTREMO, pt.y() + TOL_EXTREMO)
    if xf_a_madre is not None:
        try:
            rect = xf_a_madre.transformBoundingBox(rect)
        except Exception:
            pass
    rumbo_tram = _rumbo(pt, vecino)
    out = []
    brutas = []
    for f in capa_origen.getFeatures(QgsFeatureRequest().setFilterRect(rect)):
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
        d = math.hypot(fv[0].x() - pt.x(), fv[0].y() - pt.y())
        if d > TOL_EXTREMO:
            continue
        brutas.append(f)
        if idx_red != -1 and red_ref is not None:
            if str(f[idx_red]) != str(red_ref):
                continue
        out.append((f, _dif_angular(_rumbo(fv[0], fv[-1]), rumbo_tram)))
    out.sort(key=lambda x: x[1])
    return out, brutas


def _capa_dudosos(crs):
    """Crea (o vacia) la capa de dudosos en el proyecto."""
    for c in QgsProject.instance().mapLayersByName(CAPA_DUDOSOS):
        QgsProject.instance().removeMapLayer(c.id())
    capa = QgsVectorLayer('Point?crs=' + crs.authid(), CAPA_DUDOSOS, 'memory')
    capa.dataProvider().addAttributes([
        QgsField('tram', QVariant.String),
        # El `fid` SIEMPRE, no solo cuando falta el ID. El B6 se pasa antes
        # del A1 --para enterarse de lo que obliga a partir un tram antes de
        # tener los IDs puestos-- y ahi `tram` viene vacio o repetido. Con el
        # fid se selecciona en la tabla de atributos sin depender de nada
        # (Marisa, 07/10/2026).
        QgsField('fid', QVariant.Int),
        QgsField('extremo', QVariant.Int),
        QgsField('motivo', QVariant.String),
        QgsField('detalle', QVariant.String),
    ])
    capa.updateFields()
    return capa


def volcar_lote(plugin, iface, dry_run=True, solo_seleccion=False,
                comparar=False, pisar=False):
    """Recorre el 211 entero y vuelca las profundidades que no admiten duda.

    Devuelve un diccionario con el recuento, y deja en el proyecto la capa
    `DUDOSO_prof_colector` con lo que no ha tocado y por que.

    `pisar=True` REESCRIBE lo que ya tiene valor. Por defecto no se hace:
    un valor puesto por una persona no se toca sin pedirlo. Pero cuando
    una pasada anterior del propio volcador dejo valores malos, repetirla
    es la forma natural de arreglarlo, y sin esto habia que corregir a
    mano uno por uno (Alcover, 05/10/2026: una compañera revisando el
    municipio se encontraba profundidades mal puestas).
    """
    log = []
    capa_destino = find_layer_by_name(CAPA_DESTINO_PATTERNS)
    capa_origen = find_source_layer(list(FIELD_MAPPING.keys()))
    if capa_destino is None:
        return {'error': 'No encuentro la capa 211_Trams_Sanejament.'}
    if capa_origen is None:
        return {'error': "No encuentro la capa madre 'Tuberias'."}

    # ⚠ Las columnas se crean AQUI, antes de buscar sus indices. Estaba al
    # reves: el error de abajo cortaba la funcion antes de llegar a crearlas,
    # asi que el codigo que las creaba no se ejecutaba nunca justo en el caso
    # para el que estaba (La Galera, 07/10/2026).
    asegurar_columnas_prof(capa_destino, avisar=log.append, en_seco=dry_run)
    idx_p1 = _find_field_idx(capa_destino, CAMPO_PROF_1)
    idx_p2 = _find_field_idx(capa_destino, CAMPO_PROF_2)
    if idx_p1 == -1 or idx_p2 == -1:
        return {'error': 'Al 211 le faltan las columnas %s / %s%s'
                         % (CAMPO_PROF_1, CAMPO_PROF_2,
                            ', y en seco no las creo: vuelve a darle a '
                            '"Volcar de verdad".' if dry_run
                            else ' y no he podido crearlas.')}

    idx_prof = _find_field_idx(capa_origen, CAMPO_PROF_ORIGEN)
    idx_corr = _find_field_idx(capa_origen, CAMPO_PROF_CORREGIDA)
    idx_com = _find_field_idx(capa_origen, 'Comentario')
    idx_red = _find_field_idx(capa_origen, 'Red')
    idx_diam_o = _find_field_idx(capa_origen, 'Diametro')
    idx_mat_o = _find_field_idx(capa_origen, 'Material')
    idx_tipo_o = _find_field_idx(capa_origen, CAMPO_TIPO_COLECTOR)
    idx_diam_d = _find_field_idx(capa_destino, 'DIAMETRE')
    idx_mat_d = _find_field_idx(capa_destino, 'MATERIAL')

    # La madre suele ir en 4326 y el tram en 25831: todo se mide en metros, en
    # la proyeccion del tram, y a la madre solo se le pide el rectangulo.
    xf_a_madre = xf_a_tram = None
    if capa_origen.crs() != capa_destino.crs():
        pr = QgsProject.instance()
        xf_a_madre = QgsCoordinateTransform(capa_destino.crs(),
                                            capa_origen.crs(), pr)
        xf_a_tram = QgsCoordinateTransform(capa_origen.crs(),
                                           capa_destino.crs(), pr)

    # La red de la madre que corresponde al saneamiento. Se deduce de lo que
    # mas aparece cerca de los trams, igual que hace el volcador al pulsar.
    red_ref = None
    if idx_red != -1:
        from collections import Counter
        c = Counter(str(f[idx_red]) for f in capa_origen.getFeatures())
        if c:
            red_ref = c.most_common(1)[0][0]
            log.append('Red de la madre para el saneamiento: %s' % red_ref)

    # El traductor de codigos de la madre: el MISMO CSV que usa el volcador
    # para escribir. Sin el, se compararia '130' contra 270 y no coincidiria
    # nunca. (Arboli, 15/09/2026: tumbaba 103 de 160 puntas buenas.)
    try:
        dom = Dominios(_carpetas_de(capa_origen, capa_destino))
    except Exception as e:
        dom = None
        log.append('sin CSV de dominios (%s): no podre corroborar con el '
                   'diametro ni el material' % e)

    # Los CD (225). Un tram que muere en un CD no tiene flecha, y eso no es
    # un fallo: es como esta la red. Se localiza para no contarlo como duda.
    capa_cd = find_layer_by_name(CAPA_CD_PATTERNS)
    # Los imbornals (223). Un tram que muere en un imbornal no tiene colector
    # de pou: tiene su lateral, y en la madre va como 'Imbornales'.
    capa_emb = find_layer_by_name(CAPA_EMB_PATTERNS)
    capa_pous = find_layer_by_name(CAPA_POUS_PATTERNS)
    # `prof_interp` marca lo que viene de interpolacion y no de medida. Sin
    # ella el volcador hace el trabajo pero no deja constancia, y eso se
    # descubre tarde: cuando alguien pregunta de donde sale un valor.
    idx_interp = _find_field_idx(capa_destino, CAMPO_INTERP)

    if capa_cd is None:
        log.append('no encuentro la 225 de connexions: los trams que acaben '
                   'en un CD saldran como dudosos')

    no_pisar = bool(getattr(plugin, 'no_pisar', True))
    dudosos = _capa_dudosos(capa_destino.crs())
    feats_dudosos = []

    n_trams = n_esc = n_ya = n_dud = n_sin_corrob = 0
    # `_apuntar` deduplica por (punto, motivo): dos trams que comparten la
    # misma punta con el mismo motivo son UNA fila. Si se cuenta aparte, el
    # mensaje dice 36 y la capa trae 25 (Marisa, 07/10/2026).
    n_dud_rep = 0
    n_pisadas = 0
    n_corr_diam = n_corr_mat = 0
    correcciones = []
    n_cmp_ok = n_cmp_mal = n_cmp_nosabe = 0
    n_con_bruta = n_comidas_red = n_cd = n_por_sentido = n_emb = 0
    n_repartida = n_interp = n_sin_dato = 0
    #: Solo se interpola si estan las capas que hacen falta.
    interp_ok = capa_cd is not None and capa_pous is not None
    #: (punto, id de la flecha) -> ya se la ha llevado un tram.
    flechas_usadas = {}
    #: (x, y, motivo) de lo ya sacado, para no repetir el punto
    #: donde se juntan dos trams.
    ya_sacados = set()
    motivos = {}

    trams = (list(capa_destino.selectedFeatures()) if solo_seleccion
             else list(capa_destino.getFeatures()))

    if not dry_run and not capa_destino.isEditable():
        capa_destino.startEditing()

    def _apuntar(pt, nombre, n_ext, motivo_c, detalle, fid=None):
        """Una fila por punto y motivo, no una por tram."""
        clave = (round(pt.x(), 2), round(pt.y(), 2), motivo_c)
        if clave in ya_sacados:
            return False
        ya_sacados.add(clave)
        f = QgsFeature(dudosos.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(pt)))
        f.setAttributes([nombre, fid, n_ext, motivo_c, detalle or ''])
        feats_dudosos.append(f)
        return True

    def _es_cd(pt):
        """Si esa punta cae sobre una connexio de la 225."""
        if capa_cd is None:
            return False
        try:
            return bool(_hay_algo_en(capa_cd, pt, capa_destino.crs()))
        except Exception:
            return False

    for tram in trams:
        g = tram.geometry()
        vs = _vertices_de(g) if g is not None and not g.isNull() else []
        if len(vs) < 2:
            continue
        n_trams += 1
        nombre = _nombre_de(tram, capa_destino)
        def _vecino(i_ext, paso):
            """El primer vertice separado de verdad del extremo.

            Con el de al lado a secas, un vertice repetido deja el rumbo en
            nada. (Arboli, tram 430152110008.)
            """
            p0 = vs[i_ext]
            i = i_ext + paso
            while 0 <= i < len(vs):
                q = vs[i]
                if math.hypot(q.x() - p0.x(), q.y() - p0.y()) >= MIN_SEGMENTO:
                    return q
                i += paso
            return vs[i_ext + paso] if 0 <= i_ext + paso < len(vs) else vs[i_ext]

        extremos = [(vs[0], _vecino(0, 1), idx_p1, 1),
                    (vs[-1], _vecino(len(vs) - 1, -1), idx_p2, 2)]
        #: Lo decidido en cada punta, para poder interpolar antes de escribir.
        pendientes = []
        interpolados = []

        # Si una de las dos puntas es un imbornal, este tram es su lateral, y
        # entonces su colector va como 'Imbornales' en la madre -- tambien en
        # la punta del pou. Lo que manda es que une el tram, no donde estoy.
        es_lateral = False
        if capa_emb is not None:
            for _p, _v, _i, _n in extremos:
                try:
                    if _hay_algo_en(capa_emb, _p, capa_destino.crs()):
                        es_lateral = True
                        break
                except Exception:
                    pass
        for pt, vecino, idx_dst, n_ext in extremos:
            if _es_cd(pt):
                # No se corta aqui: un tram que muere en un CD no tiene flecha,
                # pero SI se puede interpolar desde su otro extremo, que es lo
                # que hace el volcador al pulsar.
                n_cd += 1
                pendientes.append([idx_dst, n_ext, pt, None,
                                   'acaba en un CD', None, True, False])
                continue

            ya = tram[idx_dst]
            tiene_ya = ya not in (None, '', 'NULL')
            # En seco NO se salta lo que ya tiene valor: se COMPARA. Es la
            # unica forma de saber si el automatico coge lo mismo que se puso a
            # mano, y los municipios ya volcados son la unica verdad que hay.
            # Lo que ya tiene valor se deja en paz. Solo se entra a
            # compararlo si se ha pedido expresamente -- es el modo de
            # validacion, no el de trabajo.
            # Con `pisar` no se salta: se recalcula y se sobreescribe.
            if tiene_ya and not (dry_run and comparar) and not pisar:
                n_ya += 1
                # Se apunta aunque no se toque: su valor es el punto de
                # partida para interpolar la otra punta.
                pendientes.append([idx_dst, n_ext, pt, ya, None, None,
                                   False, True])
                continue

            valor = None
            cand, brutas = _candidatas(capa_origen, pt, vecino, red_ref,
                                       idx_red, xf_a_madre, xf_a_tram)

            # En un imbornal manda el imbornal: tiene UN solo lateral, y
            # el pliego guarda ahi la cota inferior del tubo. La flecha de la
            # madre, si la hay, es una segunda escritura del mismo dato.
            es_emb_aqui = False
            if capa_emb is not None:
                try:
                    es_emb_aqui = bool(_hay_algo_en(capa_emb, pt,
                                                    capa_destino.crs()))
                except Exception:
                    es_emb_aqui = False
            if es_emb_aqui:
                v_emb = None
                try:
                    v_emb, _m = _prof_del_embornal_en(capa_emb, pt,
                                                      capa_destino.crs())
                except Exception:
                    v_emb = None
                if v_emb is not None:
                    try:
                        valor = round(float(v_emb), 2)
                    except (TypeError, ValueError):
                        valor = v_emb
                    n_emb += 1
                    cand = []

            # Las que van hacia el otro lado no son de este tram.
            if cand and any(c[1] <= ANGULO_CONTRARIO for c in cand):
                cand = [c for c in cand if c[1] <= ANGULO_CONTRARIO]

            # --- las candidatas, por tandas de fiabilidad -------------
            #
            # El angulo es lo ultimo: el sentido y el diametro los escribio
            # quien midio; el rumbo lo deduzco yo. Ver la cabecera del modulo.
            def _todas_dicen_lo_mismo(cs):
                """Si todas las empatadas por angulo traen la misma medida.

                Tres flechas duplicadas no son una duda: den la que den, la
                respuesta es la misma.
                """
                vals = []
                for c in cs:
                    if c[1] - cs[0][1] >= MARGEN_ANG:
                        break            # ya no esta empatada con la primera
                    v, _m = _prof_de_la_flecha(c[0], idx_prof, idx_com, idx_corr)
                    if v is None:
                        return False
                    vals.append(float(v))
                return bool(vals) and (max(vals) - min(vals)) <= TOL_COMPARA

            def _cuadra(c):
                """Si el diametro Y el material de esa flecha cuadran."""
                if dom is None:
                    return False
                okd = okm = None
                # Lo que escribio el operario en el comentario ('DN180'), para
                # cuando la columna de dominio viene vacia. Es lo que hace el
                # volcador al pulsar.
                com = {'diametro': None, 'material': None}
                if idx_com != -1:
                    try:
                        com = del_comentario(c[0][idx_com])
                    except Exception:
                        pass
                if idx_diam_o != -1 and idx_diam_d != -1:
                    v, _ = dom.diametro(c[0][idx_diam_o])
                    if v is None:
                        v = com.get('diametro')
                    if v is not None:
                        okd = _mismo_diametro(tram[idx_diam_d], v)
                if idx_mat_o != -1 and idx_mat_d != -1:
                    v, _ = dom.material(c[0][idx_mat_o], red_ref)
                    if v is None:
                        v = com.get('material')
                    if v is not None:
                        okm = _mismo_material(tram[idx_mat_d], v)
                return okd is True and okm is True

            def _es_tipo(c, nombre):
                return (idx_tipo_o != -1
                        and _norm(c[0][idx_tipo_o]) == _norm(nombre))

            # Si la punta cae en un imbornal, el sentido de pou no aplica:
            # la flecha que toca es la del lateral.
            quiero = TIPO_IMBORNAL if es_lateral else SENTIDO.get(n_ext)
            sent = [c for c in cand if _es_tipo(c, quiero)] if quiero else []
            cuad = [c for c in cand if _cuadra(c)]
            no_aux = [c for c in cand if not _es_tipo(c, 'Auxiliar')]
            tanda_n = 0
            for n, tanda in ((1, [c for c in sent if c in cuad]),
                             (2, sent), (3, cuad), (4, no_aux), (5, cand)):
                if tanda:
                    cand, tanda_n = tanda, n
                    break
            unica = (len(cand) == 1)
            if unica and tanda_n <= 3:
                n_por_sentido += 1

            if brutas:
                n_con_bruta += 1
            if brutas and not cand:
                n_comidas_red += 1
            motivo = detalle = None

            #: Si no hay entre que elegir, el rumbo no aporta nada y solo
            #: puede estorbar: la flecha arranca en ese punto exacto y es de la
            #: red que toca. (Arboli 430152110008 a 68 grados; Maspujols 118 a
            #: 63, un lateral de imbornal sin diametro.)
            sin_dudas = unica

            if valor is not None:
                pass                      # ya lo ha dado el imbornal
            elif not cand:
                # La flecha del lateral arranca en el pou y muere en el
                # imbornal, asi que en la punta del imbornal no hay ninguna.
                # Pero el imbornal trae SU medida, y el pliego define ese campo
                # como la cota inferior del tubo: justo lo que falta aqui.
                v_emb = None
                if capa_emb is not None:
                    try:
                        v_emb, mot_emb = _prof_del_embornal_en(
                            capa_emb, pt, capa_destino.crs())
                    except Exception:
                        v_emb = None
                if v_emb is not None:
                    try:
                        valor = round(float(v_emb), 2)
                    except (TypeError, ValueError):
                        valor = v_emb
                    n_emb += 1
                else:
                    motivo = 'no arranca ninguna flecha'
            elif cand[0][1] > ANGULO_MAX and not sin_dudas:
                motivo = 'la flecha mas parecida se va de rumbo'
                detalle = '%d grados' % int(round(cand[0][1] * 57.2958))
            elif cand and _prof_de_la_flecha(
                    cand[0][0], idx_prof, idx_com, idx_corr)[0] is None:
                # Antes que el empate: si la flecha que toca no trae medida,
                # el empate es irrelevante y decirlo despista.
                motivo = '__sin_dato__'
                detalle = ('%d candidata(s) y ninguna con el campo relleno'
                           % len(cand))
            elif (len(cand) > 1 and (cand[1][1] - cand[0][1]) < MARGEN_ANG
                  and not _todas_dicen_lo_mismo(cand)):
                motivo = 'dos flechas apuntan casi igual'
                detalle = ('%d candidatas (tanda %d): fid %s y fid %s; '
                           'la 1a a %d grados y la 2a a %d'
                           % (len(cand), tanda_n, cand[0][0].id(),
                              cand[1][0].id(),
                              int(round(cand[0][1] * 57.2958)),
                              int(round(cand[1][1] * 57.2958))))
            else:
                flecha = cand[0][0]
                # --- la segunda opinion: diametro y material ---------------
                ok_d = ok_m = None
                diam_flecha = mat_flecha = None
                if dom is not None:
                    com_f = {'diametro': None, 'material': None}
                    if idx_com != -1:
                        try:
                            com_f = del_comentario(flecha[idx_com])
                        except Exception:
                            pass
                    if idx_diam_o != -1 and idx_diam_d != -1:
                        v, _via = dom.diametro(flecha[idx_diam_o])
                        if v is None:
                            v = com_f.get('diametro')
                        if v is not None:
                            diam_flecha = v
                            ok_d = _mismo_diametro(tram[idx_diam_d], v)
                    if idx_mat_o != -1 and idx_mat_d != -1:
                        v, _via = dom.material(flecha[idx_mat_o], red_ref)
                        if v is None:
                            v = com_f.get('material')
                        if v is not None:
                            mat_flecha = v
                            ok_m = _mismo_material(tram[idx_mat_d], v)
                if (ok_d is False or ok_m is False) and pisar:
                    # Pisando, la flecha manda: el tram se corrige con lo que
                    # dice la madre en vez de mandarlo a dudosos. Es lo que
                    # pidio Marisa (06/10/2026): "si le vuelvo a dar al
                    # volcador, que me pise todo lo que no coincida".
                    #
                    # ⚠ La flecha se eligio por posicion y rumbo, no por el
                    # diametro -- que es justo lo que no cuadra. Si la flecha
                    # fuese la equivocada, aqui se propaga su error al tram.
                    # Por eso solo pasa con `pisar`, que es deliberado, y cada
                    # correccion queda en el log.
                    if ok_d is False and diam_flecha is not None:
                        if not dry_run:
                            capa_destino.changeAttributeValue(
                                tram.id(), idx_diam_d, diam_flecha)
                        correcciones.append(
                            '%s: DIAMETRE %s -> %s'
                            % (nombre, tram[idx_diam_d], diam_flecha))
                        n_corr_diam += 1
                    if ok_m is False and mat_flecha is not None:
                        if not dry_run:
                            capa_destino.changeAttributeValue(
                                tram.id(), idx_mat_d, mat_flecha)
                        correcciones.append(
                            '%s: MATERIAL %s -> %s'
                            % (nombre, tram[idx_mat_d], mat_flecha))
                        n_corr_mat += 1
                    ok_d = ok_m = True
                if ok_d is False or ok_m is False:
                    motivo = 'el diametro o el material no cuadran con la flecha'
                    _fd = dom.diametro(flecha[idx_diam_o])[0] if (
                        dom is not None and idx_diam_o != -1) else '?'
                    _fm = dom.material(flecha[idx_mat_o], red_ref)[0] if (
                        dom is not None and idx_mat_o != -1) else '?'
                    detalle = ('tram %s / %s  ·  flecha fid %s: %s / %s'
                               % (tram[idx_diam_d] if idx_diam_d != -1 else '?',
                                  tram[idx_mat_d] if idx_mat_d != -1 else '?',
                                  flecha.id(), _fd, _fm))
                elif (round(pt.x(), 2), round(pt.y(), 2),
                      flecha.id()) in flechas_usadas:
                    # Esa flecha ya es de otro tram. Dos colectores distintos
                    # no comparten medida: o falta una flecha por dibujar, o
                    # uno de los dos trams no va ahi.
                    motivo = 'esa flecha ya se la ha llevado otro tram'
                    detalle = ('la tiene %s; aqui hacen falta tantas flechas '
                               'como colectores'
                               % flechas_usadas[(round(pt.x(), 2),
                                                 round(pt.y(), 2),
                                                 flecha.id())])
                    n_repartida += 1
                else:
                    v, mot = _prof_de_la_flecha(flecha, idx_prof, idx_com,
                                                idx_corr)
                    if v is None:
                        motivo = '__sin_dato__'
                        detalle = mot
                    else:
                        # A 2 decimales, que es como trabaja el pliego. La
                        # madre trae 3 en muchas flechas (0,846) y eso dejaba
                        # la columna con unos valores de 2 y otros de 3, que es
                        # incomodo de leer y de comparar.
                        #
                        # ⚠ SOLO aqui. El volcador de pulsar sigue escribiendo
                        # el dato tal y como se midio: decision de Marisa el
                        # 16/09/2026 (*"en el volcador no toques nada, solo en
                        # B6"*). Los dos escriben en la misma columna, asi que
                        # un municipio volcado a medias con cada herramienta
                        # tendra las dos precisiones -- y no pasa nada, porque
                        # lo que se entrega son el PROF_NODE y el Z_NODE, que
                        # los redondea el B1/B2.
                        try:
                            valor = round(float(v), 2)
                        except (TypeError, ValueError):
                            valor = v
                        flechas_usadas[(round(pt.x(), 2), round(pt.y(), 2),
                                        flecha.id())] = nombre
                        if ok_d is None and ok_m is None:
                            n_sin_corrob += 1

            if tiene_ya and pisar:
                # Se ha pedido pisar: el valor nuevo manda sobre el viejo.
                if valor is not None:
                    n_pisadas += 1
            elif tiene_ya:
                # Comparar, no escribir.
                n_ya += 1
                if valor is None:
                    n_cmp_nosabe += 1
                    motivos[motivo] = motivos.get(motivo, 0) + 1
                    motivo_c = ('tiene valor a mano y yo no sabria ponerlo: %s'
                                % motivo)
                else:
                    try:
                        # Los dos lados redondeados: el B6 escribe a 2
                        # decimales y lo de mano puede tener 3, asi que
                        # comparar en crudo daba 0,725 != 0,72.
                        igual = abs(float(ya) - float(valor)) <= TOL_COMPARA
                    except (TypeError, ValueError):
                        igual = str(ya).strip() == str(valor).strip()
                    if igual:
                        n_cmp_ok += 1
                        continue
                    n_cmp_mal += 1
                    motivo_c = 'DIFIERE de lo puesto a mano'
                    detalle = 'a mano %s  ·  automatico %s' % (ya, valor)
                _apuntar(pt, nombre, n_ext, motivo_c, detalle,
                         fid=tram.id())
                continue

            pendientes.append([idx_dst, n_ext, pt, valor, motivo, detalle,
                               False, False])

        # --- interpolar, si una punta tiene medida y la otra no ------------
        #
        # Igual que el volcador de pulsar. Va DESPUES de decidir las dos: para
        # interpolar en una punta hace falta el valor de la otra.
        if len(pendientes) == 2 and interp_ok:
            con = [p for p in pendientes if p[3] is not None]
            sin = [p for p in pendientes if p[3] is None]
            if len(con) == 1 and len(sin) == 1:
                v, mot = None, None
                try:
                    v, mot = _prof_interpolada_en_cd(
                        sin[0][2], g, con[0][3], capa_destino, capa_origen,
                        idx_prof, red_ref, idx_red, idx_com, capa_emb,
                        capa_cd, capa_pous, xf_a_madre, xf_a_tram, idx_corr)
                except Exception as e:
                    log.append('  [!] no he podido interpolar en %s: %s'
                               % (nombre, e))
                if v is not None:
                    try:
                        sin[0][3] = round(float(v), 2)
                    except (TypeError, ValueError):
                        sin[0][3] = v
                    sin[0][4] = None
                    interpolados.append((tram.id(), sin[0][1]))
                    n_interp += 1

        # --- y ahora si, escribir ------------------------------------------
        marcas = []
        for (idx_dst, n_ext, pt, valor, motivo, detalle, era_cd,
             solo_lectura) in pendientes:
            if solo_lectura:
                continue                  # ya lo tenia: ni se toca ni se cuenta
            if valor is not None:
                if not dry_run:
                    capa_destino.changeAttributeValue(tram.id(), idx_dst, valor)
                n_esc += 1
                if (tram.id(), n_ext) in interpolados:
                    marcas.append(str(n_ext))
            elif era_cd:
                pass                  # un CD sin interpolar no es una duda
            elif motivo == '__sin_dato__':
                # La madre no trae la medida. No se resuelve pulsando: falta
                # el dato de campo, asi que no es una duda del gabinete.
                n_sin_dato += 1
            else:
                if _apuntar(pt, nombre, n_ext, motivo, detalle,
                            fid=tram.id()):
                    n_dud += 1
                    motivos[motivo] = motivos.get(motivo, 0) + 1
                else:
                    # Ya estaba sacada esa punta por ese mismo motivo.
                    n_dud_rep += 1
        # Un valor calculado NO es un valor medido, y se ve igual. Queda
        # marcado en una columna interna, nunca en el OBSERVACIO.
        if marcas and not dry_run and idx_interp != -1:
            capa_destino.changeAttributeValue(tram.id(), idx_interp,
                                              SEP_INTERP.join(marcas))

    if feats_dudosos:
        dudosos.dataProvider().addFeatures(feats_dudosos)
        dudosos.updateExtents()
        QgsProject.instance().addMapLayer(dudosos)

    log.append('capa de trams: "%s" (%d)'
               % (capa_destino.name(), capa_destino.featureCount()))
    log.append('capa madre:    "%s" (%d)'
               % (capa_origen.name(), capa_origen.featureCount()))
    log.append('puntas con alguna flecha arrancando a <= %.2f m: %d'
               % (TOL_EXTREMO, n_con_bruta))
    if n_cd:
        log.append('puntas que acaban en un CD (225), que no llevan flecha y '
                   'por eso no se cuentan: %d' % n_cd)
    if n_emb:
        log.append('puntas resueltas leyendo la profundidad del propio '
                   'imbornal, donde no arranca flecha: %d' % n_emb)
    if n_sin_dato:
        log.append('puntas cuya flecha existe pero NO trae profundidad en la '
                   'madre: %d  (falta el dato de campo; no salen en los '
                   'dudosos porque no se arreglan desde aqui)' % n_sin_dato)
    if n_interp:
        log.append('puntas CALCULADAS por interpolacion, no medidas (quedan '
                   'marcadas en %s): %d' % (CAMPO_INTERP, n_interp))
    if not interp_ok:
        log.append('[!] sin la 225 o la 222 cargadas no puedo interpolar en '
                   'los CD')
    if n_repartida:
        log.append('puntas donde la flecha que tocaba ya era de otro tram: %d '
                   '(suele ser que falta una flecha por dibujar)' % n_repartida)
    if n_por_sentido:
        log.append('puntas resueltas por el sentido del colector o por el '
                   'diametro, sin tener que mirar el angulo: %d'
                   % n_por_sentido)
    if n_comidas_red:
        log.append('puntas donde SI habia flecha pero el filtro de red la '
                   'descarto: %d  (red usada: %s)' % (n_comidas_red, red_ref))
    return {
        'dry_run': dry_run,
        'diag': log,
        'trams': n_trams,
        'escritas': n_esc,
        'ya_tenian': n_ya,
        'pisadas': n_pisadas,
        'corr_diametro': n_corr_diam,
        'corr_material': n_corr_mat,
        'correcciones': correcciones,
        'dudosas': n_dud,
        'dudosas_repetidas': n_dud_rep,
        'sin_corroborar': n_sin_corrob,
        'cmp_ok': n_cmp_ok,
        'cmp_mal': n_cmp_mal,
        'cmp_nosabe': n_cmp_nosabe,
        'cd': n_cd,
        'interp': n_interp,
        'sin_dato': n_sin_dato,
        'motivos': motivos,
        'log': log,
    }
