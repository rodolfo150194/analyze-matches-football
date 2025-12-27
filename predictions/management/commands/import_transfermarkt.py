"""
Import Transfermarkt Command

Imports squad market values and transfer activity from Transfermarkt.com

This command:
1. Scrapes team market values (total squad value, avg player value)
2. Scrapes squad composition (size, avg age, foreigners)
3. Optionally scrapes individual player market values
4. Optionally scrapes transfer activity (income, expenditure, net spend)

Usage:
    # Import market values for Premier League 2024
    python manage.py import_transfermarkt --competitions PL --seasons 2024

    # Import with transfer activity
    python manage.py import_transfermarkt --competitions PL --seasons 2024 --import-type all

    # Import only market values (faster)
    python manage.py import_transfermarkt --competitions PL,PD --seasons 2024 --import-type market-values

    # Dry run (preview without saving)
    python manage.py import_transfermarkt --competitions PL --seasons 2024 --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from predictions.models import Competition, Team, TeamMarketValue, Player
from predictions.scrapers.transfermarkt_scraper import TransfermarktScraper
from predictions.scrapers.utils import fuzzy_match_team, fuzzy_match_player


class Command(BaseCommand):
    help = 'Import market values and transfer data from Transfermarkt.com'

    def add_arguments(self, parser):
        parser.add_argument(
            '--competitions',
            type=str,
            default='PL',
            help='Comma-separated competition codes (PL,PD,BL1,SA,FL1)'
        )
        parser.add_argument(
            '--seasons',
            type=str,
            required=True,
            help='Comma-separated season years (2023,2024)'
        )
        parser.add_argument(
            '--import-type',
            type=str,
            choices=['market-values', 'transfers', 'all'],
            default='market-values',
            help='What to import (market-values: faster, all: complete)'
        )
        parser.add_argument(
            '--update-player-values',
            action='store_true',
            help='Update individual player market values (slower, requires scraping each team)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-import (overwrite existing data)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview import without saving to database'
        )

    def handle(self, *args, **options):
        # Parse arguments
        competitions = options['competitions'].split(',')
        seasons = [int(s) for s in options['seasons'].split(',')]
        import_type = options['import_type']
        update_player_values = options['update_player_values']
        force = options['force']
        dry_run = options['dry_run']

        # Header
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS('IMPORTACIÓN DESDE TRANSFERMARKT'))
        self.stdout.write("=" * 80)
        self.stdout.write(f"Competiciones: {', '.join(competitions)}")
        self.stdout.write(f"Temporadas: {', '.join(map(str, seasons))}")
        self.stdout.write(f"Tipo de importación: {import_type}")
        if update_player_values:
            self.stdout.write("Actualizando valores individuales de jugadores")
        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] No se guardara nada"))
        if force:
            self.stdout.write(self.style.WARNING("[FORCE] Sobreescribira datos existentes"))
        self.stdout.write("")

        # Initialize scraper
        scraper = TransfermarktScraper()

        # Counters
        total_teams_processed = 0
        total_values_created = 0
        total_values_updated = 0
        total_players_updated = 0

        # Process each competition and season
        for comp_code in competitions:
            for season in seasons:
                self.stdout.write(f"\n{comp_code} - Temporada {season}/{season + 1}")
                self.stdout.write("=" * 80)

                result = self.import_season(
                    scraper, comp_code, season, import_type,
                    update_player_values, force, dry_run
                )

                if result:
                    total_teams_processed += result.get('teams_processed', 0)
                    total_values_created += result.get('values_created', 0)
                    total_values_updated += result.get('values_updated', 0)
                    total_players_updated += result.get('players_updated', 0)

        # Summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS('RESUMEN'))
        self.stdout.write("=" * 80)
        self.stdout.write(f"Equipos procesados: {total_teams_processed}")
        self.stdout.write(f"Valuaciones creadas: {total_values_created}")
        self.stdout.write(f"Valuaciones actualizadas: {total_values_updated}")
        if update_player_values:
            self.stdout.write(f"Jugadores actualizados: {total_players_updated}")
        self.stdout.write("=" * 80)

    def import_season(self, scraper, comp_code, season, import_type,
                      update_player_values, force, dry_run):
        """Import market values for one competition/season"""

        try:
            # Get competition
            competition = Competition.objects.get(code=comp_code)
        except Competition.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"  [ERROR] Competición {comp_code} no encontrada"))
            return None

        result = {
            'teams_processed': 0,
            'values_created': 0,
            'values_updated': 0,
            'players_updated': 0,
        }

        # Get league market values
        self.stdout.write("\n  [MARKET VALUES] Scraping market values...")

        teams_data = scraper.get_league_market_values(comp_code, season)

        if not teams_data:
            self.stdout.write(self.style.WARNING("  [WARN] No se encontraron datos"))
            return result

        self.stdout.write(f"  [OK] {len(teams_data)} equipos encontrados")

        # Get existing teams for fuzzy matching
        existing_teams = Team.objects.filter(competition=competition)

        # Process each team
        for team_data in teams_data:
            try:
                team_result = self.process_team_market_value(
                    team_data, competition, season, existing_teams,
                    scraper, import_type, update_player_values, force, dry_run
                )

                result['teams_processed'] += 1

                if team_result.get('created'):
                    result['values_created'] += 1
                elif team_result.get('updated'):
                    result['values_updated'] += 1

                result['players_updated'] += team_result.get('players_updated', 0)

            except Exception as e:
                team_name = team_data.get('team_name', 'Unknown')
                self.stdout.write(
                    self.style.WARNING(f"  [WARN] Error procesando {team_name}: {e}")
                )
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"  [OK] {result['values_created']} creados, "
                f"{result['values_updated']} actualizados"
            )
        )

        return result

    def process_team_market_value(self, team_data, competition, season, existing_teams,
                                   scraper, import_type, update_player_values, force, dry_run):
        """
        Process a single team's market value data

        Returns:
            Dict with 'created', 'updated', 'players_updated'
        """
        result = {'created': False, 'updated': False, 'players_updated': 0}

        team_name = team_data.get('team_name', '')

        # Fuzzy match team
        team, score = fuzzy_match_team(team_name, existing_teams, threshold=75)

        if not team:
            self.stdout.write(
                self.style.WARNING(f"    [SKIP] No se pudo matchear: {team_name}")
            )
            return result

        if score < 90:
            self.stdout.write(
                f"    [MATCH] {team_name} -> {team.name} ({score}%)"
            )

        # Check if TeamMarketValue already exists
        existing_value = TeamMarketValue.objects.filter(
            team=team,
            competition=competition,
            season=season
        ).first()

        if existing_value and not force:
            return result

        # Extract data
        total_value = team_data.get('total_market_value_eur', 0)
        avg_value = team_data.get('avg_player_value_eur', 0)
        squad_size = team_data.get('squad_size', 0)
        avg_age = team_data.get('avg_age', 0)
        foreigners = team_data.get('foreigners_count', 0)

        if not dry_run:
            with transaction.atomic():
                # Create or update TeamMarketValue
                market_value, created = TeamMarketValue.objects.update_or_create(
                    team=team,
                    competition=competition,
                    season=season,
                    defaults={
                        'total_market_value_eur': total_value,
                        'avg_player_value_eur': avg_value,
                        'squad_size': squad_size,
                        'avg_age': avg_age,
                        'foreigners_count': foreigners,
                        'scraped_at': timezone.now(),
                    }
                )

                result['created'] = created
                result['updated'] = not created

                # Get transfer data if requested
                if import_type in ['transfers', 'all']:
                    team_id = team_data.get('team_id')
                    if team_id:
                        transfer_data = scraper.get_team_transfers(team_id, season)

                        if transfer_data:
                            market_value.transfer_income_eur = transfer_data.get('transfer_income_eur', 0)
                            market_value.transfer_expenditure_eur = transfer_data.get('transfer_expenditure_eur', 0)
                            market_value.net_transfer_eur = transfer_data.get('net_transfer_eur', 0)
                            market_value.save()

                # Update individual player values if requested
                if update_player_values:
                    team_id = team_data.get('team_id')
                    if team_id:
                        players_updated = self.update_player_values(
                            scraper, team_id, team, season, dry_run
                        )
                        result['players_updated'] = players_updated

        return result

    def update_player_values(self, scraper, team_id, team, season, dry_run):
        """
        Update individual player market values

        Args:
            scraper: TransfermarktScraper instance
            team_id: Transfermarkt team ID
            team: Team model instance
            season: Season year
            dry_run: Whether to actually save

        Returns:
            Number of players updated
        """
        players_data = scraper.get_team_squad_values(team_id, season)

        if not players_data:
            return 0

        updated_count = 0
        existing_players = Player.objects.filter(team=team)

        for player_data in players_data:
            player_name = player_data.get('player_name', '')
            market_value = player_data.get('market_value_eur', 0)

            if not player_name or market_value == 0:
                continue

            # Fuzzy match player
            player, score = fuzzy_match_player(player_name, existing_players, threshold=85)

            if player and not dry_run:
                # Update market value
                player.market_value_eur = market_value

                # Update Transfermarkt ID if available
                player_id = player_data.get('player_id')
                if player_id and not player.transfermarkt_id:
                    player.transfermarkt_id = int(player_id)

                player.save()
                updated_count += 1

        return updated_count
