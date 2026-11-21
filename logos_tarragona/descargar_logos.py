import os
import re
import time
import json
import urllib.request
import urllib.parse
import ssl

# ============================================================
# CONFIGURACIÓN INICIAL
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETA_SALIDA = os.path.join(SCRIPT_DIR, "logos_municipios")
LOG_FILE = os.path.join(SCRIPT_DIR, "log_descarga.txt")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def log(mensaje):
    print(mensaje)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(mensaje + "\n")

# ============================================================
# FUNCIONES
# ============================================================
def limpiar_nombre_archivo(nombre):
    nombre = nombre.replace("File:", "")
    nombre = re.sub(r'\.(svg|png)$', '', nombre, flags=re.IGNORECASE)
    nombre = nombre.replace("à", "a").replace("è", "e").replace("é", "e").replace("í", "i")
    nombre = nombre.replace("ò", "o").replace("ó", "o").replace("ú", "u").replace("ü", "u").replace("ç", "c")
    nombre = re.sub(r"['\,\.\·\-\s]+", "_", nombre)
    nombre = re.sub(r'[^a-zA-Z0-9_]', '', nombre)
    return nombre

def obtener_escudos_con_urls():
    log("📥 Conectando con Wikimedia (Obteniendo TODOS los escudos)...")
    archivos = []
    
    # Parámetros base de la consulta
    params = {
        "action": "query", 
        "generator": "categorymembers", 
        "gcmtitle": "Category:SVG coats of arms of municipalities of the province of Tarragona",
        "gcmlimit": "50", # Pedimos lotes de 50
        "gcmtype": "file", 
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": 800,
        "format": "json"
    }
    
    paginas_descargadas = 1
    
    while True:
        url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={'User-Agent': 'QGIS-Logo-Downloader/14.0 (angellrnzo@example.com)'})
        
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=20) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                if "query" in data and "pages" in data["query"]:
                    for page_id, page in data["query"]["pages"].items():
                        if "imageinfo" in page:
                            info = page["imageinfo"][0]
                            url_img = info.get("thumburl", info.get("url"))
                            archivos.append({
                                "titulo": page["title"],
                                "url": url_img
                            })
                
                # MAGIA AQUÍ: Si hay más páginas, actualizamos los parámetros con TODO el bloque "continue"
                if "continue" in data:
                    params.update(data["continue"])
                    paginas_descargadas += 1
                    print(f"  ... obteniendo lote {paginas_descargadas} de la lista ...")
                    time.sleep(1)
                else:
                    break # Si no hay "continue", es que hemos llegado al final
                    
        except Exception as e:
            log(f"⚠️ Error consultando la API: {e}")
            break
            
    log(f"✅ Se han encontrado un total de {len(archivos)} escudos.")
    return archivos

def descargar_con_reintentos(url, ruta_destino, intentos=3):
    req = urllib.request.Request(url, headers={'User-Agent': 'QGIS-Logo-Downloader/14.0 (angellrnzo@example.com)'})
    for intento in range(intentos):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=20) as response:
                with open(ruta_destino, 'wb') as f:
                    f.write(response.read())
            return True
        except Exception as e:
            if intento == intentos - 1:
                print(f"   ❌ Error final: {e}")
                return False
            time.sleep(5)
    return False

# ============================================================
# PROCESO PRINCIPAL
# ============================================================
def main():
    log("🚀 INICIANDO DESCARGA COMPLETA (V14)")
    log("="*50)
    
    if not os.path.exists(CARPETA_SALIDA):
        os.makedirs(CARPETA_SALIDA)

    archivos_wikimedia = obtener_escudos_con_urls()
    if not archivos_wikimedia:
        log("❌ No se pudieron obtener los archivos.")
        input("Pulsa Enter para salir...")
        return

    exitos = 0
    fallos = 0
    log("\n--- INICIO DE DESCARGAS ---")

    for i, archivo in enumerate(archivos_wikimedia, start=1):
        nombre_limpio = limpiar_nombre_archivo(archivo["titulo"])
        ruta_png = os.path.join(CARPETA_SALIDA, f"{nombre_limpio}.png")
        
        # Si ya lo descargamos en el intento anterior, lo saltamos
        if os.path.exists(ruta_png):
            exitos += 1
            continue

        print(f"🔍 [{i:03d}/{len(archivos_wikimedia)}] Procesando: {nombre_limpio}...")
        
        if not archivo["url"]:
            fallos += 1
            continue

        if descargar_con_reintentos(archivo["url"], ruta_png):
            print(f"   ✅ Guardado")
            log(f"DESCARGADO: {nombre_limpio}.png")
            exitos += 1
            time.sleep(1.5) 
        else:
            fallos += 1

    log("\n" + "="*50)
    log(f"🎉 FINALIZADO: {exitos} descargados en total, {fallos} fallos.")
    log(f"📂 Carpeta: {CARPETA_SALIDA}")

if __name__ == "__main__":
    main()
    input("\n✅ Proceso terminado. Pulsa Enter para salir...")