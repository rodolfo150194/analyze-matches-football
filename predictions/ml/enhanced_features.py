"""
Features mejorados para mayor precisión en las predicciones (Django ORM)
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List
from django.db.models import Q

from predictions.models import Match
from predictions.ml.features import FeatureEngineer


class EnhancedFeatureEngineer(FeatureEngineer):
    """Feature engineer mejorado con features adicionales para mayor accuracy"""

    def get_ultra_recent_form(self, team_id: int, before_date: datetime, is_home: bool = None) -> Dict:
        """
        Forma ultra-reciente (últimos 3 partidos) con más peso que la forma general
        """
        if is_home is not None:
            filter_cond = Q(home_team_id=team_id) if is_home else Q(away_team_id=team_id)
        else:
            filter_cond = Q(home_team_id=team_id) | Q(away_team_id=team_id)

        matches = Match.objects.filter(
            filter_cond,
            status='FINISHED',
            utc_date__lt=before_date
        ).order_by('-utc_date')[:3]

        if not matches:
            return {'points': 0, 'gf': 0, 'ga': 0, 'win_rate': 0}

        points = []
        gf = []
        ga = []

        for match in matches:
            if match.home_team_id == team_id:
                goals_for = match.home_score or 0
                goals_against = match.away_score or 0
            else:
                goals_for = match.away_score or 0
                goals_against = match.home_score or 0

            gf.append(goals_for)
            ga.append(goals_against)

            if goals_for > goals_against:
                points.append(3)
            elif goals_for < goals_against:
                points.append(0)
            else:
                points.append(1)

        return {
            'points': np.mean(points),
            'gf': np.mean(gf),
            'ga': np.mean(ga),
            'win_rate': points.count(3) / len(points) if points else 0
        }

    def get_momentum(self, team_id: int, before_date: datetime) -> Dict:
        """
        Calcular momentum: ¿El equipo está mejorando o empeorando?
        Compara últimos 3 vs anteriores 3
        """
        matches = Match.objects.filter(
            Q(home_team_id=team_id) | Q(away_team_id=team_id),
            status='FINISHED',
            utc_date__lt=before_date
        ).order_by('-utc_date')[:6]

        if len(matches) < 6:
            return {'momentum_points': 0, 'momentum_goals': 0, 'improving': 0}

        # Últimos 3
        recent_points = []
        recent_gf = []
        for match in matches[:3]:
            if match.home_team_id == team_id:
                gf = match.home_score or 0
                ga = match.away_score or 0
            else:
                gf = match.away_score or 0
                ga = match.home_score or 0

            recent_gf.append(gf)
            recent_points.append(3 if gf > ga else (1 if gf == ga else 0))

        # Anteriores 3
        previous_points = []
        previous_gf = []
        for match in matches[3:6]:
            if match.home_team_id == team_id:
                gf = match.home_score or 0
                ga = match.away_score or 0
            else:
                gf = match.away_score or 0
                ga = match.home_score or 0

            previous_gf.append(gf)
            previous_points.append(3 if gf > ga else (1 if gf == ga else 0))

        momentum_points = np.mean(recent_points) - np.mean(previous_points)
        momentum_goals = np.mean(recent_gf) - np.mean(previous_gf)

        return {
            'momentum_points': momentum_points,
            'momentum_goals': momentum_goals,
            'improving': 1 if momentum_points > 0 else 0
        }

    def get_advanced_stats(self, team_id: int, before_date: datetime, n_matches: int = 5) -> Dict:
        """
        Estadísticas avanzadas de forma reciente incluyendo corners, tiros, eficiencia
        """
        matches = Match.objects.filter(
            Q(home_team_id=team_id) | Q(away_team_id=team_id),
            status='FINISHED',
            utc_date__lt=before_date,
            corners_home__isnull=False  # Filtrar solo con stats
        ).order_by('-utc_date')[:n_matches]

        if not matches:
            return {
                'avg_corners': 0,
                'avg_shots': 0,
                'avg_shots_on_target': 0,
                'conversion_rate': 0,
                'shot_accuracy': 0
            }

        corners = []
        shots = []
        shots_on_target = []
        goals = []

        for match in matches:
            if match.home_team_id == team_id:
                if match.corners_home:
                    corners.append(match.corners_home)
                if match.shots_home:
                    shots.append(match.shots_home)
                if match.shots_on_target_home:
                    shots_on_target.append(match.shots_on_target_home)
                goals.append(match.home_score or 0)
            else:
                if match.corners_away:
                    corners.append(match.corners_away)
                if match.shots_away:
                    shots.append(match.shots_away)
                if match.shots_on_target_away:
                    shots_on_target.append(match.shots_on_target_away)
                goals.append(match.away_score or 0)

        total_shots = sum(shots) if shots else 0
        total_sot = sum(shots_on_target) if shots_on_target else 0
        total_goals = sum(goals) if goals else 0

        return {
            'avg_corners': np.mean(corners) if corners else 0,
            'avg_shots': np.mean(shots) if shots else 0,
            'avg_shots_on_target': np.mean(shots_on_target) if shots_on_target else 0,
            'conversion_rate': (total_goals / total_shots * 100) if total_shots > 0 else 0,
            'shot_accuracy': (total_sot / total_shots * 100) if total_shots > 0 else 0
        }

    def get_defensive_stats(self, team_id: int, before_date: datetime, n_matches: int = 5) -> Dict:
        """
        Estadísticas defensivas: clean sheets, goles concedidos en diferentes escenarios
        """
        matches = Match.objects.filter(
            Q(home_team_id=team_id) | Q(away_team_id=team_id),
            status='FINISHED',
            utc_date__lt=before_date
        ).order_by('-utc_date')[:n_matches]

        if not matches:
            return {'clean_sheets': 0, 'avg_ga_first_half': 0}

        clean_sheets = 0
        ga_first_half = []

        for match in matches:
            if match.home_team_id == team_id:
                ga = match.away_score or 0
                ga_ht = match.away_score_ht or 0
            else:
                ga = match.home_score or 0
                ga_ht = match.home_score_ht or 0

            if ga == 0:
                clean_sheets += 1

            if ga_ht is not None:
                ga_first_half.append(ga_ht)

        return {
            'clean_sheets': clean_sheets / len(matches),
            'avg_ga_first_half': np.mean(ga_first_half) if ga_first_half else 0
        }

    def get_season_home_away_split(self, team_id: int, competition_id: int,
                                    season: int, before_date: datetime) -> Dict:
        """
        Estadísticas de temporada separadas por local/visitante
        Complementa get_season_stats con split detallado de rendimiento en casa vs fuera
        """
        # Partidos de local
        home_matches = Match.objects.filter(
            home_team_id=team_id,
            competition_id=competition_id,
            season=season,
            status='FINISHED',
            utc_date__lt=before_date
        )

        # Partidos de visitante
        away_matches = Match.objects.filter(
            away_team_id=team_id,
            competition_id=competition_id,
            season=season,
            status='FINISHED',
            utc_date__lt=before_date
        )

        home_count = home_matches.count()
        away_count = away_matches.count()

        # Inicializar contadores para local
        home_wins = home_draws = home_losses = 0
        home_gf = home_ga = 0
        home_clean_sheets = home_btts = home_over25 = 0

        for match in home_matches:
            gf = match.home_score or 0
            ga = match.away_score or 0
            home_gf += gf
            home_ga += ga

            if gf > ga:
                home_wins += 1
            elif gf < ga:
                home_losses += 1
            else:
                home_draws += 1

            if ga == 0:
                home_clean_sheets += 1
            if gf > 0 and ga > 0:
                home_btts += 1
            if gf + ga > 2.5:
                home_over25 += 1

        # Inicializar contadores para visitante
        away_wins = away_draws = away_losses = 0
        away_gf = away_ga = 0
        away_clean_sheets = away_btts = away_over25 = 0

        for match in away_matches:
            gf = match.away_score or 0
            ga = match.home_score or 0
            away_gf += gf
            away_ga += ga

            if gf > ga:
                away_wins += 1
            elif gf < ga:
                away_losses += 1
            else:
                away_draws += 1

            if ga == 0:
                away_clean_sheets += 1
            if gf > 0 and ga > 0:
                away_btts += 1
            if gf + ga > 2.5:
                away_over25 += 1

        return {
            # Stats de local (temporada completa)
            'home_matches': home_count,
            'home_ppg': (home_wins * 3 + home_draws) / home_count if home_count > 0 else 0,
            'home_win_rate': home_wins / home_count if home_count > 0 else 0,
            'home_avg_gf': home_gf / home_count if home_count > 0 else 0,
            'home_avg_ga': home_ga / home_count if home_count > 0 else 0,
            'home_clean_sheet_rate': home_clean_sheets / home_count if home_count > 0 else 0,
            'home_btts_rate': home_btts / home_count if home_count > 0 else 0,
            'home_over25_rate': home_over25 / home_count if home_count > 0 else 0,

            # Stats de visitante (temporada completa)
            'away_matches': away_count,
            'away_ppg': (away_wins * 3 + away_draws) / away_count if away_count > 0 else 0,
            'away_win_rate': away_wins / away_count if away_count > 0 else 0,
            'away_avg_gf': away_gf / away_count if away_count > 0 else 0,
            'away_avg_ga': away_ga / away_count if away_count > 0 else 0,
            'away_clean_sheet_rate': away_clean_sheets / away_count if away_count > 0 else 0,
            'away_btts_rate': away_btts / away_count if away_count > 0 else 0,
            'away_over25_rate': away_over25 / away_count if away_count > 0 else 0,
        }

    def get_h2h_advanced(self, team1_id: int, team2_id: int, before_date: datetime) -> Dict:
        """
        Head-to-Head avanzado con métricas de mercados de apuestas
        Complementa get_head_to_head con BTTS%, Over 2.5%, etc.
        """
        matches = Match.objects.filter(
            Q(home_team_id=team1_id, away_team_id=team2_id) |
            Q(home_team_id=team2_id, away_team_id=team1_id),
            status='FINISHED',
            utc_date__lt=before_date
        ).order_by('-utc_date')[:10]

        if not matches:
            return {
                'h2h_btts_rate': 0,
                'h2h_over25_rate': 0,
                'h2h_high_scoring': 0,  # Over 3.5
            }

        btts_count = 0
        over25_count = 0
        over35_count = 0

        for match in matches:
            # Determinar goles de cada equipo
            if match.home_team_id == team1_id:
                t1_goals = match.home_score or 0
                t2_goals = match.away_score or 0
            else:
                t1_goals = match.away_score or 0
                t2_goals = match.home_score or 0

            total = t1_goals + t2_goals

            if t1_goals > 0 and t2_goals > 0:
                btts_count += 1
            if total > 2.5:
                over25_count += 1
            if total > 3.5:
                over35_count += 1

        n = len(matches)
        return {
            'h2h_btts_rate': btts_count / n if n > 0 else 0,
            'h2h_over25_rate': over25_count / n if n > 0 else 0,
            'h2h_high_scoring': over35_count / n if n > 0 else 0,
        }

    def get_elo_features(self, home_id: int, away_id: int, competition_id: int,
                         season: int, before_date: datetime) -> Dict:
        """
        Obtener features basados en ratings Elo (sistema dual: persistente + temporada)

        Args:
            home_id: ID del equipo local
            away_id: ID del equipo visitante
            competition_id: ID de la competición
            season: Temporada actual
            before_date: Fecha límite (prevenir data leakage)

        Returns:
            Dictionary con 12 features Elo:
                - 6 features del Elo persistente (global)
                - 6 features del Elo de temporada
        """
        from predictions.models import EloRating
        from predictions.ml.elo import calculate_expected_score, DEFAULT_HOME_ADVANTAGE

        # Valores por defecto si no existe rating
        default_rating = 1500.0
        default_momentum = 0.0

        # ========== ELO PERSISTENTE (Global por competición) ==========
        try:
            home_elo_persistent = EloRating.objects.get(
                team_id=home_id,
                competition_id=competition_id,
                season__isnull=True  # NULL = persistente
            )

            # Verificar que no incluye datos futuros
            if home_elo_persistent.last_match_date and home_elo_persistent.last_match_date >= before_date:
                # Warning: usar rating por defecto si incluye datos futuros
                home_rating_persistent = default_rating
                home_momentum_persistent = default_momentum
            else:
                home_rating_persistent = home_elo_persistent.rating
                home_momentum_persistent = home_elo_persistent.elo_momentum

        except EloRating.DoesNotExist:
            home_rating_persistent = default_rating
            home_momentum_persistent = default_momentum

        try:
            away_elo_persistent = EloRating.objects.get(
                team_id=away_id,
                competition_id=competition_id,
                season__isnull=True
            )

            if away_elo_persistent.last_match_date and away_elo_persistent.last_match_date >= before_date:
                away_rating_persistent = default_rating
                away_momentum_persistent = default_momentum
            else:
                away_rating_persistent = away_elo_persistent.rating
                away_momentum_persistent = away_elo_persistent.elo_momentum

        except EloRating.DoesNotExist:
            away_rating_persistent = default_rating
            away_momentum_persistent = default_momentum

        # Calcular expected score persistente
        expected_home_persistent = calculate_expected_score(
            home_rating_persistent,
            away_rating_persistent,
            DEFAULT_HOME_ADVANTAGE
        )

        # ========== ELO DE TEMPORADA ==========
        try:
            home_elo_season = EloRating.objects.get(
                team_id=home_id,
                competition_id=competition_id,
                season=season
            )

            if home_elo_season.last_match_date and home_elo_season.last_match_date >= before_date:
                home_rating_season = default_rating
                home_momentum_season = default_momentum
            else:
                home_rating_season = home_elo_season.rating
                home_momentum_season = home_elo_season.elo_momentum

        except EloRating.DoesNotExist:
            home_rating_season = default_rating
            home_momentum_season = default_momentum

        try:
            away_elo_season = EloRating.objects.get(
                team_id=away_id,
                competition_id=competition_id,
                season=season
            )

            if away_elo_season.last_match_date and away_elo_season.last_match_date >= before_date:
                away_rating_season = default_rating
                away_momentum_season = default_momentum
            else:
                away_rating_season = away_elo_season.rating
                away_momentum_season = away_elo_season.elo_momentum

        except EloRating.DoesNotExist:
            away_rating_season = default_rating
            away_momentum_season = default_momentum

        # Calcular expected score de temporada
        expected_home_season = calculate_expected_score(
            home_rating_season,
            away_rating_season,
            DEFAULT_HOME_ADVANTAGE
        )

        # Retornar 12 features
        return {
            # ELO PERSISTENTE (6 features)
            'home_elo_persistent': home_rating_persistent,
            'away_elo_persistent': away_rating_persistent,
            'elo_diff_persistent': home_rating_persistent - away_rating_persistent,
            'elo_expected_home_persistent': expected_home_persistent,
            'elo_momentum_home_persistent': home_momentum_persistent,
            'elo_momentum_away_persistent': away_momentum_persistent,

            # ELO DE TEMPORADA (6 features)
            'home_elo_season': home_rating_season,
            'away_elo_season': away_rating_season,
            'elo_diff_season': home_rating_season - away_rating_season,
            'elo_expected_home_season': expected_home_season,
            'elo_momentum_home_season': home_momentum_season,
            'elo_momentum_away_season': away_momentum_season,
        }

    def calculate_enhanced_features(self, match: Match) -> Dict:
        """
        Calcular features mejorados para un partido
        Incluye todos los features originales + los nuevos
        """
        # Obtener features base
        features = self.calculate_match_features(match)

        home_id = match.home_team_id
        away_id = match.away_team_id
        match_date = match.utc_date

        # FEATURES ULTRA-RECIENTES (últimos 3 partidos)
        home_ultra_recent = self.get_ultra_recent_form(home_id, match_date)
        away_ultra_recent = self.get_ultra_recent_form(away_id, match_date)

        features['home_ultra_recent_points'] = home_ultra_recent['points']
        features['home_ultra_recent_gf'] = home_ultra_recent['gf']
        features['home_ultra_recent_ga'] = home_ultra_recent['ga']
        features['away_ultra_recent_points'] = away_ultra_recent['points']
        features['away_ultra_recent_gf'] = away_ultra_recent['gf']
        features['away_ultra_recent_ga'] = away_ultra_recent['ga']

        # MOMENTUM
        home_momentum = self.get_momentum(home_id, match_date)
        away_momentum = self.get_momentum(away_id, match_date)

        features['home_momentum_points'] = home_momentum['momentum_points']
        features['home_momentum_goals'] = home_momentum['momentum_goals']
        features['home_improving'] = home_momentum['improving']
        features['away_momentum_points'] = away_momentum['momentum_points']
        features['away_momentum_goals'] = away_momentum['momentum_goals']
        features['away_improving'] = away_momentum['improving']

        # ESTADÍSTICAS AVANZADAS
        home_advanced = self.get_advanced_stats(home_id, match_date)
        away_advanced = self.get_advanced_stats(away_id, match_date)

        features['home_avg_corners'] = home_advanced['avg_corners']
        features['home_avg_shots'] = home_advanced['avg_shots']
        features['home_conversion_rate'] = home_advanced['conversion_rate']
        features['home_shot_accuracy'] = home_advanced['shot_accuracy']
        features['away_avg_corners'] = away_advanced['avg_corners']
        features['away_avg_shots'] = away_advanced['avg_shots']
        features['away_conversion_rate'] = away_advanced['conversion_rate']
        features['away_shot_accuracy'] = away_advanced['shot_accuracy']

        # ESTADÍSTICAS DEFENSIVAS
        home_defense = self.get_defensive_stats(home_id, match_date)
        away_defense = self.get_defensive_stats(away_id, match_date)

        features['home_clean_sheets_rate'] = home_defense['clean_sheets']
        features['away_clean_sheets_rate'] = away_defense['clean_sheets']

        # FEATURES DERIVADOS MEJORADOS
        features['momentum_diff'] = home_momentum['momentum_points'] - away_momentum['momentum_points']
        features['ultra_recent_form_diff'] = home_ultra_recent['points'] - away_ultra_recent['points']
        features['shot_efficiency_diff'] = home_advanced['conversion_rate'] - away_advanced['conversion_rate']

        # ESTADÍSTICAS DE TEMPORADA SEPARADAS POR LOCAL/VISITANTE
        home_season_split = self.get_season_home_away_split(
            home_id, match.competition_id, match.season, match_date
        )
        away_season_split = self.get_season_home_away_split(
            away_id, match.competition_id, match.season, match_date
        )

        # El equipo local jugando en casa en esta temporada
        features['home_season_home_ppg'] = home_season_split['home_ppg']
        features['home_season_home_win_rate'] = home_season_split['home_win_rate']
        features['home_season_home_avg_gf'] = home_season_split['home_avg_gf']
        features['home_season_home_avg_ga'] = home_season_split['home_avg_ga']
        features['home_season_home_clean_sheet_rate'] = home_season_split['home_clean_sheet_rate']
        features['home_season_home_btts_rate'] = home_season_split['home_btts_rate']
        features['home_season_home_over25_rate'] = home_season_split['home_over25_rate']

        # El equipo visitante jugando fuera en esta temporada
        features['away_season_away_ppg'] = away_season_split['away_ppg']
        features['away_season_away_win_rate'] = away_season_split['away_win_rate']
        features['away_season_away_avg_gf'] = away_season_split['away_avg_gf']
        features['away_season_away_avg_ga'] = away_season_split['away_avg_ga']
        features['away_season_away_clean_sheet_rate'] = away_season_split['away_clean_sheet_rate']
        features['away_season_away_btts_rate'] = away_season_split['away_btts_rate']
        features['away_season_away_over25_rate'] = away_season_split['away_over25_rate']

        # HEAD-TO-HEAD AVANZADO
        h2h_advanced = self.get_h2h_advanced(home_id, away_id, match_date)
        features['h2h_btts_rate'] = h2h_advanced['h2h_btts_rate']
        features['h2h_over25_rate'] = h2h_advanced['h2h_over25_rate']
        features['h2h_high_scoring_rate'] = h2h_advanced['h2h_high_scoring']

        # FEATURES DERIVADOS ADICIONALES
        # Comparar rendimiento en casa del local vs fuera del visitante
        features['venue_ppg_diff'] = home_season_split['home_ppg'] - away_season_split['away_ppg']
        features['venue_gf_diff'] = home_season_split['home_avg_gf'] - away_season_split['away_avg_gf']
        features['venue_ga_diff'] = home_season_split['home_avg_ga'] - away_season_split['away_avg_ga']

        # Indicador de si ambos equipos tienen alta tendencia a BTTS
        features['both_high_btts'] = 1 if (home_season_split['home_btts_rate'] > 0.5 and
                                            away_season_split['away_btts_rate'] > 0.5) else 0

        # Indicador de si ambos equipos tienen alta tendencia a Over 2.5
        features['both_high_over25'] = 1 if (home_season_split['home_over25_rate'] > 0.5 and
                                              away_season_split['away_over25_rate'] > 0.5) else 0

        # INTERACCIONES ENTRE FEATURES (capturan patrones no lineales)
        # Usar features existentes ya calculadas

        # Interacción forma x fuerza de ataque
        features['home_form_x_attack'] = features['home_form_points'] * features['home_form_gf']
        features['away_form_x_attack'] = features['away_form_points'] * features['away_form_gf']

        # Interacción PPG x goles (equipos fuertes que anotan mucho)
        features['home_strength_index'] = features['home_season_ppg'] * features['home_season_gf']
        features['away_strength_index'] = features['away_season_ppg'] * features['away_season_gf']

        # Interacción BTTS tendencies (probabilidad combinada)
        features['combined_btts_probability'] = features['home_season_btts_rate'] * features['away_season_btts_rate']

        # Interacción Over 2.5 tendencies
        features['combined_over25_probability'] = features['home_season_over25_rate'] * features['away_season_over25_rate']

        # Interacción forma reciente x venue (local en racha en casa)
        features['home_form_venue_boost'] = home_ultra_recent['points'] * home_season_split['home_win_rate']
        features['away_form_venue_penalty'] = away_ultra_recent['points'] * (1 - away_season_split['away_win_rate'])

        # Ratio de calidad (PPG home/away para detectar mismatches)
        home_ppg = max(features['home_season_ppg'], 0.01)
        away_ppg = max(features['away_season_ppg'], 0.01)
        features['quality_ratio'] = home_ppg / away_ppg

        # Promedio de goles esperados (combinación de ataque y defensa)
        expected_home_goals = (features['home_form_gf'] + features['away_form_ga']) / 2
        expected_away_goals = (features['away_form_gf'] + features['home_form_ga']) / 2
        features['expected_total_goals'] = expected_home_goals + expected_away_goals
        features['expected_goal_diff'] = expected_home_goals - expected_away_goals

        return features

    def generate_enhanced_training_data(self, competition_code: str, seasons: List[int]) -> List[Dict]:
        """
        Generar dataset de entrenamiento con features mejorados
        """
        from predictions.models import Competition

        comp = Competition.objects.filter(code=competition_code).first()
        if not comp:
            raise ValueError(f"Competición {competition_code} no encontrada")

        all_features = []

        for season in seasons:
            print(f"Procesando temporada {season} con features mejorados...")

            matches = Match.objects.filter(
                competition_id=comp.id,
                season=season,
                status='FINISHED'
            ).order_by('utc_date')

            # Saltar primeros 15 partidos para tener suficiente historia
            for match in matches[15:]:
                try:
                    features = self.calculate_enhanced_features(match)
                    all_features.append(features)
                except Exception as e:
                    # print(f"  Error en partido {match.id}: {e}")
                    continue

        print(f"Total: {len(all_features)} partidos procesados con features mejorados")
        return all_features
