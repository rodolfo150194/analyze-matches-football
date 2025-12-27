"""
Views for predictions app
"""

from django.shortcuts import render, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count, Sum, F, Case, When, IntegerField
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django import forms
from predictions.models import Match, Competition, PlayerStats


@login_required
def matches_list(request):
    """
    Display list of matches with filters for competition and season
    Includes standings table and players table when competition+season selected
    """
    # Get filter parameters from GET request
    competition_code = request.GET.get('competition', '')
    season = request.GET.get('season', '')
    status = request.GET.get('status', '')
    page = request.GET.get('page', 1)

    # Start with all matches
    matches = Match.objects.select_related(
        'competition', 'home_team', 'away_team'
    ).all()

    # Apply filters
    selected_competition = None
    if competition_code:
        matches = matches.filter(competition__code=competition_code)
        selected_competition = Competition.objects.filter(code=competition_code).first()

    season_int = None
    if season:
        try:
            season_int = int(season)
            matches = matches.filter(season=season_int)
        except ValueError:
            pass

    if status:
        matches = matches.filter(status=status)

    # Order by date (most recent first)
    matches = matches.order_by('-utc_date')

    # Pagination
    paginator = Paginator(matches, 25)  # 25 matches per page
    try:
        matches_page = paginator.page(page)
    except PageNotAnInteger:
        matches_page = paginator.page(1)
    except EmptyPage:
        matches_page = paginator.page(paginator.num_pages)

    # Get available competitions for filter dropdown
    competitions = Competition.objects.all().order_by('name')

    # Get available seasons
    available_seasons = Match.objects.values_list('season', flat=True).distinct().order_by('-season')

    # Get available statuses
    status_choices = Match.STATUS_CHOICES

    # Calculate standings if competition and season are selected
    standings = None
    if selected_competition and season_int:
        standings = calculate_standings(selected_competition, season_int)

    # Get players if competition and season are selected
    players = []
    if selected_competition and season_int:
        players_qs = PlayerStats.objects.filter(
            competition=selected_competition,
            season=season_int
        ).select_related('player', 'team').order_by('-goals', '-assists', '-xg')[:50]
        players = list(players_qs)  # Force evaluation

    # Prepare data for JavaScript
    import json

    # Convert matches to JSON-safe dict
    matches_data = {}
    for match in matches_page:
        # Get head-to-head history (last 10 matches between these teams)
        h2h_matches = Match.objects.filter(
            Q(home_team=match.home_team, away_team=match.away_team) |
            Q(home_team=match.away_team, away_team=match.home_team),
            status='FINISHED',
            utc_date__lt=match.utc_date  # Only matches before this one
        ).select_related('home_team', 'away_team', 'competition').order_by('-utc_date')[:10]

        h2h_data = []
        for h2h in h2h_matches:
            h2h_data.append({
                'date': h2h.utc_date.strftime('%d/%m/%Y') if h2h.utc_date else '',
                'competition': h2h.competition.code,
                'homeTeam': h2h.home_team.short_name,
                'awayTeam': h2h.away_team.short_name,
                'homeScore': h2h.home_score,
                'awayScore': h2h.away_score,
                'result': h2h.result  # H/D/A
            })

        # Get recent home team matches (last 10)
        home_recent_matches = Match.objects.filter(
            Q(home_team=match.home_team) | Q(away_team=match.home_team),
            status='FINISHED',
            utc_date__lt=match.utc_date
        ).select_related('home_team', 'away_team', 'competition').order_by('-utc_date')[:10]

        home_recent_data = []
        for recent in home_recent_matches:
            is_home = recent.home_team == match.home_team
            home_recent_data.append({
                'date': recent.utc_date.strftime('%d/%m/%Y') if recent.utc_date else '',
                'competition': recent.competition.code,
                'homeTeam': recent.home_team.short_name,
                'awayTeam': recent.away_team.short_name,
                'homeScore': recent.home_score,
                'awayScore': recent.away_score,
                'isHome': is_home,
                'result': recent.result
            })

        # Get recent away team matches (last 10)
        away_recent_matches = Match.objects.filter(
            Q(home_team=match.away_team) | Q(away_team=match.away_team),
            status='FINISHED',
            utc_date__lt=match.utc_date
        ).select_related('home_team', 'away_team', 'competition').order_by('-utc_date')[:10]

        away_recent_data = []
        for recent in away_recent_matches:
            is_home = recent.home_team == match.away_team
            away_recent_data.append({
                'date': recent.utc_date.strftime('%d/%m/%Y') if recent.utc_date else '',
                'competition': recent.competition.code,
                'homeTeam': recent.home_team.short_name,
                'awayTeam': recent.away_team.short_name,
                'homeScore': recent.home_score,
                'awayScore': recent.away_score,
                'isHome': is_home,
                'result': recent.result
            })

        matches_data[str(match.id)] = {  # Convert to string for consistent JSON keys
            'homeTeam': match.home_team.name,
            'awayTeam': match.away_team.name,
            'homeTeamShort': match.home_team.short_name,
            'awayTeamShort': match.away_team.short_name,
            'competition': match.competition.name,
            'date': match.utc_date.strftime('%d/%m/%Y %H:%M') if match.utc_date else '',
            'status': match.get_status_display(),
            'homeScore': match.home_score,
            'awayScore': match.away_score,
            'homeScoreHT': match.home_score_ht,
            'awayScoreHT': match.away_score_ht,
            'shots': {'home': match.shots_home, 'away': match.shots_away},
            'shotsOnTarget': {'home': match.shots_on_target_home, 'away': match.shots_on_target_away},
            'corners': {'home': match.corners_home, 'away': match.corners_away},
            'possession': {'home': match.possession_home, 'away': match.possession_away},
            'xg': {'home': float(match.xg_home) if match.xg_home else None, 'away': float(match.xg_away) if match.xg_away else None},
            'fouls': {'home': match.fouls_home, 'away': match.fouls_away},
            'yellowCards': {'home': match.yellow_cards_home, 'away': match.yellow_cards_away},
            'redCards': {'home': match.red_cards_home, 'away': match.red_cards_away},
            'offsides': {'home': match.offsides_home, 'away': match.offsides_away},
            'headToHead': h2h_data,
            'homeRecent': home_recent_data,
            'awayRecent': away_recent_data
        }

    # Convert teams to JSON-safe dict
    teams_data = {}
    if standings:
        for team_standing in standings:
            # Get team_id and ensure it exists
            team_id = team_standing.get('team_id')
            if not team_id:
                continue  # Skip if no team_id

            ts = team_standing.get('team_stats')
            teams_data[str(team_id)] = {  # Convert to string for consistent JSON keys
                'name': team_standing['team'].name,
                'played': team_standing['played'],
                'won': team_standing['won'],
                'drawn': team_standing['drawn'],
                'lost': team_standing['lost'],
                'goalsFor': team_standing['goals_for'],
                'goalsAgainst': team_standing['goals_against'],
                'goalDifference': team_standing['goal_difference'],
                'points': team_standing['points'],
                'cleanSheets': ts['clean_sheets'] if ts else None,
                'failedToScore': ts['failed_to_score'] if ts else None,
                'bttsCount': ts['btts_count'] if ts else None,
                'over25Count': ts['over_25_count'] if ts else None,
                'avgGoalsFor': float(ts['avg_goals_for']) if ts and ts['avg_goals_for'] else None,
                'avgGoalsAgainst': float(ts['avg_goals_against']) if ts and ts['avg_goals_against'] else None,
                'homeWins': ts['home_wins'] if ts else None,
                'homeDraws': ts['home_draws'] if ts else None,
                'homeLosses': ts['home_losses'] if ts else None,
                'awayWins': ts['away_wins'] if ts else None,
                'awayDraws': ts['away_draws'] if ts else None,
                'awayLosses': ts['away_losses'] if ts else None,
            }

    # Convert players to JSON-safe dict
    players_data = {}
    for player_stat in players:
        players_data[str(player_stat.id)] = {  # Convert to string for consistent JSON keys
            'name': player_stat.player.name,
            'team': player_stat.team.short_name,
            'position': player_stat.player.position,
            'nationality': player_stat.player.nationality or '-',
            'matches': player_stat.matches_played,
            'minutes': player_stat.minutes_played,
            'goals': player_stat.goals,
            'assists': player_stat.assists,
            'xg': float(player_stat.xg) if player_stat.xg else 0,
            'xa': float(player_stat.xa) if player_stat.xa else 0,
            'shots': player_stat.shots_total,
            'shotsOnTarget': player_stat.shots_on_target,
            'yellowCards': player_stat.yellow_cards,
            'redCards': player_stat.red_cards,
            'tackles': player_stat.tackles,
            'interceptions': player_stat.interceptions,
            'passes': player_stat.passes_completed,
            'passAccuracy': float(player_stat.pass_completion_pct) if player_stat.pass_completion_pct else 0,
            'keyPasses': player_stat.key_passes,
            'dribbles': player_stat.dribbles_completed,
            'foulsDrawn': player_stat.fouls_drawn,
        }

    context = {
        'matches': matches_page,
        'competitions': competitions,
        'available_seasons': available_seasons,
        'status_choices': status_choices,
        'selected_competition': competition_code,
        'selected_season': season,
        'selected_status': status,
        'total_matches': paginator.count,
        'standings': standings,
        'players': players,
        'show_additional_tables': bool(selected_competition and season_int),
        'matches_data_json': json.dumps(matches_data),
        'teams_data_json': json.dumps(teams_data),
        'players_data_json': json.dumps(players_data),
    }

    return render(request, 'predictions/matches_list.html', context)


def calculate_standings(competition, season):
    """
    Calculate standings table for a competition and season
    Returns list of dicts with team standings and TeamStats
    """
    from predictions.models import TeamStats

    # Get all finished matches for this competition and season
    matches = Match.objects.filter(
        competition=competition,
        season=season,
        status='FINISHED'
    ).select_related('home_team', 'away_team')

    # Dictionary to store team stats
    teams_stats = {}

    for match in matches:
        # Skip if scores are missing
        if match.home_score is None or match.away_score is None:
            continue

        # Initialize teams if not exists
        if match.home_team.id not in teams_stats:
            teams_stats[match.home_team.id] = {
                'team': match.home_team,
                'team_id': match.home_team.id,
                'played': 0,
                'won': 0,
                'drawn': 0,
                'lost': 0,
                'goals_for': 0,
                'goals_against': 0,
                'goal_difference': 0,
                'points': 0,
            }

        if match.away_team.id not in teams_stats:
            teams_stats[match.away_team.id] = {
                'team': match.away_team,
                'team_id': match.away_team.id,
                'played': 0,
                'won': 0,
                'drawn': 0,
                'lost': 0,
                'goals_for': 0,
                'goals_against': 0,
                'goal_difference': 0,
                'points': 0,
            }

        # Update stats
        home_stats = teams_stats[match.home_team.id]
        away_stats = teams_stats[match.away_team.id]

        home_stats['played'] += 1
        away_stats['played'] += 1

        home_stats['goals_for'] += match.home_score
        home_stats['goals_against'] += match.away_score
        away_stats['goals_for'] += match.away_score
        away_stats['goals_against'] += match.home_score

        # Determine result
        if match.home_score > match.away_score:  # Home win
            home_stats['won'] += 1
            home_stats['points'] += 3
            away_stats['lost'] += 1
        elif match.home_score < match.away_score:  # Away win
            away_stats['won'] += 1
            away_stats['points'] += 3
            home_stats['lost'] += 1
        else:  # Draw
            home_stats['drawn'] += 1
            away_stats['drawn'] += 1
            home_stats['points'] += 1
            away_stats['points'] += 1

        # Update goal difference
        home_stats['goal_difference'] = home_stats['goals_for'] - home_stats['goals_against']
        away_stats['goal_difference'] = away_stats['goals_for'] - away_stats['goals_against']

    # Get TeamStats for additional info
    team_stats_objs = {
        ts.team_id: ts for ts in TeamStats.objects.filter(
            competition=competition,
            season=season
        ).select_related('team')
    }

    # Add TeamStats data to each team
    for team_id, stats in teams_stats.items():
        if team_id in team_stats_objs:
            ts = team_stats_objs[team_id]
            stats['team_stats'] = {
                'clean_sheets': ts.clean_sheets,
                'failed_to_score': ts.failed_to_score,
                'btts_count': ts.btts_count,
                'over_25_count': ts.over_25_count,
                'avg_goals_for': ts.avg_goals_for,
                'avg_goals_against': ts.avg_goals_against,
                'home_wins': ts.home_wins,
                'home_draws': ts.home_draws,
                'home_losses': ts.home_losses,
                'away_wins': ts.away_wins,
                'away_draws': ts.away_draws,
                'away_losses': ts.away_losses,
            }
        else:
            stats['team_stats'] = None

    # Convert to list and sort by points, then goal difference, then goals scored
    standings_list = list(teams_stats.values())
    standings_list.sort(
        key=lambda x: (x['points'], x['goal_difference'], x['goals_for']),
        reverse=True
    )

    # Add position
    for i, team_stats in enumerate(standings_list, 1):
        team_stats['position'] = i

    return standings_list


# ============================================================================
# Authentication Views
# ============================================================================

class CustomUserCreationForm(UserCreationForm):
    """
    Custom registration form with email field
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    class Meta:
        from django.contrib.auth.models import User
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        from django.contrib.auth.models import User
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email address is already registered.')
        return email


def login_view(request):
    """
    Handle user login
    """
    # Redirect if already logged in
    if request.user.is_authenticated:
        return redirect('predictions:matches_list')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')

        # Authenticate user
        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)

            # Set session expiry
            if not remember_me:
                # Session expires when browser closes
                request.session.set_expiry(0)
            else:
                # Session expires in 2 weeks
                request.session.set_expiry(1209600)

            messages.success(request, f'Welcome back, {user.username}!')

            # Redirect to next page or matches list
            next_url = request.POST.get('next') or request.GET.get('next') or 'predictions:matches_list'
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')

    # Pass 'next' parameter to template
    next_url = request.GET.get('next', '')

    return render(request, 'predictions/login.html', {'next': next_url})


def register_view(request):
    """
    Handle user registration
    """
    # Redirect if already logged in
    if request.user.is_authenticated:
        return redirect('predictions:matches_list')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            messages.success(request, 'Account created successfully! Please log in.')
            return redirect('predictions:login')
        else:
            # Form errors will be displayed in the template
            pass
    else:
        form = CustomUserCreationForm()

    return render(request, 'predictions/register.html', {'form': form})


def logout_view(request):
    """
    Handle user logout
    """
    username = request.user.username if request.user.is_authenticated else None
    auth_logout(request)

    if username:
        messages.info(request, f'You have been logged out, {username}.')
    else:
        messages.info(request, 'You have been logged out.')

    return redirect('predictions:login')
