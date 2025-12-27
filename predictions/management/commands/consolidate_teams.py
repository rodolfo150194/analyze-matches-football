"""
Consolidate duplicate teams in database

This command merges duplicate teams that represent the same entity
but were created for different competitions (e.g., Barcelona in La Liga and Champions League)
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from predictions.models import Team, Match, Player, TeamStats, TeamMarketValue
from predictions.scrapers.utils import fuzzy_match_team
from thefuzz import fuzz


class Command(BaseCommand):
    help = 'Consolidate duplicate teams in database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview consolidation without making changes'
        )
        parser.add_argument(
            '--threshold',
            type=int,
            default=90,
            help='Fuzzy matching threshold (default: 90)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        threshold = options['threshold']

        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS('CONSOLIDACION DE EQUIPOS DUPLICADOS'))
        self.stdout.write("=" * 80)

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] No se realizaran cambios"))

        self.stdout.write("")

        # Get all teams
        all_teams = list(Team.objects.all().order_by('id'))

        consolidated = 0
        processed = set()

        for team in all_teams:
            if team.id in processed:
                continue

            # Find similar teams
            similar_teams = []
            for other_team in all_teams:
                if other_team.id == team.id or other_team.id in processed:
                    continue

                # Check by api_id if both have it
                if team.api_id and other_team.api_id:
                    # Skip if same api_id (shouldn't happen due to unique constraint)
                    if team.api_id == other_team.api_id:
                        similar_teams.append(other_team)
                        continue

                # Check by name similarity
                ratio = fuzz.ratio(team.name.lower(), other_team.name.lower())
                if ratio >= threshold:
                    similar_teams.append(other_team)

            if similar_teams:
                # Filter out false positives (exact name match only)
                exact_matches = [t for t in similar_teams if t.name.lower() == team.name.lower()]

                if not exact_matches:
                    continue  # Skip if no exact name matches

                self.stdout.write(f"\n[DUPLICADO ENCONTRADO] {team.name} (ID: {team.id}, api_id: {team.api_id})")
                self.stdout.write(f"  Equipos similares:")
                for similar in exact_matches:
                    self.stdout.write(f"    - {similar.name} (ID: {similar.id}, api_id: {similar.api_id}, Competition: {similar.competition.code if similar.competition else 'None'})")

                similar_teams = exact_matches  # Use only exact matches

                if not dry_run:
                    # Consolidate: keep the one with api_id, or the first one
                    keeper = team
                    if not team.api_id:
                        for similar in similar_teams:
                            if similar.api_id:
                                keeper = similar
                                break

                    # Merge all similar teams into keeper
                    teams_to_merge = [t for t in similar_teams if t.id != keeper.id]
                    self.merge_teams(keeper, teams_to_merge)

                    processed.add(keeper.id)
                    for t in teams_to_merge:
                        processed.add(t.id)

                    consolidated += 1
                    self.stdout.write(self.style.SUCCESS(f"  [OK] Consolidado en {keeper.name} (ID: {keeper.id})"))
                else:
                    self.stdout.write(self.style.WARNING("  [DRY-RUN] Se consolidarian"))

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS('RESUMEN'))
        self.stdout.write("=" * 80)
        self.stdout.write(f"Equipos consolidados: {consolidated}")
        self.stdout.write(f"Equipos antes: {len(all_teams)}")
        if not dry_run:
            self.stdout.write(f"Equipos despues: {Team.objects.count()}")
        self.stdout.write("=" * 80)

    def merge_teams(self, keeper, teams_to_merge):
        """Merge multiple teams into a single team"""
        with transaction.atomic():
            for team in teams_to_merge:
                # Update all matches
                Match.objects.filter(home_team=team).update(home_team=keeper)
                Match.objects.filter(away_team=team).update(away_team=keeper)

                # Update players
                Player.objects.filter(team=team).update(team=keeper)

                # Update team stats (keep both if different competition/season)
                TeamStats.objects.filter(team=team).update(team=keeper)

                # Update market values
                TeamMarketValue.objects.filter(team=team).update(team=keeper)

                # Merge api_ids if needed
                if team.api_id and not keeper.api_id:
                    keeper.api_id = team.api_id
                    keeper.save()

                # Delete the duplicate team
                team.delete()

                self.stdout.write(f"    Eliminado: {team.name} (ID: {team.id})")
