"""
Ensemble de modelos ML + Poisson/Dixon-Coles
Combina predicciones de Machine Learning con modelos estadísticos para mejor accuracy
"""

import numpy as np
from typing import Dict, Tuple, Optional
from predictions.models import Match, PoissonParams
from predictions.ml.predictor import EnhancedPredictor
from predictions.ml.poisson import DixonColesModel, PoissonModel


class EnsemblePredictor:
    """
    Combina predicciones de ML y Poisson/Dixon-Coles usando votación ponderada

    Ventajas del ensemble:
    - ML captura patrones complejos de forma y momentum
    - Poisson/Dixon-Coles modela distribución de goles naturalmente
    - Combinación reduce varianza y mejora robustez

    Pesos típicos:
    - Para resultado (H/D/A): 70% ML, 30% Poisson
    - Para Over/Under y BTTS: 50% ML, 50% Poisson (Poisson es más fuerte aquí)
    """

    def __init__(self, ml_weight: float = 0.7, use_dixon_coles: bool = True):
        """
        Args:
            ml_weight: Peso para predicciones ML (0-1). Poisson = 1 - ml_weight
            use_dixon_coles: Si True usa Dixon-Coles, si False usa Poisson básico
        """
        self.ml_weight = ml_weight
        self.poisson_weight = 1.0 - ml_weight
        self.use_dixon_coles = use_dixon_coles

        # Cargar predictor ML con modelos entrenados
        import os
        self.ml_predictor = EnhancedPredictor()
        models_path = os.path.join('predictions', 'ml', 'enhanced_models.pkl')
        if os.path.exists(models_path):
            self.ml_predictor.load_models(models_path)
        else:
            raise FileNotFoundError(
                f"Modelos ML no encontrados en {models_path}. "
                "Ejecuta: python manage.py train_models"
            )

        # Pesos específicos por mercado (pueden ajustarse mediante calibración)
        self.market_weights = {
            'result': {'ml': 0.70, 'poisson': 0.30},    # ML mejor en resultado
            'over_25': {'ml': 0.50, 'poisson': 0.50},   # Equilibrado
            'btts': {'ml': 0.50, 'poisson': 0.50},      # Equilibrado
            'over_35': {'ml': 0.45, 'poisson': 0.55},   # Poisson mejor en goles
        }

    def predict_match(self, match: Match) -> Dict:
        """
        Genera predicción combinada ML + Poisson para un partido

        Args:
            match: Objeto Match de Django

        Returns:
            Dictionary con probabilidades combinadas:
            - 'prob_home', 'prob_draw', 'prob_away': Resultado del partido
            - 'prob_over_25', 'prob_btts': Mercados de goles
            - 'lambda_home', 'lambda_away': Goles esperados (Poisson)
            - 'ml_probs', 'poisson_probs': Predicciones individuales
            - 'confidence': Nivel de confianza (0-100)
        """
        # 1. Predicción ML (requiere parámetros separados)
        ml_prediction = self.ml_predictor.predict_match(
            home_team_id=match.home_team_id,
            away_team_id=match.away_team_id,
            match_date=match.utc_date,
            competition_id=match.competition_id,
            season=match.season
        )

        # Adaptar formato ML (viene con estructura anidada)
        ml_flat = {
            'prob_home': ml_prediction['result']['home_win'],
            'prob_draw': ml_prediction['result']['draw'],
            'prob_away': ml_prediction['result']['away_win'],
            'prob_over_25': ml_prediction['over_25']['yes'],
            'prob_btts': ml_prediction['btts']['yes'],
        }

        # 2. Predicción Poisson/Dixon-Coles
        poisson_prediction = self._predict_poisson(match)

        if poisson_prediction is None:
            # Si no hay parámetros Poisson, usar solo ML
            return {
                **ml_flat,
                'method': 'ml_only',
                'confidence': 60,
                'ml_probs': ml_flat,
                'poisson_probs': None,
            }

        # 3. Combinar predicciones con pesos específicos por mercado
        combined = self._combine_predictions(ml_flat, poisson_prediction)

        # 4. Calcular confianza basada en acuerdo entre modelos
        confidence = self._calculate_confidence(ml_flat, poisson_prediction)

        combined['method'] = 'ensemble'
        combined['confidence'] = confidence
        combined['ml_probs'] = ml_flat
        combined['poisson_probs'] = poisson_prediction
        combined['lambda_home'] = poisson_prediction.get('lambda_home')
        combined['lambda_away'] = poisson_prediction.get('lambda_away')

        return combined

    def _predict_poisson(self, match: Match) -> Optional[Dict]:
        """
        Genera predicción usando Poisson/Dixon-Coles

        Args:
            match: Match object

        Returns:
            Dictionary con probabilidades o None si no hay parámetros
        """
        try:
            # Obtener parámetros de ataque/defensa de ambos equipos
            home_params = PoissonParams.objects.get(
                team=match.home_team,
                competition=match.competition,
                season=match.season
            )
            away_params = PoissonParams.objects.get(
                team=match.away_team,
                competition=match.competition,
                season=match.season
            )
        except PoissonParams.DoesNotExist:
            # No hay parámetros calculados para estos equipos
            return None

        # Determinar home_advantage promedio de la liga
        # TODO: Esto podría venir de estimate_team_strengths guardado en BD
        home_advantage = 1.3

        # Crear modelo
        if self.use_dixon_coles:
            model = DixonColesModel(home_advantage=home_advantage, rho=-0.13)
        else:
            model = PoissonModel(home_advantage=home_advantage)

        # Calcular λ (goles esperados)
        lambda_home, lambda_away = model.calculate_expected_goals(
            home_attack=home_params.attack_strength,
            home_defense=home_params.defense_strength,
            away_attack=away_params.attack_strength,
            away_defense=away_params.defense_strength
        )

        # Generar predicciones de mercados
        predictions = model.predict_match_outcome(lambda_home, lambda_away, max_goals=10)

        return {
            'prob_home': predictions['home_win'],
            'prob_draw': predictions['draw'],
            'prob_away': predictions['away_win'],
            'prob_over_25': predictions['over_25'],
            'prob_btts': predictions['btts'],
            'lambda_home': lambda_home,
            'lambda_away': lambda_away,
            'expected_total_goals': predictions['expected_total_goals'],
        }

    def _combine_predictions(self, ml_pred: Dict, poisson_pred: Dict) -> Dict:
        """
        Combina predicciones ML y Poisson con pesos específicos por mercado

        Args:
            ml_pred: Predicción de ML
            poisson_pred: Predicción de Poisson

        Returns:
            Predicciones combinadas
        """
        # Pesos para resultado (H/D/A)
        w_ml = self.market_weights['result']['ml']
        w_poisson = self.market_weights['result']['poisson']

        prob_home = (w_ml * ml_pred['prob_home']) + (w_poisson * poisson_pred['prob_home'])
        prob_draw = (w_ml * ml_pred['prob_draw']) + (w_poisson * poisson_pred['prob_draw'])
        prob_away = (w_ml * ml_pred['prob_away']) + (w_poisson * poisson_pred['prob_away'])

        # Normalizar para que sumen 1.0
        total = prob_home + prob_draw + prob_away
        prob_home /= total
        prob_draw /= total
        prob_away /= total

        # Pesos para Over 2.5
        w_ml_over = self.market_weights['over_25']['ml']
        w_poisson_over = self.market_weights['over_25']['poisson']

        prob_over_25 = (w_ml_over * ml_pred.get('prob_over_25', 0.5)) + \
                       (w_poisson_over * poisson_pred['prob_over_25'])

        # Pesos para BTTS
        w_ml_btts = self.market_weights['btts']['ml']
        w_poisson_btts = self.market_weights['btts']['poisson']

        prob_btts = (w_ml_btts * ml_pred.get('prob_btts', 0.5)) + \
                    (w_poisson_btts * poisson_pred['prob_btts'])

        return {
            'prob_home': prob_home,
            'prob_draw': prob_draw,
            'prob_away': prob_away,
            'prob_over_25': prob_over_25,
            'prob_btts': prob_btts,
            'expected_total_goals': poisson_pred['expected_total_goals'],
        }

    def _calculate_confidence(self, ml_pred: Dict, poisson_pred: Dict) -> int:
        """
        Calcula nivel de confianza (0-100) basado en acuerdo entre modelos

        Confianza alta cuando:
        - Ambos modelos predicen el mismo resultado
        - Las probabilidades son similares
        - La predicción es clara (no 33-33-33)

        Args:
            ml_pred: Predicción ML
            poisson_pred: Predicción Poisson

        Returns:
            Confianza de 0 a 100
        """
        # Determinar resultado predicho por cada modelo
        ml_result = max(
            ('home', ml_pred['prob_home']),
            ('draw', ml_pred['prob_draw']),
            ('away', ml_pred['prob_away']),
            key=lambda x: x[1]
        )[0]

        poisson_result = max(
            ('home', poisson_pred['prob_home']),
            ('draw', poisson_pred['prob_draw']),
            ('away', poisson_pred['prob_away']),
            key=lambda x: x[1]
        )[0]

        # Base: 50 puntos si ambos concuerdan, 30 si difieren
        confidence = 50 if ml_result == poisson_result else 30

        # Bonus por diferencia de probabilidades (predicción clara)
        # Si la prob máxima es > 0.5, suma hasta +30 puntos
        max_ml_prob = max(ml_pred['prob_home'], ml_pred['prob_draw'], ml_pred['prob_away'])
        max_poisson_prob = max(
            poisson_pred['prob_home'],
            poisson_pred['prob_draw'],
            poisson_pred['prob_away']
        )

        avg_max_prob = (max_ml_prob + max_poisson_prob) / 2

        if avg_max_prob > 0.5:
            confidence += int((avg_max_prob - 0.5) * 60)  # 0-30 puntos extra

        # Bonus por similitud de probabilidades (diferencia < 0.1 = coherencia)
        prob_diff_home = abs(ml_pred['prob_home'] - poisson_pred['prob_home'])
        prob_diff_draw = abs(ml_pred['prob_draw'] - poisson_pred['prob_draw'])
        prob_diff_away = abs(ml_pred['prob_away'] - poisson_pred['prob_away'])

        avg_diff = (prob_diff_home + prob_diff_draw + prob_diff_away) / 3

        if avg_diff < 0.1:
            confidence += 20  # Muy coherentes
        elif avg_diff < 0.2:
            confidence += 10  # Moderadamente coherentes

        return min(confidence, 100)

    def calibrate_weights(self, validation_matches: list) -> Dict:
        """
        Calibra pesos óptimos de ensemble usando conjunto de validación

        Prueba diferentes combinaciones de pesos y selecciona la que maximiza
        accuracy en el conjunto de validación.

        Args:
            validation_matches: Lista de Match objects con resultados conocidos

        Returns:
            Dictionary con mejores pesos y accuracy obtenida
        """
        # TODO: Implementar grid search de pesos óptimos
        # Por ahora retorna pesos por defecto

        best_weights = {
            'result': {'ml': 0.70, 'poisson': 0.30},
            'over_25': {'ml': 0.50, 'poisson': 0.50},
            'btts': {'ml': 0.50, 'poisson': 0.50},
        }

        return {
            'weights': best_weights,
            'accuracy_result': 0.0,
            'accuracy_over_25': 0.0,
            'accuracy_btts': 0.0,
            'note': 'Calibración no implementada - usando pesos por defecto'
        }


class ValueBetDetector:
    """
    Detecta apuestas de valor comparando probabilidades del ensemble vs odds de bookmakers

    Value Bet = Probabilidad del modelo > Probabilidad implícita en las odds
    """

    def __init__(self, ensemble: EnsemblePredictor, min_edge: float = 0.05):
        """
        Args:
            ensemble: EnsemblePredictor configurado
            min_edge: Edge mínimo para considerar value bet (default: 5%)
        """
        self.ensemble = ensemble
        self.min_edge = min_edge

    def find_value_bets(self, match: Match) -> list:
        """
        Encuentra apuestas de valor para un partido

        Args:
            match: Match object con odds disponibles

        Returns:
            Lista de value bets detectadas:
            [
                {
                    'market': 'home_win',
                    'model_prob': 0.55,
                    'implied_prob': 0.45,
                    'edge': 0.10,
                    'odds': 2.22,
                    'recommended_stake': 2.5  # % del bankroll
                }
            ]
        """
        value_bets = []

        # Generar predicción ensemble
        prediction = self.ensemble.predict_match(match)

        # Verificar odds disponibles
        if not match.odds_b365_home:
            return []  # Sin odds disponibles

        # Convertir odds a probabilidades implícitas
        implied_home = 1 / match.odds_b365_home if match.odds_b365_home else 0
        implied_draw = 1 / match.odds_b365_draw if match.odds_b365_draw else 0
        implied_away = 1 / match.odds_b365_away if match.odds_b365_away else 0

        # Normalizar (odds incluyen margen de bookmaker)
        total_implied = implied_home + implied_draw + implied_away
        if total_implied > 0:
            implied_home /= total_implied
            implied_draw /= total_implied
            implied_away /= total_implied

        # Comparar home win
        edge_home = prediction['prob_home'] - implied_home
        if edge_home > self.min_edge:
            value_bets.append({
                'market': 'home_win',
                'model_prob': prediction['prob_home'],
                'implied_prob': implied_home,
                'edge': edge_home,
                'odds': match.odds_b365_home,
                'confidence': prediction.get('confidence', 70),
                'recommended_stake': self._kelly_stake(
                    prediction['prob_home'],
                    match.odds_b365_home,
                    fraction=0.25
                )
            })

        # Comparar draw
        edge_draw = prediction['prob_draw'] - implied_draw
        if edge_draw > self.min_edge:
            value_bets.append({
                'market': 'draw',
                'model_prob': prediction['prob_draw'],
                'implied_prob': implied_draw,
                'edge': edge_draw,
                'odds': match.odds_b365_draw,
                'confidence': prediction.get('confidence', 70),
                'recommended_stake': self._kelly_stake(
                    prediction['prob_draw'],
                    match.odds_b365_draw,
                    fraction=0.25
                )
            })

        # Comparar away win
        edge_away = prediction['prob_away'] - implied_away
        if edge_away > self.min_edge:
            value_bets.append({
                'market': 'away_win',
                'model_prob': prediction['prob_away'],
                'implied_prob': implied_away,
                'edge': edge_away,
                'odds': match.odds_b365_away,
                'confidence': prediction.get('confidence', 70),
                'recommended_stake': self._kelly_stake(
                    prediction['prob_away'],
                    match.odds_b365_away,
                    fraction=0.25
                )
            })

        # TODO: Agregar value bets para Over/Under y BTTS

        return value_bets

    def _kelly_stake(self, probability: float, odds: float, fraction: float = 0.25) -> float:
        """
        Calcula stake óptimo usando Kelly Criterion

        Formula: f* = (bp - q) / b
        Donde:
        - b = odds - 1 (net odds)
        - p = probabilidad de ganar
        - q = 1 - p (probabilidad de perder)

        Args:
            probability: Probabilidad de ganar (0-1)
            odds: Odds decimales del bookmaker
            fraction: Fracción de Kelly (default: 0.25 = Kelly conservador)

        Returns:
            Porcentaje del bankroll a apostar (0-100)
        """
        b = odds - 1  # Net odds
        p = probability
        q = 1 - p

        # Kelly formula
        kelly = (b * p - q) / b

        # Aplicar fracción conservadora
        kelly = kelly * fraction

        # Límites (0-10% del bankroll como máximo)
        kelly = max(0, min(kelly, 0.10))

        return round(kelly * 100, 2)  # Retorna como porcentaje
