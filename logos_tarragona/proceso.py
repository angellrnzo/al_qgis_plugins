import os
import re
import unicodedata
from PIL import Image

# ============================================================
# CONFIGURACIÓN
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETA_ENTRADA = os.path.join(SCRIPT_DIR, "logos_faltantes")
CARPETA_WIKI = os.path.join(SCRIPT_DIR, "logos_municipios")
CARPETA_FINAL = os.path.join(SCRIPT_DIR, "logos_finales")

# Diccionario: { "nombre_en_tu_carpeta": ("Nombre_Oficial_Wiki.png", "nombre_final_numerado.png") }
MAPEO = {
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
    # Extras
    "81_vilaverd": ("Escut_heraldic_de_Vilaverd.png", "81_vilaverd.png"),
    "62_montblanc": ("Escut_de_Montblanc.png", "62_montblanc.png")
}

def normalizar(texto):
    """Limpia los nombres para que coincidan exactamente (ignorando mayúsculas/tildes)."""
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    texto = texto.replace("ç", "c").replace("-", "_").replace(" ", "_")
    texto = re.sub(r'[^a-z0-9_]', '', texto)
    return texto

def procesar_imagen_completa(ruta_in, ruta_wiki, ruta_final):
    try:
        img = Image.open(ruta_in).convert("RGBA")
        
        # 1. Quitar el fondo blanco
        datas = img.getdata()
        newData = []
        for item in datas:
            # Umbral de 240 para limpiar blancos
            if item[0] > 240 and item[1] > 240 and item[2] > 240:
                newData.append((255, 255, 255, 0)) # Transparente
            else:
                newData.append(item)
        img.putdata(newData)
        
        # 2. AUTO-RECORTE: Eliminar márgenes vacíos (crucial para Alcover y Ascó)
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)

        # 3. Redimensionar a 800 píxeles máximo
        if img.width > 800 or img.height > 800:
            img.thumbnail((800, 800), Image.Resampling.LANCZOS)
            
        # 4. Guardar en ambas carpetas SIEMPRE como PNG
        img.save(ruta_wiki, "PNG")
        img.save(ruta_final, "PNG")
        
        return True
    except Exception as e:
        print(f"   ❌ Error al procesar {os.path.basename(ruta_in)}: {e}")
        return False

def main():
    for carpeta in [CARPETA_WIKI, CARPETA_FINAL]:
        if not os.path.exists(carpeta):
            os.makedirs(carpeta)

    if not os.path.exists(CARPETA_ENTRADA):
        print(f"❌ No existe la carpeta: {CARPETA_ENTRADA}")
        print("👉 Crea la carpeta 'logos_faltantes' y mete ahí tus archivos.")
        input("Pulsa Enter para salir...")
        return

    print("🚀 PROCESANDO Y LIMPIANDO TUS ARCHIVOS...\n")
    
    archivos = os.listdir(CARPETA_ENTRADA)
    encontrados = 0
    procesados = set()

    for f in archivos:
        # AHORA SÍ ACEPTA WEBP Y PNG/JPG
        if not f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            continue
            
        nombre_base = os.path.splitext(f)[0]
        nombre_norm = normalizar(nombre_base)
        
        # Buscar coincidencia exacta con el diccionario
        match_key = None
        for key in MAPEO.keys():
            if key == nombre_norm:
                match_key = key
                break
                
        if match_key:
            nombre_wiki, nombre_final = MAPEO[match_key]
            
            ruta_in = os.path.join(CARPETA_ENTRADA, f)
            ruta_wiki = os.path.join(CARPETA_WIKI, nombre_wiki)
            ruta_final = os.path.join(CARPETA_FINAL, nombre_final)
            
            if procesar_imagen_completa(ruta_in, ruta_wiki, ruta_final):
                print(f"✅ {f:28} -> Limpio, recortado y guardado como .png")
                encontrados += 1
                procesados.add(match_key)
        else:
            print(f"⚠️ Archivo no reconocido: {f} (Revisa que el nombre sea correcto)")

    # --- LIMPIEZA EXTRA PARA LOS QUE YA ESTABAN EN LAS CARPETAS (ASCO, ETC) ---
    print("\n🧹 Revisando y limpiando carpetas finales (por si Ascó u otros tienen fondo)...")
    for carpeta in [CARPETA_WIKI, CARPETA_FINAL]:
        for f in os.listdir(carpeta):
            if f.lower().endswith('.png'):
                ruta = os.path.join(carpeta, f)
                # Solo procesamos si tienen fondo blanco o les falta el recorte
                # Lo forzamos para asegurar que todos pasan por el auto-recorte
                procesar_imagen_completa(ruta, ruta, ruta)

    print("\n" + "="*50)
    print(f"🎉 FINALIZADO: {encontrados} imágenes nuevas procesadas.")
    
    faltan = set(MAPEO.keys()) - procesados
    if faltan:
        print(f"\n⚠️ Aún te faltan {len(faltan)} imágenes por descargar o renombrar en 'logos_faltantes':")
        for x in faltan:
            print(f"   - {x}")
    else:
        print("\n✨ ¡Felicidades! Tus carpetas 'logos_municipios' y 'logos_finales' están completas, limpias y recortadas.")

if __name__ == "__main__":
    main()
    input("\n✅ Proceso terminado. Pulsa Enter para salir...")