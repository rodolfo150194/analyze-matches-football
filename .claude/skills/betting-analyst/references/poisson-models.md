# Poisson Models for Football Prediction

## Theory

Football goals follow a Poisson distribution because:
- Goals are rare events (low count per match)
- Each goal is approximately independent
- Rate is relatively constant within a match

## Basic Poisson Model

```python
import numpy as np
from scipy.stats import poisson

def poisson_match_probabilities(home_xg, away_xg, max_goals=10):
    """
    Calculate match outcome probabilities from expected goals.
    
    Args:
        home_xg: Expected goals for home team
        away_xg: Expected goals for away team
        max_goals: Maximum goals to consider per team
    
    Returns:
        dict with home_win, draw, away_win probabilities
    """
    home_probs = [poisson.pmf(i, home_xg) for i in range(max_goals)]
    away_probs = [poisson.pmf(i, away_xg) for i in range(max_goals)]
    
    home_win = sum(
        home_probs[i] * away_probs[j] 
        for i in range(max_goals) 
        for j in range(i)
    )
    
    draw = sum(
        home_probs[i] * away_probs[i] 
        for i in range(max_goals)
    )
    
    away_win = sum(
        home_probs[i] * away_probs[j] 
        for i in range(max_goals) 
        for j in range(i+1, max_goals)
    )
    
    return {
        "home_win": home_win,
        "draw": draw,
        "away_win": away_win,
        "home_xg": home_xg,
        "away_xg": away_xg
    }
```

## Dixon-Coles Adjustment

Standard Poisson underestimates low-scoring draws. Dixon-Coles corrects this:

```python
def dixon_coles_adjustment(home_goals, away_goals, home_xg, away_xg, rho=-0.13):
    """
    Adjust probability for correlation in low-scoring games.
    
    rho: correlation parameter (typically -0.1 to -0.2)
    """
    if home_goals == 0 and away_goals == 0:
        return 1 - home_xg * away_xg * rho
    elif home_goals == 0 and away_goals == 1:
        return 1 + home_xg * rho
    elif home_goals == 1 and away_goals == 0:
        return 1 + away_xg * rho
    elif home_goals == 1 and away_goals == 1:
        return 1 - rho
    else:
        return 1.0

def poisson_dixon_coles(home_xg, away_xg, rho=-0.13, max_goals=10):
    """Full probability matrix with Dixon-Coles adjustment."""
    matrix = np.zeros((max_goals, max_goals))
    
    for i in range(max_goals):
        for j in range(max_goals):
            base_prob = poisson.pmf(i, home_xg) * poisson.pmf(j, away_xg)
            adjustment = dixon_coles_adjustment(i, j, home_xg, away_xg, rho)
            matrix[i, j] = base_prob * adjustment
    
    # Normalize
    matrix /= matrix.sum()
    
    return matrix
```

## Estimating Attack/Defense Strengths

```python
from scipy.optimize import minimize

def estimate_team_strengths(matches, teams):
    """
    Estimate attack and defense parameters for each team.
    
    matches: list of (home_team, away_team, home_goals, away_goals)
    teams: list of team names
    """
    n_teams = len(teams)
    team_idx = {t: i for i, t in enumerate(teams)}
    
    def neg_log_likelihood(params):
        # params: [attack_1..n, defense_1..n, home_advantage, rho]
        attack = params[:n_teams]
        defense = params[n_teams:2*n_teams]
        home_adv = params[2*n_teams]
        rho = params[2*n_teams + 1]
        
        ll = 0
        for home, away, hg, ag in matches:
            hi, ai = team_idx[home], team_idx[away]
            
            home_xg = np.exp(attack[hi] + defense[ai] + home_adv)
            away_xg = np.exp(attack[ai] + defense[hi])
            
            # Poisson log-likelihood with Dixon-Coles
            adj = dixon_coles_adjustment(hg, ag, home_xg, away_xg, rho)
            prob = poisson.pmf(hg, home_xg) * poisson.pmf(ag, away_xg) * adj
            
            ll += np.log(max(prob, 1e-10))
        
        return -ll
    
    # Initial params
    x0 = np.concatenate([
        np.zeros(n_teams),  # attack
        np.zeros(n_teams),  # defense  
        [0.25],             # home advantage
        [-0.13]             # rho
    ])
    
    # Constraint: sum of attack = 0 (identifiability)
    constraints = {'type': 'eq', 'fun': lambda x: x[:n_teams].sum()}
    
    result = minimize(neg_log_likelihood, x0, constraints=constraints, method='SLSQP')
    
    return {
        'attack': dict(zip(teams, result.x[:n_teams])),
        'defense': dict(zip(teams, result.x[n_teams:2*n_teams])),
        'home_advantage': result.x[2*n_teams],
        'rho': result.x[2*n_teams + 1]
    }
```

## Time-Weighted Model

Recent matches matter more:

```python
def time_decay_weight(days_ago, half_life=60):
    """
    Exponential decay weight.
    half_life: days until weight is halved (30-90 typical)
    """
    return np.exp(-np.log(2) * days_ago / half_life)

# Use in likelihood:
# ll += weight * np.log(prob)
```

## Over/Under Markets

```python
def over_under_probabilities(home_xg, away_xg, line=2.5, max_goals=15):
    """Calculate over/under probabilities for total goals."""
    matrix = poisson_dixon_coles(home_xg, away_xg, max_goals=max_goals)
    
    over = sum(
        matrix[i, j] 
        for i in range(max_goals) 
        for j in range(max_goals) 
        if i + j > line
    )
    
    return {"over": over, "under": 1 - over}
```

## BTTS (Both Teams To Score)

```python
def btts_probability(home_xg, away_xg):
    """Probability both teams score at least once."""
    home_scores = 1 - poisson.pmf(0, home_xg)
    away_scores = 1 - poisson.pmf(0, away_xg)
    return home_scores * away_scores
```

## Model Validation

```python
def ranked_probability_score(predicted_probs, actual_outcome):
    """
    RPS: Better than Brier for ordinal outcomes (home/draw/away).
    Lower is better. Range: 0-1.
    """
    cumulative_pred = np.cumsum(predicted_probs)
    cumulative_actual = np.cumsum(actual_outcome)
    return np.mean((cumulative_pred - cumulative_actual) ** 2)
```

## Common Pitfalls

1. **Ignoring score effects**: Teams behave differently when leading/trailing
2. **Static parameters**: Update weekly, football evolves
3. **Small sample size**: Need 50+ matches per team minimum
4. **Ignoring context**: Cup vs league, fatigue, motivation
5. **xG vs goals**: Train on xG when available, more stable than actual goals
