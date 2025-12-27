---
name: betting-analyst
description: Professional sports betting analysis skill for identifying value bets using statistical models. Use when analyzing match predictions, calculating expected value (EV), comparing model probabilities vs bookmaker odds, implementing Kelly criterion for bankroll management, detecting value betting opportunities, or building betting strategies. Triggers on queries about odds analysis, value betting, betting edge calculation, bankroll management, or sports prediction model evaluation.
---

# Betting Analyst

Professional framework for identifying value bets by comparing model predictions against bookmaker odds.

## Core Concepts

### Value Betting Fundamentals

A value bet exists when: `Model Probability > Implied Probability from Odds`

```
Implied Probability = 1 / Decimal Odds
Edge = Model Probability - Implied Probability
Value Bet = Edge > 0 (with margin of safety)
```

**Minimum edge threshold**: 3-5% for recreational, 2-3% for sharp action.

### Margin and True Odds

Bookmakers include margin (overround) in their odds:

```python
def calculate_margin(home_odds, draw_odds, away_odds):
    """Typical margins: 2-5% for major leagues, 5-10% for minor."""
    return (1/home_odds + 1/draw_odds + 1/away_odds - 1) * 100

def remove_margin(odds, margin):
    """Convert to true probability."""
    implied = 1 / odds
    return implied / (1 + margin/100)
```

## Value Detection Workflow

1. **Generate model probability** → Run prediction model on match
2. **Extract bookmaker odds** → Get closing line (most accurate)
3. **Calculate implied probability** → 1/odds, adjust for margin
4. **Compute edge** → Model prob - Implied prob
5. **Apply Kelly criterion** → Determine stake size
6. **Validate bet** → Check against filters (min odds, max stake, league limits)

## Kelly Criterion

Optimal stake sizing to maximize long-term growth:

```python
def kelly_stake(probability, odds, bankroll, fraction=0.25):
    """
    Full Kelly is aggressive. Use fractional Kelly (0.25-0.5) for safety.
    
    Args:
        probability: Model's win probability (0-1)
        odds: Decimal odds offered
        bankroll: Current bankroll
        fraction: Kelly fraction (0.25 = quarter Kelly, recommended)
    
    Returns:
        Optimal stake amount
    """
    edge = probability * odds - 1
    if edge <= 0:
        return 0  # No value, don't bet
    
    kelly_fraction = edge / (odds - 1)
    stake = bankroll * kelly_fraction * fraction
    
    # Cap at 5% of bankroll maximum
    return min(stake, bankroll * 0.05)
```

**Kelly fraction recommendations:**
- 0.25 (Quarter Kelly): Conservative, recommended for most
- 0.33 (Third Kelly): Moderate risk
- 0.5 (Half Kelly): Aggressive but manageable
- 1.0 (Full Kelly): Maximum growth, high variance—avoid

## Expected Value Analysis

```python
def calculate_ev(probability, odds, stake):
    """
    Expected value per bet.
    
    Positive EV = profitable long-term
    """
    win_amount = stake * (odds - 1)
    lose_amount = stake
    
    ev = (probability * win_amount) - ((1 - probability) * lose_amount)
    roi = ev / stake * 100  # ROI percentage
    
    return {"ev": ev, "roi": roi}
```

## Bet Grading System

Grade value bets by confidence level:

| Grade | Edge | Confidence | Kelly Fraction | Max Stake |
|-------|------|------------|----------------|-----------|
| A+ | >10% | Very High | 0.5 | 3% bankroll |
| A | 7-10% | High | 0.4 | 2.5% bankroll |
| B | 5-7% | Medium-High | 0.33 | 2% bankroll |
| C | 3-5% | Medium | 0.25 | 1.5% bankroll |
| D | 2-3% | Low | 0.15 | 1% bankroll |

## Model Calibration

### Brier Score

Measures prediction accuracy (lower is better):

```python
def brier_score(predictions, outcomes):
    """
    predictions: list of probabilities (0-1)
    outcomes: list of actual results (0 or 1)
    
    Excellent: <0.20, Good: 0.20-0.25, Average: 0.25-0.30
    """
    return sum((p - o)**2 for p, o in zip(predictions, outcomes)) / len(predictions)
```

### Calibration Check

Model probability should match actual win rate:

```python
def calibration_analysis(predictions, outcomes, bins=10):
    """
    Group predictions into bins and compare predicted vs actual rate.
    Well-calibrated: predicted ≈ actual for each bin.
    """
    results = []
    for i in range(bins):
        low, high = i/bins, (i+1)/bins
        mask = [(low <= p < high) for p in predictions]
        if sum(mask) > 0:
            predicted = sum(p for p, m in zip(predictions, mask) if m) / sum(mask)
            actual = sum(o for o, m in zip(outcomes, mask) if m) / sum(mask)
            results.append({"bin": f"{low:.1f}-{high:.1f}", 
                          "predicted": predicted, 
                          "actual": actual,
                          "samples": sum(mask)})
    return results
```

## Closing Line Value (CLV)

The ultimate measure of betting skill. Compare your bet odds vs closing odds:

```python
def clv_analysis(bet_odds, closing_odds):
    """
    Positive CLV = beating the market consistently.
    
    CLV > 0 over 500+ bets indicates genuine edge.
    """
    clv = (bet_odds - closing_odds) / closing_odds * 100
    return clv

# Example: Bet at 2.10, closed at 1.95
# CLV = (2.10 - 1.95) / 1.95 * 100 = 7.7% CLV ✓
```

## Market Types & Edge Potential

| Market | Typical Edge | Difficulty | Notes |
|--------|--------------|------------|-------|
| 1X2 (Match Result) | 2-5% | High | Most liquid, hardest to beat |
| Over/Under Goals | 3-6% | Medium | Model expected goals well |
| Asian Handicap | 2-4% | High | Sharpest market |
| BTTS | 3-7% | Medium | Consistent edges possible |
| Corners | 5-10% | Low | Less efficient, more variance |
| Player Props | 5-15% | Low | Inefficient but limited stakes |

## Risk Management Rules

1. **Maximum stake**: Never exceed 5% bankroll per bet
2. **Daily loss limit**: Stop at 10% bankroll loss
3. **Minimum odds**: Avoid odds < 1.50 (edge erodes quickly)
4. **Maximum odds**: Be cautious with odds > 5.0 (high variance)
5. **Correlation**: Avoid parlays unless correlated (same match)
6. **Sample size**: Need 500+ bets to evaluate strategy reliably

## Red Flags & Pitfalls

**Avoid these common mistakes:**

- **Favorite-longshot bias**: Longshots are overbet, favorites underbet
- **Recency bias**: Don't overweight recent results
- **Home field overestimation**: Market already prices this in
- **Ignoring lineup/injuries**: Check before betting
- **Chasing losses**: Stick to Kelly, never increase stakes after losses
- **Overconfidence in model**: Always use fractional Kelly

## Output Format

When analyzing a betting opportunity, structure output as:

```
## Match Analysis: [Home] vs [Away]

### Model Prediction
- Home Win: XX.X%
- Draw: XX.X%  
- Away Win: XX.X%
- Expected Goals: X.XX - X.XX

### Bookmaker Odds (Margin: X.X%)
- Home: X.XX (implied: XX.X%)
- Draw: X.XX (implied: XX.X%)
- Away: X.XX (implied: XX.X%)

### Value Assessment
| Outcome | Edge | Grade | Recommended Stake |
|---------|------|-------|-------------------|
| Home | +X.X% | B | €XX (X.X% bankroll) |

### Recommendation
[Clear action: BET / SKIP with reasoning]

### Risk Factors
- [Key concerns or caveats]
```

## Advanced Topics

For deeper analysis, see reference files:
- **Poisson modeling**: See [poisson-models.md](references/poisson-models.md)
- **Feature engineering**: See [features.md](references/features.md)
- **Odds movement**: See [line-movement.md](references/line-movement.md)
