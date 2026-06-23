"""
Pipeline de cálculo del Indicador de Puntualidad (IP):

1. Recorre cada fecha presente en las expediciones.
2. Para cada (Servicio, Sentido) presente en el A5, filtra la LPP del
   tipo de día correspondiente.
3. Para cada Punto de Control (PC), cruza la LPP contra la LPO del día
   y asigna (de forma cronológica/greedy) la pasada observada que
   corresponda a cada TPP.
4. Agrega los resultados en un DataFrame y calcula el IP mensual final.
"""

import pandas as pd

from src.calcular_ip import calcular_ip_un_tpp
from src.tiempo import clasificar_tipo_dia


def calcular_resultados(df_a5: pd.DataFrame, df_lpo: pd.DataFrame, fechas: list) -> pd.DataFrame:
    """
    Calcula el IP de cada TPP para todas las fechas, servicios, sentidos
    y puntos de control presentes en df_a5 / df_lpo.

    Retorna un DataFrame con una fila por TPP evaluado, con columnas:
    fecha, tipo_dia, Servicio, Sentido, correlativo_pc, TPP, Periodo, IP
    """
    servicios_sentido_a5 = list(
        df_a5[["Servicio", "Sentido"]].drop_duplicates().itertuples(index=False, name=None)
    )

    resultados = []

    for fecha in sorted(fechas):
        tipo_dia_actual = clasificar_tipo_dia(fecha)
        lpo_del_dia = df_lpo[df_lpo["fecha"] == fecha]

        for servicio, sentido in servicios_sentido_a5:
            lpp_grupo = df_a5[
                (df_a5.Servicio == servicio)
                & (df_a5.Sentido == sentido)
                & (df_a5.tipo_dia == tipo_dia_actual)
            ].sort_values("correlativo_pc")

            if lpp_grupo.empty:
                continue

            for pc in lpp_grupo["correlativo_pc"].unique():
                resultados.extend(
                    _calcular_ip_por_pc(
                        lpp_grupo=lpp_grupo,
                        lpo_del_dia=lpo_del_dia,
                        servicio=servicio,
                        sentido=sentido,
                        pc=pc,
                        fecha=fecha,
                        tipo_dia_actual=tipo_dia_actual,
                    )
                )

    return pd.DataFrame(resultados)


def _calcular_ip_por_pc(
    lpp_grupo: pd.DataFrame,
    lpo_del_dia: pd.DataFrame,
    servicio,
    sentido,
    pc,
    fecha,
    tipo_dia_actual: str,
) -> list[dict]:
    """Calcula el IP de todas las TPP de un mismo (servicio, sentido, pc, fecha)."""

    # Lista de Pasadas Programadas (LPP) para este punto de control,
    # ordenadas cronológicamente.
    lpp_pc = lpp_grupo[lpp_grupo.correlativo_pc == pc].sort_values("TPP_seg")

    # Lista de Pasadas Observadas (LPO) disponibles para este mismo
    # servicio/sentido/pc/día, ordenadas cronológicamente.
    lpo_pc = lpo_del_dia[
        (lpo_del_dia.Servicio == servicio)
        & (lpo_del_dia.Sentido == sentido)
        & (lpo_del_dia.correlativo_pc == pc)
    ][["TPO_seg", "Periodo"]].to_dict("records")
    lpo_pc.sort(key=lambda x: x["TPO_seg"])

    filas = []
    for _, fila in lpp_pc.iterrows():
        ip_valor, bus_usado = calcular_ip_un_tpp(
            fila["TPP_seg"], fila["IPP_anterior_seg"], fila["IPP_posterior_seg"], lpo_pc
        )

        periodo_usado = None
        if bus_usado is not None:
            periodo_usado = bus_usado["Periodo"]
            # Se elimina la pasada usada de la LPO disponible (regla de la
            # resolución: cada pasada observada se asigna a un único TPP).
            lpo_pc.remove(bus_usado)

        filas.append(
            {
                "fecha": fecha,
                "tipo_dia": tipo_dia_actual,
                "Servicio": servicio,
                "Sentido": sentido,
                "correlativo_pc": pc,
                "TPP": fila["TPP"],
                "Periodo": periodo_usado,
                "IP": ip_valor,
            }
        )

    return filas


def calcular_ip_mensual(df_resultados: pd.DataFrame) -> tuple[float, float]:
    """
    Calcula el IP mensual (IP_M') y aplica los topes de la normativa
    para obtener el IP_M final:
        - si IP_M' < 0.50 -> IP_M = 0.50
        - si IP_M' > 0.90 -> IP_M = 1.00
        - en otro caso    -> IP_M = IP_M'

    Retorna (ip_promedio, ip_final)
    """
    ip_promedio = round(df_resultados["IP"].mean(), 2)

    if ip_promedio < 0.50:
        ip_final = 0.50
    elif ip_promedio > 0.90:
        ip_final = 1.0
    else:
        ip_final = ip_promedio

    return ip_promedio, ip_final
