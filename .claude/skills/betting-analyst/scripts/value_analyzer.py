#!/usr/bin/env python3
"""
Value Bet Analyzer

Analyzes model predictions against bookmaker odds to identify value bets.

Usage:
    python value_analyzer.py --prediction 0.55 --odds 2.10 --bankroll 1000
    python value_analyzer.py --file predictions.json --bankroll 1000
"""

import argparse
import json
from dataclasses import dataclass
from typing import Optional


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


def remove_margin(odds: float, margin: float) -> float:
    """Get true probability by removing margin."""
    implied = 1 / odds
    return implied / (1 + margin/100)


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
                fraction: float = 0.25, max_stake_pct: float = 0.05) -> tuple[float, float]:
    """
    Calculate Kelly criterion stake.
    
    Returns:
        (stake_amount, kelly_fraction)
    """
    edge = probability * odds - 1
    if edge <= 0:
        return 0, 0
    
    kelly_fraction = edge / (odds - 1)
    stake = bankroll * kelly_fraction * fraction
    
    # Cap at max stake
    stake = min(stake, bankroll * max_stake_pct)
    
    return stake, kelly_fraction


def calculate_ev(probability: float, odds: float, stake: float) -> tuple[float, float]:
    """
    Calculate expected value and ROI.
    
    Returns:
        (expected_value, roi_percentage)
    """
    win_amount = stake * (odds - 1)
    lose_amount = stake
    
    ev = (probability * win_amount) - ((1 - probability) * lose_amount)
    roi = ev / stake * 100 if stake > 0 else 0
    
    return ev, roi


def analyze_bet(model_prob: float, odds: float, bankroll: float,
                outcome: str = "unknown", kelly_fraction: float = 0.25,
                min_edge: float = 0.03) -> ValueBet:
    """
    Complete value bet analysis.
    
    Args:
        model_prob: Model's probability (0-1)
        odds: Decimal odds offered
        bankroll: Current bankroll
        outcome: Bet description (e.g., "Home Win")
        kelly_fraction: Kelly divisor (0.25 = quarter Kelly)
        min_edge: Minimum edge threshold for value
    
    Returns:
        ValueBet analysis result
    """
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
                  bankroll: float, kelly_fraction: float = 0.25,
                  min_edge: float = 0.03) -> dict:
    """
    Analyze all outcomes for a match.
    """
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
        "recommendation": _generate_recommendation(analyses, margin)
    }


def _generate_recommendation(analyses: dict, margin: float) -> str:
    """Generate betting recommendation."""
    value_bets = [(k, v) for k, v in analyses.items() if v.is_value]
    
    if not value_bets:
        return "SKIP - No value detected"
    
    if margin > 8:
        return "CAUTION - High margin market, edges may be illusory"
    
    best = max(value_bets, key=lambda x: x[1].edge)
    outcome, bet = best
    
    if bet.grade in ["A+", "A"]:
        return f"STRONG BET - {outcome.upper()} ({bet.grade}) at {bet.odds:.2f}"
    elif bet.grade in ["B", "C"]:
        return f"BET - {outcome.upper()} ({bet.grade}) at {bet.odds:.2f}"
    else:
        return f"SMALL BET - {outcome.upper()} ({bet.grade}) at {bet.odds:.2f}"


def format_analysis(result: dict, home_team: str = "Home", 
                    away_team: str = "Away") -> str:
    """Format analysis for display."""
    output = []
    output.append(f"\n{'='*60}")
    output.append(f"MATCH ANALYSIS: {home_team} vs {away_team}")
    output.append(f"{'='*60}")
    output.append(f"\nBookmaker Margin: {result['margin']:.1f}%")
    
    output.append("\n--- Value Assessment ---")
    for outcome, analysis in result['analyses'].items():
        status = "✓ VALUE" if analysis.is_value else "✗ No Value"
        output.append(f"\n{outcome.upper()}: {status}")
        output.append(f"  Model: {analysis.model_prob*100:.1f}% | "
                     f"Implied: {analysis.implied_prob*100:.1f}% | "
                     f"Edge: {analysis.edge*100:+.1f}%")
        if analysis.is_value:
            output.append(f"  Grade: {analysis.grade} | "
                         f"Stake: ${analysis.stake:.2f} | "
                         f"EV: ${analysis.ev:.2f} ({analysis.roi:.1f}% ROI)")
    
    output.append(f"\n--- Recommendation ---")
    output.append(result['recommendation'])
    output.append("")
    
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="Value Bet Analyzer")
    parser.add_argument("--prediction", type=float, help="Model probability (0-1)")
    parser.add_argument("--odds", type=float, help="Decimal odds")
    parser.add_argument("--bankroll", type=float, default=1000, help="Bankroll")
    parser.add_argument("--kelly", type=float, default=0.25, help="Kelly fraction")
    parser.add_argument("--min-edge", type=float, default=0.03, help="Min edge threshold")
    parser.add_argument("--file", type=str, help="JSON file with predictions")
    
    # Match analysis
    parser.add_argument("--home-prob", type=float, help="Home win probability")
    parser.add_argument("--draw-prob", type=float, help="Draw probability")
    parser.add_argument("--away-prob", type=float, help="Away win probability")
    parser.add_argument("--home-odds", type=float, help="Home odds")
    parser.add_argument("--draw-odds", type=float, help="Draw odds")
    parser.add_argument("--away-odds", type=float, help="Away odds")
    parser.add_argument("--home-team", type=str, default="Home")
    parser.add_argument("--away-team", type=str, default="Away")
    
    args = parser.parse_args()
    
    if args.home_prob and args.home_odds:
        # Full match analysis
        result = analyze_match(
            args.home_prob, args.draw_prob, args.away_prob,
            args.home_odds, args.draw_odds, args.away_odds,
            args.bankroll, args.kelly, args.min_edge
        )
        print(format_analysis(result, args.home_team, args.away_team))
    
    elif args.prediction and args.odds:
        # Single bet analysis
        result = analyze_bet(
            args.prediction, args.odds, args.bankroll,
            kelly_fraction=args.kelly, min_edge=args.min_edge
        )
        print(f"\nBet Analysis:")
        print(f"  Model Probability: {result.model_prob*100:.1f}%")
        print(f"  Implied Probability: {result.implied_prob*100:.1f}%")
        print(f"  Edge: {result.edge*100:+.1f}%")
        print(f"  Grade: {result.grade}")
        print(f"  Is Value: {'Yes' if result.is_value else 'No'}")
        if result.is_value:
            print(f"  Recommended Stake: ${result.stake:.2f}")
            print(f"  Expected Value: ${result.ev:.2f}")
            print(f"  ROI: {result.roi:.1f}%")
    
    elif args.file:
        with open(args.file) as f:
            predictions = json.load(f)
        
        for match in predictions:
            result = analyze_match(
                match['home_prob'], match['draw_prob'], match['away_prob'],
                match['home_odds'], match['draw_odds'], match['away_odds'],
                args.bankroll, args.kelly, args.min_edge
            )
            print(format_analysis(result, 
                                  match.get('home_team', 'Home'),
                                  match.get('away_team', 'Away')))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
