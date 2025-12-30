"""
Modelos Django para el sistema de predicción de fútbol
Migrado desde SQLAlchemy
"""

from django.db import models
from django.utils import timezone


class Competition(models.Model):
    """Competición/Liga"""
    api_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True)
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, db_index=True)  # PL, BL1, SA, etc.
    country = models.CharField(max_length=100)
    current_season = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'competitions'
        verbose_name = 'Competition'
        verbose_name_plural = 'Competitions'

    def __str__(self):
        return f"{self.name} ({self.code})"


class Team(models.Model):
    """Equipo"""
    api_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True)
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=50)
    tla = models.CharField(max_length=10)  # Abreviatura (3 letras)
    crest_url = models.URLField(max_length=500, null=True, blank=True)
    manager = models.CharField(max_length=200, null=True, blank=True, help_text='Current team manager/coach')
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name='teams',
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'teams'
        verbose_name = 'Team'
        verbose_name_plural = 'Teams'

    def __str__(self):
        return self.name


class Match(models.Model):
    """Partido"""
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('FINISHED', 'Finished'),
        ('POSTPONED', 'Postponed'),
        ('CANCELLED', 'Cancelled'),
        ('IN_PLAY', 'In Play'),
    ]

    api_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True)
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name='matches'
    )
    season = models.IntegerField(db_index=True)
    matchday = models.IntegerField(null=True, blank=True)

    # Equipos
    home_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='home_matches'
    )
    away_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='away_matches'
    )

    # Fecha y estado
    utc_date = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')

    # Resultado
    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)
    home_score_ht = models.IntegerField(null=True, blank=True)  # Half-time
    away_score_ht = models.IntegerField(null=True, blank=True)

    # Estadísticas detalladas
    # Tiros
    shots_home = models.IntegerField(null=True, blank=True)
    shots_away = models.IntegerField(null=True, blank=True)
    shots_on_target_home = models.IntegerField(null=True, blank=True)
    shots_on_target_away = models.IntegerField(null=True, blank=True)
    shots_off_target_home = models.IntegerField(null=True, blank=True)
    shots_off_target_away = models.IntegerField(null=True, blank=True)
    shots_blocked_home = models.IntegerField(null=True, blank=True)
    shots_blocked_away = models.IntegerField(null=True, blank=True)

    # Corners
    corners_home = models.IntegerField(null=True, blank=True)
    corners_away = models.IntegerField(null=True, blank=True)

    # Tarjetas
    yellow_cards_home = models.IntegerField(null=True, blank=True)
    yellow_cards_away = models.IntegerField(null=True, blank=True)
    red_cards_home = models.IntegerField(null=True, blank=True)
    red_cards_away = models.IntegerField(null=True, blank=True)

    # Faltas y fueras de juego
    fouls_home = models.IntegerField(null=True, blank=True)
    fouls_away = models.IntegerField(null=True, blank=True)
    offsides_home = models.IntegerField(null=True, blank=True)
    offsides_away = models.IntegerField(null=True, blank=True)

    # Posesión
    possession_home = models.IntegerField(null=True, blank=True)
    possession_away = models.IntegerField(null=True, blank=True)

    # Expected Goals (xG)
    xg_home = models.FloatField(null=True, blank=True, help_text='Expected Goals del equipo local')
    xg_away = models.FloatField(null=True, blank=True, help_text='Expected Goals del equipo visitante')

    # Información del partido
    attendance = models.IntegerField(null=True, blank=True)
    referee = models.CharField(max_length=200, null=True, blank=True)
    venue = models.CharField(max_length=300, null=True, blank=True, help_text='Stadium/venue name')

    # Estadísticas adicionales
    hit_woodwork_home = models.IntegerField(null=True, blank=True)
    hit_woodwork_away = models.IntegerField(null=True, blank=True)
    free_kicks_conceded_home = models.IntegerField(null=True, blank=True)
    free_kicks_conceded_away = models.IntegerField(null=True, blank=True)
    booking_points_home = models.IntegerField(null=True, blank=True)  # 10 = yellow, 25 = red
    booking_points_away = models.IntegerField(null=True, blank=True)


    class Meta:
        db_table = 'matches'
        verbose_name = 'Match'
        verbose_name_plural = 'Matches'
        indexes = [
            models.Index(fields=['competition', 'season', 'home_team', 'away_team']),
            models.Index(fields=['status', 'utc_date']),
        ]

    def __str__(self):
        return f"{self.home_team.name} vs {self.away_team.name} ({self.utc_date.date()})"

    @property
    def result(self):
        """Resultado del partido: H (home win), D (draw), A (away win)"""
        if self.home_score is None or self.away_score is None:
            return None
        if self.home_score > self.away_score:
            return 'H'
        elif self.home_score < self.away_score:
            return 'A'
        else:
            return 'D'

    @property
    def half_time_result(self):
        """Resultado de medio tiempo: H (home win), D (draw), A (away win)"""
        if self.home_score_ht is None or self.away_score_ht is None:
            return None
        if self.home_score_ht > self.away_score_ht:
            return 'H'
        elif self.home_score_ht < self.away_score_ht:
            return 'A'
        else:
            return 'D'

    @property
    def total_goals(self):
        """Total de goles del partido"""
        if self.home_score is None or self.away_score is None:
            return None
        return self.home_score + self.away_score

    @property
    def both_teams_scored(self):
        """BTTS - Both Teams To Score"""
        if self.home_score is None or self.away_score is None:
            return None
        return self.home_score > 0 and self.away_score > 0

    @property
    def xg_total(self):
        """Total xG del partido (home + away)"""
        if self.xg_home is None or self.xg_away is None:
            return None
        return self.xg_home + self.xg_away

    @property
    def xg_difference(self):
        """Diferencia xG (home - away)"""
        if self.xg_home is None or self.xg_away is None:
            return None
        return self.xg_home - self.xg_away

    @property
    def xg_overperformance_home(self):
        """Sobrerendimiento xG del equipo local (goles - xG)"""
        if self.home_score is None or self.xg_home is None:
            return None
        return self.home_score - self.xg_home

    @property
    def xg_overperformance_away(self):
        """Sobrerendimiento xG del equipo visitante (goles - xG)"""
        if self.away_score is None or self.xg_away is None:
            return None
        return self.away_score - self.xg_away


class TeamStats(models.Model):
    """Estadísticas calculadas por equipo"""
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='stats')
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE)
    season = models.IntegerField()
    calculated_at = models.DateTimeField(default=timezone.now)

    # Manager de la temporada
    manager = models.CharField(max_length=200, null=True, blank=True)

    # Estadísticas generales
    matches_played = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    draws = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    goals_for = models.IntegerField(default=0)
    goals_against = models.IntegerField(default=0)

    # Estadísticas de local
    home_matches = models.IntegerField(default=0)
    home_wins = models.IntegerField(default=0)
    home_draws = models.IntegerField(default=0)
    home_losses = models.IntegerField(default=0)
    home_goals_for = models.IntegerField(default=0)
    home_goals_against = models.IntegerField(default=0)

    # Estadísticas de visitante
    away_matches = models.IntegerField(default=0)
    away_wins = models.IntegerField(default=0)
    away_draws = models.IntegerField(default=0)
    away_losses = models.IntegerField(default=0)
    away_goals_for = models.IntegerField(default=0)
    away_goals_against = models.IntegerField(default=0)

    # Forma reciente
    form_points = models.FloatField(default=0)
    form_goals_for = models.FloatField(default=0)
    form_goals_against = models.FloatField(default=0)

    # Métricas avanzadas
    avg_goals_for = models.FloatField(default=0)
    avg_goals_against = models.FloatField(default=0)
    clean_sheets = models.IntegerField(default=0)
    failed_to_score = models.IntegerField(default=0)
    btts_count = models.IntegerField(default=0)
    over_25_count = models.IntegerField(default=0)

    # Expected Goals (xG) - Métricas
    avg_xg_for = models.FloatField(default=0, help_text='Promedio xG a favor por partido')
    avg_xg_against = models.FloatField(default=0, help_text='Promedio xG en contra por partido')
    xg_overperformance = models.FloatField(default=0, help_text='Goles reales - xG esperado (promedio)')
    total_xg_for = models.FloatField(default=0, help_text='Total xG a favor en la temporada')
    total_xg_against = models.FloatField(default=0, help_text='Total xG en contra en la temporada')

    class Meta:
        db_table = 'team_stats'
        verbose_name = 'Team Statistics'
        verbose_name_plural = 'Team Statistics'
        unique_together = [['team', 'competition', 'season']]
        indexes = [
            models.Index(fields=['team', 'season']),
        ]

    def __str__(self):
        return f"{self.team.name} - {self.season}"

    @property
    def points(self):
        """Puntos totales"""
        return (self.wins * 3) + self.draws

    @property
    def goal_difference(self):
        """Diferencia de goles"""
        return self.goals_for - self.goals_against


class HeadToHead(models.Model):
    """Historial de enfrentamientos directos"""
    team1 = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='h2h_as_team1'
    )
    team2 = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='h2h_as_team2'
    )
    calculated_at = models.DateTimeField(default=timezone.now)

    total_matches = models.IntegerField(default=0)
    team1_wins = models.IntegerField(default=0)
    team2_wins = models.IntegerField(default=0)
    draws = models.IntegerField(default=0)
    team1_goals = models.IntegerField(default=0)
    team2_goals = models.IntegerField(default=0)

    # JSON con últimos enfrentamientos
    recent_matches = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'head_to_head'
        verbose_name = 'Head to Head'
        verbose_name_plural = 'Head to Head'
        unique_together = [['team1', 'team2']]
        indexes = [
            models.Index(fields=['team1', 'team2']),
        ]

    def __str__(self):
        return f"{self.team1.name} vs {self.team2.name}"


class EloRating(models.Model):
    """
    Elo ratings para equipos - Sistema dual
    - season=NULL: Elo persistente (global por competición, evoluciona año tras año)
    - season=2024: Elo de temporada específica (se resetea cada año)
    """
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='elo_ratings'
    )
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name='elo_ratings'
    )
    season = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text='NULL para Elo persistente, año para Elo de temporada'
    )

    # Rating actual
    rating = models.FloatField(default=1500.0)

    # Métricas de tracking
    matches_played = models.IntegerField(default=0)
    peak_rating = models.FloatField(default=1500.0)
    lowest_rating = models.FloatField(default=1500.0)

    # Momentum: últimos 5 ratings almacenados como JSON array
    last_5_ratings = models.TextField(default='[]')

    # Metadata
    last_match_date = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'elo_ratings'
        verbose_name = 'Elo Rating'
        verbose_name_plural = 'Elo Ratings'
        unique_together = [['team', 'competition', 'season']]
        indexes = [
            models.Index(fields=['team', 'competition']),
            models.Index(fields=['competition', 'season', '-rating']),
        ]

    def __str__(self):
        season_str = f"Season {self.season}" if self.season else "Persistent"
        return f"{self.team.name} ({self.competition.code}) - {season_str}: {self.rating:.0f}"

    @property
    def elo_momentum(self):
        """
        Calcular momentum Elo desde últimos 5 partidos
        Retorna diferencia entre rating actual y rating hace 5 partidos
        """
        import json
        try:
            ratings = json.loads(self.last_5_ratings)
            if len(ratings) < 2:
                return 0
            return ratings[-1] - ratings[0]
        except (json.JSONDecodeError, IndexError):
            return 0


class PoissonParams(models.Model):
    """
    Parámetros de ataque/defensa para modelos Poisson y Dixon-Coles
    Almacena las fuerzas estimadas de cada equipo por temporada/competición
    """
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='poisson_params'
    )
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name='poisson_params'
    )
    season = models.IntegerField(db_index=True)

    # Parámetros del modelo Poisson
    attack_strength = models.FloatField(
        default=1.0,
        help_text='Fuerza ofensiva relativa (1.0 = promedio)'
    )
    defense_strength = models.FloatField(
        default=1.0,
        help_text='Fuerza defensiva relativa (1.0 = promedio)'
    )

    # Estadísticas usadas para el cálculo
    matches_played = models.IntegerField(default=0)
    avg_goals_scored = models.FloatField(default=0.0)
    avg_goals_conceded = models.FloatField(default=0.0)

    # Metadata
    calculated_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'poisson_params'
        verbose_name = 'Poisson Parameters'
        verbose_name_plural = 'Poisson Parameters'
        unique_together = [['team', 'competition', 'season']]
        indexes = [
            models.Index(fields=['team', 'competition', 'season']),
            models.Index(fields=['competition', 'season']),
        ]

    def __str__(self):
        return f"{self.team.name} ({self.competition.code} {self.season}): ATT={self.attack_strength:.2f}, DEF={self.defense_strength:.2f}"

    @property
    def offensive_rating(self):
        """Rating ofensivo (attack_strength × 100)"""
        return self.attack_strength * 100

    @property
    def defensive_rating(self):
        """Rating defensivo (menor es mejor, defense_strength × 100)"""
        return self.defense_strength * 100


class Prediction(models.Model):
    """Predicciones realizadas"""
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='predictions'
    )
    created_at = models.DateTimeField(default=timezone.now)

    # Probabilidades predichas
    prob_home = models.FloatField()
    prob_draw = models.FloatField()
    prob_away = models.FloatField()

    # Mercados adicionales
    prob_over_25 = models.FloatField(null=True, blank=True)
    prob_btts = models.FloatField(null=True, blank=True)

    # Corners
    predicted_corners = models.FloatField(null=True, blank=True)
    prob_over_95_corners = models.FloatField(null=True, blank=True)
    prob_over_105_corners = models.FloatField(null=True, blank=True)

    # Tiros
    predicted_shots = models.FloatField(null=True, blank=True)
    predicted_shots_on_target = models.FloatField(null=True, blank=True)

    # Metadata
    model_version = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'predictions'
        verbose_name = 'Prediction'
        verbose_name_plural = 'Predictions'
        indexes = [
            models.Index(fields=['match', 'created_at']),
        ]

    def __str__(self):
        return f"Prediction for {self.match}"


class Player(models.Model):
    """Jugador individual"""
    # Identifiers (múltiples fuentes)
    api_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True)
    fbref_id = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    transfermarkt_id = models.IntegerField(null=True, blank=True, db_index=True)
    sofascore_id = models.IntegerField(null=True, blank=True, db_index=True)

    # Info básica
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=100)
    nationality = models.CharField(max_length=100, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    photo = models.CharField(max_length=500, null=True, blank=True, help_text='Path to player photo')

    # Posición
    position = models.CharField(max_length=20)  # GK, DF, MF, FW
    position_detail = models.CharField(max_length=50, null=True, blank=True)

    # Físico
    height_cm = models.IntegerField(null=True, blank=True)
    weight_kg = models.IntegerField(null=True, blank=True)
    foot = models.CharField(max_length=10, null=True, blank=True)

    # Equipo actual
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, related_name='players')

    # Valor de mercado
    market_value_eur = models.IntegerField(null=True, blank=True)
    contract_expires = models.DateField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'players'
        verbose_name = 'Player'
        verbose_name_plural = 'Players'
        indexes = [
            models.Index(fields=['team', 'position']),
            models.Index(fields=['market_value_eur']),
        ]

    def __str__(self):
        return f"{self.name} ({self.position})"


class PlayerStats(models.Model):
    """Estadísticas de jugador por temporada (FBRef)"""
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='season_stats')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='player_stats')
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE)
    season = models.IntegerField(db_index=True)

    # Apariencias
    matches_played = models.IntegerField(default=0)
    minutes_played = models.IntegerField(default=0)
    starts = models.IntegerField(default=0)

    # Goles & Asistencias
    goals = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    penalties_scored = models.IntegerField(default=0)
    penalties_attempted = models.IntegerField(default=0)

    # Expected Goals
    xg = models.FloatField(default=0)
    npxg = models.FloatField(default=0, help_text='Non-Penalty xG')
    xa = models.FloatField(default=0, help_text='Expected Assists')

    # Tiros
    shots_total = models.IntegerField(default=0)
    shots_on_target = models.IntegerField(default=0)
    shot_accuracy_pct = models.FloatField(default=0)

    # Pases (FBRef)
    passes_completed = models.IntegerField(default=0)
    passes_attempted = models.IntegerField(default=0)
    pass_completion_pct = models.FloatField(default=0)
    progressive_passes = models.IntegerField(default=0)
    key_passes = models.IntegerField(default=0)

    # Defensivo
    tackles = models.IntegerField(default=0)
    interceptions = models.IntegerField(default=0)
    blocks = models.IntegerField(default=0)
    clearances = models.IntegerField(default=0)
    pressures = models.IntegerField(default=0)

    # Disciplina
    yellow_cards = models.IntegerField(default=0)
    red_cards = models.IntegerField(default=0)
    fouls_committed = models.IntegerField(default=0)
    fouls_drawn = models.IntegerField(default=0)

    # Duelos aéreos
    aerials_won = models.IntegerField(default=0)
    aerials_lost = models.IntegerField(default=0)
    aerial_win_pct = models.FloatField(default=0)

    # Regates
    dribbles_completed = models.IntegerField(default=0)
    dribbles_attempted = models.IntegerField(default=0)
    dribble_success_pct = models.FloatField(default=0)

    # Portero (si position=GK)
    saves = models.IntegerField(null=True, blank=True)
    save_pct = models.FloatField(null=True, blank=True)
    clean_sheets = models.IntegerField(null=True, blank=True)
    goals_conceded = models.IntegerField(null=True, blank=True)
    pens_saved = models.IntegerField(null=True, blank=True)

    # Metadata
    calculated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'player_stats'
        verbose_name = 'Player Statistics'
        verbose_name_plural = 'Player Statistics'
        unique_together = [['player', 'team', 'competition', 'season']]
        indexes = [
            models.Index(fields=['player', 'season']),
            models.Index(fields=['team', 'season']),
            models.Index(fields=['xg', 'xa']),
        ]

    def __str__(self):
        return f"{self.player.name} - {self.team.short_name} {self.season}"


class MatchPlayerStats(models.Model):
    """Rendimiento de jugador en un partido específico"""
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='player_performances')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='match_stats')
    team = models.ForeignKey(Team, on_delete=models.CASCADE)

    # Apariencia
    started = models.BooleanField(default=False)
    substitute = models.BooleanField(default=False)
    minutes_played = models.IntegerField(default=0)
    position = models.CharField(max_length=20)
    shirt_number = models.IntegerField(null=True, blank=True)

    # Rendimiento
    goals = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    rating = models.FloatField(null=True, blank=True, help_text='SofaScore rating (1-10)')

    # xG del partido
    xg = models.FloatField(null=True, blank=True)
    xa = models.FloatField(null=True, blank=True, help_text='Expected Assists')

    # Estadísticas de tiros
    shots = models.IntegerField(default=0)
    shots_on_target = models.IntegerField(default=0)
    shots_off_target = models.IntegerField(default=0)
    shots_blocked = models.IntegerField(default=0)
    big_chances_missed = models.IntegerField(default=0)

    # Estadísticas de pases
    passes_completed = models.IntegerField(default=0)
    passes_attempted = models.IntegerField(default=0)
    key_passes = models.IntegerField(default=0)
    accurate_crosses = models.IntegerField(default=0)
    total_crosses = models.IntegerField(default=0)
    big_chances_created = models.IntegerField(default=0)

    # Estadísticas defensivas
    tackles = models.IntegerField(default=0)
    tackles_won = models.IntegerField(default=0)
    interceptions = models.IntegerField(default=0)
    clearances = models.IntegerField(default=0)
    blocked_shots = models.IntegerField(default=0)

    # Duelos
    duels_won = models.IntegerField(default=0)
    duels_lost = models.IntegerField(default=0)
    aerials_won = models.IntegerField(default=0)
    aerials_lost = models.IntegerField(default=0)
    dribbles_successful = models.IntegerField(default=0)
    dribbles_attempted = models.IntegerField(default=0)
    was_fouled = models.IntegerField(default=0)

    # Disciplina
    fouls_committed = models.IntegerField(default=0)
    yellow_card = models.BooleanField(default=False)
    red_card = models.BooleanField(default=False)

    # Otros
    touches = models.IntegerField(default=0)
    dispossessed = models.IntegerField(default=0)
    offsides = models.IntegerField(default=0)

    # Portero (si aplica)
    saves = models.IntegerField(null=True, blank=True)
    saves_inside_box = models.IntegerField(null=True, blank=True)
    punches = models.IntegerField(null=True, blank=True)
    runs_out = models.IntegerField(null=True, blank=True)
    successful_runs_out = models.IntegerField(null=True, blank=True)
    high_claims = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'match_player_stats'
        verbose_name = 'Match Player Statistics'
        verbose_name_plural = 'Match Player Statistics'
        unique_together = [['match', 'player']]
        indexes = [
            models.Index(fields=['match', 'team']),
            models.Index(fields=['player', 'match']),
            models.Index(fields=['rating']),
        ]

    def __str__(self):
        return f"{self.player.name} - {self.match}"


class ShotEvent(models.Model):
    """Evento de tiro individual con xG (shot maps)"""
    SHOT_RESULT_CHOICES = [
        ('Goal', 'Goal'),
        ('SavedShot', 'Saved'),
        ('MissedShots', 'Missed'),
        ('BlockedShot', 'Blocked'),
        ('ShotOnPost', 'Hit Post'),
    ]

    BODY_PART_CHOICES = [
        ('RightFoot', 'Right Foot'),
        ('LeftFoot', 'Left Foot'),
        ('Head', 'Header'),
        ('Other', 'Other'),
    ]

    SITUATION_CHOICES = [
        ('OpenPlay', 'Open Play'),
        ('SetPiece', 'Set Piece'),
        ('Corner', 'Corner'),
        ('Penalty', 'Penalty'),
        ('FastBreak', 'Counter Attack'),
        ('DirectFreekick', 'Free Kick'),
    ]

    # Relaciones
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='shot_events')
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, related_name='shots')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='shot_events')

    # Metadata del tiro
    minute = models.IntegerField()
    result = models.CharField(max_length=20, choices=SHOT_RESULT_CHOICES)

    # Calidad del tiro
    xg = models.FloatField(help_text='Expected Goal value for this shot')

    # Ubicación
    x = models.FloatField(help_text='X coordinate (0-100, pitch length)')
    y = models.FloatField(help_text='Y coordinate (0-100, pitch width)')
    body_part = models.CharField(max_length=20, choices=BODY_PART_CHOICES, null=True, blank=True)
    situation = models.CharField(max_length=20, choices=SITUATION_CHOICES, null=True, blank=True)

    # Asistencia
    assisted_by = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assists_given'
    )

    class Meta:
        db_table = 'shot_events'
        verbose_name = 'Shot Event'
        verbose_name_plural = 'Shot Events'
        indexes = [
            models.Index(fields=['match', 'team']),
            models.Index(fields=['player', 'match']),
            models.Index(fields=['xg']),
        ]

    def __str__(self):
        return f"{self.player.name if self.player else 'Unknown'} - {self.result} (xG: {self.xg:.2f})"


class TeamMarketValue(models.Model):
    """Valuación de mercado del plantel (Transfermarkt)"""
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='market_values')
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE)
    season = models.IntegerField(db_index=True)

    # Valor del plantel
    total_market_value_eur = models.BigIntegerField(help_text='Total squad value in EUR')
    avg_player_value_eur = models.IntegerField(help_text='Average player value in EUR')

    # Composición del plantel
    squad_size = models.IntegerField()
    avg_age = models.FloatField()
    foreigners_count = models.IntegerField()

    # Actividad de traspasos
    transfer_income_eur = models.BigIntegerField(null=True, blank=True)
    transfer_expenditure_eur = models.BigIntegerField(null=True, blank=True)
    net_transfer_eur = models.BigIntegerField(null=True, blank=True)

    # Metadata
    scraped_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'team_market_values'
        verbose_name = 'Team Market Value'
        verbose_name_plural = 'Team Market Values'
        unique_together = [['team', 'competition', 'season']]
        indexes = [
            models.Index(fields=['team', 'season']),
            models.Index(fields=['total_market_value_eur']),
        ]

    def __str__(self):
        return f"{self.team.name} - {self.season} (€{self.total_market_value_eur:,})"


class PlayerInjury(models.Model):
    """Lesiones y ausencias de jugadores"""
    INJURY_STATUS_CHOICES = [
        ('Injured', 'Injured'),
        ('Doubtful', 'Doubtful'),
        ('Suspended', 'Suspended'),
        ('Recovered', 'Recovered'),
    ]

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='injuries')

    # Detalles de la lesión
    injury_type = models.CharField(max_length=200, null=True, blank=True)
    status = models.CharField(max_length=20, choices=INJURY_STATUS_CHOICES)

    # Línea de tiempo
    injury_date = models.DateField()
    expected_return_date = models.DateField(null=True, blank=True)
    actual_return_date = models.DateField(null=True, blank=True)

    # Impacto
    matches_missed = models.IntegerField(default=0)

    class Meta:
        db_table = 'player_injuries'
        verbose_name = 'Player Injury'
        verbose_name_plural = 'Player Injuries'
        indexes = [
            models.Index(fields=['player', 'status']),
            models.Index(fields=['injury_date', 'expected_return_date']),
        ]

    def __str__(self):
        return f"{self.player.name} - {self.status} ({self.injury_type or 'Unknown'})"


class MatchIncident(models.Model):
    """Eventos del partido (goles, tarjetas, sustituciones)"""
    INCIDENT_TYPE_CHOICES = [
        ('goal', 'Goal'),
        ('ownGoal', 'Own Goal'),
        ('penalty', 'Penalty'),
        ('missedPenalty', 'Missed Penalty'),
        ('yellowCard', 'Yellow Card'),
        ('redCard', 'Red Card'),
        ('yellowRedCard', 'Second Yellow Card'),
        ('substitution', 'Substitution'),
        ('injuryTime', 'Injury Time'),
        ('var', 'VAR Decision'),
    ]

    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='incidents')
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='match_incidents')
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')

    # Tipo y momento del incidente
    incident_type = models.CharField(max_length=20, choices=INCIDENT_TYPE_CHOICES)
    time = models.IntegerField(help_text='Minute of the incident')
    time_added = models.IntegerField(null=True, blank=True, help_text='Added time minutes (e.g., 45+2)')

    # Detalles del incidente
    score_home = models.IntegerField(null=True, blank=True, help_text='Home score after this incident')
    score_away = models.IntegerField(null=True, blank=True, help_text='Away score after this incident')
    assist_player = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assists_incidents',
        help_text='Player who assisted (for goals)'
    )

    # Para sustituciones
    player_in = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='substitutions_in',
        help_text='Player coming in (for substitutions)'
    )
    player_out = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='substitutions_out',
        help_text='Player going out (for substitutions)'
    )

    # Información adicional
    is_home = models.BooleanField(default=True, help_text='True if home team incident')
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'match_incidents'
        verbose_name = 'Match Incident'
        verbose_name_plural = 'Match Incidents'
        ordering = ['match', 'time', 'time_added']
        indexes = [
            models.Index(fields=['match', 'incident_type']),
            models.Index(fields=['player', 'incident_type']),
            models.Index(fields=['match', 'time']),
        ]
        # Note: No unique constraint as multiple incidents can happen at same time
        # (e.g., two yellow cards in same minute). Handled in import logic.

    def __str__(self):
        time_str = f"{self.time}'" if not self.time_added else f"{self.time}+{self.time_added}'"
        player_str = self.player.name if self.player else 'Unknown'
        return f"{self.match} - {time_str} {self.incident_type}: {player_str}"


class Injury(models.Model):
    """Lesiones de jugadores"""
    INJURY_STATUS_CHOICES = [
        ('injured', 'Injured'),
        ('doubtful', 'Doubtful'),
        ('recovering', 'Recovering'),
        ('fit', 'Fit'),
    ]

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='injury_records')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='team_injuries')

    # Detalles de la lesión
    injury_type = models.CharField(max_length=200, help_text='Type of injury (e.g., Hamstring, Ankle, Knee)')
    status = models.CharField(max_length=20, choices=INJURY_STATUS_CHOICES, default='injured')

    # Fechas
    start_date = models.DateField(null=True, blank=True, help_text='Date when injury occurred')
    expected_return_date = models.DateField(null=True, blank=True, help_text='Expected return date')
    actual_return_date = models.DateField(null=True, blank=True, help_text='Actual return date')

    # Información adicional
    description = models.TextField(null=True, blank=True)
    severity = models.CharField(max_length=50, null=True, blank=True, help_text='Minor, Moderate, Severe')

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'injuries'
        verbose_name = 'Injury'
        verbose_name_plural = 'Injuries'
        ordering = ['-start_date', '-created_at']
        indexes = [
            models.Index(fields=['player', 'status']),
            models.Index(fields=['team', 'status']),
            models.Index(fields=['start_date', 'expected_return_date']),
        ]

    def __str__(self):
        return f"{self.player.name} - {self.injury_type} ({self.status})"

    @property
    def is_active(self):
        """Check if injury is still active"""
        return self.status in ['injured', 'doubtful', 'recovering']


class ImportJob(models.Model):
    """
    Background import job tracking
    Stores metadata, logs, and progress for data imports
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]

    # Job metadata
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='import_jobs'
    )

    # Import parameters
    competitions = models.CharField(max_length=200)  # "PL,PD,BL1"
    seasons = models.CharField(max_length=200)  # "2023,2024"
    import_teams = models.BooleanField(default=False)
    import_matches = models.BooleanField(default=False)
    import_players = models.BooleanField(default=False)
    import_standings = models.BooleanField(default=False)
    force = models.BooleanField(default=False)
    dry_run = models.BooleanField(default=False)

    # Results (JSON stored as text)
    result_counts = models.TextField(null=True, blank=True)

    # Logs (append-only)
    logs = models.TextField(default='')

    # Progress tracking
    progress_percentage = models.IntegerField(default=0)
    current_step = models.CharField(max_length=500, default='')

    # Cancellation flag
    cancel_requested = models.BooleanField(default=False, db_index=True)

    # Error tracking
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'import_jobs'
        verbose_name = 'Import Job'
        verbose_name_plural = 'Import Jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"Import {self.id} - {self.status} - {self.competitions}"

    def append_log(self, message):
        """Thread-safe log appending"""
        from django.db import transaction
        with transaction.atomic():
            # Reload to get latest logs
            job = ImportJob.objects.select_for_update().get(pk=self.pk)
            job.logs += message + '\n'
            job.save(update_fields=['logs'])

    def update_progress(self, percentage, step):
        """Thread-safe progress updating"""
        # Use .update() instead of .save() to avoid stale data issues
        # This is atomic and safe to call from async contexts via sync_to_async
        ImportJob.objects.filter(pk=self.pk).update(
            progress_percentage=percentage,
            current_step=step
        )

    def get_log_lines(self):
        """Return logs as list of lines"""
        return [line for line in self.logs.split('\n') if line.strip()]
