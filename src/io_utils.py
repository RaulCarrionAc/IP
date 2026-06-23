"""
Carga y limpieza de las dos fuentes de datos del cálculo de IP:

- LPP (Lista de Pasadas Programadas): hoja "LPP" del archivo A5 (.xlsx)
- LPO (Lista de Pasadas Observadas): archivo de expediciones (.xls / .csv)
"""

from pathlib import Path

import pandas as pd

from src.tiempo import a_segundos, clasificar_tipo_dia

# Mapeo de sentido: debe quedar IGUAL en ambas fuentes (A5 y expediciones).
# En el A5, "Sentido" viene codificado como entero (0 = Ida, 1 = Reg).
# En expediciones viene como texto ("Ida"/"Reg") o abreviado ("I"/"V").
MAPEO_SENTIDO = {"Ida": 0, "Reg": 1, "I": 0, "V": 1}

# Nombres de columnas del A5 tal como vienen en el Excel -> nombres internos
CAMPOS_A5 = {
    "Correlativo Punto\nde Control": "correlativo_pc",
    "Intervalo Anterior\n(IPPdk-1)": "IPP_anterior",
    "Hora de Pasada Programada\n(TPPdk)": "TPP",
    "Intervalo Posterior\n(IPPdk)": "IPP_posterior",
    "Tipo de Día": "tipo_dia",
}


# Palabras que indican que una celda es una etiqueta (no un valor), usadas
# para no confundir el siguiente label con el valor buscado.
_PALABRAS_LABEL = (
    "FECHA",
    "TIPO",
    "REGIÓN",
    "REGION",
    "ZONA",
    "UNIDAD",
    "RES N",
    "CON VERSIONES",
    "ESTACIONALIDAD",
)

# Estacionalidades conocidas, usadas para inferirla desde el nombre del
# archivo cuando la hoja no la declara explícitamente (ej. formato "lider").
_ESTACIONALIDADES_CONOCIDAS = ("NORMAL", "ESTIVAL", "A1", "A2")


def _parece_label(valor) -> bool:
    if not isinstance(valor, str):
        return False
    v = valor.strip().upper()
    return any(p in v for p in _PALABRAS_LABEL)


def _buscar_etiqueta(raw: pd.DataFrame, *etiquetas: str, max_filas: int = 25):
    """Busca la primera celda (dentro de las primeras `max_filas`) cuyo
    texto coincida exactamente (sin espacios extra, sin distinguir
    mayúsculas) con alguna de las etiquetas dadas. Retorna (fila, col) o
    None si no se encontró ninguna."""
    limite = min(max_filas, raw.shape[0])
    objetivo = {e.strip().upper() for e in etiquetas}
    for i in range(limite):
        for j in range(raw.shape[1]):
            val = raw.iat[i, j]
            if isinstance(val, str) and val.strip().upper() in objetivo:
                return i, j
    return None


def _valor_asociado(raw: pd.DataFrame, fila: int, col: int):
    """
    Dada la posición de una etiqueta, busca su valor asociado soportando
    dos layouts distintos de encabezado:
      - Vertical (ej. UN07): el valor está en la misma columna, fila siguiente.
      - Horizontal (ej. lider): el valor está en la misma fila, columnas siguientes.
    """
    # 1. Layout vertical: misma columna, fila siguiente
    if fila + 1 < raw.shape[0]:
        val = raw.iat[fila + 1, col]
        if pd.notna(val) and not _parece_label(val):
            return val

    # 2. Layout horizontal: misma fila, columnas siguientes
    for c in range(col + 1, raw.shape[1]):
        val = raw.iat[fila, c]
        if pd.notna(val) and not _parece_label(val):
            return val

    return None


def _inferir_estacionalidad_de_nombre(nombre_archivo: str) -> str:
    """Si la hoja no declara la estacionalidad explícitamente, se intenta
    inferir desde el nombre del archivo (ej. '..._NORMAL_2026_2_A5__2.xlsx')."""
    nombre = nombre_archivo.upper()
    for clave in _ESTACIONALIDADES_CONOCIDAS:
        if clave in nombre:
            return clave
    return "DESCONOCIDA"


def leer_vigencia_a5(a5_path: Path, hoja: str = "LPP"):
    """
    Lee desde el encabezado del archivo A5:
        - Estacionalidad (ej. "NORMAL", "A1"). Si la hoja no la declara
          explícitamente, se infiere desde el nombre del archivo.
        - Fecha de inicio y fin de vigencia del A5 (busca tanto la
          etiqueta "FECHA INICIO A5"/"FECHA FIN A5" como, en formatos sin
          el sufijo "A5", simplemente "FECHA INICIO"/"FECHA FIN").

    Soporta tanto layouts "verticales" (etiqueta en una fila, valor en la
    fila siguiente) como "horizontales" (etiqueta y valor en la misma
    fila, con columnas vacías entre medio).

    Retorna (estacionalidad, fecha_inicio, fecha_fin).
    """
    a5_path = Path(a5_path)
    raw = pd.read_excel(a5_path, sheet_name=hoja, header=None)

    pos_inicio = _buscar_etiqueta(raw, "FECHA INICIO A5", "FECHA INICIO")
    pos_fin = _buscar_etiqueta(raw, "FECHA FIN A5", "FECHA FIN")
    if pos_inicio is None or pos_fin is None:
        raise ValueError(
            f"No se encontraron las etiquetas de vigencia (FECHA INICIO/FIN) en {a5_path}"
        )

    fecha_inicio = pd.to_datetime(_valor_asociado(raw, *pos_inicio), dayfirst=True).date()
    fecha_fin = pd.to_datetime(_valor_asociado(raw, *pos_fin), dayfirst=True).date()

    pos_est = _buscar_etiqueta(raw, "Estacionalidad")
    if pos_est is not None:
        valor_est = _valor_asociado(raw, *pos_est)
        estacionalidad = str(valor_est).strip() if valor_est is not None else None
    else:
        estacionalidad = None

    if not estacionalidad:
        estacionalidad = _inferir_estacionalidad_de_nombre(a5_path.name)

    return estacionalidad, fecha_inicio, fecha_fin


def buscar_a5_para_fecha(empresa_dir: Path, fecha, estacionalidades_validas=("NORMAL",)) -> Path:
    """
    Busca, entre los .xlsx ubicados directamente en empresa_dir (es decir,
    sin entrar a las subcarpetas de mes), el archivo A5 cuya estacionalidad
    esté dentro de `estacionalidades_validas` (por defecto solo "NORMAL",
    que es la que aplica al cálculo de IP) y cuyo rango de vigencia
    (FECHA INICIO A5 / FECHA FIN A5) cubre la fecha dada.

    Otras estacionalidades no incluidas en `estacionalidades_validas`
    (ej. "A1") se ignoran porque corresponden a otros indicadores, no al IP.

    Cuando exista también un A5 estival (ej. para enero-febrero), basta
    con agregar su nombre de estacionalidad a `estacionalidades_validas`,
    por ejemplo: ("NORMAL", "ESTIVAL").
    """
    fecha = pd.Timestamp(fecha).date()
    validas = {e.upper() for e in estacionalidades_validas}

    for a5_path in sorted(empresa_dir.glob("*.xlsx")):
        try:
            est, fecha_inicio, fecha_fin = leer_vigencia_a5(a5_path)
        except Exception:
            continue
        if est.upper() not in validas:
            continue
        if fecha_inicio <= fecha <= fecha_fin:
            return a5_path

    raise FileNotFoundError(
        f"No se encontró un A5 con estacionalidad en {estacionalidades_validas} "
        f"vigente para la fecha {fecha} en {empresa_dir}"
    )


def cargar_lpp(a5_path: Path, hoja: str = "LPP", skiprows: int = 10) -> pd.DataFrame:
    """
    Lee la hoja LPP del archivo A5 y la deja lista para el cruce:
    - Renombra columnas a nombres internos.
    - Agrega columnas *_seg con la conversión a segundos de IPP_anterior,
      TPP e IPP_posterior.
    """
    df_a5 = pd.read_excel(a5_path, sheet_name=hoja, skiprows=skiprows, header=0)
    df_a5 = df_a5.rename(columns=CAMPOS_A5)

    for col in ["IPP_anterior", "TPP", "IPP_posterior"]:
        df_a5[col + "_seg"] = df_a5[col].apply(a_segundos)

    return df_a5


def cargar_lpo(expediciones_path: Path, formato: str = "html") -> pd.DataFrame:
    """
    Lee el archivo de expediciones y retorna el DataFrame "ancho" original
    (una fila por expedición, columnas 1..N con la hora de paso por cada PC).

    formato:
        - "html": el archivo .xls exportado por el sistema es en realidad HTML
          (pd.read_html). Es el formato original.
        - "csv": un csv ya exportado (equivalente, útil para pruebas locales).
    """
    if formato == "html":
        df_expediciones = pd.read_html(expediciones_path)[0]
    elif formato == "csv":
        df_expediciones = pd.read_csv(expediciones_path, index_col=0)
    else:
        raise ValueError(f"Formato de expediciones no soportado: {formato}")

    return _limpiar_expediciones(df_expediciones)


def _limpiar_expediciones(df_expediciones: pd.DataFrame) -> pd.DataFrame:
    """Aplica el mapeo de sentido, filtra estado válido y clasifica tipo de día."""
    df_expediciones = df_expediciones.copy()

    df_expediciones["Sentido"] = df_expediciones["Sentido"].replace(MAPEO_SENTIDO)
    df_expediciones["Estado"] = df_expediciones["Estado"].str.strip().str.lower()
    df_expediciones = df_expediciones[df_expediciones["Estado"] == "valida"].copy()

    df_expediciones["fecha"] = pd.to_datetime(df_expediciones["Inicio Expedicion"]).dt.date
    df_expediciones["tipo_dia"] = df_expediciones["fecha"].apply(clasificar_tipo_dia)

    return df_expediciones


def construir_lpo_largo(df_expediciones: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte el DataFrame ancho de expediciones (una fila por expedición,
    columnas 1..N = horas de paso por PC) a formato largo: una fila por
    (expedición, correlativo_pc), con la hora de paso (TPO) en segundos.
    """
    columnas_pc = [c for c in df_expediciones.columns if str(c).isdigit()]

    df_lpo = df_expediciones.melt(
        id_vars=["Servicio", "Sentido", "fecha", "Inicio Expedicion", "Estado", "Bus", "Periodo"],
        value_vars=columnas_pc,
        var_name="correlativo_pc",
        value_name="TPO",
    )

    df_lpo["correlativo_pc"] = df_lpo["correlativo_pc"].astype(int)
    df_lpo["TPO_seg"] = df_lpo["TPO"].apply(a_segundos)
    df_lpo = df_lpo[(df_lpo["Estado"] == "valida") & df_lpo["TPO_seg"].notna()]

    return df_lpo
