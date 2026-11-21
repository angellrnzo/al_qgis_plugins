import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETA_ORIGEN = os.path.join(SCRIPT_DIR, "logos_municipios")
ARCHIVO_SALIDA = os.path.join(SCRIPT_DIR, "lista_descargados.txt")

def main():
    print(f"📂 Leyendo la carpeta: {CARPETA_ORIGEN}")
    
    if not os.path.exists(CARPETA_ORIGEN):
        print("❌ La carpeta no existe. Asegúrate de haber ejecutado el script de descarga.")
        input("Pulsa Enter para salir...")
        return

    # Obtener todos los archivos PNG y ordenarlos alfabéticamente
    archivos = sorted([f for f in os.listdir(CARPETA_ORIGEN) if f.lower().endswith('.png')])
    
    if not archivos:
        print("⚠️ La carpeta está vacía.")
        input("Pulsa Enter para salir...")
        return

    # Guardar la lista en un archivo de texto
    with open(ARCHIVO_SALIDA, 'w', encoding='utf-8') as f:
        for archivo in archivos:
            f.write(archivo + "\n")

    print(f"✅ Se han encontrado {len(archivos)} archivos.")
    print(f"📄 La lista se ha guardado en: {ARCHIVO_SALIDA}")
    print("\n👉 Abre el archivo 'lista_descargados.txt' y copia/pega su contenido aquí en el chat.")

if __name__ == "__main__":
    main()
    input("\n✅ Proceso terminado. Pulsa Enter para salir...")