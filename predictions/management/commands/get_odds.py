"""
Comando Django para obtener cuotas de casas de apuestas con análisis de value bets
Uso: python manage.py get_odds --days 7 --competitions PL,PD
"""

from django.core.management.base import BaseCommand
from predictions.models import Match, Competition, Prediction
from django.utils import timezone
from datetime import timedelta
import requests
import os
import sys
from pathlib import Path

# Importar funciones del value_analyzer
sys.path.append(str(Path(__file__).parent.parent.parent / 'ml'))
from dataclasses import dataclass
from typing import Optional


# ============================================================================
# FUNCIONES DE VALUE BET ANALYSIS (desde betting-analyst skill)
# ============================================================================

@dataclass
class ValueBet:
    outcome: str
    model_prob: float
    odds: float
    implied_prob: float
    edge: float
    grade: str
    kelly_fraction: float
    stake: float
    ev: float
    roi: float
    is_value: bool


def calculate_implied_probability(odds: float) -> float:
    """Convert decimal odds to implied probability."""
    return 1 / odds


def calculate_margin(home_odds: float, draw_odds: float, away_odds: float) -> float:
    """Calculate bookmaker margin (overround)."""
    return (1/home_odds + 1/draw_odds + 1/away_odds - 1) * 100


def calculate_edge(model_prob: float, implied_prob: float) -> float:
    """Calculate edge (model vs market)."""
    return model_prob - implied_prob


def grade_bet(edge: float) -> str:
    """Grade bet quality by edge size."""
    if edge > 0.10:
        return "A+"
    elif edge > 0.07:
        return "A"
    elif edge > 0.05:
        return "B"
    elif edge > 0.03:
        return "C"
    elif edge > 0.02:
        return "D"
    else:
        return "F"


def kelly_stake(probability: float, odds: float, bankroll: float,
                fraction: float = 0.25, max_stake_pct: float = 0.05) -> tuple:
    """Calculate Kelly criterion stake."""
    edge = probability * odds - 1
    if edge <= 0:
        return 0, 0

    kelly_fraction = edge / (odds - 1)
    stake = bankroll * kelly_fraction * fraction

    # Cap at max stake
    stake = min(stake, bankroll * max_stake_pct)

    return stake, kelly_fraction


def calculate_ev(probability: float, odds: float, stake: float) -> tuple:
    """Calculate expected value and ROI."""
    win_amount = stake * (odds - 1)
    lose_amount = stake

    ev = (probability * win_amount) - ((1 - probability) * lose_amount)
    roi = ev / stake * 100 if stake > 0 else 0

    return ev, roi


def analyze_bet(model_prob: float, odds: float, bankroll: float,
                outcome: str = "unknown", kelly_fraction: float = 0.25,
                min_edge: float = 0.03) -> ValueBet:
    """Complete value bet analysis."""
    implied_prob = calculate_implied_probability(odds)
    edge = calculate_edge(model_prob, implied_prob)
    grade = grade_bet(edge)
    stake, kelly = kelly_stake(model_prob, odds, bankroll, kelly_fraction)
    ev, roi = calculate_ev(model_prob, odds, stake) if stake > 0 else (0, 0)
    is_value = edge >= min_edge

    return ValueBet(
        outcome=outcome,
        model_prob=model_prob,
        odds=odds,
        implied_prob=implied_prob,
        edge=edge,
        grade=grade,
        kelly_fraction=kelly,
        stake=stake,
        ev=ev,
        roi=roi,
        is_value=is_value
    )


def analyze_match(home_prob: float, draw_prob: float, away_prob: float,
                  home_odds: float, draw_odds: float, away_odds: float,
                  bankroll: float = 1000, kelly_fraction: float = 0.25,
                  min_edge: float = 0.03) -> dict:
    """Analyze all outcomes for a match."""
    margin = calculate_margin(home_odds, draw_odds, away_odds)

    analyses = {
        "home": analyze_bet(home_prob, home_odds, bankroll, "Home Win",
                           kelly_fraction, min_edge),
        "draw": analyze_bet(draw_prob, draw_odds, bankroll, "Draw",
                           kelly_fraction, min_edge),
        "away": analyze_bet(away_prob, away_odds, bankroll, "Away Win",
                           kelly_fraction, min_edge),
    }

    value_bets = [k for k, v in analyses.items() if v.is_value]
    best_value = max(analyses.items(), key=lambda x: x[1].edge)

    return {
        "margin": margin,
        "analyses": analyses,
        "value_bets": value_bets,
        "best_value": best_value[0] if best_value[1].is_value else None,
    }


# ============================================================================
# COMANDO DJANGO
# ============================================================================

class Command(BaseCommand):
    help = 'Obtiene cuotas de casas de apuestas para partidos próximos'

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
            default='PL,PD',
            help='Códigos de competiciones'
        )
        parser.add_argument(
            '--bankroll',
            type=float,
            default=1000,
            help='Bankroll para cálculo de stakes (default: 1000)'
        )
        parser.add_argument(
            '--kelly',
            type=float,
            default=0.25,
            help='Kelly fraction (default: 0.25 = quarter Kelly)'
        )
        parser.add_argument(
            '--min-edge',
            type=float,
            default=0.03,
            help='Minimum edge threshold for value (default: 0.03 = 3%)'
        )

    def format_table_header(self):
        """Formato de header para la tabla de análisis"""
        header = f"\n{'':2}{'PARTIDO':<40}{'MERCADO':<12}{'CUOTA':>7}{'MODEL':>7}{'IMPL':>7}{'EDGE':>7}{'GRADE':>7}{'STAKE':>10}{'EV':>10}{'ROI':>7}"
        separator = "=" * 120
        return f"{separator}\n{header}\n{separator}"

    def format_match_row(self, home_team, away_team, market, analysis, currency="€"):
        """Formato de fila para cada mercado analizado"""
        status = "✓" if analysis.is_value else "✗"
        match_name = f"{home_team} vs {away_team}"

        return (f"{status:2}{match_name:<40}{market:<12}"
                f"{analysis.odds:>7.2f}{analysis.model_prob*100:>6.1f}%"
                f"{analysis.implied_prob*100:>6.1f}%{analysis.edge*100:>6.1f}%"
                f"{analysis.grade:>7}{currency}{analysis.stake:>9.2f}"
                f"{currency}{analysis.ev:>9.2f}{analysis.roi:>6.1f}%")

    def handle(self, *args, **options):
        days = options['days']
        competitions = options['competitions'].split(',')
        bankroll = options['bankroll']
        kelly_fraction = options['kelly']
        min_edge = options['min_edge']

        # API Key de The Odds API
        api_key = os.getenv('API_KEY_ODDS')
        if not api_key:
            self.stdout.write(self.style.ERROR('ERROR: API_KEY_ODDS no configurada'))
            self.stdout.write('Configura la variable de entorno API_KEY_ODDS')
            return

        self.stdout.write("="*120)
        self.stdout.write(self.style.SUCCESS('ANÁLISIS DE VALUE BETS - CUOTAS vs MODELO'))
        self.stdout.write("="*120)
        self.stdout.write(f"Próximos {days} días | Bankroll: €{bankroll:.2f} | Kelly: {kelly_fraction:.2f} | Min Edge: {min_edge*100:.1f}%")
        self.stdout.write(f"Competiciones: {', '.join(competitions)}")

        # Mapeo de competiciones a sport keys de The Odds API
        SPORT_KEYS = {
            'PL': 'soccer_epl',
            'PD': 'soccer_spain_la_liga',
            'BL1': 'soccer_germany_bundesliga',
            'SA': 'soccer_italy_serie_a',
            'FL1': 'soccer_france_ligue_one',
            'CL': 'soccer_uefa_champs_league',
        }

        base_url = "https://api.the-odds-api.com/v4/sports"

        total_matches = 0
        total_value_bets = 0
        total_ev = 0

        for comp_code in competitions:
            if comp_code not in SPORT_KEYS:
                self.stdout.write(self.style.WARNING(f'\n{comp_code}: No soportada'))
                continue

            sport_key = SPORT_KEYS[comp_code]

            try:
                # Obtener odds de la API
                url = f"{base_url}/{sport_key}/odds"
                params = {
                    'apiKey': api_key,
                    'regions': 'eu,us',
                    'markets': 'h2h,totals,spreads',
                    'oddsFormat': 'decimal'
                }

                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                events = response.json()

                if not events:
                    self.stdout.write(f"\n{comp_code}: Sin partidos próximos")
                    continue

                # Mostrar header de tabla
                self.stdout.write(f"\n{comp_code} - {len(events)} partidos encontrados")
                self.stdout.write(self.format_table_header())

                # Analizar cada partido
                for event in events:
                    home_team_name = event.get('home_team')
                    away_team_name = event.get('away_team')

                    # Extraer cuotas h2h (1X2)
                    bookmakers = event.get('bookmakers', [])
                    if not bookmakers:
                        continue

                    markets = bookmakers[0].get('markets', [])
                    h2h_market = next((m for m in markets if m['key'] == 'h2h'), None)

                    if not h2h_market:
                        continue

                    outcomes = h2h_market.get('outcomes', [])
                    if len(outcomes) < 3:
                        continue

                    # Mapear cuotas
                    odds_map = {o['name']: o['price'] for o in outcomes}
                    home_odds = odds_map.get(home_team_name)
                    away_odds = odds_map.get(away_team_name)

                    # Encontrar cuota de empate (puede tener nombre variable)
                    draw_odds = None
                    for name, odds in odds_map.items():
                        if name.lower() in ['draw', 'tie', 'empate']:
                            draw_odds = odds
                            break

                    # Si no se encuentra draw por nombre, usar la tercera cuota
                    if draw_odds is None:
                        draw_odds = [v for k, v in odds_map.items()
                                    if k not in [home_team_name, away_team_name]][0]

                    if not all([home_odds, draw_odds, away_odds]):
                        continue

                    # Buscar predicción del modelo en la base de datos
                    try:
                        # Buscar partido por nombres de equipos
                        match = Match.objects.filter(
                            home_team__name__icontains=home_team_name.split()[-1],
                            away_team__name__icontains=away_team_name.split()[-1],
                            status='SCHEDULED',
                            utc_date__gte=timezone.now(),
                            utc_date__lte=timezone.now() + timedelta(days=days)
                        ).select_related('home_team', 'away_team').first()

                        if not match:
                            self.stdout.write(f"  {home_team_name} vs {away_team_name} - Sin predicción en BD")
                            continue

                        # Buscar predicción
                        prediction = Prediction.objects.filter(match=match).first()

                        if not prediction:
                            self.stdout.write(f"  {match.home_team.name} vs {match.away_team.name} - Sin predicción del modelo")
                            continue

                        # Analizar value bets
                        analysis = analyze_match(
                            prediction.prob_home,
                            prediction.prob_draw,
                            prediction.prob_away,
                            home_odds,
                            draw_odds,
                            away_odds,
                            bankroll,
                            kelly_fraction,
                            min_edge
                        )

                        # Mostrar análisis para cada mercado
                        for market_name, market_key in [('Home Win', 'home'),
                                                         ('Draw', 'draw'),
                                                         ('Away Win', 'away')]:
                            bet = analysis['analyses'][market_key]
                            row = self.format_match_row(
                                match.home_team.short_name,
                                match.away_team.short_name,
                                market_name,
                                bet
                            )

                            # Colorear según si es value bet
                            if bet.is_value:
                                self.stdout.write(self.style.SUCCESS(row))
                                total_value_bets += 1
                                total_ev += bet.ev
                            else:
                                self.stdout.write(row)

                        total_matches += 1

                    except Exception as e:
                        self.stdout.write(f"  Error analizando {home_team_name} vs {away_team_name}: {e}")
                        continue

                # Mostrar uso de API
                remaining = response.headers.get('x-requests-remaining')
                if remaining:
                    self.stdout.write(f"\n  API Requests restantes: {remaining}")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"\n{comp_code} [ERROR]: {e}"))

        # Resumen final
        self.stdout.write("\n" + "="*120)
        self.stdout.write(self.style.SUCCESS(f'RESUMEN: {total_matches} partidos analizados | {total_value_bets} value bets encontradas | EV Total: €{total_ev:.2f}'))
        self.stdout.write("="*120)
