import os

# ============================================================
# CONFIGURACIÓN
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETA_DESTINO = os.path.join(SCRIPT_DIR, "logos_finales")
ARCHIVO_REPORTE = os.path.join(SCRIPT_DIR, "reporte_faltantes.txt")

# Lista exacta de los 82 archivos esperados
LISTA_ESPERADA = [
    "01_alcover.png", "02_aldover.png", "03_alfara_de_carles.png", "04_almoster.png",
    "05_arboli.png", "06_arnes.png", "07_asco.png", "08_batea.png", "09_bellmunt_del_priorat.png",
    "10_benifallet.png", "11_benissanet.png", "12_blancafort.png", "13_bot.png",
    "14_botarell.png", "15_cabaces.png", "16_capafonts.png", "17_capcanes.png",
    "18_caseres.png", "19_colldejou.png", "20_constanti.png", "21_cornudella_de_montsant.png",
    "22_duesaigues.png", "23_el_lloar.png", "24_el_masroig.png", "25_el_mila.png",
    "26_el_molar.png", "27_el_morell.png", "28_el_pinell_de_brai.png", "29_el_rourell.png",
    "30_els_guiamets.png", "31_falset.png", "32_flix.png", "33_garcia.png", "34_ginestar.png",
    "35_godall.png", "36_gratallops.png", "37_horta_de_sant_joan.png", "38_l_aleixar.png",
    "39_l_espluga_de_francoli.png", "40_la_bisbal_de_falset.png", "41_la_fatarella.png",
    "42_la_febro.png", "43_la_figuera.png", "44_la_galera.png", "45_la_maso.png",
    "46_la_morera_de_montsant.png", "47_la_palma_d_ebre.png", "48_la_pobla_de_mafumet.png",
    "49_la_riba.png", "50_la_senia.png", "51_la_torre_de_fontaubella.png",
    "52_la_torre_de_l_espanyol.png", "53_la_vilella_alta.png", "54_la_vilella_baixa.png",
    "55_marca.png", "56_margalef.png", "57_mas_de_barberans.png", "58_maspujols.png",
    "59_miravet.png", "60_mont_ral.png", "61_mont_roig_del_camp.png", "62_montblanc.png",
    "63_montbrio_del_camp.png", "64_pauls.png", "65_perafort.png", "66_poboleda.png",
    "67_porrera.png", "68_pradell_de_la_teixeta.png", "69_prades.png", "70_prat_de_comte.png",
    "71_riba_roja_d_ebre.png", "72_riudoms.png", "73_senan.png", "74_torroja_del_priorat.png",
    "75_ulldemolins.png", "76_vallclara.png", "77_vilallonga_del_camp.png",
    "78_vilanova_d_escornalbou.png", "79_vilanova_de_prades.png", "80_vilaplana.png",
    "81_vilaverd.png", "82_vinebre.png"
]

def main():
    if not os.path.exists(CARPETA_DESTINO):
        print(f"❌ No existe la carpeta: {CARPETA_DESTINO}. Crea la carpeta y mete los archivos ahí.")
        input("Pulsa Enter para salir...")
        return

    print(f"🔎 Verificando la carpeta: {CARPETA_DESTINO}\n")

    encontrados = 0
    faltantes = []

    for nombre_archivo in LISTA_ESPERADA:
        ruta_completa = os.path.join(CARPETA_DESTINO, nombre_archivo)
        
        if os.path.isfile(ruta_completa):
            print(f"✅ OK: {nombre_archivo}")
            encontrados += 1
        else:
            print(f"❌ FALTA: {nombre_archivo}")
            faltantes.append(nombre_archivo)

    print("\n" + "="*50)
    print(f"📊 RESULTADO: Tienes {encontrados} de {len(LISTA_ESPERADA)} logos.")

    if faltantes:
        print(f"\n⚠️ Te faltan {len(faltantes)} logos por descargar o renombrar.")
        print(f"Los he guardado en el archivo: {ARCHIVO_REPORTE}")
        
        with open(ARCHIVO_REPORTE, 'w', encoding='utf-8') as f:
            for f_name in faltantes:
                f.write(f_name + "\n")
    else:
        print("\n🎉 ¡FELICIDADES! Tienes la colección completa de los 82 municipios lista para usar en tu plugin de QGIS.")
        if os.path.exists(ARCHIVO_REPORTE):
            os.remove(ARCHIVO_REPORTE)

if __name__ == "__main__":
    main()
    input("\n✅ Proceso terminado. Pulsa Enter para salir...")