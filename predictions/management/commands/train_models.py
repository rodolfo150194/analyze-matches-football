"""
Comando Django para entrenar modelos de Machine Learning
Uso: python manage.py train_models
"""

from django.core.management.base import BaseCommand
from predictions.models import Match, Competition
from datetime import datetime
import os
import sys


class Command(BaseCommand):
    help = 'Entrena los modelos de Machine Learning con los datos históricos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--competitions',
            type=str,
            default='PL,PD,BL1,CL',
            help='Códigos de competiciones separados por coma'
        )
        parser.add_argument(
            '--seasons',
            type=str,
            default='2023,2024',
            help='Temporadas separadas por coma'
        )

    def handle(self, *args, **options):
        # Parse competiciones y temporadas
        competitions = options['competitions'].split(',')
        seasons = [int(s) for s in options['seasons'].split(',')]

        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS('ENTRENAMIENTO DE MODELOS ML'))
        self.stdout.write("="*70)
        self.stdout.write(f"Competiciones: {', '.join(competitions)}")
        self.stdout.write(f"Temporadas: {', '.join(map(str, seasons))}")
        self.stdout.write("")

        # Verificar datos
        total_matches = 0
        for comp_code in competitions:
            try:
                comp = Competition.objects.get(code=comp_code)
                for season in seasons:
                    count = Match.objects.filter(
                        competition=comp,
                        season=season,
                        status='FINISHED'
                    ).count()
                    total_matches += count
                    self.stdout.write(f"  {comp_code} {season}: {count} partidos")
            except Competition.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  {comp_code}: No encontrada"))

        self.stdout.write("")
        self.stdout.write(f"Total partidos disponibles: {total_matches}")

        if total_matches < 100:
            self.stdout.write(self.style.ERROR('ERROR: Insuficientes datos para entrenar'))
            self.stdout.write('Ejecuta primero: python manage.py import_leagues')
            return

        self.stdout.write("")
        self.stdout.write("Iniciando entrenamiento...")
        self.stdout.write("")

        try:
            from predictions.ml.predictor import EnhancedPredictor

            # Crear predictor
            predictor = EnhancedPredictor()

            # Entrenar modelos
            results = predictor.train(competitions, seasons)

            # Guardar modelos
            models_path = os.path.join('predictions', 'ml', 'enhanced_models.pkl')
            predictor.save_models(models_path)

            self.stdout.write("")
            self.stdout.write("="*70)
            self.stdout.write(self.style.SUCCESS('ENTRENAMIENTO COMPLETADO'))
            self.stdout.write("="*70)
            self.stdout.write(f"Modelos guardados en: {models_path}")
            self.stdout.write("")

        except ImportError as e:
            self.stdout.write(self.style.ERROR(f'Error importando predictor: {e}'))
            self.stdout.write('')
            self.stdout.write('Asegurate de tener instaladas las dependencias:')
            self.stdout.write('  pip install pandas numpy scikit-learn xgboost lightgbm')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error durante el entrenamiento: {e}'))
            import traceback
            traceback.print_exc()
