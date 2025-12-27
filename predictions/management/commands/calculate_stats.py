"""
Comando Django para calcular TODAS las estadísticas (TeamStats + HeadToHead)
Uso: python manage.py calculate_stats --seasons 2023,2024 --competitions PL,PD
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Calcula todas las estadísticas: TeamStats y Head to Head'

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
        parser.add_argument(
            '--skip-team-stats',
            action='store_true',
            help='Saltar cálculo de estadísticas de equipos'
        )
        parser.add_argument(
            '--skip-h2h',
            action='store_true',
            help='Saltar cálculo de head to head'
        )

    def handle(self, *args, **options):
        self.stdout.write("")
        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS('CÁLCULO DE ESTADÍSTICAS COMPLETO'))
        self.stdout.write("="*70)
        self.stdout.write("")

        # Preparar argumentos comunes
        common_args = []
        if options['competitions']:
            common_args.extend(['--competitions', options['competitions']])
        if options['force']:
            common_args.append('--force')

        # 1. Calcular estadísticas de equipos
        if not options['skip_team_stats']:
            self.stdout.write(self.style.WARNING('PASO 1/2: Calculando estadísticas de equipos...'))
            self.stdout.write("")

            team_stats_args = common_args.copy()
            if options['seasons']:
                team_stats_args.extend(['--seasons', options['seasons']])

            call_command('calculate_team_stats', *team_stats_args)
            self.stdout.write("")

        # 2. Calcular Head to Head
        if not options['skip_h2h']:
            self.stdout.write(self.style.WARNING('PASO 2/2: Calculando head to head...'))
            self.stdout.write("")

            call_command('calculate_head_to_head', *common_args)
            self.stdout.write("")

        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS('PROCESO COMPLETO FINALIZADO'))
        self.stdout.write("="*70)
