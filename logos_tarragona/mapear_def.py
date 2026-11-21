import os
import shutil

# ============================================================
# CONFIGURACIÓN
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETA_ORIGEN = os.path.join(SCRIPT_DIR, "logos_municipios")
CARPETA_DESTINO = os.path.join(SCRIPT_DIR, "logos_finales")
ARCHIVO_FALTANTES = os.path.join(SCRIPT_DIR, "faltantes.txt")

# Diccionario exacto: { "Nombre_Final.png": "Nombre_Original_Descargado.png" o None }
MAPEO = {
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
    "82_vinebre.png": "Escut_de_Vinebre.png"
}

def main():
    if not os.path.exists(CARPETA_DESTINO):
        os.makedirs(CARPETA_DESTINO)
        
    if not os.path.exists(CARPETA_ORIGEN):
        print(f"❌ No existe la carpeta de origen: {CARPETA_ORIGEN}")
        return

    exitos = 0
    faltantes = []

    print("🚀 INICIANDO MAPEO Y RENOMBRADO...\n")

    for nombre_final, nombre_original in MAPEO.items():
        if nombre_original is None:
            faltantes.append(nombre_final.replace('.png', '').split('_', 1)[1].upper())
            continue
            
        ruta_origen = os.path.join(CARPETA_ORIGEN, nombre_original)
        ruta_destino = os.path.join(CARPETA_DESTINO, nombre_final)

        if os.path.exists(ruta_origen):
            shutil.copy2(ruta_origen, ruta_destino)
            print(f"✅ {nombre_final:35} <- {nombre_original}")
            exitos += 1
        else:
            print(f"⚠️ ERROR: No se encontró {nombre_original} en la carpeta de origen.")
            faltantes.append(nombre_final.replace('.png', '').split('_', 1)[1].upper())

    print("\n" + "="*50)
    print(f"🎉 FINALIZADO: {exitos} archivos copiados a la carpeta '{CARPETA_DESTINO}'.")
    
    if faltantes:
        print(f"\n⚠️ Quedan {len(faltantes)} municipios que no estaban en la descarga de Wikipedia.")
        print("Los he guardado en el archivo 'faltantes.txt' para que los busques a mano.")
        
        with open(ARCHIVO_FALTANTES, 'w', encoding='utf-8') as f:
            for muni in faltantes:
                f.write(muni + "\n")

if __name__ == "__main__":
    main()
    input("\n✅ Proceso terminado. Pulsa Enter para salir...")