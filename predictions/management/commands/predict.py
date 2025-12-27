"""
Comando Django para generar predicciones de partidos próximos
Uso:
  python manage.py predict --days 7 --method ml
  python manage.py predict --days 7 --method ensemble
  python manage.py predict --days 7 --method ensemble --find-value
"""

from django.core.management.base import BaseCommand
from predictions.models import Match, Prediction, Competition
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Genera predicciones para partidos próximos usando ML, Poisson o Ensemble'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Número de días hacia adelante'
        )
        parser.add_argument(
            '--competitions',
            type=str,
            default='PL,PD,BL1,CL',
            help='Códigos de competiciones'
        )
        parser.add_argument(
            '--method',
            type=str,
            default='ensemble',
            choices=['ml', 'ensemble'],
            help='Método de predicción: ml (solo ML) o ensemble (ML + Poisson)'
        )
        parser.add_argument(
            '--find-value',
            action='store_true',
            help='Buscar value bets comparando con odds de bookmakers'
        )
        parser.add_argument(
            '--min-edge',
            type=float,
            default=0.05,
            help='Edge mínimo para value bets (default: 0.05 = 5%%)'
        )

    def handle(self, *args, **options):
        days = options['days']
        competitions = options['competitions'].split(',')
        method = options['method']
        find_value = options['find_value']
        min_edge = options['min_edge']

        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS('GENERACIÓN DE PREDICCIONES'))
        self.stdout.write("="*70)
        self.stdout.write(f"Próximos {days} días")
        self.stdout.write(f"Competiciones: {', '.join(competitions)}")
        self.stdout.write(f"Método: {method.upper()}")
        if find_value:
            self.stdout.write(f"Buscando value bets (edge mínimo: {min_edge:.1%})")
        self.stdout.write("")

        # Obtener partidos próximos
        start_date = timezone.now()
        end_date = start_date + timedelta(days=days)

        upcoming_matches = Match.objects.filter(
            competition__code__in=competitions,
            utc_date__gte=start_date,
            utc_date__lte=end_date,
            status__in=['SCHEDULED', 'TIMED']  # Incluir TIMED (partidos con hora confirmada)
        ).order_by('utc_date')

        self.stdout.write(f"Partidos encontrados: {upcoming_matches.count()}")

        if upcoming_matches.count() == 0:
            self.stdout.write(self.style.WARNING('No hay partidos próximos'))
            return

        self.stdout.write("")

        # Cargar predictor según el método seleccionado
        try:
            import os

            if method == 'ml':
                from predictions.ml.predictor import EnhancedPredictor
                predictor = EnhancedPredictor()
                models_path = os.path.join('predictions', 'ml', 'enhanced_models.pkl')

                if not os.path.exists(models_path):
                    self.stdout.write(self.style.WARNING(
                        'ADVERTENCIA: Modelos ML no encontrados. Ejecuta primero:'
                    ))
                    self.stdout.write('  python manage.py train_models')
                    return

                predictor.load_models(models_path)
                self.stdout.write(self.style.SUCCESS('Modelos ML cargados exitosamente'))

            elif method == 'ensemble':
                from predictions.ml.ensemble import EnsemblePredictor, ValueBetDetector

                predictor = EnsemblePredictor(
                    ml_weight=0.70,  # 70% ML, 30% Poisson para resultados
                    use_dixon_coles=True
                )
                self.stdout.write(self.style.SUCCESS('Ensemble predictor inicializado (ML + Dixon-Coles)'))

                if find_value:
                    value_detector = ValueBetDetector(predictor, min_edge=min_edge)
                    self.stdout.write(self.style.SUCCESS(f'Value bet detector activado (edge min: {min_edge:.1%})'))

            self.stdout.write("")

            # Generar predicciones
            predictions_created = 0
            value_bets_found = 0

            for match in upcoming_matches:
                try:
                    # Hacer predicción según el método
                    if method == 'ml':
                        # ML usa parámetros separados
                        predictions = predictor.predict_match(
                            home_team_id=match.home_team_id,
                            away_team_id=match.away_team_id,
                            match_date=match.utc_date,
                            competition_id=match.competition_id,
                            season=match.season
                        )
                        # Adaptar formato para guardar en BD
                        prob_home = predictions['result']['home_win']
                        prob_draw = predictions['result']['draw']
                        prob_away = predictions['result']['away_win']
                        prob_over_25 = predictions['over_25']['yes']
                        prob_btts = predictions['btts']['yes']
                        predicted_corners = predictions.get('total_corners', {}).get('predicted')
                        most_likely = predictions['result']['most_likely']
                        confidence = None
                        lambda_home = None
                        lambda_away = None

                    elif method == 'ensemble':
                        # Ensemble usa el objeto Match directamente
                        predictions = predictor.predict_match(match)
                        prob_home = predictions['prob_home']
                        prob_draw = predictions['prob_draw']
                        prob_away = predictions['prob_away']
                        prob_over_25 = predictions['prob_over_25']
                        prob_btts = predictions['prob_btts']
                        predicted_corners = None
                        confidence = predictions.get('confidence', 70)
                        lambda_home = predictions.get('lambda_home')
                        lambda_away = predictions.get('lambda_away')

                        # Determinar resultado más probable
                        max_prob = max(prob_home, prob_draw, prob_away)
                        if max_prob == prob_home:
                            most_likely = 'home_win'
                        elif max_prob == prob_draw:
                            most_likely = 'draw'
                        else:
                            most_likely = 'away_win'

                    # Guardar en base de datos
                    from predictions.models import Prediction

                    prediction_obj, created = Prediction.objects.update_or_create(
                        match=match,
                        defaults={
                            'prob_home': prob_home,
                            'prob_draw': prob_draw,
                            'prob_away': prob_away,
                            'prob_over_25': prob_over_25,
                            'prob_btts': prob_btts,
                            'predicted_corners': predicted_corners,
                        }
                    )

                    if created:
                        predictions_created += 1

                    # Mostrar predicción
                    self.stdout.write(
                        f"\n{match.utc_date.strftime('%Y-%m-%d %H:%M')} - "
                        f"{match.competition.code}: "
                        f"{match.home_team.name} vs {match.away_team.name}"
                    )
                    self.stdout.write(
                        f"  Resultado: H {prob_home:.2%} | "
                        f"D {prob_draw:.2%} | "
                        f"A {prob_away:.2%}"
                    )
                    self.stdout.write(f"  Mas probable: {most_likely}")
                    self.stdout.write(f"  Over 2.5: {prob_over_25:.2%}")
                    self.stdout.write(f"  BTTS: {prob_btts:.2%}")

                    if method == 'ensemble' and confidence:
                        self.stdout.write(f"  Confianza: {confidence}%")
                    if lambda_home and lambda_away:
                        self.stdout.write(
                            f"  Goles esperados: {lambda_home:.2f} - {lambda_away:.2f} "
                            f"(Total: {lambda_home + lambda_away:.2f})"
                        )

                    # Buscar value bets si está activado
                    if find_value and method == 'ensemble':
                        try:
                            value_bets = value_detector.find_value_bets(match)
                            if value_bets:
                                value_bets_found += len(value_bets)
                                self.stdout.write(self.style.SUCCESS(
                                    f"  >>> VALUE BETS ENCONTRADAS: {len(value_bets)}"
                                ))
                                for vb in value_bets:
                                    self.stdout.write(
                                        f"      {vb['market'].upper()}: "
                                        f"Edge {vb['edge']:.1%} | "
                                        f"Model {vb['model_prob']:.2%} vs Book {vb['implied_prob']:.2%} | "
                                        f"Odds {vb['odds']:.2f} | "
                                        f"Stake sugerido: {vb['recommended_stake']:.1f}%"
                                    )
                        except Exception as ve:
                            pass  # Silenciar errores de value bet para no interrumpir

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  Error en predicción: {e}"))
                    import traceback
                    traceback.print_exc()
                    continue

            self.stdout.write("")
            self.stdout.write("="*70)
            self.stdout.write(self.style.SUCCESS(f'Total predicciones generadas: {predictions_created}'))
            if find_value and value_bets_found > 0:
                self.stdout.write(self.style.SUCCESS(f'Value bets encontradas: {value_bets_found}'))
            self.stdout.write("="*70)

        except ImportError as e:
            self.stdout.write(self.style.ERROR(f'Error importando predictor: {e}'))
            self.stdout.write('Asegurate de tener instaladas las dependencias:')
            self.stdout.write('  pip install pandas numpy scikit-learn xgboost lightgbm')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error durante la predicción: {e}'))
            import traceback
            traceback.print_exc()
