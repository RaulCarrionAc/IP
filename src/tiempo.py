"""
Utilidades de tiempo: conversión de horas a segundos y clasificación
del tipo de día (DL / DS / DF) según feriados y día de la semana en Chile.
"""

import pandas as pd
import numpy as np
import holidays

# Calendario de feriados de Chile (se calcula una sola vez al importar el módulo)
FERIADOS_CL = holidays.Chile()


def a_segundos(valor):
    """
    Convierte un valor de hora (str "HH:MM:SS", datetime.time o pd.Timedelta)
    a la cantidad equivalente de segundos.

    Retorna np.nan si el valor es nulo.
    """
    if pd.isna(valor):
        return np.nan
    if isinstance(valor, pd.Timedelta):
        return valor.total_seconds()
    if hasattr(valor, "hour"):  # datetime.time
        return valor.hour * 3600 + valor.minute * 60 + valor.second
    h, m, s = map(int, str(valor).split(":"))
    return h * 3600 + m * 60 + s


def clasificar_tipo_dia(fecha) -> str:
    """
    Clasifica una fecha en:
        - "DF": domingo o feriado
        - "DS": sábado
        - "DL": día laboral (lunes a viernes no feriado)
    """
    fecha = pd.Timestamp(fecha).date()
    if fecha in FERIADOS_CL:
        return "DF"

    dow = pd.Timestamp(fecha).dayofweek  # 0=lunes ... 6=domingo
    if dow == 6:
        return "DF"
    elif dow == 5:
        return "DS"
    else:
        return "DL"
