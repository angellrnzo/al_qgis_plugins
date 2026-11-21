# -*- coding: utf-8 -*-
"""
logos_tarragona.py — Pipeline interactivo de escudos municipales de Tarragona.

Un solo script con menú que guía el trabajo completo:
  1) Descargar escudos desde Wikimedia Commons
  2) Procesar imágenes manuales (logos_faltantes/)
  3) Mapear y renombrar a logos_finales/ (NN_municipio.png)
  4) Verificar la colección completa (82 municipios)
  5) Limpiar fondos blancos en lote
  6) Listar archivos descargados
  7) Pipeline completo guiado (pregunta qué pasos ejecutar)

Uso:  python logos_tarragona.py
Requiere: Pillow  (pip install -r requirements.txt)
"""

import os
import re
import sys

# Consolas Windows en cp1252 no tragan emojis — forzar UTF-8 con fallback
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import time
import shutil
import ssl
import unicodedata
import urllib.request
import urllib.parse

from PIL import Image

# ============================================================
# CONFIGURACIÓN
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETA_WIKI = os.path.join(SCRIPT_DIR, "logos_municipios")      # descargas crudas de Wikipedia
CARPETA_FALTANTES = os.path.join(SCRIPT_DIR, "logos_faltantes")  # imágenes conseguidas a mano
CARPETA_FINAL = os.path.join(SCRIPT_DIR, "logos_finales")        # resultado: NN_municipio.png
LOG_FILE = os.path.join(SCRIPT_DIR, "log_descarga.txt")
ARCHIVO_FALTANTES = os.path.join(SCRIPT_DIR, "faltantes.txt")
ARCHIVO_REPORTE = os.path.join(SCRIPT_DIR, "reporte_faltantes.txt")
ARCHIVO_LISTA = os.path.join(SCRIPT_DIR, "lista_descargados.txt")

IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp")

# Mapeo final -> original en logos_municipios (None = no vino de Wikipedia)
MAPEO_FINAL = {
    "01_alcover.png": None,
    "02_aldover.png": "Escut_d_Aldover.png",
    "03_alfara_de_carles.png": "Escut_d_Alfara_de_Carles.png",
    "04_almoster.png": "Escut_d_Almoster.png",
    "05_arboli.png": None,
    "06_arnes.png": "Escut_d_Arnes.png",
    "07_asco.png": "Escut_d_Asco.png",
    "08_batea.png": "Escut_de_Batea.png",
    "09_bellmunt_del_priorat.png": "Escudo_de_Bellmunt_del_Priorato_Tarragona.png",
    "10_benifallet.png": "Escut_de_Benifallet.png",
    "11_benissanet.png": None,
    "12_blancafort.png": "Escut_de_Blancafort.png",
    "13_bot.png": None,
    "14_botarell.png": "Escut_de_Botarell.png",
    "15_cabaces.png": "Escudo_de_Cabaces_Tarragona.png",
    "16_capafonts.png": None,
    "17_capcanes.png": "Escudo_de_Capsanes_Tarragona.png",
    "18_caseres.png": "Escut_de_Caseres.png",
    "19_colldejou.png": None,
    "20_constanti.png": "Escut_de_Constanti.png",
    "21_cornudella_de_montsant.png": "Escut_de_Cornudella_de_Montsant.png",
    "22_duesaigues.png": "Escudo_de_Dosaiguas_Tarragona.png",
    "23_el_lloar.png": "Escut_del_Lloar.png",
    "24_el_masroig.png": "Escudo_de_El_Masroig_Tarragona.png",
    "25_el_mila.png": "Escut_del_Mila.png",
    "26_el_molar.png": "Escut_del_Molar.png",
    "27_el_morell.png": "Escut_del_Morell.png",
    "28_el_pinell_de_brai.png": "Escut_del_Pinell_de_Brai.png",
    "29_el_rourell.png": "Escut_del_Rourell.png",
    "30_els_guiamets.png": "Escut_dels_Guiamets.png",
    "31_falset.png": "Escut_de_Falset.png",
    "32_flix.png": "Escut_de_Flix.png",
    "33_garcia.png": "Escut_de_Garcia.png",
    "34_ginestar.png": "Escut_de_Ginestar.png",
    "35_godall.png": "Escut_de_Godall.png",
    "36_gratallops.png": "Escudo_de_Gratallops_Tarragona.png",
    "37_horta_de_sant_joan.png": "Escut_d_Horta_de_Sant_Joan.png",
    "38_l_aleixar.png": "Blaso_de_l_Aleixar.png",
    "39_l_espluga_de_francoli.png": "Escut_de_l_Espluga_de_Francoli.png",
    "40_la_bisbal_de_falset.png": "Escut_de_la_Bisbal_de_Falset.png",
    "41_la_fatarella.png": "Escudo_de_Fatarella_Tarragona.png",
    "42_la_febro.png": None,
    "43_la_figuera.png": "Escudo_de_La_Figuera_Tarragona.png",
    "44_la_galera.png": "Escut_de_la_Galera.png",
    "45_la_maso.png": "Escut_de_la_Maso.png",
    "46_la_morera_de_montsant.png": "Escudo_de_La_Morera_de_Montsant_Tarragona.png",
    "47_la_palma_d_ebre.png": "Escut_de_la_Palma_d_Ebre.png",
    "48_la_pobla_de_mafumet.png": "Escut_de_la_Pobla_de_Mafumet.png",
    "49_la_riba.png": None,
    "50_la_senia.png": "Escut_de_la_Senia.png",
    "51_la_torre_de_fontaubella.png": "Escut_de_la_Torre_de_Fontaubella.png",
    "52_la_torre_de_l_espanyol.png": None,
    "53_la_vilella_alta.png": "Escut_de_la_Vilella_Alta.png",
    "54_la_vilella_baixa.png": "Escut_de_la_Vilella_Baixa.png",
    "55_marca.png": "Escut_de_Marca.png",
    "56_margalef.png": "Escudo_de_Margalef_de_Montsant_Tarragona.png",
    "57_mas_de_barberans.png": "Escut_de_Mas_de_Barberans.png",
    "58_maspujols.png": "Escut_de_Maspujols.png",
    "59_miravet.png": "Escut_de_Miravet.png",
    "60_mont_ral.png": None,
    "61_mont_roig_del_camp.png": None,
    "62_montblanc.png": "Escut_de_Montblanc.png",
    "63_montbrio_del_camp.png": "Escudo_de_Montbrio_de_Tarragona_Tarragona.png",
    "64_pauls.png": None,
    "65_perafort.png": "Logo_Perafort.png",
    "66_poboleda.png": "Escut_de_Poboleda.png",
    "67_porrera.png": None,
    "68_pradell_de_la_teixeta.png": "Escut_de_Pradell_de_la_Teixeta.png",
    "69_prades.png": None,
    "70_prat_de_comte.png": "Escut_de_Prat_de_Comte.png",
    "71_riba_roja_d_ebre.png": "Escut_de_Riba_roja_d_Ebre.png",
    "72_riudoms.png": None,
    "73_senan.png": "Escut_de_Senan.png",
    "74_torroja_del_priorat.png": "Escudo_de_Torroja_Tarragona.png",
    "75_ulldemolins.png": "Escut_d_Ulldemolins.png",
    "76_vallclara.png": "Escut_de_Vallclara.png",
    "77_vilallonga_del_camp.png": None,
    "78_vilanova_d_escornalbou.png": None,
    "79_vilanova_de_prades.png": "Escut_de_Vilanova_de_Prades_2015.png",
    "80_vilaplana.png": "Escut_de_Vilaplana.png",
    "81_vilaverd.png": "Escut_heraldic_de_Vilaverd.png",
    "82_vinebre.png": "Escut_de_Vinebre.png",
}

# Mapeo para imágenes manuales: nombre normalizado -> (nombre_wiki, nombre_final)
MAPEO_MANUAL = {
    "01_alcover": ("Escut_d_Alcover.png", "01_alcover.png"),
    "05_arboli": ("Escut_d_Arboli.png", "05_arboli.png"),
    "11_benissanet": ("Escut_de_Benissanet.png", "11_benissanet.png"),
    "13_bot": ("Escut_de_Bot.png", "13_bot.png"),
    "16_capafonts": ("Escut_de_Capafonts.png", "16_capafonts.png"),
    "19_colldejou": ("Escut_de_Colldejou.png", "19_colldejou.png"),
    "42_la_febro": ("Escut_de_la_Febro.png", "42_la_febro.png"),
    "49_la_riba": ("Escut_de_la_Riba.png", "49_la_riba.png"),
    "52_la_torre_de_l_espanyol": ("Escut_de_la_Torre_de_l_Espanyol.png", "52_la_torre_de_l_espanyol.png"),
    "60_mont_ral": ("Escut_de_Mont_ral.png", "60_mont_ral.png"),
    "61_mont_roig_del_camp": ("Escut_de_Mont_roig_del_Camp.png", "61_mont_roig_del_camp.png"),
    "64_pauls": ("Escut_de_Pauls.png", "64_pauls.png"),
    "67_porrera": ("Escut_de_Porrera.png", "67_porrera.png"),
    "69_prades": ("Escut_de_Prades.png", "69_prades.png"),
    "72_riudoms": ("Escut_de_Riudoms.png", "72_riudoms.png"),
    "77_vilallonga_del_camp": ("Escut_de_Vilallonga_del_Camp.png", "77_vilallonga_del_camp.png"),
    "78_vilanova_d_escornalbou": ("Escut_de_Vilanova_d_Escornalbou.png", "78_vilanova_d_escornalbou.png"),
    "81_vilaverd": ("Escut_heraldic_de_Vilaverd.png", "81_vilaverd.png"),
    "62_montblanc": ("Escut_de_Montblanc.png", "62_montblanc.png"),
}

LISTA_ESPERADA = list(MAPEO_FINAL.keys())

# ============================================================
# UTILIDADES
# ============================================================
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def log(mensaje):
    print(mensaje)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(mensaje + "\n")
    except OSError:
        pass


def pausar():
    input("\nPulsa Enter para continuar...")


def normalizar(texto):
    texto = texto.lower()
    texto = "".join(c for c in unicodedata.normalize("NFD", texto)
                    if unicodedata.category(c) != "Mn")
    texto = texto.replace("ç", "c").replace("-", "_").replace(" ", "_")
    return re.sub(r"[^a-z0-9_]", "", texto)


def limpiar_nombre_archivo(nombre):
    nombre = nombre.replace("File:", "")
    nombre = re.sub(r"\.(svg|png)$", "", nombre, flags=re.IGNORECASE)
    for a, b in [("à", "a"), ("è", "e"), ("é", "e"), ("í", "i"), ("ò", "o"),
                 ("ó", "o"), ("ú", "u"), ("ü", "u"), ("ç", "c")]:
        nombre = nombre.replace(a, b)
    nombre = re.sub(r"['\,\.\·\-\s]+", "_", nombre)
    return re.sub(r"[^a-zA-Z0-9_]", "", nombre)


def procesar_imagen(ruta_in, ruta_salida):
    """Quita fondo blanco, auto-recorta y guarda PNG máx 800px."""
    try:
        img = Image.open(ruta_in).convert("RGBA")
        img.putdata([
            (255, 255, 255, 0) if p[0] > 240 and p[1] > 240 and p[2] > 240 else p
            for p in img.getdata()
        ])
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        if img.width > 800 or img.height > 800:
            img.thumbnail((800, 800), Image.Resampling.LANCZOS)
        img.save(ruta_salida, "PNG")
        return True
    except Exception as e:
        print(f"   ❌ Error procesando {os.path.basename(ruta_in)}: {e}")
        return False


# ============================================================
# PASOS DEL PIPELINE
# ============================================================
def paso_descargar():
    """Descarga escudos desde Wikimedia Commons → logos_municipios/."""
    os.makedirs(CARPETA_WIKI, exist_ok=True)
    print("📥 Conectando con Wikimedia (todos los escudos de la categoría)...")

    params = {
        "action": "query", "generator": "categorymembers",
        "gcmtitle": "Category:SVG coats of arms of municipalities of the province of Tarragona",
        "gcmlimit": "50", "gcmtype": "file", "prop": "imageinfo",
        "iiprop": "url", "iiurlwidth": 800, "format": "json",
    }
    archivos, lote = [], 0

    while True:
        url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "User-Agent": "QGIS-Logo-Downloader/14.0 (angellrnzo@example.com)"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
            for page in data.get("query", {}).get("pages", {}).values():
                if "imageinfo" in page:
                    info = page["imageinfo"][0]
                    archivos.append({
                        "titulo": page["title"],
                        "url": info.get("thumburl", info.get("url")),
                    })
            if "continue" in data:
                params.update(data["continue"])
                lote += 1
                print(f"  ... lote {lote} ...")
                time.sleep(1)
            else:
                break
        except Exception as e:
            log(f"⚠️ Error consultando la API: {e}")
            break

    print(f"✅ {len(archivos)} escudos encontrados. Descargando...")
    exitos = fallos = 0
    for i, a in enumerate(archivos, 1):
        limpio = limpiar_nombre_archivo(a["titulo"])
        destino = os.path.join(CARPETA_WIKI, f"{limpio}.png")
        if os.path.exists(destino):
            exitos += 1
            continue
        print(f"🔍 [{i:03d}/{len(archivos)}] {limpio}...")
        if not a["url"]:
            fallos += 1
            continue
        ok = False
        for intento in range(3):
            try:
                req = urllib.request.Request(a["url"], headers={
                    "User-Agent": "QGIS-Logo-Downloader/14.0 (angellrnzo@example.com)"})
                with urllib.request.urlopen(req, context=ctx, timeout=20) as r:
                    with open(destino, "wb") as f:
                        f.write(r.read())
                ok = True
                break
            except Exception:
                if intento < 2:
                    time.sleep(5)
        if ok:
            exitos += 1
            time.sleep(1.5)
        else:
            fallos += 1
            print("   ❌ falló")

    print(f"\n🎉 Descarga: {exitos} ok, {fallos} fallos → {CARPETA_WIKI}")


def paso_procesar_faltantes():
    """Procesa imágenes manuales de logos_faltantes/ → ambas carpetas, y limpia todo."""
    os.makedirs(CARPETA_WIKI, exist_ok=True)
    os.makedirs(CARPETA_FINAL, exist_ok=True)

    if not os.path.exists(CARPETA_FALTANTES):
        print(f"❌ No existe {CARPETA_FALTANTES}")
        print("👉 Créala y mete ahí las imágenes que conseguiste a mano.")
        return

    print("🚀 Procesando imágenes manuales...\n")
    procesados = set()
    for f in sorted(os.listdir(CARPETA_FALTANTES)):
        if not f.lower().endswith(IMG_EXTS):
            continue
        norm = normalizar(os.path.splitext(f)[0])
        if norm in MAPEO_MANUAL:
            nombre_wiki, nombre_final = MAPEO_MANUAL[norm]
            ruta_in = os.path.join(CARPETA_FALTANTES, f)
            if procesar_imagen(ruta_in, os.path.join(CARPETA_WIKI, nombre_wiki)) and \
               procesar_imagen(ruta_in, os.path.join(CARPETA_FINAL, nombre_final)):
                print(f"✅ {f} → {nombre_final}")
                procesados.add(norm)
        else:
            print(f"⚠️ No reconocido: {f}")

    # Re-limpieza global de ambas carpetas (fondo blanco + recorte)
    print("\n🧹 Re-limpiando fondos en logos_municipios/ y logos_finales/...")
    for carpeta in (CARPETA_WIKI, CARPETA_FINAL):
        n = 0
        for f in os.listdir(carpeta):
            if f.lower().endswith(".png"):
                ruta = os.path.join(carpeta, f)
                if procesar_imagen(ruta, ruta):
                    n += 1
        print(f"   {n} imágenes en {os.path.basename(carpeta)}")

    faltan = set(MAPEO_MANUAL) - procesados
    if faltan:
        print(f"\n⚠️ Manuales pendientes ({len(faltan)}):")
        for x in sorted(faltan):
            print(f"   - {x}")
    else:
        print("\n✨ Manuales completos.")


def paso_mapear():
    """Copia logos_municipios/ → logos_finales/ con nombre NN_municipio.png."""
    os.makedirs(CARPETA_FINAL, exist_ok=True)
    if not os.path.exists(CARPETA_WIKI):
        print(f"❌ No existe {CARPETA_WIKI} — ejecuta primero la descarga.")
        return

    print("🚀 Mapeando y renombrando...\n")
    exitos, faltantes = 0, []
    for nombre_final, nombre_original in MAPEO_FINAL.items():
        if nombre_original is None:
            faltantes.append(nombre_final)
            continue
        origen = os.path.join(CARPETA_WIKI, nombre_original)
        if os.path.exists(origen):
            shutil.copy2(origen, os.path.join(CARPETA_FINAL, nombre_final))
            print(f"✅ {nombre_final}  <-  {nombre_original}")
            exitos += 1
        else:
            print(f"⚠️ No encontrado: {nombre_original}")
            faltantes.append(nombre_final)

    print(f"\n🎉 {exitos} copiados a {os.path.basename(CARPETA_FINAL)}.")
    if faltantes:
        with open(ARCHIVO_FALTANTES, "w", encoding="utf-8") as f:
            for x in faltantes:
                f.write(x + "\n")
        print(f"⚠️ {len(faltantes)} pendientes → {os.path.basename(ARCHIVO_FALTANTES)}")


def paso_verificar():
    """Comprueba que logos_finales/ tiene los 82 municipios esperados."""
    print(f"🔎 Verificando {CARPETA_FINAL}...\n")
    encontrados, faltantes = 0, []
    for nombre in LISTA_ESPERADA:
        if os.path.isfile(os.path.join(CARPETA_FINAL, nombre)):
            encontrados += 1
        else:
            print(f"❌ FALTA: {nombre}")
            faltantes.append(nombre)

    print(f"\n📊 {encontrados}/{len(LISTA_ESPERADA)} logos")
    if faltantes:
        with open(ARCHIVO_REPORTE, "w", encoding="utf-8") as f:
            f.write("\n".join(faltantes))
        print(f"⚠️ Faltan {len(faltantes)} → {os.path.basename(ARCHIVO_REPORTE)}")
    else:
        print("🎉 ¡Colección completa de los 82 municipios!")
        if os.path.exists(ARCHIVO_REPORTE):
            os.remove(ARCHIVO_REPORTE)


def paso_limpiar():
    """Quita fondo blanco en lote sobre ambas carpetas de imágenes."""
    total = 0
    for carpeta in (CARPETA_WIKI, CARPETA_FINAL):
        if not os.path.exists(carpeta):
            continue
        n = 0
        for f in os.listdir(carpeta):
            if f.lower().endswith(".png"):
                ruta = os.path.join(carpeta, f)
                if procesar_imagen(ruta, ruta):
                    n += 1
        print(f"✅ {n} limpiadas en {os.path.basename(carpeta)}")
        total += n
    print(f"\n🎉 Total: {total} imágenes limpiadas.")


def paso_listar():
    """Genera lista_descargados.txt con los PNG de logos_municipios/."""
    if not os.path.exists(CARPETA_WIKI):
        print(f"❌ No existe {CARPETA_WIKI}")
        return
    archivos = sorted(f for f in os.listdir(CARPETA_WIKI) if f.lower().endswith(".png"))
    with open(ARCHIVO_LISTA, "w", encoding="utf-8") as f:
        f.write("\n".join(archivos))
    print(f"✅ {len(archivos)} archivos → {os.path.basename(ARCHIVO_LISTA)}")
    print("👉 Abre el .txt y pégamelo en el chat si hace falta revisarlo.")


PASOS = {
    "1": ("Descargar escudos de Wikimedia", paso_descargar),
    "2": ("Procesar imágenes manuales (logos_faltantes/)", paso_procesar_faltantes),
    "3": ("Mapear y renombrar → logos_finales/", paso_mapear),
    "4": ("Verificar colección completa (82)", paso_verificar),
    "5": ("Limpiar fondos blancos en lote", paso_limpiar),
    "6": ("Listar archivos descargados", paso_listar),
}

ORDEN_COMPLETO = ["2", "3", "4"]  # proceso manual → mapear → verificar


def menu():
    while True:
        print("\n" + "=" * 55)
        print("🛡️  LOGOS TARRAGONA — Pipeline de escudos municipales")
        print("=" * 55)
        for k, (desc, _) in PASOS.items():
            print(f"  [{k}] {desc}")
        print("  [7] Pipeline completo guiado (te pregunto qué ejecutar)")
        print("  [0] Salir")
        op = input("\nOpción: ").strip()

        if op == "0":
            return
        if op == "7":
            pipeline_guiado()
            continue
        if op in PASOS:
            PASOS[op][1]()
            pausar()
        else:
            print("❌ Opción no válida.")


def pipeline_guiado():
    """Recorre el flujo preguntando qué pasos ejecutar."""
    print("\n🔧 PIPELINE GUIADO")
    print("Te haré unas preguntas y ejecutaré solo lo necesario.\n")

    if not os.path.exists(CARPETA_WIKI) or not os.listdir(CARPETA_WIKI):
        if input("¿Descargar escudos de Wikimedia ahora? [s/N]: ").strip().lower() == "s":
            paso_descargar()
    else:
        print(f"ℹ️ logos_municipios/ ya tiene {len(os.listdir(CARPETA_WIKI))} archivos — salto descarga.")

    if os.path.exists(CARPETA_FALTANTES) and any(
            f.lower().endswith(IMG_EXTS) for f in os.listdir(CARPETA_FALTANTES)):
        if input("¿Procesar imágenes manuales de logos_faltantes/? [s/N]: ").strip().lower() == "s":
            paso_procesar_faltantes()

    if input("¿Mapear/renombrar hacia logos_finales/? [s/N]: ").strip().lower() == "s":
        paso_mapear()

    if input("¿Limpiar fondos blancos en lote? [s/N]: ").strip().lower() == "s":
        paso_limpiar()

    paso_verificar()
    print("\n🏁 Pipeline guiado terminado.")


if __name__ == "__main__":
    try:
        menu()
    except KeyboardInterrupt:
        print("\n👋 Saliendo...")
