"""
Re-import Match Data by Competition, Matchday, and Season

Re-imports match statistics, lineups, and incidents for specific matchdays or entire seasons.
Useful when data import failed or when you need to update specific matches.

Usage:
    # Re-import Premier League matchday 20 from 2024/25 season
    python manage.py reimport_matchday --competition PL --seasons 2024 --matchday 20

    # Re-import multiple matchdays
    python manage.py reimport_matchday --competition PL --seasons 2024 --matchday 18,19,20

    # Re-import ALL matchdays from 2024/25 season
    python manage.py reimport_matchday --competition PL --seasons 2024

    # Re-import ALL matchdays from multiple seasons
    python manage.py reimport_matchday --competition PL --seasons 2023,2024

    # Preview without actually importing (dry-run)
    python manage.py reimport_matchday --competition PL --seasons 2024 --matchday 20 --dry-run

    # Force re-import even if data already exists
    python manage.py reimport_matchday --competition PL --seasons 2024 --force
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from asgiref.sync import sync_to_async
from predictions.models import Match, Competition
from predictions.sofascore_api import SofascoreAPI
from predictions.management.commands.import_sofascore_complete import Command as ImportCommand
import asyncio


class Command(BaseCommand):
    help = 'Re-import match data (stats, lineups, incidents) by competition, matchday, and season'

    def add_arguments(self, parser):
        parser.add_argument(
            '--competition',
            type=str,
            required=True,
            help='Competition code (e.g., PL, PD, BL1, SA, FL1, CL)'
        )
        parser.add_argument(
            '--seasons',
            type=str,
            required=True,
            help='Season year(s), comma-separated (e.g., 2024 or 2023,2024)'
        )
        parser.add_argument(
            '--matchday',
            type=str,
            required=False,
            help='Matchday number(s), comma-separated (e.g., 20 or 18,19,20). If omitted, imports ALL matchdays'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-import even if data already exists'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be imported without actually importing'
        )

    def handle(self, *args, **options):
        competition_code = options['competition']
        seasons_str = options['seasons']
        matchdays_str = options.get('matchday')
        force = options['force']
        dry_run = options['dry_run']

        # Parse seasons
        seasons = [int(s.strip()) for s in seasons_str.split(',')]

        # Parse matchdays (if provided)
        matchdays = None
        if matchdays_str:
            matchdays = [int(md.strip()) for md in matchdays_str.split(',')]

        # Header
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS('RE-IMPORTAR DATOS DE JORNADA'))
        self.stdout.write("=" * 80)
        self.stdout.write(f"Competicion: {competition_code}")
        self.stdout.write(f"Temporadas: {', '.join(f'{s}/{s+1}' for s in seasons)}")
        if matchdays:
            self.stdout.write(f"Jornadas: {', '.join(map(str, matchdays))}")
        else:
            self.stdout.write(f"Jornadas: TODAS")
        self.stdout.write("")

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] No se guardara nada"))
        if force:
            self.stdout.write(self.style.WARNING("[FORCE] Re-importara datos existentes"))
        self.stdout.write("")

        # Run async import
        asyncio.run(self.reimport_async(
            competition_code, seasons, matchdays, force, dry_run
        ))

    async def reimport_async(self, competition_code, seasons, matchdays, force, dry_run):
        """Async wrapper for re-import"""
        # Get competition
        try:
            competition = await sync_to_async(Competition.objects.get)(code=competition_code)
        except Competition.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Competicion '{competition_code}' no encontrada"))
            return

        api = SofascoreAPI()
        import_cmd = ImportCommand()
        import_cmd.stdout = self.stdout  # Pass stdout to import command

        total_stats = {
            'matches_found': 0,
            'matches_with_api_id': 0,
            'matches_reimported': 0,
            'matches_failed': 0,
            'lineups_imported': 0,
            'incidents_imported': 0,
            'stats_imported': 0,
        }

        try:
            # Process each season
            for season in seasons:
                self.stdout.write(f"\n{'='*80}")
                self.stdout.write(f"TEMPORADA {season}/{season + 1}")
                self.stdout.write("=" * 80)

                # Get matchdays to process
                matchdays_to_process = matchdays

                if matchdays_to_process is None:
                    # Get all unique matchdays for this season
                    def get_matchdays():
                        return list(
                            Match.objects.filter(
                                competition=competition,
                                season=season,
                                status='FINISHED',
                                matchday__isnull=False
                            ).values_list('matchday', flat=True).distinct().order_by('matchday')
                        )

                    matchdays_to_process = await sync_to_async(get_matchdays)()

                    if not matchdays_to_process:
                        self.stdout.write(self.style.WARNING(f"  No se encontraron jornadas para temporada {season}/{season + 1}"))
                        continue

                    self.stdout.write(f"  Se reimportaran {len(matchdays_to_process)} jornadas: {', '.join(map(str, matchdays_to_process))}")
                    self.stdout.write("")

                # Process each matchday
                for matchday in matchdays_to_process:
                    self.stdout.write(f"\n  JORNADA {matchday}")
                    self.stdout.write("  " + "-" * 76)

                    # Get matches for this matchday
                    matches = await sync_to_async(list)(
                        Match.objects.filter(
                            competition=competition,
                            season=season,
                            matchday=matchday,
                            status='FINISHED'  # Only finished matches
                        ).select_related('home_team', 'away_team')
                    )

                    total_stats['matches_found'] += len(matches)

                    if not matches:
                        self.stdout.write(self.style.WARNING(f"    No se encontraron partidos para jornada {matchday}"))
                        continue

                    self.stdout.write(f"    Encontrados {len(matches)} partidos")

                    for idx, match in enumerate(matches, 1):
                        # Check if match has api_id
                        if not match.api_id:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"    [{idx}/{len(matches)}] {match.home_team.short_name} vs "
                                    f"{match.away_team.short_name} - SIN api_id (omitido)"
                                )
                            )
                            continue

                        total_stats['matches_with_api_id'] += 1

                        # Check current data status
                        has_lineups = await sync_to_async(match.player_performances.exists)()
                        has_incidents = await sync_to_async(match.incidents.exists)()
                        has_stats = match.shots_home is not None

                        status_parts = []
                        if has_lineups:
                            status_parts.append(f"Alineaciones: {await sync_to_async(match.player_performances.count)()}")
                        if has_incidents:
                            status_parts.append(f"Eventos: {await sync_to_async(match.incidents.count)()}")
                        if has_stats:
                            status_parts.append("Stats: OK")

                        status_str = " | ".join(status_parts) if status_parts else "SIN DATOS"

                        self.stdout.write(
                            f"    [{idx}/{len(matches)}] {match.home_team.short_name} vs "
                            f"{match.away_team.short_name} ({match.home_score}-{match.away_score})"
                        )
                        self.stdout.write(f"        Estado actual: {status_str}")

                        if dry_run:
                            self.stdout.write(self.style.WARNING(f"        [DRY-RUN] Se reimportarian datos"))
                            total_stats['matches_reimported'] += 1
                            continue

                        # Re-import match stats, lineups, and incidents
                        try:
                            success = await import_cmd.import_match_stats(
                                api, match, match.api_id, force=force
                            )

                            if success:
                                # Check what was imported
                                new_has_lineups = await sync_to_async(match.player_performances.exists)()
                                new_has_incidents = await sync_to_async(match.incidents.exists)()
                                new_has_stats = match.shots_home is not None

                                imported_parts = []
                                if new_has_lineups and not has_lineups:
                                    lineups_count = await sync_to_async(match.player_performances.count)()
                                    imported_parts.append(f"Alineaciones: {lineups_count}")
                                    total_stats['lineups_imported'] += 1
                                elif new_has_lineups:
                                    imported_parts.append("Alineaciones: Actualizado")

                                if new_has_incidents and not has_incidents:
                                    incidents_count = await sync_to_async(match.incidents.count)()
                                    imported_parts.append(f"Eventos: {incidents_count}")
                                    total_stats['incidents_imported'] += 1
                                elif new_has_incidents:
                                    imported_parts.append("Eventos: Actualizado")

                                if new_has_stats and not has_stats:
                                    imported_parts.append("Stats: Importado")
                                    total_stats['stats_imported'] += 1
                                elif new_has_stats:
                                    imported_parts.append("Stats: Actualizado")

                                imported_str = " | ".join(imported_parts) if imported_parts else "Sin cambios"
                                self.stdout.write(
                                    self.style.SUCCESS(f"        ✓ Reimportado: {imported_str}")
                                )
                                total_stats['matches_reimported'] += 1
                            else:
                                self.stdout.write(
                                    self.style.ERROR(f"        ✗ No se pudieron obtener datos de SofaScore")
                                )
                                total_stats['matches_failed'] += 1

                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f"        ✗ Error: {str(e)}")
                            )
                            total_stats['matches_failed'] += 1

                        # Small delay to avoid rate limiting
                        await asyncio.sleep(0.5)

        finally:
            await api.close()

        # Summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS('RESUMEN TOTAL'))
        self.stdout.write("=" * 80)
        self.stdout.write(f"Partidos encontrados: {total_stats['matches_found']}")
        self.stdout.write(f"Partidos con api_id: {total_stats['matches_with_api_id']}")
        self.stdout.write(f"Partidos reimportados: {total_stats['matches_reimported']}")
        self.stdout.write(f"Partidos fallidos: {total_stats['matches_failed']}")
        self.stdout.write(f"Alineaciones importadas: {total_stats['lineups_imported']}")
        self.stdout.write(f"Eventos importados: {total_stats['incidents_imported']}")
        self.stdout.write(f"Estadisticas importadas: {total_stats['stats_imported']}")
        self.stdout.write("=" * 80)
