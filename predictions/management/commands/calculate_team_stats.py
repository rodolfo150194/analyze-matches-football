"""
Comando Django para calcular estadísticas de equipos por temporada
Uso: python manage.py calculate_team_stats --seasons 2023,2024 --competitions PL,PD
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q, Avg, Count
from predictions.models import Competition, Team, Match, TeamStats


class Command(BaseCommand):
    help = 'Calcula estadísticas de equipos por temporada'

    def add_arguments(self, parser):
        parser.add_argument(
            '--seasons',
            type=str,
            help='Temporadas separadas por coma (ej: 2023,2024). Si no se especifica, calcula todas'
        )
        parser.add_argument(
            '--competitions',
            type=str,
            help='Códigos de competiciones separados por coma (ej: PL,PD). Si no se especifica, calcula todas'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar recalcular estadísticas existentes'
        )

    def handle(self, *args, **options):
        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS('CÁLCULO DE ESTADÍSTICAS DE EQUIPOS'))
        self.stdout.write("="*70)

        # Filtrar competiciones
        competitions = Competition.objects.all()
        if options['competitions']:
            comp_codes = options['competitions'].split(',')
            competitions = competitions.filter(code__in=comp_codes)
            self.stdout.write(f"Competiciones: {', '.join(comp_codes)}")
        else:
            self.stdout.write("Competiciones: Todas")

        # Filtrar temporadas
        if options['seasons']:
            seasons = [int(s) for s in options['seasons'].split(',')]
            self.stdout.write(f"Temporadas: {', '.join(str(s) for s in seasons)}")
        else:
            # Obtener todas las temporadas disponibles
            seasons = Match.objects.values_list('season', flat=True).distinct().order_by('season')
            seasons = list(seasons)
            self.stdout.write(f"Temporadas: {seasons[0]}-{seasons[-1]} ({len(seasons)} temporadas)")

        self.stdout.write("")

        total_stats = 0
        for competition in competitions:
            for season in seasons:
                # Obtener equipos que jugaron en esta competición/temporada
                teams = Team.objects.filter(
                    Q(home_matches__competition=competition, home_matches__season=season) |
                    Q(away_matches__competition=competition, away_matches__season=season)
                ).distinct()

                for team in teams:
                    # Verificar si ya existe
                    if not options['force']:
                        if TeamStats.objects.filter(team=team, competition=competition, season=season).exists():
                            continue

                    stats = self.calculate_team_stats(team, competition, season)
                    if stats:
                        total_stats += 1

        self.stdout.write("")
        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS(f'COMPLETADO: {total_stats} estadísticas calculadas'))
        self.stdout.write("="*70)

    def calculate_team_stats(self, team, competition, season):
        """Calcular estadísticas para un equipo en una temporada"""

        # Obtener todos los partidos FINISHED
        home_matches = Match.objects.filter(
            competition=competition,
            season=season,
            home_team=team,
            status='FINISHED'
        )

        away_matches = Match.objects.filter(
            competition=competition,
            season=season,
            away_team=team,
            status='FINISHED'
        )

        # Si no hay partidos, no crear stats
        total_matches = home_matches.count() + away_matches.count()
        if total_matches == 0:
            return None

        # Crear o actualizar estadísticas
        stats, created = TeamStats.objects.get_or_create(
            team=team,
            competition=competition,
            season=season,
            defaults={'calculated_at': timezone.now()}
        )

        # Actualizar timestamp
        stats.calculated_at = timezone.now()

        # Estadísticas generales
        stats.matches_played = total_matches
        stats.home_matches = home_matches.count()
        stats.away_matches = away_matches.count()

        # Inicializar contadores
        wins = 0
        draws = 0
        losses = 0
        goals_for = 0
        goals_against = 0

        home_wins = 0
        home_draws = 0
        home_losses = 0
        home_goals_for = 0
        home_goals_against = 0

        away_wins = 0
        away_draws = 0
        away_losses = 0
        away_goals_for = 0
        away_goals_against = 0

        clean_sheets = 0
        failed_to_score = 0
        btts_count = 0
        over_25_count = 0

        # Procesar partidos de local
        for match in home_matches:
            gf = match.home_score or 0
            ga = match.away_score or 0

            goals_for += gf
            goals_against += ga
            home_goals_for += gf
            home_goals_against += ga

            # Resultado
            if gf > ga:
                wins += 1
                home_wins += 1
            elif gf < ga:
                losses += 1
                home_losses += 1
            else:
                draws += 1
                home_draws += 1

            # Métricas
            if ga == 0:
                clean_sheets += 1
            if gf == 0:
                failed_to_score += 1
            if gf > 0 and ga > 0:
                btts_count += 1
            if (gf + ga) > 2.5:
                over_25_count += 1

        # Procesar partidos de visitante
        for match in away_matches:
            gf = match.away_score or 0
            ga = match.home_score or 0

            goals_for += gf
            goals_against += ga
            away_goals_for += gf
            away_goals_against += ga

            # Resultado
            if gf > ga:
                wins += 1
                away_wins += 1
            elif gf < ga:
                losses += 1
                away_losses += 1
            else:
                draws += 1
                away_draws += 1

            # Métricas
            if ga == 0:
                clean_sheets += 1
            if gf == 0:
                failed_to_score += 1
            if gf > 0 and ga > 0:
                btts_count += 1
            if (gf + ga) > 2.5:
                over_25_count += 1

        # Guardar estadísticas generales
        stats.wins = wins
        stats.draws = draws
        stats.losses = losses
        stats.goals_for = goals_for
        stats.goals_against = goals_against

        # Estadísticas de local
        stats.home_wins = home_wins
        stats.home_draws = home_draws
        stats.home_losses = home_losses
        stats.home_goals_for = home_goals_for
        stats.home_goals_against = home_goals_against

        # Estadísticas de visitante
        stats.away_wins = away_wins
        stats.away_draws = away_draws
        stats.away_losses = away_losses
        stats.away_goals_for = away_goals_for
        stats.away_goals_against = away_goals_against

        # Métricas avanzadas
        stats.avg_goals_for = goals_for / total_matches if total_matches > 0 else 0
        stats.avg_goals_against = goals_against / total_matches if total_matches > 0 else 0
        stats.clean_sheets = clean_sheets
        stats.failed_to_score = failed_to_score
        stats.btts_count = btts_count
        stats.over_25_count = over_25_count

        # Forma reciente (últimos 5 partidos)
        recent_matches = list(home_matches.order_by('-utc_date')[:5]) + \
                        list(away_matches.order_by('-utc_date')[:5])
        recent_matches = sorted(recent_matches, key=lambda x: x.utc_date, reverse=True)[:5]

        if recent_matches:
            form_points = []
            form_gf = []
            form_ga = []

            for match in recent_matches:
                if match.home_team_id == team.id:
                    gf = match.home_score or 0
                    ga = match.away_score or 0
                else:
                    gf = match.away_score or 0
                    ga = match.home_score or 0

                form_gf.append(gf)
                form_ga.append(ga)

                if gf > ga:
                    form_points.append(3)
                elif gf < ga:
                    form_points.append(0)
                else:
                    form_points.append(1)

            stats.form_points = sum(form_points) / len(form_points) if form_points else 0
            stats.form_goals_for = sum(form_gf) / len(form_gf) if form_gf else 0
            stats.form_goals_against = sum(form_ga) / len(form_ga) if form_ga else 0

        stats.save()

        action = "creada" if created else "actualizada"
        self.stdout.write(
            self.style.SUCCESS(
                f"  {team.name} ({competition.code} {season}): {stats.matches_played}J "
                f"{wins}V {draws}E {losses}D - {action}"
            )
        )

        return stats
