"""
Comando Django para importar partidos futuros desde Football-Data.org API
Uso: python manage.py import_fixtures --competitions PL,PD
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from predictions.models import Competition, Team, Match
import requests
import os
from datetime import datetime
import time
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Mapeo de nombres de API a nombres históricos (CSV)
TEAM_NAME_MAPPING = {
    # Premier League
    'Manchester United FC': 'Man United',
    'Manchester City FC': 'Man City',
    'Arsenal FC': 'Arsenal',
    'Liverpool FC': 'Liverpool',
    'Chelsea FC': 'Chelsea',
    'Tottenham Hotspur FC': 'Tottenham',
    'Newcastle United FC': 'Newcastle',
    'Brighton & Hove Albion FC': 'Brighton',
    'Aston Villa FC': 'Aston Villa',
    'Brentford FC': 'Brentford',
    'Nottingham Forest FC': "Nott'm Forest",
    'Everton FC': 'Everton',
    'Wolverhampton Wanderers FC': 'Wolves',
    'West Ham United FC': 'West Ham',
    'AFC Bournemouth': 'Bournemouth',
    'Fulham FC': 'Fulham',
    'Crystal Palace FC': 'Crystal Palace',
    'Burnley FC': 'Burnley',
    'Leeds United FC': 'Leeds',
    'Leicester City FC': 'Leicester',
    'Southampton FC': 'Southampton',

    # La Liga (nombres de API -> CSV)
    'FC Barcelona': 'Barcelona',
    'Real Madrid CF': 'Real Madrid',
    'Club Atlético de Madrid': 'Ath Madrid',
    'Athletic Club': 'Ath Bilbao',
    'Real Sociedad de Fútbol': 'Sociedad',
    'Sevilla FC': 'Sevilla',
    'Valencia CF': 'Valencia',
    'Villarreal CF': 'Villarreal',
    'Real Betis Balompié': 'Betis',
    'RC Celta de Vigo': 'Celta',
    'RCD Espanyol de Barcelona': 'Espanol',
    'Rayo Vallecano de Madrid': 'Vallecano',
    'Getafe CF': 'Getafe',
    'CA Osasuna': 'Osasuna',
    'Girona FC': 'Girona',
    'RCD Mallorca': 'Mallorca',
    'Deportivo Alavés': 'Alaves',
    'Elche CF': 'Elche',
    'RC Strasbourg Alsace': 'Strasbourg',

    # Bundesliga
    'FC Bayern München': 'Bayern Munich',
    'Borussia Dortmund': 'Dortmund',
    'RB Leipzig': 'RB Leipzig',
    'Bayer 04 Leverkusen': 'Leverkusen',
    'VfL Wolfsburg': 'Wolfsburg',
    'Borussia Mönchengladbach': "M'Gladbach",
    'Eintracht Frankfurt': 'Ein Frankfurt',
    'VfB Stuttgart': 'Stuttgart',
    '1. FSV Mainz 05': 'Mainz',
    'SC Freiburg': 'Freiburg',
    '1. FC Union Berlin': 'Union Berlin',
    'TSG 1899 Hoffenheim': 'Hoffenheim',

    # Serie A
    'Juventus FC': 'Juventus',
    'AC Milan': 'Milan',
    'FC Internazionale Milano': 'Inter',
    'SSC Napoli': 'Napoli',
    'Atalanta BC': 'Atalanta',
    'AS Roma': 'Roma',
    'SS Lazio': 'Lazio',
    'ACF Fiorentina': 'Fiorentina',
    'Bologna FC 1909': 'Bologna',
    'Torino FC': 'Torino',
    'Udinese Calcio': 'Udinese',
    'Hellas Verona FC': 'Verona',
    'Cagliari Calcio': 'Cagliari',
    'US Lecce': 'Lecce',
    'Parma Calcio 1913': 'Parma',
    'US Sassuolo Calcio': 'Sassuolo',
    'Genoa CFC': 'Genoa',
    'UC Sampdoria': 'Sampdoria',
    'Empoli FC': 'Empoli',
    'Como 1907': 'Como',
    'AC Monza': 'Monza',
    'US Salernitana 1919': 'Salernitana',
    'Spezia Calcio': 'Spezia',
    'AC Pisa 1909': 'Pisa',
    'US Cremonese': 'Cremonese',

    # Ligue 1
    'Paris Saint-Germain FC': 'Paris SG',
    'Olympique de Marseille': 'Marseille',
    'Olympique Lyonnais': 'Lyon',
    'AS Monaco FC': 'Monaco',
    'Lille OSC': 'Lille',
    'OGC Nice': 'Nice',
    'Stade Rennais FC 1901': 'Rennes',
}


class Command(BaseCommand):
    help = 'Importa partidos futuros (fixtures) desde Football-Data.org API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--competitions',
            type=str,
            default='PL,PD,BL1,SA,FL1',
            help='Códigos de competiciones separados por coma (PL,PD,BL1,SA,FL1)'
        )
        parser.add_argument(
            '--season',
            type=int,
            default=2025,
            help='Temporada a importar (default: 2025)'
        )

    def handle(self, *args, **options):
        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS('IMPORTACIÓN DE FIXTURES'))
        self.stdout.write("="*70)

        # API Key
        api_key = os.getenv('API_KEY_FOOTBALL_DATA')
        if not api_key:
            self.stdout.write(self.style.ERROR('ERROR: API_KEY_FOOTBALL_DATA no encontrada en .env'))
            return

        competitions = options['competitions'].split(',')
        season = options['season']

        self.stdout.write(f"Competiciones: {', '.join(competitions)}")
        self.stdout.write(f"Temporada: {season}")
        self.stdout.write(f"Rate limit: 10 requests/minuto (espera de 7 segundos entre llamadas)")
        self.stdout.write("")

        # Mapeo de códigos a IDs de football-data.org
        COMPETITION_IDS = {
            'PL': 2021,   # Premier League
            'PD': 2014,   # La Liga
            'BL1': 2002,  # Bundesliga
            'SA': 2019,   # Serie A
            'FL1': 2015,  # Ligue 1
        }

        total_imported = 0
        total_updated = 0
        total_skipped = 0

        for idx, comp_code in enumerate(competitions):
            if comp_code not in COMPETITION_IDS:
                self.stdout.write(self.style.WARNING(f"  {comp_code}: Código no reconocido"))
                continue

            # Obtener competición de la BD
            try:
                competition = Competition.objects.get(code=comp_code)
            except Competition.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  {comp_code}: No existe en BD, saltando..."))
                continue

            self.stdout.write(f"\n{competition.name} ({comp_code}):")
            self.stdout.write("-"*70)

            # Llamar a la API
            comp_id = COMPETITION_IDS[comp_code]
            url = f"https://api.football-data.org/v4/competitions/{comp_id}/matches"
            headers = {'X-Auth-Token': api_key}
            params = {'season': season, 'status': 'SCHEDULED'}

            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)

                if response.status_code == 429:
                    self.stdout.write(self.style.WARNING(f"  Rate limit alcanzado, esperando 60 segundos..."))
                    time.sleep(60)
                    response = requests.get(url, headers=headers, params=params, timeout=30)

                if response.status_code != 200:
                    self.stdout.write(self.style.ERROR(f"  Error API: {response.status_code}"))
                    self.stdout.write(f"  Response: {response.text[:200]}")
                    continue

                data = response.json()
                matches_data = data.get('matches', [])

                self.stdout.write(f"  Partidos encontrados: {len(matches_data)}")

                imported = 0
                updated = 0
                skipped = 0

                for match_data in matches_data:
                    result = self.import_match(match_data, competition, season)
                    if result == 'imported':
                        imported += 1
                    elif result == 'updated':
                        updated += 1
                    else:
                        skipped += 1

                self.stdout.write(self.style.SUCCESS(
                    f"  OK - Importados: {imported}, Actualizados: {updated}, Omitidos: {skipped}"
                ))

                total_imported += imported
                total_updated += updated
                total_skipped += skipped

                # Esperar 7 segundos entre llamadas (10 requests/min = 1 cada 6s, usamos 7s para margen)
                if idx < len(competitions) - 1:  # No esperar después del último
                    self.stdout.write(f"  Esperando 7 segundos (rate limit)...")
                    time.sleep(7)

            except requests.exceptions.RequestException as e:
                self.stdout.write(self.style.ERROR(f"  Error de conexión: {e}"))
                continue

        self.stdout.write("")
        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS(
            f'COMPLETADO: {total_imported} importados, {total_updated} actualizados, {total_skipped} omitidos'
        ))
        self.stdout.write("="*70)

    def import_match(self, match_data, competition, season):
        """Importar un partido desde los datos de la API"""

        # Extraer información del partido
        api_id = match_data.get('id')
        utc_date = match_data.get('utcDate')
        status = match_data.get('status')

        home_team_data = match_data.get('homeTeam', {})
        away_team_data = match_data.get('awayTeam', {})

        home_team_name = home_team_data.get('name')
        away_team_name = away_team_data.get('name')
        home_team_api_id = home_team_data.get('id')
        away_team_api_id = away_team_data.get('id')

        if not all([api_id, utc_date, home_team_name, away_team_name]):
            return 'skipped'

        # Parsear fecha
        try:
            match_date = datetime.fromisoformat(utc_date.replace('Z', '+00:00'))
        except:
            return 'skipped'

        # Buscar equipos existentes usando mapeo manual
        # 1. Intentar por API_ID
        home_team = Team.objects.filter(api_id=home_team_api_id).first()
        if not home_team:
            # 2. Usar mapeo manual si existe
            mapped_name = TEAM_NAME_MAPPING.get(home_team_name)
            if mapped_name:
                home_team = Team.objects.filter(name=mapped_name, competition=competition).first()

        if not home_team:
            # 3. Crear nuevo equipo
            home_team = Team.objects.create(
                api_id=home_team_api_id,
                name=home_team_name,
                short_name=home_team_data.get('shortName', home_team_name[:20]),
                tla=home_team_data.get('tla', home_team_name[:3].upper()),
                competition=competition
            )
        else:
            # Actualizar API_ID si no lo tiene
            if not home_team.api_id:
                home_team.api_id = home_team_api_id
                home_team.save()

        away_team = Team.objects.filter(api_id=away_team_api_id).first()
        if not away_team:
            mapped_name = TEAM_NAME_MAPPING.get(away_team_name)
            if mapped_name:
                away_team = Team.objects.filter(name=mapped_name, competition=competition).first()

        if not away_team:
            away_team = Team.objects.create(
                api_id=away_team_api_id,
                name=away_team_name,
                short_name=away_team_data.get('shortName', away_team_name[:20]),
                tla=away_team_data.get('tla', away_team_name[:3].upper()),
                competition=competition
            )
        else:
            if not away_team.api_id:
                away_team.api_id = away_team_api_id
                away_team.save()

        # Verificar si el partido ya existe
        existing = Match.objects.filter(
            api_id=api_id
        ).first()

        if existing:
            # Actualizar si cambió el status o fecha
            if existing.status != status or existing.utc_date != match_date:
                existing.status = status
                existing.utc_date = match_date
                existing.save()
                return 'updated'
            return 'skipped'

        # Crear nuevo partido
        Match.objects.create(
            api_id=api_id,
            competition=competition,
            season=season,
            home_team=home_team,
            away_team=away_team,
            utc_date=match_date,
            status=status,
            matchday=match_data.get('matchday')
        )

        return 'imported'
