"""
Punto de entrada del cálculo del Indicador de Puntualidad (IP).

Recorre automáticamente todas las carpetas de mes con datos dentro de
data/<EMPRESA>/ (ej. Abril26, Mayo26, Junio26, ...) y genera un reporte
Excel por cada una.

Estructura de carpetas esperada:

    proyecto/
    ├── main.py
    ├── src/
    │   ├── tiempo.py
    │   ├── io_utils.py
    │   ├── calcular_ip.py
    │   ├── pipeline.py
    │   ├── exportar.py
    │   └── descubrir.py
    └── data/
        └── toptur/
            ├── POT_..._A5__2.xlsx          (puede haber más de uno)
            ├── POT_..._A1_2.xlsx
            ├── Enero26/
            │   └── expediciones_toptur_enero26.xls
            ├── Febrero26/
            │   └── expediciones_toptur_febrero26.xls
            └── ...

Cada archivo A5 (.xlsx) debe declarar en su encabezado su rango de
vigencia ("FECHA INICIO A5" / "FECHA FIN A5"); el A5 correcto para cada
mes se elige automáticamente según esa vigencia.

Uso:
    python main.py
"""

import datetime
from pathlib import Path

from src.descubrir import listar_meses
from src.exportar import exportar_reporte_excel
from src.io_utils import buscar_a5_para_fecha, cargar_lpo, cargar_lpp, construir_lpo_largo
from src.pipeline import calcular_ip_mensual, calcular_resultados

# --- Configuración de rutas 
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SALIDA = ROOT / "salida"

EMPRESA = "lider"
EMPRESA_DIR = DATA / EMPRESA

FORMATO_EXPEDICIONES = "html"

# Estacionalidades del A5 que aplican al cálculo de IP. Otros archivos A5
# (ej. "A1") existen en la misma carpeta pero corresponden a otros
# indicadores y se ignoran. Cuando llegue el A5 estival (enero-febrero),
# agrega su nombre de estacionalidad aquí, ej: ("NORMAL", "ESTIVAL").
ESTACIONALIDADES_VALIDAS = ("NORMAL", "ESTIVAL")


def procesar_mes(mes_info: dict) -> None:
    """Calcula y exporta el reporte de IP para un mes específico."""
    carpeta = mes_info["carpeta"]
    mes_nombre = mes_info["mes_nombre"]
    anio_str = mes_info["anio_str"]
    expediciones_path = mes_info["expediciones_path"]

    print(f"--- Procesando {mes_nombre}{anio_str} ({carpeta.name}) ---")

    # 0. Elegir el A5 vigente para ese mes
    anchor_fecha = datetime.date(mes_info["anio_num"], mes_info["mes_num"], 1)
    a5_path = buscar_a5_para_fecha(
        EMPRESA_DIR, anchor_fecha, estacionalidades_validas=ESTACIONALIDADES_VALIDAS
    )
    print(f"  A5 vigente: {a5_path.name}")

    # 1. Carga de datos ---------------------------------------------------
    df_a5 = cargar_lpp(a5_path)
    df_expediciones = cargar_lpo(expediciones_path, formato=FORMATO_EXPEDICIONES)
    df_lpo = construir_lpo_largo(df_expediciones)

    # 2. Cálculo del IP por TPP ------------------------------------------
    fechas = df_expediciones["fecha"].unique()
    df_resultados = calcular_resultados(df_a5, df_lpo, fechas)

    if df_resultados.empty:
        print("  No se generaron resultados: revisa el cruce Servicio/Sentido/PC/Tipo de día.")
        return

    # 3. Agregación final --------------------------------------------------
    ip_promedio, ip_final = calcular_ip_mensual(df_resultados)
    print(f"  IP_M' = {ip_promedio}  →  IP_M = {ip_final}")

    # 4. Exportación a Excel ------------------------------------------------
    exportar_reporte_excel(
        df_resultados, SALIDA, empresa=EMPRESA.upper(), mes=mes_nombre, anio=anio_str
    )


def main() -> None:
    meses = listar_meses(EMPRESA_DIR)

    if not meses:
        print(f"No se encontraron carpetas de mes con datos en {EMPRESA_DIR}")
        return

    for mes_info in meses:
        try:
            procesar_mes(mes_info)
        except Exception as e:
            print(f"  ERROR procesando '{mes_info['carpeta'].name}': {e}")
        print()


if __name__ == "__main__":
    main()
