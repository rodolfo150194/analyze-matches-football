"""
Comando Django para calcular historial de enfrentamientos directos (Head to Head)
Uso: python manage.py calculate_head_to_head --competitions PL,PD
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from predictions.models import Competition, Team, Match, HeadToHead
import json


class Command(BaseCommand):
    help = 'Calcula historial de enfrentamientos directos entre equipos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--competitions',
            type=str,
            help='Códigos de competiciones separados por coma (ej: PL,PD). Si no se especifica, calcula todas'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar recalcular enfrentamientos existentes'
        )
        parser.add_argument(
            '--recent',
            type=int,
            default=10,
            help='Número de partidos recientes a guardar en JSON (default: 10)'
        )

    def handle(self, *args, **options):
        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS('CÁLCULO DE HEAD TO HEAD'))
        self.stdout.write("="*70)

        # Filtrar competiciones
        competitions = Competition.objects.all()
        if options['competitions']:
            comp_codes = options['competitions'].split(',')
            competitions = competitions.filter(code__in=comp_codes)
            self.stdout.write(f"Competiciones: {', '.join(comp_codes)}")
        else:
            self.stdout.write("Competiciones: Todas")

        self.stdout.write(f"Partidos recientes a guardar: {options['recent']}")
        self.stdout.write("")

        total_h2h = 0

        for competition in competitions:
            self.stdout.write(f"\n{competition.name} ({competition.code}):")

            # Obtener todos los equipos de esta competición
            teams = Team.objects.filter(
                Q(home_matches__competition=competition) |
                Q(away_matches__competition=competition)
            ).distinct()

            teams_list = list(teams)
            self.stdout.write(f"  Equipos: {len(teams_list)}")

            # Calcular H2H para cada par de equipos
            for i, team1 in enumerate(teams_list):
                for team2 in teams_list[i+1:]:
                    # Verificar si ya existe
                    if not options['force']:
                        exists = HeadToHead.objects.filter(
                            Q(team1=team1, team2=team2) | Q(team1=team2, team2=team1)
                        ).exists()
                        if exists:
                            continue

                    h2h = self.calculate_h2h(team1, team2, competition, options['recent'])
                    if h2h:
                        total_h2h += 1

            self.stdout.write(self.style.SUCCESS(f"  Completado"))

        self.stdout.write("")
        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS(f'COMPLETADO: {total_h2h} enfrentamientos calculados'))
        self.stdout.write("="*70)

    def calculate_h2h(self, team1, team2, competition, recent_limit):
        """Calcular historial entre dos equipos"""

        # Obtener todos los partidos entre estos equipos
        matches = Match.objects.filter(
            Q(home_team=team1, away_team=team2) | Q(home_team=team2, away_team=team1),
            competition=competition,
            status='FINISHED'
        ).order_by('-utc_date')

        total_matches = matches.count()

        # Si no hay enfrentamientos, no crear registro
        if total_matches == 0:
            return None

        # Normalizar: team1 siempre es el que tiene ID menor (para evitar duplicados)
        if team1.id > team2.id:
            team1, team2 = team2, team1

        # Crear o actualizar H2H
        h2h, created = HeadToHead.objects.get_or_create(
            team1=team1,
            team2=team2,
            defaults={'calculated_at': timezone.now()}
        )

        # Actualizar timestamp
        h2h.calculated_at = timezone.now()

        # Inicializar contadores
        team1_wins = 0
        team2_wins = 0
        draws = 0
        team1_goals = 0
        team2_goals = 0

        recent_matches_data = []

        for match in matches:
            # Determinar quién jugó de local
            if match.home_team_id == team1.id:
                # team1 local, team2 visitante
                t1_score = match.home_score or 0
                t2_score = match.away_score or 0
                t1_venue = 'H'
            else:
                # team2 local, team1 visitante
                t1_score = match.away_score or 0
                t2_score = match.home_score or 0
                t1_venue = 'A'

            team1_goals += t1_score
            team2_goals += t2_score

            # Resultado
            if t1_score > t2_score:
                team1_wins += 1
                result = 'W1'  # Win team1
            elif t1_score < t2_score:
                team2_wins += 1
                result = 'W2'  # Win team2
            else:
                draws += 1
                result = 'D'   # Draw

            # Guardar en recientes (limitar cantidad)
            if len(recent_matches_data) < recent_limit:
                recent_matches_data.append({
                    'date': match.utc_date.strftime('%Y-%m-%d'),
                    'team1_venue': t1_venue,  # H o A
                    'team1_score': t1_score,
                    'team2_score': t2_score,
                    'result': result,  # W1, W2, o D
                    'competition': competition.code,
                    'season': match.season
                })

        # Guardar estadísticas
        h2h.total_matches = total_matches
        h2h.team1_wins = team1_wins
        h2h.team2_wins = team2_wins
        h2h.draws = draws
        h2h.team1_goals = team1_goals
        h2h.team2_goals = team2_goals
        h2h.recent_matches = json.dumps(recent_matches_data)

        h2h.save()

        action = "creado" if created else "actualizado"
        self.stdout.write(
            f"    {team1.short_name} vs {team2.short_name}: "
            f"{total_matches} partidos ({team1_wins}-{draws}-{team2_wins}) - {action}"
        )

        return h2h
