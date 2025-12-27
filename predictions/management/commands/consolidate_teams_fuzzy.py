"""
Consolidate duplicate teams using FUZZY matching

This command merges duplicate teams using fuzzy name matching
(e.g., "Leicester" and "Leicester City", "Wolves" and "Wolverhampton")
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from predictions.models import Team, Match, Player, TeamStats, TeamMarketValue
from thefuzz import fuzz


class Command(BaseCommand):
    help = 'Consolidate duplicate teams using fuzzy name matching'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview consolidation without making changes'
        )
        parser.add_argument(
            '--threshold',
            type=int,
            default=85,
            help='Fuzzy matching threshold (default: 85, higher = stricter)'
        )
        parser.add_argument(
            '--competition',
            type=str,
            help='Only consolidate teams in this competition (e.g., PL)'
        )
        parser.add_argument(
            '--cross-competition',
            action='store_true',
            help='Allow consolidation across different competitions (e.g., Bayern in BL1 and CL)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        threshold = options['threshold']
        comp_filter = options['competition']
        cross_comp = options['cross_competition']

        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS('CONSOLIDACION DE EQUIPOS DUPLICADOS (FUZZY)'))
        self.stdout.write("=" * 80)
        self.stdout.write(f"Threshold: {threshold}")

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] No se realizaran cambios"))

        if comp_filter:
            self.stdout.write(f"Competicion: {comp_filter}")

        if cross_comp:
            self.stdout.write(self.style.WARNING("MODO CROSS-COMPETITION: Consolidara entre competiciones"))

        self.stdout.write("")

        # Get teams
        if comp_filter:
            all_teams = list(Team.objects.filter(competition__code=comp_filter).order_by('id'))
        else:
            all_teams = list(Team.objects.all().order_by('id'))

        self.stdout.write(f"Total equipos a analizar: {len(all_teams)}")
        self.stdout.write("")

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

                # Skip if different competition (unless --competition or --cross-competition was specified)
                if not comp_filter and not cross_comp:
                    if team.competition_id != other_team.competition_id:
                        continue

                # Check by name similarity using multiple methods
                ratio_simple = fuzz.ratio(team.name.lower(), other_team.name.lower())
                ratio_partial = fuzz.partial_ratio(team.name.lower(), other_team.name.lower())
                ratio_token = fuzz.token_set_ratio(team.name.lower(), other_team.name.lower())

                # Use the highest ratio
                max_ratio = max(ratio_simple, ratio_partial, ratio_token)

                if max_ratio >= threshold:
                    similar_teams.append({
                        'team': other_team,
                        'ratio': max_ratio,
                        'method': 'simple' if max_ratio == ratio_simple else
                                  'partial' if max_ratio == ratio_partial else 'token'
                    })

            if similar_teams:
                self.stdout.write(f"\n[DUPLICADO ENCONTRADO] {team.name} (ID: {team.id}, api_id: {team.api_id})")
                self.stdout.write(f"  Equipos similares:")
                for item in similar_teams:
                    similar = item['team']
                    ratio = item['ratio']
                    method = item['method']
                    self.stdout.write(
                        f"    - {similar.name} (ID: {similar.id}, api_id: {similar.api_id}, "
                        f"similarity: {ratio}%, method: {method})"
                    )

                if not dry_run:
                    # Strategy: keep the one with api_id, or the one with the longer name
                    # (longer name is usually more complete, e.g., "Leicester City" > "Leicester")
                    teams_list = [team] + [item['team'] for item in similar_teams]

                    # Prefer team with api_id
                    keeper = None
                    for t in teams_list:
                        if t.api_id:
                            keeper = t
                            break

                    # If none have api_id, keep the one with the longest name
                    if not keeper:
                        keeper = max(teams_list, key=lambda t: len(t.name))

                    # Merge all others into keeper
                    teams_to_merge = [t for t in teams_list if t.id != keeper.id]
                    self.merge_teams(keeper, teams_to_merge)

                    processed.add(keeper.id)
                    for t in teams_to_merge:
                        processed.add(t.id)

                    consolidated += 1
                    self.stdout.write(self.style.SUCCESS(f"  [OK] Consolidado en {keeper.name} (ID: {keeper.id})"))
                else:
                    # Show what would be kept
                    teams_list = [team] + [item['team'] for item in similar_teams]
                    keeper = None
                    for t in teams_list:
                        if t.api_id:
                            keeper = t
                            break
                    if not keeper:
                        keeper = max(teams_list, key=lambda t: len(t.name))

                    self.stdout.write(self.style.WARNING(f"  [DRY-RUN] Se mantendria: {keeper.name} (ID: {keeper.id})"))
                    for t in teams_list:
                        if t.id != keeper.id:
                            self.stdout.write(f"           Se eliminaria: {t.name} (ID: {t.id})")

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS('RESUMEN'))
        self.stdout.write("=" * 80)
        self.stdout.write(f"Equipos consolidados: {consolidated}")
        self.stdout.write(f"Equipos antes: {len(all_teams)}")
        if not dry_run:
            if comp_filter:
                after = Team.objects.filter(competition__code=comp_filter).count()
            else:
                after = Team.objects.count()
            self.stdout.write(f"Equipos despues: {after}")
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

                # Handle team stats carefully to avoid unique constraint violations
                # Delete stats for the team being merged if keeper already has stats for same comp/season
                team_stats = TeamStats.objects.filter(team=team)
                for stat in team_stats:
                    # Check if keeper already has stats for this comp/season
                    keeper_has_stat = TeamStats.objects.filter(
                        team=keeper,
                        competition=stat.competition,
                        season=stat.season
                    ).exists()

                    if keeper_has_stat:
                        # Keeper already has this stat, delete the duplicate
                        stat.delete()
                    else:
                        # Keeper doesn't have this stat, update to keeper
                        stat.team = keeper
                        stat.save()

                # Update market values
                TeamMarketValue.objects.filter(team=team).update(team=keeper)

                # Merge api_ids if needed
                if team.api_id and not keeper.api_id:
                    keeper.api_id = team.api_id
                    keeper.save()

                # Delete the duplicate team
                team.delete()

                self.stdout.write(f"    Eliminado: {team.name} (ID: {team.id})")
