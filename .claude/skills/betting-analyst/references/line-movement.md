# Line Movement & Odds Analysis

## Understanding Odds Movement

### Why Lines Move

1. **Sharp action**: Professional bettors (sharps) move lines with large bets
2. **Public money**: Recreational bettors (squares) create volume
3. **Information**: Injuries, lineups, weather updates
4. **Liability management**: Books balance their exposure

**Key insight**: Closing line is the most accurate prediction. Sharp books (Pinnacle, Betfair) are most efficient.

## Tracking Odds Movement

```python
from datetime import datetime

def track_line_movement(odds_history):
    """
    Analyze how odds moved from opening to closing.
    
    odds_history: list of {timestamp, home, draw, away} dicts
    """
    if len(odds_history) < 2:
        return {}
    
    opening = odds_history[0]
    closing = odds_history[-1]
    
    # Calculate movement
    home_move = (1/closing['home'] - 1/opening['home']) * 100
    draw_move = (1/closing['draw'] - 1/opening['draw']) * 100
    away_move = (1/closing['away'] - 1/opening['away']) * 100
    
    return {
        "home_movement": home_move,  # Positive = odds shortened (more likely)
        "draw_movement": draw_move,
        "away_movement": away_move,
        "home_opened": opening['home'],
        "home_closed": closing['home'],
        "away_opened": opening['away'],
        "away_closed": closing['away'],
        "steam_home": home_move > 3,  # Significant sharp action
        "steam_away": away_move > 3,
    }
```

## Steam Moves

A "steam move" is sudden, sharp line movement across multiple books—indicates sharp information.

```python
def detect_steam_move(odds_snapshots, threshold=3, time_window_minutes=15):
    """
    Detect rapid line movement (steam).
    
    threshold: minimum % probability shift
    time_window_minutes: how fast the move happened
    """
    steam_moves = []
    
    for i in range(1, len(odds_snapshots)):
        prev, curr = odds_snapshots[i-1], odds_snapshots[i]
        
        time_diff = (curr['timestamp'] - prev['timestamp']).total_seconds() / 60
        
        if time_diff > time_window_minutes:
            continue
        
        for outcome in ['home', 'draw', 'away']:
            prob_change = (1/curr[outcome] - 1/prev[outcome]) * 100
            
            if abs(prob_change) >= threshold:
                steam_moves.append({
                    "outcome": outcome,
                    "direction": "steam_in" if prob_change > 0 else "steam_out",
                    "magnitude": prob_change,
                    "timestamp": curr['timestamp'],
                })
    
    return steam_moves
```

## Reverse Line Movement (RLM)

When the line moves opposite to where public money is going—strong sharp indicator.

```python
def detect_rlm(public_betting_percentages, line_movement):
    """
    Reverse line movement detection.
    
    public_betting_percentages: {home: %, away: %}
    line_movement: from track_line_movement()
    """
    rlm_signals = []
    
    # Public on home but line moves toward away
    if public_betting_percentages['home'] > 60 and line_movement['home_movement'] < -2:
        rlm_signals.append({
            "side": "away",
            "public_pct": public_betting_percentages['home'],
            "line_move": line_movement['home_movement'],
            "strength": "strong" if public_betting_percentages['home'] > 70 else "moderate"
        })
    
    # Public on away but line moves toward home
    if public_betting_percentages['away'] > 60 and line_movement['away_movement'] < -2:
        rlm_signals.append({
            "side": "home",
            "public_pct": public_betting_percentages['away'],
            "line_move": line_movement['away_movement'],
            "strength": "strong" if public_betting_percentages['away'] > 70 else "moderate"
        })
    
    return rlm_signals
```

## Closing Line Value (CLV)

The gold standard for measuring betting skill.

```python
def calculate_clv(bet_odds, closing_odds, bet_side):
    """
    Calculate CLV for a single bet.
    
    Positive CLV = you beat the closing line
    Consistent positive CLV over 500+ bets = genuine edge
    """
    clv_pct = (bet_odds - closing_odds) / closing_odds * 100
    
    return {
        "clv_pct": clv_pct,
        "bet_odds": bet_odds,
        "closing_odds": closing_odds,
        "beat_close": clv_pct > 0,
    }

def clv_analysis(bets):
    """
    Aggregate CLV analysis across all bets.
    """
    clvs = [b['clv_pct'] for b in bets if 'clv_pct' in b]
    
    if not clvs:
        return {}
    
    positive_clv = [c for c in clvs if c > 0]
    
    return {
        "avg_clv": sum(clvs) / len(clvs),
        "positive_clv_rate": len(positive_clv) / len(clvs),
        "total_bets": len(clvs),
        "best_clv": max(clvs),
        "worst_clv": min(clvs),
        "is_sharp": sum(clvs) / len(clvs) > 0 and len(clvs) >= 500,
    }
```

## Optimal Bet Timing

```python
def optimal_bet_timing(historical_odds_data):
    """
    Analyze when to place bets for best value.
    
    General findings:
    - Sharp markets: Bet early (before sharps correct inefficiencies)
    - Soft markets: Bet late (after sharps have moved the line)
    - Breaking news: Bet immediately after (before books react)
    """
    # Calculate average CLV by time before match
    timing_analysis = {}
    
    for hours_before in [168, 72, 48, 24, 12, 6, 2, 1]:  # 1 week to 1 hour
        bets_at_time = [b for b in historical_odds_data 
                       if b.get('hours_before_match') == hours_before]
        
        if bets_at_time:
            avg_clv = sum(b['clv_pct'] for b in bets_at_time) / len(bets_at_time)
            timing_analysis[f"{hours_before}h_before"] = avg_clv
    
    return timing_analysis
```

## Book Comparison

```python
def compare_bookmakers(odds_by_book):
    """
    Find best odds across bookmakers.
    
    odds_by_book: {bookmaker: {home, draw, away}}
    """
    best_odds = {"home": 0, "draw": 0, "away": 0}
    best_books = {"home": None, "draw": None, "away": None}
    
    for book, odds in odds_by_book.items():
        for outcome in ['home', 'draw', 'away']:
            if odds[outcome] > best_odds[outcome]:
                best_odds[outcome] = odds[outcome]
                best_books[outcome] = book
    
    # Calculate edge from shopping
    avg_odds = {
        outcome: sum(b[outcome] for b in odds_by_book.values()) / len(odds_by_book)
        for outcome in ['home', 'draw', 'away']
    }
    
    edge_from_shopping = {
        outcome: (best_odds[outcome] - avg_odds[outcome]) / avg_odds[outcome] * 100
        for outcome in ['home', 'draw', 'away']
    }
    
    return {
        "best_odds": best_odds,
        "best_books": best_books,
        "edge_from_shopping": edge_from_shopping,
    }
```

## Sharp vs Soft Books

| Book Type | Examples | Characteristics |
|-----------|----------|-----------------|
| **Sharp** | Pinnacle, Betfair Exchange | Low margin, high limits, accurate lines |
| **Soft** | Bet365, William Hill, 1xBet | Higher margin, lower limits, slower to move |

**Strategy**:
- Use sharp book odds as "true" probability reference
- Find value in soft books that lag behind sharp moves
- Closing line from Pinnacle is the benchmark

## Arbitrage Detection

```python
def detect_arbitrage(odds_by_book):
    """
    Find arbitrage opportunities across books.
    
    Arb exists when: 1/home + 1/draw + 1/away < 1
    """
    best = compare_bookmakers(odds_by_book)['best_odds']
    
    total_implied = 1/best['home'] + 1/best['draw'] + 1/away
    
    if total_implied < 1:
        profit_pct = (1 - total_implied) * 100
        
        # Calculate stakes for $100 profit
        stake_home = 100 / best['home'] / total_implied
        stake_draw = 100 / best['draw'] / total_implied
        stake_away = 100 / best['away'] / total_implied
        
        return {
            "is_arb": True,
            "profit_pct": profit_pct,
            "stakes": {
                "home": stake_home,
                "draw": stake_draw,
                "away": stake_away,
            },
            "books": compare_bookmakers(odds_by_book)['best_books'],
        }
    
    return {"is_arb": False}
```

## Key Insights

1. **Respect the closing line**: It's the most accurate forecast
2. **Track your CLV**: Only reliable metric for skill over 500+ bets
3. **Shop for odds**: 5-10% edge available just from line shopping
4. **Follow steam**: Sharp money is informed money
5. **Beware of RLM**: Public is usually wrong
6. **Bet timing matters**: Optimal window depends on market type
7. **Sharp books = truth**: Use Pinnacle/Betfair as benchmark
