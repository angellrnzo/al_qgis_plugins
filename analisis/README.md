# analisis/ —/plugins de terceros (referencia, NO empaquetar)

Material de análisis de plugins QGIS de terceros. **No son plugins del
repo**: no ejecutar `package-plugin.ps1` sobre estas carpetas.

| Carpeta / archivo | Qué es |
| :--- | :--- |
| `volcador_tuberias_original/` | Fuente original de `Volcador Tuberias a Trams` (Marisa Pardo Villar / Dielmo, `version=1.24.1`). Referencia para comparar contra nuestra versión modificada. |
| `iconos_preview.png` | Preview de los iconos propios generados para la v1.4.2 (baldoza verde + glifo blanco). |

## volcador_tuberias — de original a v1.4.2

- El plugin oficial traía las acciones secundarias con `QIcon()` vacío
  (salian como texto plano en la barra).
- Nuestra versión (`../volcador_tuberias/`, zip `dist/volcador_tuberias-v1.4.2.zip`)
  agrega `icons/` con 6 PNGs propios cableados en `initGui` y entrada de
  changelog 1.4.2. Logica intacta.
- Ojo con los ambitos: sus funciones de volcado/lote son de **saneamiento**
  (211/222/231); `girar` si sirve para potables (111/211).
