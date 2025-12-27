"""
Comando para resetear la base de datos completa o por competición

ADVERTENCIA: Este comando elimina TODOS los datos de las tablas seleccionadas.
Úsalo solo si vas a reimportar desde cero.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from predictions.models import (
    Match, Team, Player, TeamStats, HeadToHead,
    Prediction, Competition, TeamMarketValue
)


class Command(BaseCommand):
    help = 'Resetea la base de datos (elimina todos los datos)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar que se eliminaria sin borrar nada'
        )
        parser.add_argument(
            '--competition',
            type=str,
            help='Solo eliminar datos de esta competición (e.g., PL, BL1)'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirmar que realmente quieres eliminar los datos'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        comp_code = options['competition']
        confirm = options['confirm']

        self.stdout.write("=" * 80)
        self.stdout.write(self.style.ERROR('RESETEO DE BASE DE DATOS'))
        self.stdout.write("=" * 80)

        if not confirm and not dry_run:
            self.stdout.write(self.style.ERROR(
                "ADVERTENCIA: Este comando eliminara TODOS los datos."
            ))
            self.stdout.write(self.style.ERROR(
                "Usa --confirm para confirmar que quieres continuar."
            ))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] No se eliminara nada'))

        if comp_code:
            self.stdout.write(f"Competicion: {comp_code}")
        else:
            self.stdout.write(self.style.ERROR("TODAS LAS COMPETICIONES"))

        self.stdout.write("")

        # Contar registros actuales
        if comp_code:
            try:
                competition = Competition.objects.get(code=comp_code)

                matches_count = Match.objects.filter(competition=competition).count()
                teams_count = Team.objects.filter(competition=competition).count()
                players_count = Player.objects.filter(team__competition=competition).count()
                stats_count = TeamStats.objects.filter(competition=competition).count()
                h2h_count = HeadToHead.objects.filter(
                    team1__competition=competition
                ).count()
                predictions_count = Prediction.objects.filter(
                    match__competition=competition
                ).count()

            except Competition.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"Competicion {comp_code} no encontrada"
                ))
                return
        else:
            matches_count = Match.objects.count()
            teams_count = Team.objects.count()
            players_count = Player.objects.count()
            stats_count = TeamStats.objects.count()
            h2h_count = HeadToHead.objects.count()
            predictions_count = Prediction.objects.count()

        self.stdout.write("Registros a eliminar:")
        self.stdout.write("-" * 80)
        self.stdout.write(f"  Partidos: {matches_count}")
        self.stdout.write(f"  Equipos: {teams_count}")
        self.stdout.write(f"  Jugadores: {players_count}")
        self.stdout.write(f"  Estadisticas equipos: {stats_count}")
        self.stdout.write(f"  Head-to-Head: {h2h_count}")
        self.stdout.write(f"  Predicciones: {predictions_count}")
        self.stdout.write("")

        if not dry_run:
            self.stdout.write(self.style.WARNING("Eliminando datos..."))
            self.stdout.write("")

            with transaction.atomic():
                if comp_code:
                    # Eliminar solo datos de esta competición
                    deleted = {}

                    # Predicciones
                    count = Prediction.objects.filter(match__competition=competition).delete()
                    deleted['Predicciones'] = count[0]

                    # HeadToHead (más complejo, necesita filtrar por ambos equipos)
                    h2h_ids = []
                    for h2h in HeadToHead.objects.all():
                        if (h2h.team1.competition == competition or
                            h2h.team2.competition == competition):
                            h2h_ids.append(h2h.id)
                    count = HeadToHead.objects.filter(id__in=h2h_ids).delete()
                    deleted['HeadToHead'] = count[0]

                    # TeamStats
                    count = TeamStats.objects.filter(competition=competition).delete()
                    deleted['TeamStats'] = count[0]

                    # Players (a través de teams)
                    count = Player.objects.filter(team__competition=competition).delete()
                    deleted['Players'] = count[0]

                    # Matches
                    count = Match.objects.filter(competition=competition).delete()
                    deleted['Matches'] = count[0]

                    # Teams
                    count = Team.objects.filter(competition=competition).delete()
                    deleted['Teams'] = count[0]

                    self.stdout.write(self.style.SUCCESS("Datos eliminados:"))
                    for model, count in deleted.items():
                        self.stdout.write(f"  {model}: {count}")

                else:
                    # Eliminar TODO (excepto Competition)
                    self.stdout.write("Eliminando Predicciones...")
                    Prediction.objects.all().delete()

                    self.stdout.write("Eliminando HeadToHead...")
                    HeadToHead.objects.all().delete()

                    self.stdout.write("Eliminando TeamStats...")
                    TeamStats.objects.all().delete()

                    self.stdout.write("Eliminando TeamMarketValue...")
                    TeamMarketValue.objects.all().delete()

                    self.stdout.write("Eliminando Players...")
                    Player.objects.all().delete()

                    self.stdout.write("Eliminando Matches...")
                    Match.objects.all().delete()

                    self.stdout.write("Eliminando Teams...")
                    Team.objects.all().delete()

                    self.stdout.write("")
                    self.stdout.write(self.style.SUCCESS("TODOS los datos eliminados"))
                    self.stdout.write(self.style.WARNING(
                        "Competiciones mantenidas (solo se eliminaron datos)"
                    ))

        # Resumen
        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS('RESUMEN'))
        self.stdout.write("=" * 80)

        if dry_run:
            self.stdout.write(f"Se eliminarian {matches_count + teams_count + players_count + stats_count + h2h_count + predictions_count} registros en total")
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "DRY-RUN COMPLETADO. Para eliminar, ejecuta con --confirm"
            ))
        else:
            self.stdout.write(self.style.SUCCESS("BASE DE DATOS RESETEADA"))
            self.stdout.write("")
            self.stdout.write("Proximo paso:")
            self.stdout.write("  python manage.py import_sofascore_complete --competitions PL,PD,BL1,SA,FL1 --seasons 2020,2021,2022,2023,2024 --all-data")

        self.stdout.write("=" * 80)
