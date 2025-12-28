
"""
Complete SofaScore Import Command

Imports all available data from SofaScore API in a unified way:
- Competitions (update with SofaScore tournament IDs)
- Teams (no duplicates, using global api_id)
- Matches (with scores, dates, status)
- Match statistics (shots, corners, possession, xG, etc.)
- Players (linked to unique teams)
- Player statistics (xG, xA, rating, passes, tackles, etc.)
- Team standings/classification

Usage:
    python manage.py import_sofascore_complete --competitions PL --seasons 2024 --all-data
    python manage.py import_sofascore_complete --competitions PL,CL --seasons 2023,2024
    python manage.py import_sofascore_complete --competitions CL --seasons 2024 --teams-only
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from asgiref.sync import sync_to_async
from predictions.models import Competition, Team, Match, Player, PlayerStats, TeamStats, MatchPlayerStats
from predictions.sofascore_api import SofascoreAPI
from predictions.scrapers.utils import safe_int, safe_float
import asyncio
from datetime import datetime
import pytz
import json
import os


# SofaScore Tournament IDs
SOFASCORE_TOURNAMENT_IDS = {
    'PL': 17,      # Premier League
    'PD': 8,       # La Liga
    'BL1': 35,     # Bundesliga
    'SA': 23,      # Serie A
    'FL1': 34,     # Ligue 1
    'CL': 7,       # Champions League
}

# Mapping from competition name patterns to codes
COMPETITION_NAME_MAPPING = {
    'Premier League': 'PL',
    'LaLiga': 'PD',
    'Primera Division': 'PD',  # Old La Liga name
    'Bundesliga': 'BL1',
    'Serie A': 'SA',
    'Ligue 1': 'FL1',
    'UEFA Champions League': 'CL',
}


def load_season_ids():
    """Load Season IDs from IDS_SOFASCORE.json"""
    json_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'IDS_SOFASCORE.json')

    if not os.path.exists(json_path):
        return {}

    with open(json_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        # Remove trailing comma and brace if exists
        if content.endswith(',\n   }'):
            content = content[:-6] + '\n   }'
        # Wrap in array if not wrapped
        if not content.startswith('['):
            content = '[' + content
        if not content.endswith(']'):
            content = content + ']'

        data = json.loads(content)

    # Parse into organized structure: {comp_code: {year: season_id}}
    season_ids = {}

    for item in data:
        name = item.get('name', '')
        year_str = item.get('year', '')
        season_id = item.get('id')

        if not name or not year_str or not season_id:
            continue

        # Extract competition code from name
        comp_code = None
        for pattern, code in COMPETITION_NAME_MAPPING.items():
            if pattern in name:
                comp_code = code
                break

        if not comp_code:
            continue

        # Extract year from year_str (e.g., "24/25" -> 2024)
        year_parts = year_str.split('/')
        if len(year_parts) == 2:
            first_year = int(year_parts[0])
            # Convert to full year (24 -> 2024, 15 -> 2015)
            if first_year < 100:
                full_year = 2000 + first_year
            else:
                full_year = first_year

            if comp_code not in season_ids:
                season_ids[comp_code] = {}

            season_ids[comp_code][full_year] = season_id

    return season_ids


# Load Season IDs dynamically from JSON
SOFASCORE_SEASON_IDS = load_season_ids()


class Command(BaseCommand):
    help = 'Complete unified import from SofaScore API'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job_id = None

    async def update_progress(self, percentage, step):
        """Update progress in ImportJob if job_id is set"""
        if self.job_id:
            try:
                from predictions.models import ImportJob

                # Use sync_to_async to call Django ORM from async context
                def _update():
                    job = ImportJob.objects.get(pk=self.job_id)
                    job.update_progress(percentage, step)

                await sync_to_async(_update)()
            except ImportJob.DoesNotExist:
                pass

    def add_arguments(self, parser):
        parser.add_argument(
            '--competitions',
            type=str,
            required=True,
            help='Comma-separated competition codes (PL,PD,BL1,SA,FL1,CL)'
        )
        parser.add_argument(
            '--seasons',
            type=str,
            required=True,
            help='Comma-separated season years (2023,2024)'
        )
        parser.add_argument(
            '--all-data',
            action='store_true',
            help='Import all data (teams, matches, stats, players)'
        )
        parser.add_argument(
            '--teams-only',
            action='store_true',
            help='Only import teams'
        )
        parser.add_argument(
            '--matches-only',
            action='store_true',
            help='Only import matches'
        )
        parser.add_argument(
            '--players-only',
            action='store_true',
            help='Only import players and player stats'
        )
        parser.add_argument(
            '--standings-only',
            action='store_true',
            help='Only import team standings/classification'
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
        parser.add_argument(
            '--job-id',
            type=int,
            required=False,
            help='ImportJob ID for progress tracking'
        )

    def handle(self, *args, **options):
        # Parse arguments
        competitions = options['competitions'].split(',')
        seasons = [int(s) for s in options['seasons'].split(',')]
        all_data = options['all_data']
        teams_only = options['teams_only']
        matches_only = options['matches_only']
        players_only = options['players_only']
        standings_only = options['standings_only']
        force = options['force']
        dry_run = options['dry_run']
        self.job_id = options.get('job_id')  # Store for progress tracking

        # If all_data, enable everything except if specific flags are set
        if all_data:
            import_teams = not matches_only and not players_only and not standings_only
            import_matches = not teams_only and not players_only and not standings_only
            import_players = not teams_only and not matches_only and not standings_only
            import_standings = not teams_only and not matches_only and not players_only
        else:
            import_teams = teams_only or (not matches_only and not players_only and not standings_only)
            import_matches = matches_only
            import_players = players_only
            import_standings = standings_only

        # Header
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS('IMPORTACION COMPLETA DESDE SOFASCORE'))
        self.stdout.write("=" * 80)
        self.stdout.write(f"Competiciones: {', '.join(competitions)}")
        self.stdout.write(f"Temporadas: {', '.join(map(str, seasons))}")
        self.stdout.write("")
        self.stdout.write("Modulos a importar:")
        if import_teams:
            self.stdout.write("[X] Equipos")
        if import_matches:
            self.stdout.write("[X] Partidos + Estadisticas")
        if import_players:
            self.stdout.write("[X] Jugadores + Estadisticas")
        if import_standings:
            self.stdout.write("[X] Clasificacion/Tabla")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] No se guardara nada"))
        if force:
            self.stdout.write(self.style.WARNING("[FORCE] Sobreescribira datos existentes"))
        self.stdout.write("")

        # Run async import
        asyncio.run(self.import_complete_async(
            competitions, seasons, force, dry_run,
            import_teams, import_matches, import_players, import_standings
        ))

    async def import_complete_async(self, competitions, seasons, force, dry_run,
                                   import_teams, import_matches, import_players, import_standings):
        """Async wrapper for complete import"""
        api = SofascoreAPI()

        # Initialize progress
        await self.update_progress(0, "Iniciando importacion...")

        # Global counters
        total_stats = {
            'teams_created': 0,
            'teams_updated': 0,
            'matches_created': 0,
            'matches_updated': 0,
            'match_stats_imported': 0,
            'players_created': 0,
            'players_updated': 0,
            'player_stats_created': 0,
            'standings_imported': 0,
        }

        try:
            # Process each competition and season
            total_items = len(competitions) * len(seasons)
            current_item = 0

            for comp_code in competitions:
                for season in seasons:
                    current_item += 1
                    self.stdout.write(f"\n{'='*80}")
                    self.stdout.write(f"{comp_code} - Temporada {season}/{season + 1} ({current_item}/{total_items})")
                    self.stdout.write("=" * 80)

                    result = await self.import_season_complete(
                        api, comp_code, season, force, dry_run,
                        import_teams, import_matches, import_players, import_standings
                    )

                    if result:
                        for key in total_stats:
                            total_stats[key] += result.get(key, 0)

        finally:
            await api.close()

        # Summary
        await self.update_progress(100, "Importacion completada!")
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS('RESUMEN TOTAL'))
        self.stdout.write("=" * 80)

        if import_teams:
            self.stdout.write(f"Equipos creados: {total_stats['teams_created']}")
            self.stdout.write(f"Equipos actualizados: {total_stats['teams_updated']}")

        if import_matches:
            self.stdout.write(f"Partidos creados: {total_stats['matches_created']}")
            self.stdout.write(f"Partidos actualizados: {total_stats['matches_updated']}")
            self.stdout.write(f"Partidos con estadisticas: {total_stats['match_stats_imported']}")

        if import_players:
            self.stdout.write(f"Jugadores creados: {total_stats['players_created']}")
            self.stdout.write(f"Jugadores actualizados: {total_stats['players_updated']}")
            self.stdout.write(f"Estadisticas de jugadores: {total_stats['player_stats_created']}")

        if import_standings:
            self.stdout.write(f"Clasificaciones importadas: {total_stats['standings_imported']}")

        self.stdout.write("=" * 80)

    async def import_season_complete(self, api, comp_code, season, force, dry_run,
                                    import_teams, import_matches, import_players, import_standings):
        """Import all data for one competition/season"""

        try:
            # Get competition
            competition = await sync_to_async(Competition.objects.get)(code=comp_code)
        except Competition.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"[ERROR] Competicion {comp_code} no encontrada en BD")
            )
            return None

        # Get tournament and season IDs
        tournament_id = SOFASCORE_TOURNAMENT_IDS.get(comp_code)
        if not tournament_id:
            self.stdout.write(
                self.style.ERROR(f"  [ERROR] SofaScore tournament ID no encontrado")
            )
            return None

        # Get season ID from dynamically loaded IDs
        season_id = None
        if comp_code in SOFASCORE_SEASON_IDS:
            season_id = SOFASCORE_SEASON_IDS[comp_code].get(season)

        if not season_id:
            self.stdout.write(
                self.style.ERROR(f"  [ERROR] Season ID no encontrado para {comp_code} {season}")
            )
            return None

        # Update competition with SofaScore ID
        if not dry_run:
            await sync_to_async(self._update_competition)(competition, tournament_id)

        result = {
            'teams_created': 0,
            'teams_updated': 0,
            'matches_created': 0,
            'matches_updated': 0,
            'match_stats_imported': 0,
            'players_created': 0,
            'players_updated': 0,
            'player_stats_created': 0,
            'standings_imported': 0,
        }

        # 1. Import teams
        if import_teams:
            self.stdout.write("\n[1/4] EQUIPOS")
            await self.update_progress(10, f"Importando equipos: {comp_code} {season}")
            teams_result = await self.import_teams(
                api, competition, tournament_id, season_id, season, force, dry_run
            )
            result['teams_created'] = teams_result.get('teams_created', 0)
            result['teams_updated'] = teams_result.get('teams_updated', 0)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[OK] {result['teams_created']} creados, "
                    f"{result['teams_updated']} actualizados"
                )
            )

        # 2. Import matches with statistics
        if import_matches:
            self.stdout.write("\n[2/4] PARTIDOS + ESTADISTICAS")
            await self.update_progress(30, f"Importando partidos: {comp_code} {season}")
            matches_result = await self.import_matches_with_stats(
                api, competition, tournament_id, season_id, season, force, dry_run
            )
            result['matches_created'] = matches_result.get('matches_created', 0)
            result['matches_updated'] = matches_result.get('matches_updated', 0)
            result['match_stats_imported'] = matches_result.get('stats_imported', 0)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[OK] {result['matches_created']} creados, "
                    f"{result['matches_updated']} actualizados, "
                    f"{result['match_stats_imported']} con stats"
                )
            )

        # 3. Import players and player stats
        if import_players:
            self.stdout.write("\n[3/4] JUGADORES + ESTADISTICAS")
            await self.update_progress(60, f"Importando jugadores: {comp_code} {season}")
            players_result = await self.import_players_with_stats(
                api, competition, tournament_id, season_id, season, force, dry_run
            )
            result['players_created'] = players_result.get('players_created', 0)
            result['players_updated'] = players_result.get('players_updated', 0)
            result['player_stats_created'] = players_result.get('stats_created', 0)
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [OK] {result['players_created']} creados, "
                    f"{result['players_updated']} actualizados, "
                    f"{result['player_stats_created']} stats"
                )
            )

        # 4. Import team standings/classification
        if import_standings:
            self.stdout.write("\n[4/4] CLASIFICACION/TABLA")
            await self.update_progress(85, f"Importando clasificacion: {comp_code} {season}")
            standings_result = await self.import_standings(
                api, competition, tournament_id, season_id, season, force, dry_run
            )
            result['standings_imported'] = standings_result.get('teams_processed', 0)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[OK] {result['standings_imported']} equipos procesados"
                )
            )

        await self.update_progress(95, f"Completado: {comp_code} {season}")
        return result

    def _update_competition(self, competition, tournament_id):
        """Update competition with SofaScore tournament ID"""
        if not competition.api_id or competition.api_id != str(tournament_id):
            competition.api_id = str(tournament_id)
            competition.save()

    async def import_teams(self, api, competition, tournament_id, season_id,
                          season, force, dry_run):
        """Import teams - avoiding duplicates using global api_id lookup"""
        result = {'teams_created': 0, 'teams_updated': 0}

        try:
            teams_data = await api.get_season_teams(tournament_id, season_id)

            if not teams_data or 'teams' not in teams_data:
                self.stdout.write(self.style.WARNING("[WARN] No teams found"))
                return result

            teams_list = teams_data.get('teams', [])
            total_teams = len(teams_list)
            self.stdout.write(f"    Procesando {total_teams} equipos...")

            for idx, team_info in enumerate(teams_list, 1):
                try:
                    team_name = team_info.get('name', 'Unknown')
                    team_id = team_info.get('id', 'N/A')

                    # Log cada 10 equipos o el primero/último
                    if idx % 10 == 0 or idx == 1 or idx == total_teams:
                        self.stdout.write(f"      [{idx}/{total_teams}] {team_name} (ID: {team_id})")

                    team_result = await self.process_team_global(
                        team_info, competition, dry_run, force
                    )

                    if team_result == 'created':
                        result['teams_created'] += 1
                        if idx % 10 != 0:  # Solo mostrar si no se mostró arriba
                            self.stdout.write(f"[{idx}/{total_teams}] ✓ {team_name} - CREADO")
                    elif team_result == 'updated':
                        result['teams_updated'] += 1

                except Exception as e:
                    team_name = team_info.get('name', 'Unknown')
                    self.stdout.write(
                        self.style.WARNING(f"[{idx}/{total_teams}] ✗ {team_name}: {e}")
                    )
                    continue

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  [ERROR] {e}"))

        return result

    async def process_team_global(self, team_info, competition, dry_run, force):
        """
        Process team using GLOBAL api_id lookup (no competition filter)
        This prevents duplicates across competitions
        """
        team_name = team_info.get('name', '')
        team_id = team_info.get('id')
        short_name = team_info.get('shortName', team_name[:50])

        if not team_name or not team_id:
            return 'skipped'

        if dry_run:
            return 'created'

        # GLOBAL lookup by api_id (not filtered by competition)
        existing_team = await sync_to_async(
            Team.objects.filter(api_id=team_id).first
        )()

        if existing_team:
            # Team exists globally - just update if needed
            if force:
                await sync_to_async(self._update_team)(
                    existing_team, team_name, short_name
                )
                return 'updated'
            return 'skipped'

        # Create new team (linked to primary competition)
        await sync_to_async(self._create_team)(
            competition, team_name, short_name, team_id
        )

        return 'created'

    def _update_team(self, team, name, short_name):
        """Update team info"""
        team.name = name
        team.short_name = short_name
        team.save()

    def _create_team(self, competition, name, short_name, api_id):
        """Create new team"""
        try:
            Team.objects.create(
                competition=competition,
                name=name,
                short_name=short_name,
                api_id=api_id
            )
        except Exception:
            pass  # Ignore if already exists due to race condition

    async def import_matches_with_stats(self, api, competition, tournament_id, season_id,
                                       season, force, dry_run):
        """Import matches with statistics"""
        result = {'matches_created': 0, 'matches_updated': 0, 'stats_imported': 0}

        try:
            matches_data = await api.get_season_matches(tournament_id, season_id, status='all')

            if not matches_data:
                return result

            total_matches = len(matches_data)
            self.stdout.write(f"Procesando {total_matches} partidos...")

            for idx, match_info in enumerate(matches_data, 1):
                try:
                    home_team_name = match_info.get('homeTeam', {}).get('name', 'Unknown')
                    away_team_name = match_info.get('awayTeam', {}).get('name', 'Unknown')
                    match_status = match_info.get('status', {}).get('type', 'unknown')
                    match_id = match_info.get('id', 'N/A')

                    # Log cada 10 partidos o el primero/último
                    if idx % 10 == 0 or idx == 1 or idx == total_matches:
                        self.stdout.write(
                            f"[{idx}/{total_matches}] {home_team_name} vs {away_team_name} "
                            f"(ID: {match_id}, Status: {match_status})"
                        )

                    match_result, has_stats = await self.process_match_with_stats(
                        match_info, competition, season, dry_run, force, api
                    )

                    if match_result == 'created':
                        result['matches_created'] += 1
                        if has_stats:
                            result['stats_imported'] += 1
                        # Mostrar confirmación para partidos creados
                        if idx % 10 != 0 and idx != 1 and idx != total_matches:
                            stats_msg = " + stats" if has_stats else ""
                            self.stdout.write(
                                f"[{idx}/{total_matches}] ✓ {home_team_name} vs {away_team_name} - CREADO{stats_msg}"
                            )
                    elif match_result == 'updated':
                        result['matches_updated'] += 1
                        if has_stats:
                            result['stats_imported'] += 1
                        # Mostrar confirmación para partidos actualizados
                        if idx % 10 != 0 and idx != 1 and idx != total_matches:
                            stats_msg = " + stats" if has_stats else ""
                            self.stdout.write(
                                f"[{idx}/{total_matches}] ↻ {home_team_name} vs {away_team_name} - ACTUALIZADO{stats_msg}"
                            )

                    # Mostrar progreso cada 10 partidos
                    if idx % 10 == 0:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Progreso: {idx}/{total_matches} - "
                                f"Creados: {result['matches_created']}, "
                                f"Actualizados: {result['matches_updated']}, "
                                f"Con stats: {result['stats_imported']}"
                            )
                        )

                except Exception as e:
                    home_team_name = match_info.get('homeTeam', {}).get('name', 'Unknown')
                    away_team_name = match_info.get('awayTeam', {}).get('name', 'Unknown')
                    self.stdout.write(
                        self.style.WARNING(f"[{idx}/{total_matches}] ✗ {home_team_name} vs {away_team_name}: {e}")
                    )
                    continue

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[ERROR] {e}"))

        return result

    async def process_match_with_stats(self, match_info, competition, season,
                                      dry_run, force, api):
        """Process single match with statistics"""
        event_id = match_info.get('id')
        home_team_info = match_info.get('homeTeam', {})
        away_team_info = match_info.get('awayTeam', {})

        home_team_id = home_team_info.get('id')
        away_team_id = away_team_info.get('id')

        if not event_id or not home_team_id or not away_team_id:
            return 'skipped', False

        # Find teams by GLOBAL api_id
        home_team = await sync_to_async(
            Team.objects.filter(api_id=home_team_id).first
        )()

        away_team = await sync_to_async(
            Team.objects.filter(api_id=away_team_id).first
        )()

        if not home_team or not away_team:
            return 'skipped', False

        if dry_run:
            return 'created', False

        # Extract match data
        match_data = self.extract_match_data(match_info)

        # Check if match exists
        existing_match = await sync_to_async(
            Match.objects.filter(api_id=event_id).first
        )()

        match_obj = None
        if existing_match:
            if force:
                await sync_to_async(self._update_match)(existing_match, match_data)
                match_obj = existing_match
            else:
                return 'skipped', False
        else:
            match_obj = await sync_to_async(self._create_match)(
                competition, home_team, away_team, season, event_id, match_data
            )

        # Import match statistics if finished
        has_stats = False
        if match_obj and match_info.get('status', {}).get('type') == 'finished':
            try:
                has_stats = await self.import_match_stats(api, match_obj, event_id)
            except Exception:
                pass

        return ('created' if not existing_match else 'updated'), has_stats

    def extract_match_data(self, match_info):
        """Extract match data from SofaScore response"""
        status_map = {
            'finished': 'FINISHED',
            'notstarted': 'SCHEDULED',
            'inprogress': 'IN_PLAY',
            'postponed': 'POSTPONED',
            'cancelled': 'CANCELLED',
            'abandoned': 'CANCELLED',
        }

        status = match_info.get('status', {}).get('type', '').lower()
        mapped_status = status_map.get(status, 'SCHEDULED')

        home_score = match_info.get('homeScore', {}).get('current')
        away_score = match_info.get('awayScore', {}).get('current')
        ht_home = match_info.get('homeScore', {}).get('period1')
        ht_away = match_info.get('awayScore', {}).get('period1')

        start_timestamp = match_info.get('startTimestamp')
        if start_timestamp:
            utc_date = datetime.utcfromtimestamp(start_timestamp).replace(tzinfo=pytz.UTC)
        else:
            utc_date = None

        return {
            'status': mapped_status,
            'utc_date': utc_date,
            'home_score': safe_int(home_score),
            'away_score': safe_int(away_score),
            'home_score_ht': safe_int(ht_home),
            'away_score_ht': safe_int(ht_away),
        }

    def _update_match(self, match, data):
        """Update match"""
        for key, value in data.items():
            if value is not None:
                setattr(match, key, value)
        match.save()

    def _create_match(self, competition, home_team, away_team, season, event_id, data):
        """Create match"""
        return Match.objects.create(
            competition=competition,
            season=season,
            home_team=home_team,
            away_team=away_team,
            api_id=event_id,
            **data
        )

    async def import_match_stats(self, api, match, event_id):
        """Import match statistics and player statistics"""
        try:
            match_data = await api.get_match_complete_data(event_id)

            if not match_data:
                return False

            has_match_stats = False
            has_player_stats = False

            # Import match-level statistics
            if 'statistics' in match_data:
                statistics = match_data.get('statistics', [])
                stats = self.extract_match_statistics(statistics)

                if stats:
                    await sync_to_async(self._update_match_stats)(match, stats)
                    has_match_stats = True

            # Import player statistics from lineups
            if 'lineups' in match_data:
                lineups = match_data.get('lineups', {})
                player_count = await self.import_match_player_stats(match, lineups)
                if player_count > 0:
                    has_player_stats = True

            return has_match_stats or has_player_stats

        except Exception:
            pass

        return False

    def extract_match_statistics(self, statistics):
        """Extract match statistics"""
        if not statistics:
            return None

        stats_list = statistics.get('statistics', [])
        if not stats_list:
            return None

        result = {}

        for period_data in stats_list:
            if period_data.get('period') != 'ALL':
                continue

            groups = period_data.get('groups', [])
            for group in groups:
                stats_items = group.get('statisticsItems', [])

                for stat in stats_items:
                    name = stat.get('name', '')
                    key = stat.get('key', '')
                    home_val = stat.get('homeValue', stat.get('home'))
                    away_val = stat.get('awayValue', stat.get('away'))

                    if 'Total shots' in name or key == 'totalShotsOnGoal':
                        result['shots_home'] = safe_int(home_val)
                        result['shots_away'] = safe_int(away_val)
                    elif 'Shots on target' in name or key == 'shotsOnTarget':
                        result['shots_on_target_home'] = safe_int(home_val)
                        result['shots_on_target_away'] = safe_int(away_val)
                    elif 'Corner kicks' in name or key == 'cornerKicks':
                        result['corners_home'] = safe_int(home_val)
                        result['corners_away'] = safe_int(away_val)
                    elif 'Yellow cards' in name or key == 'yellowCards':
                        result['yellow_cards_home'] = safe_int(home_val)
                        result['yellow_cards_away'] = safe_int(away_val)
                    elif 'Fouls' in name or key == 'fouls':
                        result['fouls_home'] = safe_int(home_val)
                        result['fouls_away'] = safe_int(away_val)
                    elif 'Ball possession' in name or key == 'ballPossession':
                        result['possession_home'] = safe_int(home_val)
                        result['possession_away'] = safe_int(away_val)
                    elif 'Expected goals' in name or key == 'expectedGoals':
                        result['xg_home'] = safe_float(home_val)
                        result['xg_away'] = safe_float(away_val)

        return result if result else None

    def _update_match_stats(self, match, stats):
        """Update match with statistics"""
        for key, value in stats.items():
            if value is not None and hasattr(match, key):
                setattr(match, key, value)
        match.save()

    async def import_players_with_stats(self, api, competition, tournament_id, season_id,
                                       season, force, dry_run):
        """Import players and their statistics"""
        result = {'players_created': 0, 'players_updated': 0, 'stats_created': 0}

        try:
            # Get all player stats
            players_data = await api.get_all_league_player_stats(
                tournament_id, season_id, accumulation='total'
            )

            if not players_data:
                return result

            total_players = len(players_data)
            self.stdout.write(f"Procesando {total_players} jugadores...")

            for idx, player_data in enumerate(players_data, 1):
                try:
                    player_name = player_data.get('player', {}).get('name', 'Unknown')
                    team_name = player_data.get('team', {}).get('name', 'Unknown')

                    # Log cada 50 jugadores o el primero/último
                    if idx % 50 == 0 or idx == 1 or idx == total_players:
                        self.stdout.write(
                            f"      [{idx}/{total_players}] {player_name} ({team_name})"
                        )

                    player_result = await self.process_player_with_stats(
                        player_data, competition, season, dry_run, force
                    )

                    if player_result == 'created':
                        result['players_created'] += 1
                        result['stats_created'] += 1
                    elif player_result == 'updated':
                        result['players_updated'] += 1
                        result['stats_created'] += 1

                except Exception as e:
                    player_name = player_data.get('player', {}).get('name', 'Unknown')
                    self.stdout.write(
                        self.style.WARNING(f"[{idx}/{total_players}] ✗ {player_name}: {e}")
                    )
                    continue

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[ERROR] {e}"))

        return result

    async def process_player_with_stats(self, player_data, competition, season,
                                       dry_run, force):
        """Process player and create stats"""
        player_info = player_data.get('player', {})
        team_info = player_data.get('team', {})

        player_name = player_info.get('name', '')
        player_id = player_info.get('id')
        team_id = team_info.get('id')

        if not player_name or not team_id:
            return 'skipped'

        # Find team by GLOBAL api_id
        team = await sync_to_async(
            Team.objects.filter(api_id=team_id).first
        )()

        if not team:
            return 'skipped'

        if dry_run:
            return 'created'

        # Get or create player
        player, player_created = await self.get_or_create_player(
            player_name, player_id, team
        )

        if not player:
            return 'skipped'

        # Create/update player stats
        stats_data = self.extract_player_stats(player_data)

        await sync_to_async(self._update_or_create_player_stats)(
            player, team, competition, season, stats_data
        )

        return 'created' if player_created else 'updated'

    async def get_or_create_player(self, player_name, player_id, team):
        """Get or create player"""
        if player_id:
            existing = await sync_to_async(
                Player.objects.filter(sofascore_id=player_id).first
            )()

            if existing:
                return existing, False

        # Create new player
        player = await sync_to_async(self._create_player)(
            player_name, player_id, team
        )

        return player, True

    def _create_player(self, name, sofascore_id, team):
        """Create player"""
        return Player.objects.create(
            name=name,
            short_name=name[:100],
            position='MF',  # Default, will be updated
            team=team,
            sofascore_id=sofascore_id,
        )

    def extract_player_stats(self, player_data):
        """Extract player statistics"""
        return {
            'matches_played': safe_int(player_data.get('appearances', 0)),
            'minutes_played': safe_int(player_data.get('minutesPlayed', 0)),
            'goals': safe_int(player_data.get('goals', 0)),
            'assists': safe_int(player_data.get('assists', 0)),
            'xg': safe_float(player_data.get('expectedGoals', 0)),
            'xa': safe_float(player_data.get('expectedAssists', 0)),
            'shots_total': safe_int(player_data.get('shotsTotal', 0)),
            'shots_on_target': safe_int(player_data.get('shotsOnTarget', 0)),
            'passes_completed': safe_int(player_data.get('accuratePass', 0)),
            'passes_attempted': safe_int(player_data.get('totalPass', 0)),
            'key_passes': safe_int(player_data.get('keyPass', 0)),
            'tackles': safe_int(player_data.get('tackles', 0)),
            'interceptions': safe_int(player_data.get('interceptions', 0)),
            'yellow_cards': safe_int(player_data.get('yellowCards', 0)),
            'red_cards': safe_int(player_data.get('redCards', 0)),
        }

    def _update_or_create_player_stats(self, player, team, competition, season, stats_data):
        """Update or create player stats"""
        PlayerStats.objects.update_or_create(
            player=player,
            team=team,
            competition=competition,
            season=season,
            defaults={
                **stats_data,
                'calculated_at': timezone.now()
            }
        )

    async def import_standings(self, api, competition, tournament_id, season_id,
                              season, force, dry_run):
        """Import team standings/classification"""
        result = {'teams_processed': 0}

        try:
            # Get standings data
            teams_data = await api.get_season_teams(tournament_id, season_id)

            if not teams_data or 'standings' not in teams_data:
                return result

            standings = teams_data.get('standings', [])

            # Process standings data
            # This would need more implementation based on SofaScore standings structure
            # For now, return placeholder

            result['teams_processed'] = len(standings) if isinstance(standings, list) else 0

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[ERROR] {e}"))

        return result

    async def import_match_player_stats(self, match, lineups):
        """Import player statistics from match lineups"""
        if not lineups:
            return 0

        players_imported = 0

        # SofaScore lineups structure: {'home': {...}, 'away': {...}}
        # or {'confirmed': True, 'home': {...}, 'away': {...}}
        home_lineup = lineups.get('home', {})
        away_lineup = lineups.get('away', {})

        # Get teams from match
        home_team = match.home_team
        away_team = match.away_team

        # Process home team players
        if home_lineup:
            home_count = await self.process_team_lineup(
                match, home_team, home_lineup
            )
            players_imported += home_count

        # Process away team players
        if away_lineup:
            away_count = await self.process_team_lineup(
                match, away_team, away_lineup
            )
            players_imported += away_count

        return players_imported

    async def process_team_lineup(self, match, team, lineup_data):
        """Process lineup for one team"""
        players_count = 0

        # Extract players from lineup (starters + substitutes)
        players_list = []

        # Starters (confirmed lineup field)
        if 'players' in lineup_data:
            for player_entry in lineup_data.get('players', []):
                player_entry['started'] = True
                player_entry['substitute'] = False
                players_list.append(player_entry)

        # Substitutes
        if 'substitutes' in lineup_data:
            for player_entry in lineup_data.get('substitutes', []):
                player_entry['started'] = False
                player_entry['substitute'] = True
                players_list.append(player_entry)

        # Process each player
        for player_entry in players_list:
            try:
                player_info = player_entry.get('player', {})
                player_id = player_info.get('id')

                if not player_id:
                    continue

                # Find player by sofascore_id
                player = await sync_to_async(
                    Player.objects.filter(sofascore_id=player_id).first
                )()

                # If player doesn't exist, create it
                if not player:
                    player_name = player_info.get('name', 'Unknown')
                    player = await sync_to_async(self._create_player)(
                        player_name, player_id, team
                    )

                # Extract statistics
                stats_data = self.extract_player_match_stats(player_entry, team)

                # Save match player stats
                await sync_to_async(self._create_or_update_match_player_stats)(
                    match, player, team, stats_data
                )

                players_count += 1

            except Exception as e:
                # Log error but continue with other players
                player_name = player_entry.get('player', {}).get('name', 'Unknown')
                continue

        return players_count

    def extract_player_match_stats(self, player_entry, team):
        """Extract player match statistics from lineup data"""
        player_info = player_entry.get('player', {})
        statistics = player_entry.get('statistics', {})

        # Basic appearance info
        started = player_entry.get('started', False)
        substitute = player_entry.get('substitute', False)
        position = player_info.get('position', 'Unknown')
        shirt_number = player_info.get('shirtNumber')

        # Extract statistics
        stats = {
            'started': started,
            'substitute': substitute,
            'position': position,
            'shirt_number': safe_int(shirt_number),
            'minutes_played': safe_int(statistics.get('minutesPlayed', 0)),
            'rating': safe_float(statistics.get('rating')),

            # Goals & assists
            'goals': safe_int(statistics.get('goals', 0)),
            'assists': safe_int(statistics.get('goalAssist', 0)),
            'xg': safe_float(statistics.get('expectedGoals')),
            'xa': safe_float(statistics.get('expectedAssists')),

            # Shots
            'shots': safe_int(statistics.get('totalShots', 0)),
            'shots_on_target': safe_int(statistics.get('shotsOnTarget', 0)),
            'shots_off_target': safe_int(statistics.get('shotsOffTarget', 0)),
            'shots_blocked': safe_int(statistics.get('blockedShots', 0)),
            'big_chances_missed': safe_int(statistics.get('bigChanceMissed', 0)),

            # Passes
            'passes_completed': safe_int(statistics.get('accuratePass', 0)),
            'passes_attempted': safe_int(statistics.get('totalPass', 0)),
            'key_passes': safe_int(statistics.get('keyPass', 0)),
            'accurate_crosses': safe_int(statistics.get('accurateCross', 0)),
            'total_crosses': safe_int(statistics.get('totalCross', 0)),
            'big_chances_created': safe_int(statistics.get('bigChanceCreated', 0)),

            # Defensive
            'tackles': safe_int(statistics.get('totalTackle', 0)),
            'tackles_won': safe_int(statistics.get('wonTackle', 0)),
            'interceptions': safe_int(statistics.get('interceptions', 0)),
            'clearances': safe_int(statistics.get('clearances', 0)),
            'blocked_shots': safe_int(statistics.get('blockedShots', 0)),

            # Duels
            'duels_won': safe_int(statistics.get('duelWon', 0)),
            'duels_lost': safe_int(statistics.get('duelLost', 0)),
            'aerials_won': safe_int(statistics.get('aerialWon', 0)),
            'aerials_lost': safe_int(statistics.get('aerialLost', 0)),
            'dribbles_successful': safe_int(statistics.get('successfulDribbles', 0)),
            'dribbles_attempted': safe_int(statistics.get('totalDribbles', 0)),
            'was_fouled': safe_int(statistics.get('wasFouled', 0)),

            # Discipline
            'fouls_committed': safe_int(statistics.get('fouls', 0)),
            'yellow_card': safe_int(statistics.get('yellowCards', 0)) > 0,
            'red_card': safe_int(statistics.get('redCards', 0)) > 0,

            # Other
            'touches': safe_int(statistics.get('touches', 0)),
            'dispossessed': safe_int(statistics.get('dispossessed', 0)),
            'offsides': safe_int(statistics.get('offsides', 0)),
        }

        # Goalkeeper stats (if position is GK)
        if position == 'G':
            stats['saves'] = safe_int(statistics.get('saves', 0))
            stats['saves_inside_box'] = safe_int(statistics.get('savesInsideBox', 0))
            stats['punches'] = safe_int(statistics.get('punches', 0))
            stats['runs_out'] = safe_int(statistics.get('goodHighClaim', 0))
            stats['successful_runs_out'] = safe_int(statistics.get('successfulRunsOut', 0))
            stats['high_claims'] = safe_int(statistics.get('highClaims', 0))

        return stats

    def _create_or_update_match_player_stats(self, match, player, team, stats_data):
        """Create or update match player statistics"""
        MatchPlayerStats.objects.update_or_create(
            match=match,
            player=player,
            defaults={
                'team': team,
                **stats_data
            }
        )
