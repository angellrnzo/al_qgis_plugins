import os
from PIL import Image

# ============================================================
# CONFIGURACIÓN
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETAS_A_LIMPIAR = [
    os.path.join(SCRIPT_DIR, "logos_municipios"),
    os.path.join(SCRIPT_DIR, "logos_finales")
]

def limpiar_fondo(ruta_imagen):
    try:
        img = Image.open(ruta_imagen).convert("RGBA")
        datas = img.getdata()
        newData = []
        
        # Recorremos cada píxel de la imagen
        for item in datas:
            # Si el píxel es blanco o casi blanco (R, G y B > 240)
            if item[0] > 240 and item[1] > 240 and item[2] > 240:
                # Lo convertimos en 100% transparente
                newData.append((255, 255, 255, 0))
            else:
                # Mantenemos el píxel original
                newData.append(item)

        img.putdata(newData)
        img.save(ruta_imagen, "PNG")
        return True
    except Exception as e:
        print(f"   ❌ Error con {os.path.basename(ruta_imagen)}: {e}")
        return False

def main():
    print("🧹 INICIANDO LIMPIEZA DE FONDOS EN LOTE...\n")
    total_limpiados = 0

    for carpeta in CARPETAS_A_LIMPIAR:
        if not os.path.exists(carpeta):
            print(f"⚠️ La carpeta no existe, saltando: {carpeta}")
            continue
            
        print(f"📂 Procesando carpeta: {os.path.basename(carpeta)}...")
        archivos = [f for f in os.listdir(carpeta) if f.lower().endswith('.png')]
        
        if not archivos:
            print("   (No hay archivos PNG aquí)")
            continue

        exitos_carpeta = 0
        for archivo in archivos:
            ruta_completa = os.path.join(carpeta, archivo)
            if limpiar_fondo(ruta_completa):
                exitos_carpeta += 1
                
        print(f"   ✅ {exitos_carpeta} imágenes limpiadas en {os.path.basename(carpeta)}.\n")
        total_limpiados += exitos_carpeta

    print("="*50)
    print(f"🎉 FINALIZADO: Se han procesado y limpiado un total de {total_limpiados} imágenes.")

if __name__ == "__main__":
    main()
    input("\n✅ Proceso terminado. Pulsa Enter para salir...")