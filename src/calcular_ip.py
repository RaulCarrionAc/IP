"""
Núcleo del cálculo del Indicador de Puntualidad (IP) por Hora de Pasada
Programada (TPP), según los niveles de tolerancia de la resolución
(páginas 46-47).
"""

from typing import Optional


def calcular_ip_un_tpp(
    tpp: float,
    ipp_ant: float,
    ipp_post: float,
    lpo_disponible: list[dict],
) -> tuple[float, Optional[dict]]:
    """
    Calcula el IP de una Hora de Pasada Programada (TPP) individual.

    Parámetros
    ----------
    tpp, ipp_ant, ipp_post : segundos (float)
        TPP: hora de pasada programada.
        ipp_ant: intervalo con la pasada programada anterior.
        ipp_post: intervalo con la pasada programada posterior.
    lpo_disponible : list[dict]
        Lista de pasadas observadas (LPO) aún no asignadas, ordenadas
        cronológicamente. Cada elemento debe tener al menos la clave
        "TPO_seg" (hora observada en segundos).

    Retorna
    -------
    (ip_valor, bus_usado)
        ip_valor: 1.0, 0.75, 0.5, 0.25 o 0.0
        bus_usado: el dict de lpo_disponible que generó el match
                   (para poder removerlo de la lista por el caller), o None.
    """
    niveles = [
        (tpp - ipp_ant / 12, tpp + ipp_post / 6, 1.0),
        (tpp - ipp_ant / 6, tpp - ipp_ant / 12, 0.75),
        (tpp + ipp_post / 6, tpp + ipp_post / 3, 0.75),
        (tpp - ipp_ant / 4, tpp - ipp_ant / 6, 0.5),
        (tpp + ipp_post / 3, tpp + ipp_post / 2, 0.5),
        (tpp - ipp_ant / 3, tpp - ipp_ant / 4, 0.25),
        (tpp + ipp_post / 2, tpp + (2 / 3) * ipp_post, 0.25),
    ]

    for lo, hi, valor in niveles:
        for bus in lpo_disponible:
            tpo = bus["TPO_seg"]
            if lo <= tpo <= hi:
                return valor, bus

    return 0.0, None
