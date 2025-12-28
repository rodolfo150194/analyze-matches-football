from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Competition, Team, Match, TeamStats, HeadToHead, Prediction,
    Player, PlayerStats, MatchPlayerStats, ShotEvent, TeamMarketValue, PlayerInjury,
    MatchIncident, Injury
)


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'country', 'current_season', 'api_id')
    list_filter = ('country', 'code')
    search_fields = ('name', 'code', 'country')
    ordering = ('name',)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'tla', 'competition', 'api_id')
    list_filter = ('competition',)
    search_fields = ('name', 'short_name', 'tla')
    ordering = ('name',)
    list_select_related = ('competition',)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        'get_match_info',
        'competition',
        'season',
        'matchday',
        'utc_date',
        'status',
        'get_score',
        'get_result'
    )
    list_filter = (
        'status',
        'competition',
        'season',
        ('utc_date', admin.DateFieldListFilter),
    )
    search_fields = (
        'home_team__name',
        'away_team__name',
        'referee',
    )
    date_hierarchy = 'utc_date'
    list_select_related = ('home_team', 'away_team', 'competition')
    ordering = ('-utc_date',)

    fieldsets = (
        ('Match Information', {
            'fields': (
                'api_id',
                'competition',
                'season',
                'matchday',
                'utc_date',
                'status'
            )
        }),
        ('Teams', {
            'fields': ('home_team', 'away_team')
        }),
        ('Score', {
            'fields': (
                ('home_score', 'away_score'),
                ('home_score_ht', 'away_score_ht')
            )
        }),
        ('Match Stats', {
            'fields': (
                ('shots_home', 'shots_away'),
                ('shots_on_target_home', 'shots_on_target_away'),
                ('shots_off_target_home', 'shots_off_target_away'),
                ('shots_blocked_home', 'shots_blocked_away'),
                ('corners_home', 'corners_away'),
                ('yellow_cards_home', 'yellow_cards_away'),
                ('red_cards_home', 'red_cards_away'),
                ('fouls_home', 'fouls_away'),
                ('offsides_home', 'offsides_away'),
                ('possession_home', 'possession_away'),
            ),
            'classes': ('collapse',)
        }),
        ('Additional Stats', {
            'fields': (
                'attendance',
                'referee',
                ('hit_woodwork_home', 'hit_woodwork_away'),
                ('free_kicks_conceded_home', 'free_kicks_conceded_away'),
                ('booking_points_home', 'booking_points_away'),
            ),
            'classes': ('collapse',)
        }),
        ('Betting Odds - 1X2', {
            'fields': (
                ('max_odds_home', 'max_odds_draw', 'max_odds_away'),
                ('avg_odds_home', 'avg_odds_draw', 'avg_odds_away'),
                ('b365_odds_home', 'b365_odds_draw', 'b365_odds_away'),
                ('ps_odds_home', 'ps_odds_draw', 'ps_odds_away'),
                ('wh_odds_home', 'wh_odds_draw', 'wh_odds_away'),
                ('bf_odds_home', 'bf_odds_draw', 'bf_odds_away'),
            ),
            'classes': ('collapse',)
        }),
        ('Betting Odds - Over/Under 2.5', {
            'fields': (
                ('max_odds_over_25', 'max_odds_under_25'),
                ('avg_odds_over_25', 'avg_odds_under_25'),
                ('b365_odds_over_25', 'b365_odds_under_25'),
                ('ps_odds_over_25', 'ps_odds_under_25'),
            ),
            'classes': ('collapse',)
        }),
        ('Betting Odds - Asian Handicap', {
            'fields': (
                'asian_handicap_size',
                ('max_odds_ah_home', 'max_odds_ah_away'),
                ('avg_odds_ah_home', 'avg_odds_ah_away'),
                ('b365_ah_size', 'b365_odds_ah_home', 'b365_odds_ah_away'),
                ('ps_odds_ah_home', 'ps_odds_ah_away'),
            ),
            'classes': ('collapse',)
        }),
        ('Betbrain Aggregates - 1X2', {
            'fields': (
                'betbrain_num_bookmakers',
                ('betbrain_max_odds_home', 'betbrain_max_odds_draw', 'betbrain_max_odds_away'),
                ('betbrain_avg_odds_home', 'betbrain_avg_odds_draw', 'betbrain_avg_odds_away'),
            ),
            'classes': ('collapse',)
        }),
        ('Betbrain Aggregates - O/U', {
            'fields': (
                'betbrain_num_ou_bookmakers',
                ('betbrain_max_odds_over_25', 'betbrain_max_odds_under_25'),
                ('betbrain_avg_odds_over_25', 'betbrain_avg_odds_under_25'),
            ),
            'classes': ('collapse',)
        }),
        ('Betbrain Aggregates - Asian Handicap', {
            'fields': (
                'betbrain_num_ah_bookmakers',
                'betbrain_ah_size',
                ('betbrain_max_odds_ah_home', 'betbrain_max_odds_ah_away'),
                ('betbrain_avg_odds_ah_home', 'betbrain_avg_odds_ah_away'),
            ),
            'classes': ('collapse',)
        }),
    )

    def get_match_info(self, obj):
        try:
            home = obj.home_team.short_name if obj.home_team else '?'
            away = obj.away_team.short_name if obj.away_team else '?'
            return f"{home} vs {away}"
        except Exception:
            return "Match info unavailable"
    get_match_info.short_description = 'Match'

    def get_score(self, obj):
        if obj.home_score is not None and obj.away_score is not None:
            return format_html(
                '<strong>{} - {}</strong>',
                obj.home_score,
                obj.away_score
            )
        return '-'
    get_score.short_description = 'Score'

    def get_result(self, obj):
        try:
            result = obj.result
            if result == 'H':
                return format_html('<span style="color: green;">Home Win</span>')
            elif result == 'A':
                return format_html('<span style="color: blue;">Away Win</span>')
            elif result == 'D':
                return format_html('<span style="color: orange;">Draw</span>')
            return '-'
        except Exception:
            return '-'
    get_result.short_description = 'Result'


@admin.register(TeamStats)
class TeamStatsAdmin(admin.ModelAdmin):
    list_display = (
        'team',
        'competition',
        'season',
        'matches_played',
        'get_record',
        'get_points',
        'get_goal_diff',
        'calculated_at'
    )
    list_filter = (
        'competition',
        'season',
        ('calculated_at', admin.DateFieldListFilter),
    )
    search_fields = ('team__name',)
    ordering = ('-season', 'competition', '-matches_played')
    list_select_related = ('team', 'competition')

    fieldsets = (
        ('Basic Info', {
            'fields': ('team', 'competition', 'season', 'calculated_at')
        }),
        ('Overall Stats', {
            'fields': (
                'matches_played',
                ('wins', 'draws', 'losses'),
                ('goals_for', 'goals_against'),
            )
        }),
        ('Home Stats', {
            'fields': (
                'home_matches',
                ('home_wins', 'home_draws', 'home_losses'),
                ('home_goals_for', 'home_goals_against'),
            )
        }),
        ('Away Stats', {
            'fields': (
                'away_matches',
                ('away_wins', 'away_draws', 'away_losses'),
                ('away_goals_for', 'away_goals_against'),
            )
        }),
        ('Form & Advanced Metrics', {
            'fields': (
                ('form_points', 'form_goals_for', 'form_goals_against'),
                ('avg_goals_for', 'avg_goals_against'),
                ('clean_sheets', 'failed_to_score'),
                ('btts_count', 'over_25_count'),
            )
        }),
    )

    readonly_fields = ('calculated_at',)

    def get_record(self, obj):
        return f"{obj.wins}W-{obj.draws}D-{obj.losses}L"
    get_record.short_description = 'W-D-L'

    def get_points(self, obj):
        points = obj.points
        return format_html('<strong>{}</strong>', points)
    get_points.short_description = 'Points'

    def get_goal_diff(self, obj):
        diff = obj.goal_difference
        color = 'green' if diff > 0 else 'red' if diff < 0 else 'gray'
        diff_str = f"{diff:+d}"
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            diff_str
        )
    get_goal_diff.short_description = 'GD'


@admin.register(HeadToHead)
class HeadToHeadAdmin(admin.ModelAdmin):
    list_display = (
        'get_matchup',
        'total_matches',
        'team1_wins',
        'draws',
        'team2_wins',
        'get_goals',
        'calculated_at'
    )
    search_fields = ('team1__name', 'team2__name')
    list_select_related = ('team1', 'team2')
    ordering = ('-calculated_at',)

    fieldsets = (
        ('Teams', {
            'fields': ('team1', 'team2', 'calculated_at')
        }),
        ('Stats', {
            'fields': (
                'total_matches',
                ('team1_wins', 'draws', 'team2_wins'),
                ('team1_goals', 'team2_goals'),
            )
        }),
        ('Recent Matches', {
            'fields': ('recent_matches',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('calculated_at',)

    def get_matchup(self, obj):
        try:
            team1 = obj.team1.name if obj.team1 else '?'
            team2 = obj.team2.name if obj.team2 else '?'
            return f"{team1} vs {team2}"
        except Exception:
            return "Matchup unavailable"
    get_matchup.short_description = 'Matchup'

    def get_goals(self, obj):
        return f"{obj.team1_goals} - {obj.team2_goals}"
    get_goals.short_description = 'Total Goals'


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = (
        'get_match',
        'get_probabilities',
        'get_over_25',
        'get_btts',
        'created_at',
        'model_version'
    )
    list_filter = (
        ('created_at', admin.DateFieldListFilter),
        'model_version',
    )
    search_fields = (
        'match__home_team__name',
        'match__away_team__name',
    )
    date_hierarchy = 'created_at'
    list_select_related = ('match__home_team', 'match__away_team')
    ordering = ('-created_at',)

    fieldsets = (
        ('Match Info', {
            'fields': ('match', 'created_at', 'model_version')
        }),
        ('Result Probabilities', {
            'fields': (
                ('prob_home', 'prob_draw', 'prob_away'),
            )
        }),
        ('Additional Markets', {
            'fields': (
                ('prob_over_25', 'prob_btts'),
                ('prob_over_95_corners', 'prob_over_105_corners'),
                'predicted_corners',
                ('predicted_shots', 'predicted_shots_on_target'),
            )
        }),
    )

    readonly_fields = ('created_at',)

    def get_match(self, obj):
        try:
            home = obj.match.home_team.short_name if obj.match.home_team else '?'
            away = obj.match.away_team.short_name if obj.match.away_team else '?'
            return f"{home} vs {away}"
        except Exception:
            return "Match info unavailable"
    get_match.short_description = 'Match'

    def get_probabilities(self, obj):
        home_pct = f"{obj.prob_home:.1%}"
        draw_pct = f"{obj.prob_draw:.1%}"
        away_pct = f"{obj.prob_away:.1%}"
        return format_html(
            'H: <strong>{}</strong> | D: <strong>{}</strong> | A: <strong>{}</strong>',
            home_pct,
            draw_pct,
            away_pct
        )
    get_probabilities.short_description = '1X2 Probabilities'

    def get_over_25(self, obj):
        if obj.prob_over_25 is not None:
            pct = f"{obj.prob_over_25:.1%}"
            return format_html('<strong>{}</strong>', pct)
        return '-'
    get_over_25.short_description = 'Over 2.5'

    def get_btts(self, obj):
        if obj.prob_btts is not None:
            pct = f"{obj.prob_btts:.1%}"
            return format_html('<strong>{}</strong>', pct)
        return '-'
    get_btts.short_description = 'BTTS'


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'position',
        'team',
        'nationality',
        'date_of_birth',
        'get_market_value',
        'fbref_id',
        'sofascore_id',
        'transfermarkt_id'
    )
    list_filter = (
        'position',
        'team__competition',
        'nationality',
    )
    search_fields = ('name', 'short_name', 'nationality')
    ordering = ('name',)
    list_select_related = ('team',)

    fieldsets = (
        ('Basic Info', {
            'fields': (
                ('name', 'short_name'),
                ('position', 'position_detail'),
                'team'
            )
        }),
        ('Personal', {
            'fields': (
                'nationality',
                'date_of_birth',
                ('height_cm', 'weight_kg'),
                'foot'
            )
        }),
        ('Market Info', {
            'fields': (
                'market_value_eur',
                'contract_expires'
            )
        }),
        ('External IDs', {
            'fields': (
                'api_id',
                'fbref_id',
                'transfermarkt_id',
                'sofascore_id'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at', 'updated_at')

    def get_market_value(self, obj):
        if obj.market_value_eur:
            if obj.market_value_eur >= 1000000:
                value = obj.market_value_eur / 1000000
                return format_html('<strong>€{:.1f}M</strong>', value)
            elif obj.market_value_eur >= 1000:
                value = obj.market_value_eur / 1000
                return format_html('€{:.0f}K', value)
            return format_html('€{:,}', obj.market_value_eur)
        return '-'
    get_market_value.short_description = 'Market Value'


@admin.register(PlayerStats)
class PlayerStatsAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'team',
        'competition',
        'season',
        'matches_played',
        'get_goals_assists',
        'get_xg_xa',
        'calculated_at'
    )
    list_filter = (
        'competition',
        'season',
        'team',
        ('calculated_at', admin.DateFieldListFilter),
    )
    search_fields = ('player__name', 'team__name')
    ordering = ('-season', '-xg')
    list_select_related = ('player', 'team', 'competition')

    fieldsets = (
        ('Basic Info', {
            'fields': ('player', 'team', 'competition', 'season', 'calculated_at')
        }),
        ('Appearances', {
            'fields': (
                ('matches_played', 'minutes_played', 'starts'),
            )
        }),
        ('Goals & Assists', {
            'fields': (
                ('goals', 'assists'),
                ('penalties_scored', 'penalties_attempted'),
                ('xg', 'npxg', 'xa'),
            )
        }),
        ('Shooting', {
            'fields': (
                ('shots_total', 'shots_on_target'),
                'shot_accuracy_pct',
            )
        }),
        ('Passing', {
            'fields': (
                ('passes_completed', 'passes_attempted'),
                'pass_completion_pct',
                ('progressive_passes', 'key_passes'),
            ),
            'classes': ('collapse',)
        }),
        ('Defensive', {
            'fields': (
                ('tackles', 'interceptions'),
                ('blocks', 'clearances'),
                'pressures',
            ),
            'classes': ('collapse',)
        }),
        ('Discipline', {
            'fields': (
                ('yellow_cards', 'red_cards'),
                ('fouls_committed', 'fouls_drawn'),
            ),
            'classes': ('collapse',)
        }),
        ('Aerial Duels', {
            'fields': (
                ('aerials_won', 'aerials_lost'),
                'aerial_win_pct',
            ),
            'classes': ('collapse',)
        }),
        ('Dribbling', {
            'fields': (
                ('dribbles_completed', 'dribbles_attempted'),
                'dribble_success_pct',
            ),
            'classes': ('collapse',)
        }),
        ('Goalkeeper Stats', {
            'fields': (
                ('saves', 'save_pct'),
                ('clean_sheets', 'goals_conceded'),
                'pens_saved',
            ),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('calculated_at',)

    def get_goals_assists(self, obj):
        return f"{obj.goals}G / {obj.assists}A"
    get_goals_assists.short_description = 'G/A'

    def get_xg_xa(self, obj):
        return format_html(
            'xG: <strong>{:.1f}</strong> | xA: <strong>{:.1f}</strong>',
            obj.xg,
            obj.xa
        )
    get_xg_xa.short_description = 'xG/xA'


@admin.register(MatchPlayerStats)
class MatchPlayerStatsAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'get_match',
        'team',
        'position',
        'started',
        'minutes_played',
        'get_goals_assists',
        'rating',
        'get_cards'
    )
    list_filter = (
        'team',
        'position',
        'started',
        'yellow_card',
        'red_card',
        ('match__utc_date', admin.DateFieldListFilter),
    )
    search_fields = ('player__name', 'match__home_team__name', 'match__away_team__name')
    ordering = ('-match__utc_date',)
    list_select_related = ('player', 'match__home_team', 'match__away_team', 'team')

    fieldsets = (
        ('Match Info', {
            'fields': ('match', 'player', 'team', 'position')
        }),
        ('Appearance', {
            'fields': (
                ('started', 'minutes_played'),
            )
        }),
        ('Performance', {
            'fields': (
                ('goals', 'assists'),
                'xg',
                'rating',
            )
        }),
        ('Stats', {
            'fields': (
                ('shots', 'shots_on_target'),
                ('passes_completed', 'passes_attempted'),
                ('tackles', 'interceptions'),
            )
        }),
        ('Cards', {
            'fields': (
                ('yellow_card', 'red_card'),
            )
        }),
    )

    def get_match(self, obj):
        try:
            home = obj.match.home_team.short_name if obj.match.home_team else '?'
            away = obj.match.away_team.short_name if obj.match.away_team else '?'
            return f"{home} vs {away}"
        except Exception:
            return "Match info unavailable"
    get_match.short_description = 'Match'

    def get_goals_assists(self, obj):
        return f"{obj.goals}G / {obj.assists}A"
    get_goals_assists.short_description = 'G/A'

    def get_cards(self, obj):
        cards = []
        if obj.yellow_card:
            cards.append('<span style="color: orange;">●</span>')
        if obj.red_card:
            cards.append('<span style="color: red;">●</span>')
        return format_html(' '.join(cards)) if cards else '-'
    get_cards.short_description = 'Cards'


@admin.register(ShotEvent)
class ShotEventAdmin(admin.ModelAdmin):
    list_display = (
        'get_match',
        'team',
        'player',
        'minute',
        'result',
        'get_xg',
        'get_location',
        'body_part',
        'situation'
    )
    list_filter = (
        'result',
        'body_part',
        'situation',
        'team',
        ('match__utc_date', admin.DateFieldListFilter),
    )
    search_fields = (
        'player__name',
        'match__home_team__name',
        'match__away_team__name'
    )
    ordering = ('-match__utc_date', 'minute')
    list_select_related = ('match__home_team', 'match__away_team', 'player', 'team', 'assisted_by')

    fieldsets = (
        ('Match Info', {
            'fields': ('match', 'team', 'player', 'minute')
        }),
        ('Shot Details', {
            'fields': (
                'result',
                'xg',
                'body_part',
                'situation',
            )
        }),
        ('Location', {
            'fields': (
                ('x', 'y'),
            )
        }),
        ('Assist', {
            'fields': ('assisted_by',)
        }),
    )

    def get_match(self, obj):
        try:
            home = obj.match.home_team.short_name if obj.match.home_team else '?'
            away = obj.match.away_team.short_name if obj.match.away_team else '?'
            date = obj.match.utc_date.strftime('%Y-%m-%d')
            return f"{home} vs {away} ({date})"
        except Exception:
            return "Match info unavailable"
    get_match.short_description = 'Match'

    def get_xg(self, obj):
        color = 'green' if obj.xg >= 0.3 else 'orange' if obj.xg >= 0.15 else 'gray'
        return format_html(
            '<span style="color: {};">{:.2f}</span>',
            color,
            obj.xg
        )
    get_xg.short_description = 'xG'

    def get_location(self, obj):
        return f"({obj.x:.0f}, {obj.y:.0f})"
    get_location.short_description = 'Coordinates'


@admin.register(TeamMarketValue)
class TeamMarketValueAdmin(admin.ModelAdmin):
    list_display = (
        'team',
        'competition',
        'season',
        'get_total_value',
        'get_avg_value',
        'squad_size',
        'avg_age',
        'get_net_transfer',
        'scraped_at'
    )
    list_filter = (
        'competition',
        'season',
        ('scraped_at', admin.DateFieldListFilter),
    )
    search_fields = ('team__name',)
    ordering = ('-season', '-total_market_value_eur')
    list_select_related = ('team', 'competition')

    fieldsets = (
        ('Basic Info', {
            'fields': ('team', 'competition', 'season', 'scraped_at')
        }),
        ('Market Value', {
            'fields': (
                'total_market_value_eur',
                'avg_player_value_eur',
            )
        }),
        ('Squad Composition', {
            'fields': (
                ('squad_size', 'avg_age'),
                'foreigners_count',
            )
        }),
        ('Transfer Activity', {
            'fields': (
                'transfer_income_eur',
                'transfer_expenditure_eur',
                'net_transfer_eur',
            )
        }),
    )

    readonly_fields = ('scraped_at',)

    def get_total_value(self, obj):
        if obj.total_market_value_eur:
            value = obj.total_market_value_eur / 1000000
            return format_html('<strong>€{:.1f}M</strong>', value)
        return '-'
    get_total_value.short_description = 'Total Value'

    def get_avg_value(self, obj):
        if obj.avg_player_value_eur:
            if obj.avg_player_value_eur >= 1000000:
                value = obj.avg_player_value_eur / 1000000
                return format_html('€{:.2f}M', value)
            elif obj.avg_player_value_eur >= 1000:
                value = obj.avg_player_value_eur / 1000
                return format_html('€{:.0f}K', value)
            return format_html('€{:,}', obj.avg_player_value_eur)
        return '-'
    get_avg_value.short_description = 'Avg Value'

    def get_net_transfer(self, obj):
        if obj.net_transfer_eur is not None:
            value = obj.net_transfer_eur / 1000000
            color = 'green' if value < 0 else 'red' if value > 0 else 'gray'
            sign = '' if value < 0 else '+'
            return format_html(
                '<span style="color: {};">{}{:.1f}M</span>',
                color,
                sign,
                value
            )
        return '-'
    get_net_transfer.short_description = 'Net Transfer'


@admin.register(PlayerInjury)
class PlayerInjuryAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'status',
        'injury_type',
        'injury_date',
        'expected_return_date',
        'matches_missed',
        'get_duration'
    )
    list_filter = (
        'status',
        ('injury_date', admin.DateFieldListFilter),
        ('expected_return_date', admin.DateFieldListFilter),
    )
    search_fields = ('player__name', 'injury_type')
    ordering = ('-injury_date',)
    list_select_related = ('player',)

    fieldsets = (
        ('Player', {
            'fields': ('player',)
        }),
        ('Injury Details', {
            'fields': (
                'injury_type',
                'status',
            )
        }),
        ('Timeline', {
            'fields': (
                'injury_date',
                'expected_return_date',
                'actual_return_date',
            )
        }),
        ('Impact', {
            'fields': ('matches_missed',)
        }),
    )

    def get_duration(self, obj):
        if obj.injury_date and obj.expected_return_date:
            duration = (obj.expected_return_date - obj.injury_date).days
            return f"{duration} days"
        elif obj.injury_date and obj.actual_return_date:
            duration = (obj.actual_return_date - obj.injury_date).days
            return format_html('<strong>{} days (actual)</strong>', duration)
        return '-'
    get_duration.short_description = 'Duration'


@admin.register(MatchIncident)
class MatchIncidentAdmin(admin.ModelAdmin):
    list_display = (
        'get_match',
        'get_time',
        'incident_type',
        'player',
        'team',
        'get_score',
        'is_home'
    )
    list_filter = (
        'incident_type',
        'is_home',
        ('match__utc_date', admin.DateFieldListFilter),
    )
    search_fields = (
        'player__name',
        'match__home_team__name',
        'match__away_team__name',
        'description'
    )
    ordering = ('-match__utc_date', 'time')
    list_select_related = ('match__home_team', 'match__away_team', 'player', 'team')

    fieldsets = (
        ('Match Info', {
            'fields': ('match', 'team', 'is_home')
        }),
        ('Incident Details', {
            'fields': (
                'incident_type',
                ('time', 'time_added'),
                'description',
            )
        }),
        ('Players Involved', {
            'fields': (
                'player',
                'assist_player',
                ('player_in', 'player_out'),
            )
        }),
        ('Score After Incident', {
            'fields': (
                ('score_home', 'score_away'),
            )
        }),
    )

    def get_match(self, obj):
        try:
            home = obj.match.home_team.short_name if obj.match.home_team else '?'
            away = obj.match.away_team.short_name if obj.match.away_team else '?'
            return f"{home} vs {away}"
        except Exception:
            return "Match info unavailable"
    get_match.short_description = 'Match'

    def get_time(self, obj):
        if obj.time_added:
            return format_html("<strong>{}'</strong> +{}", obj.time, obj.time_added)
        return format_html("<strong>{}'</strong>", obj.time)
    get_time.short_description = 'Time'

    def get_score(self, obj):
        if obj.score_home is not None and obj.score_away is not None:
            return f"{obj.score_home}-{obj.score_away}"
        return '-'
    get_score.short_description = 'Score After'


@admin.register(Injury)
class InjuryAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'team',
        'injury_type',
        'status',
        'severity',
        'start_date',
        'expected_return_date',
        'is_active',
    )
    list_filter = (
        'status',
        'severity',
        'team',
        ('start_date', admin.DateFieldListFilter),
        ('expected_return_date', admin.DateFieldListFilter),
    )
    search_fields = ('player__name', 'injury_type', 'description')
    ordering = ('-start_date',)
    list_select_related = ('player', 'team')

    fieldsets = (
        ('Player & Team', {
            'fields': ('player', 'team')
        }),
        ('Injury Details', {
            'fields': (
                'injury_type',
                ('status', 'severity'),
                'description',
            )
        }),
        ('Timeline', {
            'fields': (
                'start_date',
                'expected_return_date',
                'actual_return_date',
            )
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at', 'updated_at')
