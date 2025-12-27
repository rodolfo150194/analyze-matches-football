"""
Comando Django para importar datos de ligas desde Football-Data.co.uk
Uso: python manage.py import_leagues --years 2015-2024
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from predictions.models import Competition, Team, Match
import requests
import pandas as pd
from io import StringIO
from datetime import datetime


class Command(BaseCommand):
    help = 'Importa datos históricos desde Football-Data.co.uk CSVs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--years',
            type=str,
            default='2015-2024',
            help='Rango de años (ej: 2015-2024)'
        )
        parser.add_argument(
            '--competitions',
            type=str,
            default='PL,PD,BL1,SA,FL1',
            help='Códigos de competiciones separados por coma'
        )

    def handle(self, *args, **options):
        # Parse años
        year_range = options['years'].split('-')
        start_year = int(year_range[0])
        end_year = int(year_range[1])
        seasons = list(range(start_year, end_year + 1))

        # Parse competiciones
        competitions = options['competitions'].split(',')

        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS('IMPORTACIÓN DESDE FOOTBALL-DATA.CO.UK'))
        self.stdout.write("="*70)
        self.stdout.write(f"Competiciones: {', '.join(competitions)}")
        self.stdout.write(f"Temporadas: {seasons[0]}-{seasons[-1]}")
        self.stdout.write(f"Total: {len(competitions)} x {len(seasons)} = {len(competitions)*len(seasons)} combinaciones")
        self.stdout.write("")

        total_imported = 0

        for comp_code in competitions:
            for season in seasons:
                imported = self.import_season(comp_code, season)
                total_imported += imported

        self.stdout.write("")
        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS(f'COMPLETADO: {total_imported} partidos importados'))
        self.stdout.write("="*70)

    def import_season(self, comp_code, season):
        """Importar una temporada específica"""

        # Mapeo de competiciones a códigos CSV
        COMPETITION_CSV_CODES = {
            'PL': {'csv': 'E0', 'name': 'Premier League', 'country': 'England'},
            'PD': {'csv': 'SP1', 'name': 'La Liga', 'country': 'Spain'},
            'BL1': {'csv': 'D1', 'name': 'Bundesliga', 'country': 'Germany'},
            'SA': {'csv': 'I1', 'name': 'Serie A', 'country': 'Italy'},
            'FL1': {'csv': 'F1', 'name': 'Ligue 1', 'country': 'France'},
        }

        if comp_code not in COMPETITION_CSV_CODES:
            self.stdout.write(self.style.ERROR(f'Competición {comp_code} no soportada'))
            return 0

        comp_info = COMPETITION_CSV_CODES[comp_code]
        csv_code = comp_info['csv']

        # Construir URL
        season_str = f"{str(season)[2:]}{str(season+1)[2:]}"
        url = f"https://www.football-data.co.uk/mmz4281/{season_str}/{csv_code}.csv"

        self.stdout.write(f"\n{comp_code} {season}/{season+1}:")
        self.stdout.write(f"  Descargando: {url}")

        try:
            # Descargar CSV
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            df = pd.read_csv(StringIO(response.text), encoding='utf-8')

            self.stdout.write(f"  Descargado: {len(df)} partidos")

            # Asegurar competición
            competition, created = Competition.objects.get_or_create(
                code=comp_code,
                defaults={
                    'name': comp_info['name'],
                    'country': comp_info['country']
                }
            )

            if created:
                self.stdout.write(f"  Competición creada: {comp_info['name']}")

            imported = 0
            updated = 0

            # Procesar cada partido
            for idx, row in df.iterrows():
                try:
                    # Parsear fecha
                    date_str = str(row.get('Date', ''))
                    if not date_str or date_str == 'nan':
                        continue

                    try:
                        if len(date_str.split('/')[-1]) == 2:
                            match_date = datetime.strptime(date_str, '%d/%m/%y')
                        else:
                            match_date = datetime.strptime(date_str, '%d/%m/%Y')
                    except:
                        continue

                    # Obtener equipos
                    home_team_name = str(row.get('HomeTeam', '')).strip()
                    away_team_name = str(row.get('AwayTeam', '')).strip()

                    if not home_team_name or not away_team_name:
                        continue

                    # Crear o obtener equipos
                    home_team, _ = Team.objects.get_or_create(
                        name=home_team_name,
                        defaults={
                            'short_name': home_team_name[:30],
                            'tla': home_team_name[:3].upper(),
                            'competition': competition
                        }
                    )

                    away_team, _ = Team.objects.get_or_create(
                        name=away_team_name,
                        defaults={
                            'short_name': away_team_name[:30],
                            'tla': away_team_name[:3].upper(),
                            'competition': competition
                        }
                    )

                    # Obtener resultados
                    fthg = row.get('FTHG')
                    ftag = row.get('FTAG')

                    # Verificar si ya existe (buscar por fecha, equipos y competición)
                    # IMPORTANTE: Buscar primero para evitar duplicados
                    existing_matches = Match.objects.filter(
                        competition=competition,
                        season=season,
                        home_team=home_team,
                        away_team=away_team,
                        utc_date__date=match_date.date()
                    )

                    if existing_matches.exists():
                        # Ya existe, actualizar el primero
                        match = existing_matches.first()
                        created = False
                    else:
                        # No existe, crear nuevo
                        match = Match.objects.create(
                            competition=competition,
                            season=season,
                            home_team=home_team,
                            away_team=away_team,
                            utc_date=match_date,
                            status='FINISHED' if pd.notna(fthg) else 'SCHEDULED',
                            home_score=int(fthg) if pd.notna(fthg) else None,
                            away_score=int(ftag) if pd.notna(ftag) else None,
                        )
                        created = True

                    # Actualizar campos básicos (para partidos existentes y nuevos)
                    match.status = 'FINISHED' if pd.notna(fthg) else 'SCHEDULED'
                    match.home_score = int(fthg) if pd.notna(fthg) else None
                    match.away_score = int(ftag) if pd.notna(ftag) else None

                    # Half-time scores
                    if 'HTHG' in row and pd.notna(row['HTHG']):
                        match.home_score_ht = int(row['HTHG'])
                    if 'HTAG' in row and pd.notna(row['HTAG']):
                        match.away_score_ht = int(row['HTAG'])

                    # Match information
                    if 'Attendance' in row and pd.notna(row['Attendance']):
                        try:
                            match.attendance = int(row['Attendance'])
                        except:
                            pass
                    if 'Referee' in row and pd.notna(row['Referee']):
                        match.referee = str(row['Referee'])

                    # Shots
                    if 'HS' in row and pd.notna(row['HS']):
                        match.shots_home = int(row['HS'])
                    if 'AS' in row and pd.notna(row['AS']):
                        match.shots_away = int(row['AS'])
                    if 'HST' in row and pd.notna(row['HST']):
                        match.shots_on_target_home = int(row['HST'])
                    if 'AST' in row and pd.notna(row['AST']):
                        match.shots_on_target_away = int(row['AST'])

                    # Corners
                    if 'HC' in row and pd.notna(row['HC']):
                        match.corners_home = int(row['HC'])
                    if 'AC' in row and pd.notna(row['AC']):
                        match.corners_away = int(row['AC'])

                    # Fouls and offsides
                    if 'HF' in row and pd.notna(row['HF']):
                        match.fouls_home = int(row['HF'])
                    if 'AF' in row and pd.notna(row['AF']):
                        match.fouls_away = int(row['AF'])
                    if 'HO' in row and pd.notna(row['HO']):
                        match.offsides_home = int(row['HO'])
                    if 'AO' in row and pd.notna(row['AO']):
                        match.offsides_away = int(row['AO'])

                    # Cards
                    if 'HY' in row and pd.notna(row['HY']):
                        match.yellow_cards_home = int(row['HY'])
                    if 'AY' in row and pd.notna(row['AY']):
                        match.yellow_cards_away = int(row['AY'])
                    if 'HR' in row and pd.notna(row['HR']):
                        match.red_cards_home = int(row['HR'])
                    if 'AR' in row and pd.notna(row['AR']):
                        match.red_cards_away = int(row['AR'])

                    # Additional statistics
                    if 'HHW' in row and pd.notna(row['HHW']):
                        match.hit_woodwork_home = int(row['HHW'])
                    if 'AHW' in row and pd.notna(row['AHW']):
                        match.hit_woodwork_away = int(row['AHW'])
                    if 'HFKC' in row and pd.notna(row['HFKC']):
                        match.free_kicks_conceded_home = int(row['HFKC'])
                    if 'AFKC' in row and pd.notna(row['AFKC']):
                        match.free_kicks_conceded_away = int(row['AFKC'])
                    if 'HBP' in row and pd.notna(row['HBP']):
                        match.booking_points_home = int(row['HBP'])
                    if 'ABP' in row and pd.notna(row['ABP']):
                        match.booking_points_away = int(row['ABP'])

                    # Betting Odds - Match Result (1X2)
                    # Market aggregates
                    if 'MaxH' in row and pd.notna(row['MaxH']):
                        match.max_odds_home = float(row['MaxH'])
                    if 'MaxD' in row and pd.notna(row['MaxD']):
                        match.max_odds_draw = float(row['MaxD'])
                    if 'MaxA' in row and pd.notna(row['MaxA']):
                        match.max_odds_away = float(row['MaxA'])
                    if 'AvgH' in row and pd.notna(row['AvgH']):
                        match.avg_odds_home = float(row['AvgH'])
                    if 'AvgD' in row and pd.notna(row['AvgD']):
                        match.avg_odds_draw = float(row['AvgD'])
                    if 'AvgA' in row and pd.notna(row['AvgA']):
                        match.avg_odds_away = float(row['AvgA'])

                    # Bet365 odds
                    if 'B365H' in row and pd.notna(row['B365H']):
                        match.b365_odds_home = float(row['B365H'])
                    if 'B365D' in row and pd.notna(row['B365D']):
                        match.b365_odds_draw = float(row['B365D'])
                    if 'B365A' in row and pd.notna(row['B365A']):
                        match.b365_odds_away = float(row['B365A'])

                    # Pinnacle odds (PSH/PSD/PSA or PH/PD/PA)
                    if 'PSH' in row and pd.notna(row['PSH']):
                        match.ps_odds_home = float(row['PSH'])
                    elif 'PH' in row and pd.notna(row['PH']):
                        match.ps_odds_home = float(row['PH'])
                    if 'PSD' in row and pd.notna(row['PSD']):
                        match.ps_odds_draw = float(row['PSD'])
                    elif 'PD' in row and pd.notna(row['PD']):
                        match.ps_odds_draw = float(row['PD'])
                    if 'PSA' in row and pd.notna(row['PSA']):
                        match.ps_odds_away = float(row['PSA'])
                    elif 'PA' in row and pd.notna(row['PA']):
                        match.ps_odds_away = float(row['PA'])

                    # William Hill odds
                    if 'WHH' in row and pd.notna(row['WHH']):
                        match.wh_odds_home = float(row['WHH'])
                    if 'WHD' in row and pd.notna(row['WHD']):
                        match.wh_odds_draw = float(row['WHD'])
                    if 'WHA' in row and pd.notna(row['WHA']):
                        match.wh_odds_away = float(row['WHA'])

                    # Betfair odds
                    if 'BFH' in row and pd.notna(row['BFH']):
                        match.bf_odds_home = float(row['BFH'])
                    if 'BFD' in row and pd.notna(row['BFD']):
                        match.bf_odds_draw = float(row['BFD'])
                    if 'BFA' in row and pd.notna(row['BFA']):
                        match.bf_odds_away = float(row['BFA'])

                    # Betbrain aggregates
                    if 'Bb1X2' in row and pd.notna(row['Bb1X2']):
                        match.betbrain_num_bookmakers = int(row['Bb1X2'])
                    if 'BbMxH' in row and pd.notna(row['BbMxH']):
                        match.betbrain_max_odds_home = float(row['BbMxH'])
                    if 'BbMxD' in row and pd.notna(row['BbMxD']):
                        match.betbrain_max_odds_draw = float(row['BbMxD'])
                    if 'BbMxA' in row and pd.notna(row['BbMxA']):
                        match.betbrain_max_odds_away = float(row['BbMxA'])
                    if 'BbAvH' in row and pd.notna(row['BbAvH']):
                        match.betbrain_avg_odds_home = float(row['BbAvH'])
                    if 'BbAvD' in row and pd.notna(row['BbAvD']):
                        match.betbrain_avg_odds_draw = float(row['BbAvD'])
                    if 'BbAvA' in row and pd.notna(row['BbAvA']):
                        match.betbrain_avg_odds_away = float(row['BbAvA'])

                    # Betting Odds - Over/Under 2.5 Goals
                    if 'Max>2.5' in row and pd.notna(row['Max>2.5']):
                        match.max_odds_over_25 = float(row['Max>2.5'])
                    if 'Max<2.5' in row and pd.notna(row['Max<2.5']):
                        match.max_odds_under_25 = float(row['Max<2.5'])
                    if 'Avg>2.5' in row and pd.notna(row['Avg>2.5']):
                        match.avg_odds_over_25 = float(row['Avg>2.5'])
                    if 'Avg<2.5' in row and pd.notna(row['Avg<2.5']):
                        match.avg_odds_under_25 = float(row['Avg<2.5'])

                    # Bet365 O/U 2.5
                    if 'B365>2.5' in row and pd.notna(row['B365>2.5']):
                        match.b365_odds_over_25 = float(row['B365>2.5'])
                    if 'B365<2.5' in row and pd.notna(row['B365<2.5']):
                        match.b365_odds_under_25 = float(row['B365<2.5'])

                    # Pinnacle O/U 2.5
                    if 'P>2.5' in row and pd.notna(row['P>2.5']):
                        match.ps_odds_over_25 = float(row['P>2.5'])
                    if 'P<2.5' in row and pd.notna(row['P<2.5']):
                        match.ps_odds_under_25 = float(row['P<2.5'])

                    # Betbrain O/U aggregates
                    if 'BbOU' in row and pd.notna(row['BbOU']):
                        match.betbrain_num_ou_bookmakers = int(row['BbOU'])
                    if 'BbMx>2.5' in row and pd.notna(row['BbMx>2.5']):
                        match.betbrain_max_odds_over_25 = float(row['BbMx>2.5'])
                    if 'BbMx<2.5' in row and pd.notna(row['BbMx<2.5']):
                        match.betbrain_max_odds_under_25 = float(row['BbMx<2.5'])
                    if 'BbAv>2.5' in row and pd.notna(row['BbAv>2.5']):
                        match.betbrain_avg_odds_over_25 = float(row['BbAv>2.5'])
                    if 'BbAv<2.5' in row and pd.notna(row['BbAv<2.5']):
                        match.betbrain_avg_odds_under_25 = float(row['BbAv<2.5'])

                    # Betting Odds - Asian Handicap
                    if 'AHh' in row and pd.notna(row['AHh']):
                        match.asian_handicap_size = float(row['AHh'])
                    if 'MaxAHH' in row and pd.notna(row['MaxAHH']):
                        match.max_odds_ah_home = float(row['MaxAHH'])
                    if 'MaxAHA' in row and pd.notna(row['MaxAHA']):
                        match.max_odds_ah_away = float(row['MaxAHA'])
                    if 'AvgAHH' in row and pd.notna(row['AvgAHH']):
                        match.avg_odds_ah_home = float(row['AvgAHH'])
                    if 'AvgAHA' in row and pd.notna(row['AvgAHA']):
                        match.avg_odds_ah_away = float(row['AvgAHA'])

                    # Bet365 Asian Handicap
                    if 'B365AH' in row and pd.notna(row['B365AH']):
                        match.b365_ah_size = float(row['B365AH'])
                    if 'B365AHH' in row and pd.notna(row['B365AHH']):
                        match.b365_odds_ah_home = float(row['B365AHH'])
                    if 'B365AHA' in row and pd.notna(row['B365AHA']):
                        match.b365_odds_ah_away = float(row['B365AHA'])

                    # Pinnacle Asian Handicap
                    if 'PAHH' in row and pd.notna(row['PAHH']):
                        match.ps_odds_ah_home = float(row['PAHH'])
                    if 'PAHA' in row and pd.notna(row['PAHA']):
                        match.ps_odds_ah_away = float(row['PAHA'])

                    # Betbrain Asian Handicap aggregates
                    if 'BbAH' in row and pd.notna(row['BbAH']):
                        match.betbrain_num_ah_bookmakers = int(row['BbAH'])
                    if 'BbAHh' in row and pd.notna(row['BbAHh']):
                        match.betbrain_ah_size = float(row['BbAHh'])
                    if 'BbMxAHH' in row and pd.notna(row['BbMxAHH']):
                        match.betbrain_max_odds_ah_home = float(row['BbMxAHH'])
                    if 'BbMxAHA' in row and pd.notna(row['BbMxAHA']):
                        match.betbrain_max_odds_ah_away = float(row['BbMxAHA'])
                    if 'BbAvAHH' in row and pd.notna(row['BbAvAHH']):
                        match.betbrain_avg_odds_ah_home = float(row['BbAvAHH'])
                    if 'BbAvAHA' in row and pd.notna(row['BbAvAHA']):
                        match.betbrain_avg_odds_ah_away = float(row['BbAvAHA'])

                    match.save()

                    if created:
                        imported += 1
                    else:
                        updated += 1

                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  Error fila {idx}: {e}"))
                    continue

            self.stdout.write(self.style.SUCCESS(f"  [OK] {imported} nuevos importados, {updated} actualizados"))
            return imported + updated

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  [ERROR] {e}"))
            return 0
