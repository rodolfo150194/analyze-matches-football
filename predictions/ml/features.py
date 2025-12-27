"""
Feature Engineering para predicción de resultados de fútbol (Django ORM)
Calcula métricas y características para el modelo de predicción.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.db.models import Q
import numpy as np

from predictions.models import Competition, Team, Match, TeamStats, HeadToHead


class FeatureEngineer:
    """Calcular características para predicción de partidos"""

    def __init__(self):
        pass  # No necesitamos inicializar session con Django ORM

    def get_team_form(self, team_id: int, before_date: datetime,
                      n_matches: int = 5) -> Dict:
        """
        Calcular forma reciente de un equipo

        Args:
            team_id: ID del equipo
            before_date: Fecha límite (partidos antes de esta fecha)
            n_matches: Cantidad de partidos a considerar

        Returns:
            Diccionario con métricas de forma
        """
        # Obtener últimos n partidos
        matches = Match.objects.filter(
            Q(home_team_id=team_id) | Q(away_team_id=team_id),
            status='FINISHED',
            utc_date__lt=before_date
        ).order_by('-utc_date')[:n_matches]

        if not matches:
            return self._empty_form()

        points = []
        goals_for = []
        goals_against = []
        results = []  # W, D, L

        for match in matches:
            is_home = match.home_team_id == team_id

            if is_home:
                gf = match.home_score or 0
                ga = match.away_score or 0
            else:
                gf = match.away_score or 0
                ga = match.home_score or 0

            goals_for.append(gf)
            goals_against.append(ga)

            if gf > ga:
                points.append(3)
                results.append('W')
            elif gf < ga:
                points.append(0)
                results.append('L')
            else:
                points.append(1)
                results.append('D')

        return {
            'matches_played': len(matches),
            'points': sum(points),
            'avg_points': np.mean(points) if points else 0,
            'goals_for': sum(goals_for),
            'goals_against': sum(goals_against),
            'avg_goals_for': np.mean(goals_for) if goals_for else 0,
            'avg_goals_against': np.mean(goals_against) if goals_against else 0,
            'goal_diff': sum(goals_for) - sum(goals_against),
            'form_string': ''.join(results),  # "WWDLW"
            'wins': results.count('W'),
            'draws': results.count('D'),
            'losses': results.count('L'),
            'win_rate': results.count('W') / len(results) if results else 0,
            'unbeaten_rate': (results.count('W') + results.count('D')) / len(results) if results else 0
        }

    def get_home_away_form(self, team_id: int, before_date: datetime,
                           is_home: bool, n_matches: int = 5) -> Dict:
        """
        Calcular forma como local o visitante específicamente

        Args:
            team_id: ID del equipo
            before_date: Fecha límite
            is_home: True para partidos de local, False para visitante
            n_matches: Cantidad de partidos
        """
        if is_home:
            filter_cond = Q(home_team_id=team_id)
        else:
            filter_cond = Q(away_team_id=team_id)

        matches = Match.objects.filter(
            filter_cond,
            status='FINISHED',
            utc_date__lt=before_date
        ).order_by('-utc_date')[:n_matches]

        if not matches:
            return self._empty_form()

        points = []
        goals_for = []
        goals_against = []

        for match in matches:
            if is_home:
                gf = match.home_score or 0
                ga = match.away_score or 0
            else:
                gf = match.away_score or 0
                ga = match.home_score or 0

            goals_for.append(gf)
            goals_against.append(ga)

            if gf > ga:
                points.append(3)
            elif gf < ga:
                points.append(0)
            else:
                points.append(1)

        return {
            'matches_played': len(matches),
            'avg_points': np.mean(points) if points else 0,
            'avg_goals_for': np.mean(goals_for) if goals_for else 0,
            'avg_goals_against': np.mean(goals_against) if goals_against else 0,
            'win_rate': points.count(3) / len(points) if points else 0
        }

    def get_head_to_head(self, team1_id: int, team2_id: int,
                         before_date: datetime, n_matches: int = 10) -> Dict:
        """
        Obtener historial de enfrentamientos directos

        Args:
            team1_id: ID del primer equipo (local en el próximo partido)
            team2_id: ID del segundo equipo (visitante)
            before_date: Fecha límite
            n_matches: Cantidad de enfrentamientos a considerar
        """
        matches = Match.objects.filter(
            Q(home_team_id=team1_id, away_team_id=team2_id) |
            Q(home_team_id=team2_id, away_team_id=team1_id),
            status='FINISHED',
            utc_date__lt=before_date
        ).order_by('-utc_date')[:n_matches]

        if not matches:
            return {
                'total_matches': 0,
                'team1_wins': 0,
                'team2_wins': 0,
                'draws': 0,
                'team1_goals': 0,
                'team2_goals': 0,
                'avg_goals': 0
            }

        team1_wins = 0
        team2_wins = 0
        draws = 0
        team1_goals = 0
        team2_goals = 0
        total_goals = []

        for match in matches:
            if match.home_team_id == team1_id:
                t1_goals = match.home_score or 0
                t2_goals = match.away_score or 0
            else:
                t1_goals = match.away_score or 0
                t2_goals = match.home_score or 0

            team1_goals += t1_goals
            team2_goals += t2_goals
            total_goals.append(t1_goals + t2_goals)

            if t1_goals > t2_goals:
                team1_wins += 1
            elif t1_goals < t2_goals:
                team2_wins += 1
            else:
                draws += 1

        return {
            'total_matches': len(matches),
            'team1_wins': team1_wins,
            'team2_wins': team2_wins,
            'draws': draws,
            'team1_goals': team1_goals,
            'team2_goals': team2_goals,
            'team1_win_rate': team1_wins / len(matches),
            'team2_win_rate': team2_wins / len(matches),
            'draw_rate': draws / len(matches),
            'avg_goals': np.mean(total_goals) if total_goals else 0,
            'team1_avg_goals': team1_goals / len(matches),
            'team2_avg_goals': team2_goals / len(matches)
        }

    def get_season_stats(self, team_id: int, competition_id: int,
                         season: int, before_date: datetime) -> Dict:
        """
        Obtener estadísticas de temporada hasta cierta fecha

        Args:
            team_id: ID del equipo
            competition_id: ID de la competición
            season: Temporada
            before_date: Fecha límite
        """
        matches = Match.objects.filter(
            Q(home_team_id=team_id) | Q(away_team_id=team_id),
            competition_id=competition_id,
            season=season,
            status='FINISHED',
            utc_date__lt=before_date
        )

        if not matches:
            return self._empty_season_stats()

        stats = {
            'matches': 0, 'wins': 0, 'draws': 0, 'losses': 0,
            'goals_for': 0, 'goals_against': 0,
            'home_wins': 0, 'home_draws': 0, 'home_losses': 0,
            'away_wins': 0, 'away_draws': 0, 'away_losses': 0,
            'clean_sheets': 0, 'failed_to_score': 0,
            'btts': 0, 'over_25': 0
        }

        for match in matches:
            is_home = match.home_team_id == team_id

            if is_home:
                gf = match.home_score or 0
                ga = match.away_score or 0
            else:
                gf = match.away_score or 0
                ga = match.home_score or 0

            stats['matches'] += 1
            stats['goals_for'] += gf
            stats['goals_against'] += ga

            # Resultado
            if gf > ga:
                stats['wins'] += 1
                if is_home:
                    stats['home_wins'] += 1
                else:
                    stats['away_wins'] += 1
            elif gf < ga:
                stats['losses'] += 1
                if is_home:
                    stats['home_losses'] += 1
                else:
                    stats['away_losses'] += 1
            else:
                stats['draws'] += 1
                if is_home:
                    stats['home_draws'] += 1
                else:
                    stats['away_draws'] += 1

            # Estadísticas adicionales
            if ga == 0:
                stats['clean_sheets'] += 1
            if gf == 0:
                stats['failed_to_score'] += 1
            if gf > 0 and ga > 0:
                stats['btts'] += 1
            if gf + ga > 2.5:
                stats['over_25'] += 1

        # Calcular promedios
        n = stats['matches']
        stats['points'] = stats['wins'] * 3 + stats['draws']
        stats['ppg'] = stats['points'] / n  # Points per game
        stats['avg_goals_for'] = stats['goals_for'] / n
        stats['avg_goals_against'] = stats['goals_against'] / n
        stats['win_rate'] = stats['wins'] / n
        stats['clean_sheet_rate'] = stats['clean_sheets'] / n
        stats['btts_rate'] = stats['btts'] / n
        stats['over_25_rate'] = stats['over_25'] / n

        return stats

    def calculate_match_features(self, match: Match) -> Dict:
        """
        Calcular todas las características para un partido

        Args:
            match: Objeto Match

        Returns:
            Diccionario con todas las features
        """
        home_id = match.home_team_id
        away_id = match.away_team_id
        match_date = match.utc_date

        # Forma general (últimos 5 partidos)
        home_form = self.get_team_form(home_id, match_date, 5)
        away_form = self.get_team_form(away_id, match_date, 5)

        # Forma como local/visitante (últimos 5)
        home_at_home = self.get_home_away_form(home_id, match_date, True, 5)
        away_at_away = self.get_home_away_form(away_id, match_date, False, 5)

        # Head to head
        h2h = self.get_head_to_head(home_id, away_id, match_date, 10)

        # Estadísticas de temporada
        home_season = self.get_season_stats(
            home_id, match.competition_id, match.season, match_date
        )
        away_season = self.get_season_stats(
            away_id, match.competition_id, match.season, match_date
        )

        features = {
            # === IDENTIFICADORES ===
            'match_id': match.id,
            'home_team_id': home_id,
            'away_team_id': away_id,
            'match_date': match_date.isoformat(),

            # === FORMA GENERAL ===
            'home_form_points': home_form['avg_points'],
            'home_form_gf': home_form['avg_goals_for'],
            'home_form_ga': home_form['avg_goals_against'],
            'home_form_win_rate': home_form['win_rate'],

            'away_form_points': away_form['avg_points'],
            'away_form_gf': away_form['avg_goals_for'],
            'away_form_ga': away_form['avg_goals_against'],
            'away_form_win_rate': away_form['win_rate'],

            # === FORMA LOCAL/VISITANTE ===
            'home_at_home_points': home_at_home['avg_points'],
            'home_at_home_gf': home_at_home['avg_goals_for'],
            'home_at_home_ga': home_at_home['avg_goals_against'],

            'away_at_away_points': away_at_away['avg_points'],
            'away_at_away_gf': away_at_away['avg_goals_for'],
            'away_at_away_ga': away_at_away['avg_goals_against'],

            # === HEAD TO HEAD ===
            'h2h_matches': h2h['total_matches'],
            'h2h_home_wins': h2h['team1_wins'],
            'h2h_away_wins': h2h['team2_wins'],
            'h2h_draws': h2h['draws'],
            'h2h_home_win_rate': h2h.get('team1_win_rate', 0),
            'h2h_avg_goals': h2h['avg_goals'],

            # === ESTADÍSTICAS DE TEMPORADA ===
            'home_season_ppg': home_season.get('ppg', 0),
            'home_season_gf': home_season.get('avg_goals_for', 0),
            'home_season_ga': home_season.get('avg_goals_against', 0),
            'home_season_clean_sheet_rate': home_season.get('clean_sheet_rate', 0),
            'home_season_btts_rate': home_season.get('btts_rate', 0),
            'home_season_over25_rate': home_season.get('over_25_rate', 0),

            'away_season_ppg': away_season.get('ppg', 0),
            'away_season_gf': away_season.get('avg_goals_for', 0),
            'away_season_ga': away_season.get('avg_goals_against', 0),
            'away_season_clean_sheet_rate': away_season.get('clean_sheet_rate', 0),
            'away_season_btts_rate': away_season.get('btts_rate', 0),
            'away_season_over25_rate': away_season.get('over_25_rate', 0),

            # === FEATURES DERIVADAS ===
            'form_diff': home_form['avg_points'] - away_form['avg_points'],
            'attack_strength_home': home_form['avg_goals_for'] / max(away_form['avg_goals_against'], 0.1),
            'attack_strength_away': away_form['avg_goals_for'] / max(home_form['avg_goals_against'], 0.1),
            'defense_strength_home': home_form['avg_goals_against'] / max(away_form['avg_goals_for'], 0.1),
            'ppg_diff': home_season.get('ppg', 0) - away_season.get('ppg', 0),
        }

        # Target (si el partido ya se jugó)
        if match.status == 'FINISHED' and match.home_score is not None:
            features['result'] = match.result  # H, D, A
            features['home_goals'] = match.home_score
            features['away_goals'] = match.away_score
            features['total_goals'] = match.total_goals
            features['btts'] = 1 if match.both_teams_scored else 0
            features['over_25'] = 1 if match.total_goals > 2.5 else 0

            # Estadísticas detalladas del partido
            features['corners_home'] = match.corners_home
            features['corners_away'] = match.corners_away
            features['shots_home'] = match.shots_home
            features['shots_away'] = match.shots_away
            features['shots_on_target_home'] = match.shots_on_target_home
            features['shots_on_target_away'] = match.shots_on_target_away
            features['possession_home'] = match.possession_home
            features['possession_away'] = match.possession_away
            features['yellow_cards_home'] = match.yellow_cards_home
            features['yellow_cards_away'] = match.yellow_cards_away
            features['red_cards_home'] = match.red_cards_home
            features['red_cards_away'] = match.red_cards_away

        return features

    def generate_training_data(self, competition_code: str,
                               seasons: List[int]) -> List[Dict]:
        """
        Generar dataset de entrenamiento

        Args:
            competition_code: Código de competición
            seasons: Lista de temporadas

        Returns:
            Lista de diccionarios con features
        """
        comp = Competition.objects.filter(code=competition_code).first()
        if not comp:
            raise ValueError(f"Competición {competition_code} no encontrada")

        all_features = []

        for season in seasons:
            print(f"Procesando temporada {season}...")

            matches = Match.objects.filter(
                competition_id=comp.id,
                season=season,
                status='FINISHED'
            ).order_by('utc_date')

            # Saltar primeros partidos (no hay suficiente historia)
            for match in matches[10:]:  # Empezar después de jornada ~5
                try:
                    features = self.calculate_match_features(match)
                    all_features.append(features)
                except Exception as e:
                    print(f"  Error en partido {match.id}: {e}")

        print(f"Total: {len(all_features)} partidos procesados")
        return all_features

    def _empty_form(self) -> Dict:
        return {
            'matches_played': 0,
            'points': 0,
            'avg_points': 0,
            'goals_for': 0,
            'goals_against': 0,
            'avg_goals_for': 0,
            'avg_goals_against': 0,
            'goal_diff': 0,
            'form_string': '',
            'wins': 0,
            'draws': 0,
            'losses': 0,
            'win_rate': 0,
            'unbeaten_rate': 0
        }

    def _empty_season_stats(self) -> Dict:
        return {
            'matches': 0, 'wins': 0, 'draws': 0, 'losses': 0,
            'goals_for': 0, 'goals_against': 0, 'points': 0,
            'ppg': 0, 'avg_goals_for': 0, 'avg_goals_against': 0,
            'win_rate': 0, 'clean_sheet_rate': 0, 'btts_rate': 0, 'over_25_rate': 0
        }
