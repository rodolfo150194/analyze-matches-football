"""
Comando Django para calcular parámetros Poisson/Dixon-Coles de equipos
Estima fuerzas de ataque/defensa usando Maximum Likelihood Estimation (MLE)
Uso: python manage.py calculate_poisson_params --competitions PL,PD --seasons 2023,2024
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Avg, Count
from predictions.models import Competition, Team, Match, PoissonParams
from predictions.ml.poisson import estimate_team_strengths, DixonColesModel
from collections import defaultdict


class Command(BaseCommand):
    help = 'Calcula parámetros Poisson/Dixon-Coles para equipos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--seasons',
            type=str,
            help='Temporadas separadas por coma (ej: 2023,2024). Si no se especifica, calcula todas'
        )
        parser.add_argument(
            '--competitions',
            type=str,
            help='Códigos de competiciones separados por coma (ej: PL,PD,BL1)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Borrar y recalcular todos los parámetros existentes'
        )
        parser.add_argument(
            '--model',
            type=str,
            default='dixon-coles',
            choices=['poisson', 'dixon-coles'],
            help='Modelo a usar: poisson (básico) o dixon-coles (con correlación)'
        )
        parser.add_argument(
            '--min-matches',
            type=int,
            default=10,
            help='Mínimo de partidos para calcular parámetros (default: 10)'
        )

    def handle(self, *args, **options):
        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS('CÁLCULO DE PARÁMETROS POISSON/DIXON-COLES'))
        self.stdout.write("="*70)

        model_type = options['model']
        min_matches = options['min_matches']
        use_dixon_coles = (model_type == 'dixon-coles')

        self.stdout.write(f"Modelo: {model_type.upper()}")
        self.stdout.write(f"Mínimo de partidos: {min_matches}")

        # Filtrar competiciones
        competitions = Competition.objects.all()
        if options['competitions']:
            comp_codes = options['competitions'].split(',')
            competitions = competitions.filter(code__in=comp_codes)
            self.stdout.write(f"Competiciones: {', '.join(comp_codes)}")
        else:
            self.stdout.write("Competiciones: Todas")

        # Filtrar temporadas
        seasons_filter = None
        if options['seasons']:
            seasons_filter = [int(s) for s in options['seasons'].split(',')]
            self.stdout.write(f"Temporadas: {', '.join(map(str, seasons_filter))}")
        else:
            self.stdout.write("Temporadas: Todas disponibles")

        # Borrar parámetros existentes si --force
        if options['force']:
            deleted_count = PoissonParams.objects.all().count()
            PoissonParams.objects.all().delete()
            self.stdout.write(f"Parámetros eliminados: {deleted_count}")

        self.stdout.write("")
        self.stdout.write("="*70)

        total_params_created = 0
        total_params_updated = 0

        # Procesar cada competición
        for competition in competitions:
            self.stdout.write(f"\nCompetición: {competition.name} ({competition.code})")
            self.stdout.write("-"*70)

            # Obtener temporadas disponibles para esta competición
            seasons = Match.objects.filter(
                competition=competition,
                status='FINISHED'
            ).values_list('season', flat=True).distinct().order_by('season')

            if seasons_filter:
                seasons = [s for s in seasons if s in seasons_filter]

            # Procesar cada temporada
            for season in seasons:
                # Obtener partidos terminados de esta temporada/competición
                matches = Match.objects.filter(
                    competition=competition,
                    season=season,
                    status='FINISHED',
                    home_score__isnull=False,
                    away_score__isnull=False
                ).select_related('home_team', 'away_team').order_by('utc_date')

                match_count = matches.count()

                if match_count < min_matches:
                    self.stdout.write(
                        f"  {season}: Solo {match_count} partidos (mínimo: {min_matches}) - OMITIDO"
                    )
                    continue

                self.stdout.write(f"  {season}: {match_count} partidos")

                # Preparar datos para estimate_team_strengths
                match_data = []
                teams_in_season = set()

                for match in matches:
                    match_data.append({
                        'home_team_id': match.home_team_id,
                        'away_team_id': match.away_team_id,
                        'home_goals': match.home_score,
                        'away_goals': match.away_score,
                    })
                    teams_in_season.add(match.home_team_id)
                    teams_in_season.add(match.away_team_id)

                # Estimar parámetros usando MLE
                try:
                    result = estimate_team_strengths(match_data, use_dixon_coles=use_dixon_coles)

                    team_params = result['teams']  # Clave correcta del resultado
                    home_advantage = result['home_advantage']
                    rho = result.get('rho', -0.13)

                    self.stdout.write(
                        f"    Home advantage: {home_advantage:.3f}, "
                        f"Rho: {rho:.3f} (Dixon-Coles)" if use_dixon_coles else ""
                    )

                    # Calcular estadísticas de goles por equipo para metadata
                    team_stats = defaultdict(lambda: {'scored': [], 'conceded': []})

                    for match in matches:
                        team_stats[match.home_team_id]['scored'].append(match.home_score)
                        team_stats[match.home_team_id]['conceded'].append(match.away_score)
                        team_stats[match.away_team_id]['scored'].append(match.away_score)
                        team_stats[match.away_team_id]['conceded'].append(match.home_score)

                    # Guardar parámetros para cada equipo
                    created_count = 0
                    updated_count = 0

                    for team_id in teams_in_season:
                        if team_id not in team_params:
                            continue

                        params = team_params[team_id]
                        stats = team_stats[team_id]

                        avg_scored = sum(stats['scored']) / len(stats['scored']) if stats['scored'] else 0
                        avg_conceded = sum(stats['conceded']) / len(stats['conceded']) if stats['conceded'] else 0

                        # Crear o actualizar PoissonParams
                        obj, created = PoissonParams.objects.update_or_create(
                            team_id=team_id,
                            competition=competition,
                            season=season,
                            defaults={
                                'attack_strength': params['attack'],
                                'defense_strength': params['defense'],
                                'matches_played': len(stats['scored']),
                                'avg_goals_scored': avg_scored,
                                'avg_goals_conceded': avg_conceded,
                                'calculated_at': timezone.now(),
                            }
                        )

                        if created:
                            created_count += 1
                            total_params_created += 1
                        else:
                            updated_count += 1
                            total_params_updated += 1

                    self.stdout.write(
                        f"    Equipos procesados: {len(teams_in_season)} "
                        f"(Creados: {created_count}, Actualizados: {updated_count})"
                    )

                    # Mostrar top 5 ataque y defensa
                    sorted_attack = sorted(
                        team_params.items(),
                        key=lambda x: x[1]['attack'],
                        reverse=True
                    )[:5]

                    sorted_defense = sorted(
                        team_params.items(),
                        key=lambda x: x[1]['defense']
                    )[:5]

                    self.stdout.write(f"\n    Top 5 Ataque:")
                    for team_id, params in sorted_attack:
                        try:
                            team = Team.objects.get(id=team_id)
                            self.stdout.write(
                                f"      {team.name[:30]:30s} - ATT: {params['attack']:.3f}"
                            )
                        except Team.DoesNotExist:
                            pass

                    self.stdout.write(f"\n    Top 5 Defensa (menor es mejor):")
                    for team_id, params in sorted_defense:
                        try:
                            team = Team.objects.get(id=team_id)
                            self.stdout.write(
                                f"      {team.name[:30]:30s} - DEF: {params['defense']:.3f}"
                            )
                        except Team.DoesNotExist:
                            pass

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"    ERROR al calcular parámetros: {str(e)}")
                    )
                    continue

        # Resumen final
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS('RESUMEN'))
        self.stdout.write("="*70)
        self.stdout.write(f"Parámetros creados: {total_params_created}")
        self.stdout.write(f"Parámetros actualizados: {total_params_updated}")
        self.stdout.write(f"Total: {total_params_created + total_params_updated}")

        # Estadísticas generales
        total_params = PoissonParams.objects.count()
        total_teams = PoissonParams.objects.values('team').distinct().count()

        self.stdout.write(f"\nEstadísticas generales:")
        self.stdout.write(f"  Total parámetros en BD: {total_params}")
        self.stdout.write(f"  Equipos únicos: {total_teams}")

        # Promedios de ataque/defensa por competición
        self.stdout.write(f"\nPromedios por competición:")
        for competition in competitions:
            avg_attack = PoissonParams.objects.filter(
                competition=competition
            ).aggregate(Avg('attack_strength'))['attack_strength__avg']

            avg_defense = PoissonParams.objects.filter(
                competition=competition
            ).aggregate(Avg('defense_strength'))['defense_strength__avg']

            if avg_attack:
                self.stdout.write(
                    f"  {competition.code}: ATT={avg_attack:.3f}, DEF={avg_defense:.3f}"
                )

        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS('CÁLCULO COMPLETADO'))
        self.stdout.write("="*70)
