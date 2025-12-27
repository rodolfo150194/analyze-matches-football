"""
Modelos Poisson y Dixon-Coles para predicción de goles en fútbol
Estos modelos son específicos para fútbol y mejoran las predicciones de Over/Under y BTTS

Referencias:
- Dixon & Coles (1997): "Modelling Association Football Scores and Inefficiencies in the Football Betting Market"
- Maher (1982): "Modelling association football scores"
- Karlis & Ntzoufras (2003): "Analysis of sports data by using bivariate Poisson models"
"""

import numpy as np
from scipy.stats import poisson
from scipy.optimize import minimize
from typing import Dict, List, Tuple
import math


class PoissonModel:
    """
    Modelo Poisson básico para predicción de goles en fútbol

    Asume que los goles siguen distribución de Poisson independiente para cada equipo:
    - λ_home = attack_home × defense_away × home_advantage
    - λ_away = attack_away × defense_home

    Donde:
    - attack_strength: Capacidad ofensiva del equipo (relativa a la media)
    - defense_strength: Capacidad defensiva del equipo (relativa a la media)
    - home_advantage: Factor de ventaja local (~1.3-1.5 en fútbol)
    """

    def __init__(self, home_advantage: float = 1.3):
        """
        Args:
            home_advantage: Factor multiplicativo de ventaja local (default: 1.3)
                           Investigación sugiere 1.3-1.5 para fútbol de élite
        """
        self.home_advantage = home_advantage
        self.team_params = {}  # {team_id: {'attack': float, 'defense': float}}
        self.league_avg_goals = 2.7  # Promedio de goles por equipo por partido

    def calculate_expected_goals(self, home_attack: float, home_defense: float,
                                 away_attack: float, away_defense: float) -> Tuple[float, float]:
        """
        Calcula los goles esperados para cada equipo usando modelo Poisson

        Fórmulas:
        - λ_home = attack_home × defense_away × home_advantage × league_avg
        - λ_away = attack_away × defense_home × league_avg

        Args:
            home_attack: Fuerza ofensiva del local (relativa a 1.0)
            home_defense: Fuerza defensiva del local (relativa a 1.0)
            away_attack: Fuerza ofensiva del visitante
            away_defense: Fuerza defensiva del visitante

        Returns:
            Tuple (λ_home, λ_away): Goles esperados para local y visitante

        Ejemplo:
            - Equipo fuerte (attack=1.3, defense=0.8) vs débil (attack=0.8, defense=1.2)
            - λ_home = 1.3 × 1.2 × 1.3 × 1.35 ≈ 2.7 goles esperados
            - λ_away = 0.8 × 0.8 × 1.35 ≈ 0.9 goles esperados
        """
        # Goles esperados local (con ventaja de casa)
        lambda_home = home_attack * away_defense * self.home_advantage * self.league_avg_goals

        # Goles esperados visitante (sin ventaja)
        lambda_away = away_attack * home_defense * self.league_avg_goals

        return lambda_home, lambda_away

    def predict_score_probability(self, lambda_home: float, lambda_away: float,
                                  home_goals: int, away_goals: int) -> float:
        """
        Calcula la probabilidad de un marcador específico usando Poisson

        Fórmula: P(X=k) = (λ^k × e^(-λ)) / k!

        Args:
            lambda_home: Goles esperados del local
            lambda_away: Goles esperados del visitante
            home_goals: Goles del local a predecir
            away_goals: Goles del visitante a predecir

        Returns:
            Probabilidad del marcador (0-1)

        Ejemplo:
            - λ_home=1.8, λ_away=1.2
            - P(2-1) = poisson(2; 1.8) × poisson(1; 1.2) ≈ 0.135 (13.5%)
        """
        # Asume independencia entre equipos
        prob_home = poisson.pmf(home_goals, lambda_home)
        prob_away = poisson.pmf(away_goals, lambda_away)

        return prob_home * prob_away

    def predict_match_outcome(self, lambda_home: float, lambda_away: float,
                             max_goals: int = 10) -> Dict[str, float]:
        """
        Predice probabilidades de resultado (H/D/A) y mercados de goles

        Args:
            lambda_home: Goles esperados del local
            lambda_away: Goles esperados del visitante
            max_goals: Máximo de goles a considerar en simulación (default: 10)

        Returns:
            Dictionary con probabilidades:
            - 'home_win', 'draw', 'away_win': Probabilidades de resultado
            - 'over_05', 'over_15', 'over_25', 'over_35': Probabilidades de Over X.5
            - 'btts': Probabilidad de ambos equipos anoten
            - 'expected_total_goals': Total de goles esperados
        """
        # Calcular matriz de probabilidades para todos los marcadores
        prob_matrix = np.zeros((max_goals + 1, max_goals + 1))

        for home_g in range(max_goals + 1):
            for away_g in range(max_goals + 1):
                prob_matrix[home_g, away_g] = self.predict_score_probability(
                    lambda_home, lambda_away, home_g, away_g
                )

        # Probabilidades de resultado
        home_win = np.sum(np.tril(prob_matrix, -1))  # Local gana (diagonal inferior)
        draw = np.sum(np.diag(prob_matrix))          # Empate (diagonal)
        away_win = np.sum(np.triu(prob_matrix, 1))   # Visitante gana (diagonal superior)

        # Probabilidades de Over/Under
        over_05 = 1 - prob_matrix[0, 0]  # Al menos 1 gol total

        under_15 = prob_matrix[0, 0] + prob_matrix[1, 0] + prob_matrix[0, 1]
        over_15 = 1 - under_15

        under_25 = np.sum(prob_matrix[0:2, 0:2])  # 0-0, 0-1, 1-0, 1-1
        over_25 = 1 - under_25

        under_35 = 0
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                if i + j <= 3:
                    under_35 += prob_matrix[i, j]
        over_35 = 1 - under_35

        # BTTS (Both Teams To Score)
        btts = 1 - prob_matrix[0, :].sum() - prob_matrix[:, 0].sum() + prob_matrix[0, 0]

        # Goles esperados totales
        expected_total = lambda_home + lambda_away

        return {
            'home_win': home_win,
            'draw': draw,
            'away_win': away_win,
            'over_05': over_05,
            'over_15': over_15,
            'over_25': over_25,
            'over_35': over_35,
            'btts': btts,
            'expected_total_goals': expected_total,
            'lambda_home': lambda_home,
            'lambda_away': lambda_away,
        }


class DixonColesModel(PoissonModel):
    """
    Modelo Dixon-Coles: Mejora del Poisson con correlación entre marcadores bajos

    El modelo Poisson asume independencia entre equipos, lo cual es incorrecto.
    Dixon-Coles ajusta las probabilidades de marcadores bajos (0-0, 1-0, 0-1, 1-1)
    usando un parámetro de correlación ρ (rho).

    Factor de ajuste τ(x,y):
    - τ(0,0) = 1 - λ_home × λ_away × ρ
    - τ(1,0) = 1 + λ_away × ρ
    - τ(0,1) = 1 + λ_home × ρ
    - τ(1,1) = 1 - ρ
    - τ(x,y) = 1 para otros marcadores

    P_DC(x,y) = τ(x,y) × P_Poisson(x,y)

    Investigación empírica sugiere ρ ≈ -0.1 a -0.2 (correlación negativa)
    """

    def __init__(self, home_advantage: float = 1.3, rho: float = -0.13):
        """
        Args:
            home_advantage: Factor de ventaja local (default: 1.3)
            rho: Parámetro de correlación (default: -0.13)
                 Valores típicos: -0.1 a -0.2
                 Negativo indica que marcadores bajos son menos probables que en Poisson
        """
        super().__init__(home_advantage)
        self.rho = rho

    def tau_correction(self, home_goals: int, away_goals: int,
                      lambda_home: float, lambda_away: float) -> float:
        """
        Calcula el factor de ajuste τ(x,y) de Dixon-Coles

        Este factor corrige las probabilidades de Poisson para marcadores bajos,
        donde el modelo Poisson tiende a sobreestimar.

        Args:
            home_goals: Goles del local
            away_goals: Goles del visitante
            lambda_home: Parámetro λ del local
            lambda_away: Parámetro λ del visitante

        Returns:
            Factor de ajuste τ (típicamente entre 0.8 y 1.2)

        Ejemplos:
            - (0,0): τ = 1 - 1.5 × 1.2 × (-0.13) ≈ 1.234 (aumenta probabilidad)
            - (1,0): τ = 1 + 1.2 × (-0.13) ≈ 0.844 (reduce probabilidad)
            - (2,1): τ = 1.0 (sin ajuste)
        """
        if home_goals == 0 and away_goals == 0:
            # Empate sin goles: aumenta probabilidad (rho negativo)
            return 1 - lambda_home * lambda_away * self.rho

        elif home_goals == 1 and away_goals == 0:
            # Local gana 1-0: reduce probabilidad
            return 1 + lambda_away * self.rho

        elif home_goals == 0 and away_goals == 1:
            # Visitante gana 0-1: reduce probabilidad
            return 1 + lambda_home * self.rho

        elif home_goals == 1 and away_goals == 1:
            # Empate 1-1: reduce probabilidad
            return 1 - self.rho

        else:
            # Otros marcadores: sin ajuste
            return 1.0

    def predict_score_probability(self, lambda_home: float, lambda_away: float,
                                  home_goals: int, away_goals: int) -> float:
        """
        Calcula probabilidad de marcador con ajuste Dixon-Coles

        P_DC(x,y) = τ(x,y) × P_Poisson(x,y)

        Args:
            lambda_home: Goles esperados del local
            lambda_away: Goles esperados del visitante
            home_goals: Goles del local a predecir
            away_goals: Goles del visitante a predecir

        Returns:
            Probabilidad ajustada del marcador
        """
        # Probabilidad Poisson base
        prob_poisson = super().predict_score_probability(
            lambda_home, lambda_away, home_goals, away_goals
        )

        # Factor de ajuste Dixon-Coles
        tau = self.tau_correction(home_goals, away_goals, lambda_home, lambda_away)

        # Probabilidad ajustada
        return tau * prob_poisson


def estimate_team_strengths(matches: List[Dict], use_dixon_coles: bool = True) -> Dict:
    """
    Estima las fuerzas de ataque y defensa de cada equipo desde datos históricos

    Usa Maximum Likelihood Estimation (MLE) para ajustar parámetros que mejor
    explican los goles observados.

    Modelo:
    - λ_home(i,j) = α_i × β_j × γ (attack_i × defense_j × home_advantage)
    - λ_away(i,j) = α_j × β_i (attack_j × defense_i)

    Restricción: Σ α_i = Σ β_i = número_de_equipos (normalización)

    Args:
        matches: Lista de diccionarios con:
                 - 'home_team_id', 'away_team_id'
                 - 'home_goals', 'away_goals'
        use_dixon_coles: Si True, estima también parámetro ρ

    Returns:
        Dictionary con:
        - 'teams': {team_id: {'attack': float, 'defense': float}}
        - 'home_advantage': float
        - 'rho': float (solo si use_dixon_coles=True)
        - 'league_avg_goals': float

    Nota: Esta es una implementación simplificada. Una versión completa
          requeriría optimización numérica más robusta.
    """
    # Por ahora, implementación simplificada usando promedios
    # TODO: Implementar MLE completo con scipy.optimize

    team_stats = {}

    # Calcular promedios de goles por equipo
    for match in matches:
        home_id = match['home_team_id']
        away_id = match['away_team_id']
        home_goals = match['home_goals']
        away_goals = match['away_goals']

        # Inicializar equipos si no existen
        if home_id not in team_stats:
            team_stats[home_id] = {
                'goals_scored': [], 'goals_conceded': [],
                'home_scored': [], 'home_conceded': [],
                'away_scored': [], 'away_conceded': []
            }
        if away_id not in team_stats:
            team_stats[away_id] = {
                'goals_scored': [], 'goals_conceded': [],
                'home_scored': [], 'home_conceded': [],
                'away_scored': [], 'away_conceded': []
            }

        # Registrar goles
        team_stats[home_id]['goals_scored'].append(home_goals)
        team_stats[home_id]['goals_conceded'].append(away_goals)
        team_stats[home_id]['home_scored'].append(home_goals)
        team_stats[home_id]['home_conceded'].append(away_goals)

        team_stats[away_id]['goals_scored'].append(away_goals)
        team_stats[away_id]['goals_conceded'].append(home_goals)
        team_stats[away_id]['away_scored'].append(away_goals)
        team_stats[away_id]['away_conceded'].append(home_goals)

    # Calcular league average
    all_goals = []
    for match in matches:
        all_goals.append(match['home_goals'])
        all_goals.append(match['away_goals'])
    league_avg = np.mean(all_goals) if all_goals else 1.35

    # Calcular fuerzas relativas
    team_params = {}

    for team_id, stats in team_stats.items():
        # Attack strength = (goles anotados / partidos) / league_avg
        avg_scored = np.mean(stats['goals_scored']) if stats['goals_scored'] else league_avg
        attack_strength = avg_scored / league_avg

        # Defense strength = (goles recibidos / partidos) / league_avg
        avg_conceded = np.mean(stats['goals_conceded']) if stats['goals_conceded'] else league_avg
        defense_strength = avg_conceded / league_avg

        team_params[team_id] = {
            'attack': max(attack_strength, 0.3),  # Mínimo 0.3
            'defense': max(defense_strength, 0.3),  # Mínimo 0.3
            'matches_played': len(stats['goals_scored'])
        }

    # Estimar home advantage
    home_advantage = 1.3  # Default basado en investigación

    # Estimar rho (simplificado)
    rho = -0.13 if use_dixon_coles else 0.0

    return {
        'teams': team_params,
        'home_advantage': home_advantage,
        'rho': rho,
        'league_avg_goals': league_avg
    }


def compare_models_accuracy(matches: List[Dict], team_strengths: Dict) -> Dict:
    """
    Compara accuracy de Poisson vs Dixon-Coles en datos históricos

    Args:
        matches: Lista de partidos con resultados reales
        team_strengths: Parámetros estimados de equipos

    Returns:
        Dictionary con métricas de accuracy para cada modelo
    """
    poisson_model = PoissonModel(home_advantage=team_strengths['home_advantage'])
    dc_model = DixonColesModel(
        home_advantage=team_strengths['home_advantage'],
        rho=team_strengths['rho']
    )

    poisson_correct = {'result': 0, 'over_25': 0, 'btts': 0}
    dc_correct = {'result': 0, 'over_25': 0, 'btts': 0}
    total = len(matches)

    for match in matches:
        home_id = match['home_team_id']
        away_id = match['away_team_id']

        if home_id not in team_strengths['teams'] or away_id not in team_strengths['teams']:
            continue

        home_params = team_strengths['teams'][home_id]
        away_params = team_strengths['teams'][away_id]

        # Calcular λs
        lambda_home, lambda_away = poisson_model.calculate_expected_goals(
            home_params['attack'], home_params['defense'],
            away_params['attack'], away_params['defense']
        )

        # Predicciones Poisson
        poisson_pred = poisson_model.predict_match_outcome(lambda_home, lambda_away)

        # Predicciones Dixon-Coles
        dc_pred = dc_model.predict_match_outcome(lambda_home, lambda_away)

        # Resultado real
        home_goals = match['home_goals']
        away_goals = match['away_goals']
        total_goals = home_goals + away_goals

        if home_goals > away_goals:
            actual_result = 'home_win'
        elif home_goals < away_goals:
            actual_result = 'away_win'
        else:
            actual_result = 'draw'

        # Comparar predicciones
        poisson_result = max(poisson_pred, key=lambda k: poisson_pred[k] if k in ['home_win', 'draw', 'away_win'] else 0)
        dc_result = max(dc_pred, key=lambda k: dc_pred[k] if k in ['home_win', 'draw', 'away_win'] else 0)

        if poisson_result == actual_result:
            poisson_correct['result'] += 1
        if dc_result == actual_result:
            dc_correct['result'] += 1

        # Over 2.5
        if (total_goals > 2.5 and poisson_pred['over_25'] > 0.5) or \
           (total_goals <= 2.5 and poisson_pred['over_25'] <= 0.5):
            poisson_correct['over_25'] += 1

        if (total_goals > 2.5 and dc_pred['over_25'] > 0.5) or \
           (total_goals <= 2.5 and dc_pred['over_25'] <= 0.5):
            dc_correct['over_25'] += 1

        # BTTS
        actual_btts = home_goals > 0 and away_goals > 0
        if (actual_btts and poisson_pred['btts'] > 0.5) or \
           (not actual_btts and poisson_pred['btts'] <= 0.5):
            poisson_correct['btts'] += 1

        if (actual_btts and dc_pred['btts'] > 0.5) or \
           (not actual_btts and dc_pred['btts'] <= 0.5):
            dc_correct['btts'] += 1

    return {
        'poisson': {
            'result_accuracy': poisson_correct['result'] / total,
            'over25_accuracy': poisson_correct['over_25'] / total,
            'btts_accuracy': poisson_correct['btts'] / total,
        },
        'dixon_coles': {
            'result_accuracy': dc_correct['result'] / total,
            'over25_accuracy': dc_correct['over_25'] / total,
            'btts_accuracy': dc_correct['btts'] / total,
        },
        'total_matches': total
    }
