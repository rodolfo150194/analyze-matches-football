"""
Funciones helper para cálculo de Elo Rating en fútbol
Basado en investigación académica sobre Elo ratings en deportes
"""

from typing import Tuple


def calculate_expected_score(rating_a: float, rating_b: float, home_advantage: float = 100) -> float:
    """
    Calcula el expected score (probabilidad de victoria) para el equipo A vs equipo B

    Fórmula Elo estándar: E_A = 1 / (1 + 10^((R_B - R_A) / 400))

    Args:
        rating_a: Rating Elo del equipo A (típicamente el local)
        rating_b: Rating Elo del equipo B (típicamente el visitante)
        home_advantage: Puntos Elo adicionales para el equipo local (default: 100)
            - Investigación sugiere 68.3-100 puntos para fútbol
            - Usamos 100 como valor conservador

    Returns:
        Probabilidad de victoria del equipo A (0-1)
        - 0.5 = 50% probabilidad (equipos iguales)
        - 0.7 = 70% probabilidad (equipo A favorito)
        - 0.3 = 30% probabilidad (equipo A underdog)

    Referencias:
        - World Football Elo Ratings (Wikipedia)
        - Hvattum & Arntzen (2010): "Using ELO ratings for match result prediction"
    """
    # Ajustar rating del equipo local con ventaja de casa
    adjusted_rating_a = rating_a + home_advantage

    # Calcular diferencia de ratings
    rating_diff = adjusted_rating_a - rating_b

    # Fórmula Elo estándar
    expected = 1 / (1 + 10 ** (-rating_diff / 400))

    return expected


def calculate_new_rating(
    current_rating: float,
    expected_score: float,
    actual_score: float,
    k_factor: float,
    goal_margin_multiplier: float
) -> float:
    """
    Calcula el nuevo rating Elo después de un partido

    Fórmula: R_new = R_old + K * G * (S - E)

    Donde:
        - R_old = Rating actual
        - K = K-factor (importancia del partido)
        - G = Goal margin multiplier (ajuste por diferencia de goles)
        - S = Actual score (1=victoria, 0.5=empate, 0=derrota)
        - E = Expected score (probabilidad pre-partido)

    Args:
        current_rating: Rating Elo actual del equipo
        expected_score: Probabilidad esperada de victoria (0-1)
        actual_score: Resultado real (1.0=victoria, 0.5=empate, 0.0=derrota)
        k_factor: Factor K del partido (típicamente 20-40)
        goal_margin_multiplier: Multiplicador por diferencia de goles (típicamente 1.0-2.0)

    Returns:
        Nuevo rating Elo del equipo

    Ejemplo:
        - Equipo con Elo 1500 gana con expected=0.6: rating sube ~15-20 puntos
        - Equipo con Elo 1500 pierde con expected=0.6: rating baja ~25-30 puntos
    """
    # Calcular cambio en rating
    rating_change = k_factor * goal_margin_multiplier * (actual_score - expected_score)

    # Nuevo rating
    new_rating = current_rating + rating_change

    return new_rating


def calculate_goal_margin_multiplier(goal_diff: int) -> float:
    """
    Calcula el multiplicador basado en la diferencia de goles

    Lógica: Victorias más amplias indican mayor dominio y deben tener más peso.
    Pero el incremento es decreciente (victoria 5-0 no vale el doble que 3-0).

    Fórmula basada en investigación:
        - Empate o victoria por 1: 1.0 (peso normal)
        - Victoria por 2: 1.5 (50% más peso)
        - Victoria por 3: 1.75 (75% más peso)
        - Victoria por 4+: 1.75 + (N-3)/8 (incremento decreciente)

    Args:
        goal_diff: Diferencia absoluta de goles (siempre positiva)

    Returns:
        Multiplicador (>= 1.0)

    Ejemplos:
        - 0-0, 1-1, 2-1: multiplier = 1.0
        - 2-0, 3-1: multiplier = 1.5
        - 3-0, 4-1: multiplier = 1.75
        - 4-0: multiplier = 1.875
        - 5-0: multiplier = 2.0

    Referencias:
        - FiveThirtyEight: "How We Calculate NBA Elo Ratings" (adaptado para fútbol)
        - World Football Elo Ratings methodology
    """
    if goal_diff <= 1:
        return 1.0
    elif goal_diff == 2:
        return 1.5
    elif goal_diff == 3:
        return 1.75
    else:
        # Para diferencias mayores a 3, incremento decreciente
        # 4 goles: 1.875, 5 goles: 2.0, 6 goles: 2.125, etc.
        return 1.75 + (goal_diff - 3) / 8.0


def get_k_factor(competition_code: str, matchday: int = None, season_progress: float = 0.5) -> float:
    """
    Calcula el K-factor dinámico basado en el contexto del partido

    El K-factor determina cuánto cambia el rating después de un partido:
        - K alto: cambios grandes (partidos importantes, early season)
        - K bajo: cambios pequeños (partidos menos importantes)

    Factores considerados:
        1. Importancia de la competición
        2. Fase de la competición (grupos vs eliminatorias)
        3. Progreso de la temporada (inicio vs final)

    Args:
        competition_code: Código de competición (PL, PD, BL1, CL, etc.)
        matchday: Jornada del partido (opcional, usado para Champions League)
        season_progress: Fracción de temporada completada (0-1)
            - 0.0 = inicio de temporada
            - 0.5 = mitad de temporada
            - 1.0 = final de temporada

    Returns:
        K-factor para este partido (típicamente 25-40)

    Valores base:
        - Champions League knockout: 40 (máximo)
        - Champions League groups: 35
        - Ligas domésticas: 30
        - Early season (<20%): 25 (menos certeza sobre formas)
        - Late season (>80%): 35 (más certeza, partidos cruciales)

    Referencias:
        - Lasek et al. (2013): "The predictive power of ranking systems in association football"
    """
    # Base K-factor para ligas domésticas
    base_k = 30

    # Ajuste por competición
    if competition_code == 'CL':  # Champions League
        if matchday and matchday > 8:
            # Knockout stage (Round of 16 onwards)
            # Jornada 9+ son eliminatorias directas
            base_k = 40
        else:
            # Group stage
            base_k = 35

    # Ajuste por progreso de temporada
    if season_progress < 0.2:
        # Primeras 20% de jornadas: menos certeza sobre formas
        k_factor = 25
    elif season_progress > 0.8:
        # Últimas 20% de jornadas: partidos más cruciales
        k_factor = 35
    else:
        # Mitad de temporada: usar base K
        k_factor = base_k

    return k_factor


def get_season_progress(competition_code: str, matchday: int = None) -> float:
    """
    Estima el progreso de la temporada basado en la jornada actual

    Diferentes competiciones tienen diferentes números de jornadas:
        - Premier League / La Liga / Bundesliga / Serie A / Ligue 1: 38 jornadas
        - Champions League: 8 jornadas (fase de grupos) + eliminatorias

    Args:
        competition_code: Código de competición (PL, PD, BL1, SA, FL1, CL)
        matchday: Número de jornada (1-38 para ligas, 1-13+ para CL)

    Returns:
        Fracción de temporada completada (0-1)
        - 0.0 = inicio
        - 0.5 = mitad
        - 1.0 = final

    Si matchday es None, retorna 0.5 (mitad de temporada como default)
    """
    if matchday is None:
        return 0.5  # Default: mitad de temporada

    # Número total de jornadas según competición
    if competition_code == 'CL':
        # Champions League: 8 grupos + 5 rondas eliminatorias = 13 jornadas máx
        total_matchdays = 13
    else:
        # Ligas domésticas: 38 jornadas
        total_matchdays = 38

    # Calcular progreso (limitado a 1.0)
    progress = min(matchday / total_matchdays, 1.0)

    return progress


def get_actual_score_from_result(result: str) -> Tuple[float, float]:
    """
    Convierte el resultado del partido en scores numéricos para Elo

    Args:
        result: 'H' (home win), 'D' (draw), 'A' (away win)

    Returns:
        Tupla (home_score, away_score) donde:
            - 1.0 = victoria
            - 0.5 = empate
            - 0.0 = derrota

    Ejemplos:
        - result='H' → (1.0, 0.0)  # Local gana
        - result='D' → (0.5, 0.5)  # Empate
        - result='A' → (0.0, 1.0)  # Visitante gana
    """
    if result == 'H':
        return (1.0, 0.0)  # Home win
    elif result == 'A':
        return (0.0, 1.0)  # Away win
    elif result == 'D':
        return (0.5, 0.5)  # Draw
    else:
        raise ValueError(f"Invalid result: {result}. Must be 'H', 'D', or 'A'")


# Constantes por defecto (pueden ser sobrescritas en el comando)
DEFAULT_INITIAL_RATING = 1500  # Rating inicial estándar Elo
DEFAULT_HOME_ADVANTAGE = 100   # Puntos Elo de ventaja local
DEFAULT_K_FACTOR = 30          # K-factor base para partidos normales
