"""
Download team logos and player photos from SofaScore API

Downloads images and stores them locally in media/ folder:
- Team logos: media/teams/{team_id}.png
- Player photos: media/players/{player_id}.png

Updates Team.crest_url and Player.photo fields with relative paths.

Usage:
    python manage.py download_images --teams --players
    python manage.py download_images --teams-only
    python manage.py download_images --players-only
    python manage.py download_images --dry-run
    python manage.py download_images --force  # Re-download existing images
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from predictions.models import Team, Player
from predictions.sofascore_api import SofascoreAPI
from asgiref.sync import sync_to_async

import asyncio
from pathlib import Path
import aiofiles


class Command(BaseCommand):
    help = 'Download team logos and player photos from SofaScore'

    def add_arguments(self, parser):
        parser.add_argument(
            '--teams',
            action='store_true',
            help='Download team logos'
        )
        parser.add_argument(
            '--players',
            action='store_true',
            help='Download player photos'
        )
        parser.add_argument(
            '--teams-only',
            action='store_true',
            help='Only download team logos'
        )
        parser.add_argument(
            '--players-only',
            action='store_true',
            help='Only download player photos'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-download existing images'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview without downloading'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of images to download (for testing)'
        )

    def handle(self, *args, **options):
        teams = options['teams']
        players = options['players']
        teams_only = options['teams_only']
        players_only = options['players_only']
        force = options['force']
        dry_run = options['dry_run']
        limit = options['limit']

        # Determine what to download
        download_teams = teams or teams_only or (not players_only)
        download_players = players or players_only or (not teams_only)

        # Header
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS('DESCARGA DE IMAGENES DESDE SOFASCORE'))
        self.stdout.write("=" * 80)

        if download_teams:
            self.stdout.write("  [X] Logos de equipos")
        if download_players:
            self.stdout.write("  [X] Fotos de jugadores")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] No se descargara nada"))
        if force:
            self.stdout.write(self.style.WARNING("[FORCE] Re-descargar imagenes existentes"))
        if limit:
            self.stdout.write(self.style.WARNING(f"[LIMIT] Maximo {limit} imagenes"))
        self.stdout.write("")

        # Run download
        asyncio.run(self.download_images_async(
            download_teams, download_players, force, dry_run, limit
        ))

    async def download_images_async(self, download_teams, download_players,
                                    force, dry_run, limit):
        """Main async download function"""
        api = SofascoreAPI(delay_min=1, delay_max=2)  # Shorter delays for images

        try:
            # Create media directories
            if not dry_run:
                self.create_media_directories()

            stats = {
                'teams_downloaded': 0,
                'teams_skipped': 0,
                'teams_failed': 0,
                'players_downloaded': 0,
                'players_skipped': 0,
                'players_failed': 0,
            }

            # Download team logos
            if download_teams:
                self.stdout.write("\n" + "=" * 80)
                self.stdout.write("LOGOS DE EQUIPOS")
                self.stdout.write("=" * 80)

                team_stats = await self.download_team_logos(
                    api, force, dry_run, limit
                )
                stats['teams_downloaded'] = team_stats['downloaded']
                stats['teams_skipped'] = team_stats['skipped']
                stats['teams_failed'] = team_stats['failed']

            # Download player photos
            if download_players:
                self.stdout.write("\n" + "=" * 80)
                self.stdout.write("FOTOS DE JUGADORES")
                self.stdout.write("=" * 80)

                player_stats = await self.download_player_photos(
                    api, force, dry_run, limit
                )
                stats['players_downloaded'] = player_stats['downloaded']
                stats['players_skipped'] = player_stats['skipped']
                stats['players_failed'] = player_stats['failed']

        finally:
            await api.close()

        # Summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS('RESUMEN'))
        self.stdout.write("=" * 80)

        if download_teams:
            self.stdout.write(f"Logos de equipos descargados: {stats['teams_downloaded']}")
            self.stdout.write(f"Logos de equipos omitidos: {stats['teams_skipped']}")
            self.stdout.write(f"Logos de equipos fallidos: {stats['teams_failed']}")

        if download_players:
            self.stdout.write(f"Fotos de jugadores descargadas: {stats['players_downloaded']}")
            self.stdout.write(f"Fotos de jugadores omitidas: {stats['players_skipped']}")
            self.stdout.write(f"Fotos de jugadores fallidas: {stats['players_failed']}")

        self.stdout.write("=" * 80)

    def create_media_directories(self):
        """Create media directories if they don't exist"""
        teams_dir = Path(settings.MEDIA_ROOT) / 'teams'
        players_dir = Path(settings.MEDIA_ROOT) / 'players'

        teams_dir.mkdir(parents=True, exist_ok=True)
        players_dir.mkdir(parents=True, exist_ok=True)

    async def download_team_logos(self, api, force, dry_run, limit):
        """Download all team logos"""
        stats = {'downloaded': 0, 'skipped': 0, 'failed': 0}

        # Get teams with api_id
        teams = await sync_to_async(list)(
            Team.objects.filter(api_id__isnull=False).order_by('name')
        )

        total = len(teams)
        if limit:
            teams = teams[:limit]
            total = len(teams)

        self.stdout.write(f"Total equipos a procesar: {total}")

        for idx, team in enumerate(teams, 1):
            try:
                team_id = team.api_id
                team_name = team.name

                # Check if already downloaded
                relative_path = f'teams/{team_id}.png'
                full_path = Path(settings.MEDIA_ROOT) / relative_path

                if not force and full_path.exists():
                    stats['skipped'] += 1
                    if idx % 10 == 0 or idx == 1 or idx == total:
                        self.stdout.write(
                            f"  [{idx}/{total}] {team_name} - OMITIDO (ya existe)"
                        )
                    continue

                if dry_run:
                    stats['downloaded'] += 1
                    self.stdout.write(
                        f"  [{idx}/{total}] {team_name} - SERIA DESCARGADO"
                    )
                    continue

                # Download image
                image_url = f"https://api.sofascore.com/api/v1/team/{team_id}/image"
                success = await self.download_image(api, image_url, full_path)

                if success:
                    # Update database
                    await self._update_team_crest(team, relative_path)
                    stats['downloaded'] += 1

                    if idx % 10 == 0 or idx == 1 or idx == total:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  [{idx}/{total}] {team_name} - DESCARGADO"
                            )
                        )
                else:
                    stats['failed'] += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"  [{idx}/{total}] {team_name} - FALLO"
                        )
                    )

            except Exception as e:
                stats['failed'] += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  [{idx}/{total}] {team.name} - ERROR: {e}"
                    )
                )

        return stats

    async def download_player_photos(self, api, force, dry_run, limit):
        """Download all player photos"""
        stats = {'downloaded': 0, 'skipped': 0, 'failed': 0}

        # Get players with sofascore_id
        players = await sync_to_async(list)(
            Player.objects.filter(sofascore_id__isnull=False).order_by('name')
        )

        total = len(players)
        if limit:
            players = players[:limit]
            total = len(players)

        self.stdout.write(f"Total jugadores a procesar: {total}")

        for idx, player in enumerate(players, 1):
            try:
                player_id = player.sofascore_id
                player_name = player.name

                # Check if already downloaded
                relative_path = f'players/{player_id}.png'
                full_path = Path(settings.MEDIA_ROOT) / relative_path

                if not force and full_path.exists():
                    stats['skipped'] += 1
                    if idx % 50 == 0 or idx == 1 or idx == total:
                        self.stdout.write(
                            f"  [{idx}/{total}] {player_name} - OMITIDO (ya existe)"
                        )
                    continue

                if dry_run:
                    stats['downloaded'] += 1
                    if idx % 50 == 0 or idx == 1 or idx == total:
                        self.stdout.write(
                            f"  [{idx}/{total}] {player_name} - SERIA DESCARGADO"
                        )
                    continue

                # Download image
                image_url = f"https://api.sofascore.com/api/v1/player/{player_id}/image"
                success = await self.download_image(api, image_url, full_path)

                if success:
                    # Update database
                    await self._update_player_photo(player, relative_path)
                    stats['downloaded'] += 1

                    if idx % 50 == 0 or idx == 1 or idx == total:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  [{idx}/{total}] {player_name} - DESCARGADO"
                            )
                        )
                else:
                    stats['failed'] += 1
                    if idx % 50 == 0:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  [{idx}/{total}] {player_name} - FALLO"
                            )
                        )

            except Exception as e:
                stats['failed'] += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  [{idx}/{total}] {player.name} - ERROR: {e}"
                    )
                )

        return stats

    async def download_image(self, api, url, output_path):
        """
        Download a single image from SofaScore
        Returns True if successful, False otherwise
        """
        try:
            await api._init_browser()
            await api._wait_if_needed()

            response = await api.page.goto(url)

            if response.status == 200:
                # Get image bytes
                image_bytes = await response.body()

                # Save to file
                async with aiofiles.open(output_path, 'wb') as f:
                    await f.write(image_bytes)

                return True
            else:
                return False

        except Exception:
            return False

    async def _update_team_crest(self, team, relative_path):
        """Update team crest_url field"""
        team.crest_url = relative_path
        await sync_to_async(team.save)(update_fields=['crest_url'])

    async def _update_player_photo(self, player, relative_path):
        """Update player photo field"""
        player.photo = relative_path
        await sync_to_async(player.save)(update_fields=['photo'])
