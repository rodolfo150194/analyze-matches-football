"""
Predictor mejorado con XGBoost, LightGBM y calibración de probabilidades
para mayor acierto en las predicciones (Django ORM)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from datetime import datetime
import pickle

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, log_loss, brier_score_loss, mean_absolute_error, r2_score
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import StandardScaler

# Modelos más potentes
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("[WARNING] XGBoost no disponible. Instalar con: pip install xgboost")

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    print("[WARNING] LightGBM no disponible. Instalar con: pip install lightgbm")

from predictions.models import Match
from predictions.ml.enhanced_features import EnhancedFeatureEngineer


class EnhancedPredictor:
    """Predictor mejorado con modelos potentes y calibración"""

    # Features OPTIMIZADOS - Reducidos a 33 para evitar overfitting (sin Elo)
    # Ratio: 6,500 partidos / 33 features = 197 partidos por feature
    ENHANCED_FEATURE_COLUMNS = [
        # === GRUPO 1: FORMA RECIENTE - Últimos 5 partidos (8 features) ===
        # Captura momentum actual sin importar venue
        'home_form_points',         # Puntos promedio últimos 5
        'home_form_gf',             # Goles a favor últimos 5
        'home_form_ga',             # Goles en contra últimos 5
        'home_form_win_rate',       # % victorias últimos 5
        'away_form_points',
        'away_form_gf',
        'away_form_ga',
        'away_form_win_rate',

        # === GRUPO 3: FORMA POR VENUE - Últimos partidos en casa/fuera (6 features) ===
        # Combina forma reciente + venue effect
        'home_at_home_points',      # Puntos en casa (últimos partidos)
        'home_at_home_gf',
        'home_at_home_ga',
        'away_at_away_points',      # Puntos fuera (últimos partidos)
        'away_at_away_gf',
        'away_at_away_ga',

        # === GRUPO 4: TEMPORADA POR VENUE (10 features) ===
        # Rendimiento de toda la temporada separado por casa/fuera
        # MÁS específico que stats generales
        'home_season_home_ppg',     # PPG del local jugando en casa
        'home_season_home_avg_gf',  # Goles a favor en casa
        'home_season_home_avg_ga',  # Goles en contra en casa
        'home_season_home_btts_rate',  # BTTS rate en casa
        'home_season_home_over25_rate',  # Over 2.5 rate en casa
        'away_season_away_ppg',     # PPG del visitante jugando fuera
        'away_season_away_avg_gf',
        'away_season_away_avg_ga',
        'away_season_away_btts_rate',
        'away_season_away_over25_rate',

        # === GRUPO 5: HEAD-TO-HEAD (4 features) ===
        # Historial directo entre equipos
        'h2h_matches',              # Número de enfrentamientos
        'h2h_home_win_rate',        # % victorias del local en H2H
        'h2h_btts_rate',            # BTTS rate en enfrentamientos directos
        'h2h_over25_rate',          # Over 2.5 rate en enfrentamientos directos

        # === GRUPO 6: CORNERS/SHOTS (4 features) ===
        # Para modelos específicos de corners y shots
        'home_avg_corners',
        'away_avg_corners',
        'home_avg_shots',
        'away_avg_shots',

        # === GRUPO 7: EXPECTED GOALS (1 feature) ===
        # Combinación de ataque y defensa para Over/Under
        'expected_total_goals',     # (home_gf + away_ga + away_gf + home_ga) / 2
    ]

    def __init__(self):
        self.fe = EnhancedFeatureEngineer()

        # Modelos principales
        self.models = {
            'result': None,  # H/D/A
            'over_25': None,  # Over 2.5
            'btts': None,  # Both teams to score
            # Corners
            'total_corners': None,  # Total de corners (regresión)
            'over_95_corners': None,  # Over 9.5 corners
            'over_105_corners': None,  # Over 10.5 corners
            # Tiros
            'total_shots': None,  # Total de tiros (regresión)
            'total_shots_on_target': None,  # Total de tiros a puerta (regresión)
        }

        self.scalers = {}
        self.stats = {
            'avg_total_goals': 2.7,
        }

    def prepare_data(self, training_data: List[Dict]) -> Tuple:
        """Preparar datos para entrenamiento"""
        df = pd.DataFrame(training_data)
        df = df[df['result'].notna()]

        # Features
        X = df[self.ENHANCED_FEATURE_COLUMNS].fillna(0).values

        # Targets
        result_map = {'H': 0, 'D': 1, 'A': 2}
        y_result = df['result'].map(result_map).values
        y_over25 = (df['total_goals'] > 2.5).astype(int).values
        y_btts = df['btts'].values

        # Corners (calcular total de corners)
        df['total_corners'] = df['corners_home'].fillna(0) + df['corners_away'].fillna(0)
        y_total_corners = df['total_corners'].values
        y_over_95_corners = (df['total_corners'] > 9.5).astype(int).values
        y_over_105_corners = (df['total_corners'] > 10.5).astype(int).values

        # Tiros
        df['total_shots'] = df['shots_home'].fillna(0) + df['shots_away'].fillna(0)
        y_total_shots = df['total_shots'].values

        # Tiros a puerta
        df['total_shots_on_target'] = df['shots_on_target_home'].fillna(0) + df['shots_on_target_away'].fillna(0)
        y_total_shots_on_target = df['total_shots_on_target'].values

        return (X, y_result, y_over25, y_btts,
                y_total_corners, y_over_95_corners, y_over_105_corners,
                y_total_shots, y_total_shots_on_target, df)

    def train_ensemble_result_model(self, X_train, y_train, X_test, y_test):
        """Entrenar modelo de resultado con ensemble de RF + XGB + LGB"""

        print("\nEntrenando modelos de RESULTADO...")
        print("-" * 70)

        models = {}
        scores = {}

        # 1. Random Forest (con mejores hiperparámetros)
        print("1. Random Forest...")
        rf_model = RandomForestClassifier(
            n_estimators=300,  # Más árboles
            max_depth=20,  # Mayor profundidad
            min_samples_split=10,  # Evitar overfitting
            min_samples_leaf=4,  # Evitar hojas muy pequeñas
            max_features='sqrt',
            max_samples=0.9,  # Bootstrap con 90% de datos
            random_state=42,
            n_jobs=-1
        )
        rf_model.fit(X_train, y_train)
        y_pred = rf_model.predict(X_test)
        rf_acc = accuracy_score(y_test, y_pred)
        scores['RandomForest'] = rf_acc
        models['rf'] = rf_model
        print(f"   Accuracy: {rf_acc:.4f}")

        # 2. XGBoost (si está disponible) - Hiperparámetros optimizados
        if XGBOOST_AVAILABLE:
            print("2. XGBoost...")
            xgb_model = xgb.XGBClassifier(
                n_estimators=300,
                max_depth=6,  # Menor profundidad para evitar overfitting
                learning_rate=0.05,  # Learning rate más bajo
                subsample=0.85,
                colsample_bytree=0.85,
                gamma=0.1,  # Regularización
                min_child_weight=3,
                reg_alpha=0.1,  # L1 regularization
                reg_lambda=1.0,  # L2 regularization
                random_state=42,
                n_jobs=-1,
                eval_metric='mlogloss'
            )
            xgb_model.fit(X_train, y_train)
            y_pred = xgb_model.predict(X_test)
            xgb_acc = accuracy_score(y_test, y_pred)
            scores['XGBoost'] = xgb_acc
            models['xgb'] = xgb_model
            print(f"   Accuracy: {xgb_acc:.4f}")

        # 3. LightGBM (si está disponible) - Hiperparámetros optimizados
        if LIGHTGBM_AVAILABLE:
            print("3. LightGBM...")
            lgb_model = lgb.LGBMClassifier(
                n_estimators=300,
                max_depth=7,
                learning_rate=0.05,
                num_leaves=50,  # Más hojas para capturar complejidad
                subsample=0.85,
                subsample_freq=1,
                colsample_bytree=0.85,
                min_child_samples=20,  # Evitar overfitting
                reg_alpha=0.1,  # L1 regularization
                reg_lambda=1.0,  # L2 regularization
                random_state=42,
                n_jobs=-1,
                verbose=-1
            )
            lgb_model.fit(X_train, y_train)
            y_pred = lgb_model.predict(X_test)
            lgb_acc = accuracy_score(y_test, y_pred)
            scores['LightGBM'] = lgb_acc
            models['lgb'] = lgb_model
            print(f"   Accuracy: {lgb_acc:.4f}")

        # Seleccionar mejor modelo
        best_name = max(scores, key=scores.get)
        model_mapping = {
            'RandomForest': 'rf',
            'XGBoost': 'xgb',
            'LightGBM': 'lgb'
        }
        best_model = models[model_mapping[best_name]]

        print(f"\n   Mejor modelo: {best_name} ({scores[best_name]:.4f})")

        # Calibrar probabilidades del mejor modelo
        print("\n4. Calibrando probabilidades...")
        calibrated_model = CalibratedClassifierCV(
            best_model,
            method='isotonic',  # Mejor que sigmoid para más datos
            cv=3
        )
        calibrated_model.fit(X_train, y_train)

        # Evaluar calibración
        y_pred_proba = calibrated_model.predict_proba(X_test)
        y_pred = calibrated_model.predict(X_test)

        cal_acc = accuracy_score(y_test, y_pred)
        cal_logloss = log_loss(y_test, y_pred_proba)

        print(f"   Calibrated Accuracy: {cal_acc:.4f}")
        print(f"   Log Loss: {cal_logloss:.4f}")

        return calibrated_model, cal_acc

    def train_binary_model(self, X_train, y_train, X_test, y_test, model_name: str):
        """Entrenar modelo binario (Over/Under, BTTS) con ensemble"""

        print(f"\nEntrenando modelos de {model_name.upper()}...")
        print("-" * 70)

        models = {}
        scores = {}

        # Random Forest
        rf_model = RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        rf_model.fit(X_train, y_train)
        y_pred = rf_model.predict(X_test)
        rf_acc = accuracy_score(y_test, y_pred)
        scores['RandomForest'] = rf_acc
        models['rf'] = rf_model

        # XGBoost
        if XGBOOST_AVAILABLE:
            xgb_model = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.1,
                subsample=0.8,
                random_state=42,
                n_jobs=-1,
                eval_metric='logloss'
            )
            xgb_model.fit(X_train, y_train)
            y_pred = xgb_model.predict(X_test)
            xgb_acc = accuracy_score(y_test, y_pred)
            scores['XGBoost'] = xgb_acc
            models['xgb'] = xgb_model

        # LightGBM
        if LIGHTGBM_AVAILABLE:
            lgb_model = lgb.LGBMClassifier(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.1,
                random_state=42,
                n_jobs=-1,
                verbose=-1
            )
            lgb_model.fit(X_train, y_train)
            y_pred = lgb_model.predict(X_test)
            lgb_acc = accuracy_score(y_test, y_pred)
            scores['LightGBM'] = lgb_acc
            models['lgb'] = lgb_model

        # Mejor modelo
        best_name = max(scores, key=scores.get)
        model_mapping = {
            'RandomForest': 'rf',
            'XGBoost': 'xgb',
            'LightGBM': 'lgb'
        }
        best_model = models[model_mapping[best_name]]

        print(f"   {best_name}: {scores[best_name]:.4f} <- Mejor")

        # Calibrar
        calibrated_model = CalibratedClassifierCV(best_model, method='isotonic', cv=3)
        calibrated_model.fit(X_train, y_train)

        cal_acc = accuracy_score(y_test, calibrated_model.predict(X_test))
        print(f"   Calibrated: {cal_acc:.4f}")

        return calibrated_model, cal_acc

    def train_regression_model(self, X_train, y_train, X_test, y_test, model_name: str):
        """Entrenar modelo de regresión para predecir totales"""

        print(f"\nEntrenando modelo de {model_name.upper()}...")
        print("-" * 70)

        models = {}
        scores = {}

        # Random Forest Regressor
        rf_model = RandomForestRegressor(
            n_estimators=200,
            max_depth=12,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        rf_model.fit(X_train, y_train)
        y_pred = rf_model.predict(X_test)
        rf_mae = mean_absolute_error(y_test, y_pred)
        rf_r2 = r2_score(y_test, y_pred)
        scores['RandomForest'] = rf_r2
        models['rf'] = rf_model

        # XGBoost Regressor
        if XGBOOST_AVAILABLE:
            xgb_model = xgb.XGBRegressor(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.1,
                subsample=0.8,
                random_state=42,
                n_jobs=-1
            )
            xgb_model.fit(X_train, y_train)
            y_pred = xgb_model.predict(X_test)
            xgb_mae = mean_absolute_error(y_test, y_pred)
            xgb_r2 = r2_score(y_test, y_pred)
            scores['XGBoost'] = xgb_r2
            models['xgb'] = xgb_model

        # LightGBM Regressor
        if LIGHTGBM_AVAILABLE:
            lgb_model = lgb.LGBMRegressor(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.1,
                random_state=42,
                n_jobs=-1,
                verbose=-1
            )
            lgb_model.fit(X_train, y_train)
            y_pred = lgb_model.predict(X_test)
            lgb_mae = mean_absolute_error(y_test, y_pred)
            lgb_r2 = r2_score(y_test, y_pred)
            scores['LightGBM'] = lgb_r2
            models['lgb'] = lgb_model

        # Mejor modelo
        best_name = max(scores, key=scores.get)
        model_mapping = {
            'RandomForest': 'rf',
            'XGBoost': 'xgb',
            'LightGBM': 'lgb'
        }
        best_model = models[model_mapping[best_name]]
        y_pred = best_model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = scores[best_name]

        print(f"   {best_name}: MAE={mae:.2f}, R2={r2:.4f} <- Mejor")

        return best_model, mae

    def train(self, competitions: List[str], seasons: List[int], test_size: float = 0.2):
        """Entrenar todos los modelos con features mejorados"""

        print("="*70)
        print("ENTRENAMIENTO CON MODELOS MEJORADOS")
        print("="*70)
        print(f"Competiciones: {competitions}")
        print(f"Temporadas: {seasons}")
        print(f"Features: {len(self.ENHANCED_FEATURE_COLUMNS)}")
        print()

        # Cargar datos
        all_data = []
        for comp in competitions:
            data = self.fe.generate_enhanced_training_data(comp, seasons)
            all_data.extend(data)

        print(f"\nTotal partidos: {len(all_data)}")

        # Preparar
        (X, y_result, y_over25, y_btts,
         y_total_corners, y_over_95_corners, y_over_105_corners,
         y_total_shots, y_total_shots_on_target, df) = self.prepare_data(all_data)

        # Split
        indices = np.arange(len(X))
        train_idx, test_idx = train_test_split(indices, test_size=test_size, random_state=42)

        X_train, X_test = X[train_idx], X[test_idx]
        y_result_train, y_result_test = y_result[train_idx], y_result[test_idx]
        y_over25_train, y_over25_test = y_over25[train_idx], y_over25[test_idx]
        y_btts_train, y_btts_test = y_btts[train_idx], y_btts[test_idx]

        # Corners
        y_total_corners_train, y_total_corners_test = y_total_corners[train_idx], y_total_corners[test_idx]
        y_over_95_corners_train, y_over_95_corners_test = y_over_95_corners[train_idx], y_over_95_corners[test_idx]
        y_over_105_corners_train, y_over_105_corners_test = y_over_105_corners[train_idx], y_over_105_corners[test_idx]

        # Tiros
        y_total_shots_train, y_total_shots_test = y_total_shots[train_idx], y_total_shots[test_idx]
        y_total_shots_on_target_train, y_total_shots_on_target_test = y_total_shots_on_target[train_idx], y_total_shots_on_target[test_idx]

        print(f"Train: {len(X_train)}, Test: {len(X_test)}")

        # Entrenar modelos
        results = {}

        # 1. RESULTADO
        self.models['result'], acc = self.train_ensemble_result_model(
            X_train, y_result_train, X_test, y_result_test
        )
        results['result'] = acc

        # 2. OVER 2.5
        self.models['over_25'], acc = self.train_binary_model(
            X_train, y_over25_train, X_test, y_over25_test, 'Over 2.5'
        )
        results['over_25'] = acc

        # 3. BTTS
        self.models['btts'], acc = self.train_binary_model(
            X_train, y_btts_train, X_test, y_btts_test, 'BTTS'
        )
        results['btts'] = acc

        # 4. TOTAL CORNERS (Regresión)
        self.models['total_corners'], mae = self.train_regression_model(
            X_train, y_total_corners_train, X_test, y_total_corners_test, 'Total Corners'
        )
        results['total_corners'] = mae

        # 5. OVER 9.5 CORNERS
        self.models['over_95_corners'], acc = self.train_binary_model(
            X_train, y_over_95_corners_train, X_test, y_over_95_corners_test, 'Over 9.5 Corners'
        )
        results['over_95_corners'] = acc

        # 6. OVER 10.5 CORNERS
        self.models['over_105_corners'], acc = self.train_binary_model(
            X_train, y_over_105_corners_train, X_test, y_over_105_corners_test, 'Over 10.5 Corners'
        )
        results['over_105_corners'] = acc

        # 7. TOTAL TIROS (Regresión)
        self.models['total_shots'], mae = self.train_regression_model(
            X_train, y_total_shots_train, X_test, y_total_shots_test, 'Total Shots'
        )
        results['total_shots'] = mae

        # 8. TOTAL TIROS A PUERTA (Regresión)
        self.models['total_shots_on_target'], mae = self.train_regression_model(
            X_train, y_total_shots_on_target_train, X_test, y_total_shots_on_target_test, 'Total Shots on Target'
        )
        results['total_shots_on_target'] = mae

        # Estadísticas
        self.stats['avg_total_goals'] = df['total_goals'].mean()
        self.stats['avg_total_corners'] = df['total_corners'].mean()
        self.stats['avg_total_shots'] = df['total_shots'].mean()
        self.stats['avg_total_shots_on_target'] = df['total_shots_on_target'].mean()

        # Resumen
        print("\n" + "="*70)
        print("RESUMEN DE ENTRENAMIENTO")
        print("="*70)

        # Modelos de clasificación (Accuracy)
        classification_models = ['result', 'over_25', 'btts', 'over_95_corners', 'over_105_corners']
        print("\nCLASIFICACION (Accuracy):")
        for model_name, metric in results.items():
            if model_name in classification_models:
                print(f"  {model_name:25s} {metric:.4f} ({metric*100:.1f}%)")

        # Modelos de regresión (MAE)
        regression_models = ['total_corners', 'total_shots', 'total_shots_on_target']
        print("\nREGRESION (MAE - Error Absoluto Medio):")
        for model_name, metric in results.items():
            if model_name in regression_models:
                print(f"  {model_name:25s} {metric:.2f}")

        # Estadísticas
        print("\nESTADISTICAS PROMEDIO:")
        print(f"  Goles:                    {self.stats['avg_total_goals']:.2f}")
        print(f"  Corners:                  {self.stats['avg_total_corners']:.2f}")
        print(f"  Tiros:                    {self.stats['avg_total_shots']:.2f}")
        print(f"  Tiros a puerta:           {self.stats['avg_total_shots_on_target']:.2f}")

        self.training_results = results

        return results

    def predict_match(self, home_team_id: int, away_team_id: int,
                     match_date: datetime, competition_id: int, season: int) -> Dict:
        """Hacer predicción para un partido"""

        # Crear match temporal
        temp_match = Match(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            utc_date=match_date,
            competition_id=competition_id,
            season=season,
            status='SCHEDULED'
        )

        # Calcular features mejorados
        features = self.fe.calculate_enhanced_features(temp_match)

        # Preparar input
        X = np.array([[features.get(col, 0) for col in self.ENHANCED_FEATURE_COLUMNS]])

        predictions = {}

        # RESULTADO
        if self.models['result']:
            probs = self.models['result'].predict_proba(X)[0]
            predictions['result'] = {
                'home_win': float(probs[0]),
                'draw': float(probs[1]),
                'away_win': float(probs[2]),
                'most_likely': ['H', 'D', 'A'][np.argmax(probs)]
            }

        # OVER 2.5
        if self.models['over_25']:
            prob = self.models['over_25'].predict_proba(X)[0]
            predictions['over_25'] = {
                'no': float(prob[0]),
                'yes': float(prob[1])
            }

        # BTTS
        if self.models['btts']:
            prob = self.models['btts'].predict_proba(X)[0]
            predictions['btts'] = {
                'no': float(prob[0]),
                'yes': float(prob[1])
            }

        # CORNERS - Total predicho
        if self.models['total_corners']:
            predicted_total = self.models['total_corners'].predict(X)[0]
            predictions['total_corners'] = {
                'predicted': float(predicted_total),
                'avg': float(self.stats.get('avg_total_corners', 10.5))
            }

        # CORNERS - Over 9.5
        if self.models['over_95_corners']:
            prob = self.models['over_95_corners'].predict_proba(X)[0]
            predictions['over_95_corners'] = {
                'no': float(prob[0]),
                'yes': float(prob[1])
            }

        # CORNERS - Over 10.5
        if self.models['over_105_corners']:
            prob = self.models['over_105_corners'].predict_proba(X)[0]
            predictions['over_105_corners'] = {
                'no': float(prob[0]),
                'yes': float(prob[1])
            }

        # TIROS - Total predicho
        if self.models['total_shots']:
            predicted_total = self.models['total_shots'].predict(X)[0]
            predictions['total_shots'] = {
                'predicted': float(predicted_total),
                'avg': float(self.stats.get('avg_total_shots', 24.0))
            }

        # TIROS A PUERTA - Total predicho
        if self.models['total_shots_on_target']:
            predicted_total = self.models['total_shots_on_target'].predict(X)[0]
            predictions['total_shots_on_target'] = {
                'predicted': float(predicted_total),
                'avg': float(self.stats.get('avg_total_shots_on_target', 9.0))
            }

        return predictions

    def save_models(self, path: str = 'enhanced_models.pkl'):
        """Guardar modelos"""
        data = {
            'models': self.models,
            'stats': self.stats,
            'feature_columns': self.ENHANCED_FEATURE_COLUMNS,
            'training_results': getattr(self, 'training_results', {})
        }

        with open(path, 'wb') as f:
            pickle.dump(data, f)

        print(f"\nModelos guardados en: {path}")

    def load_models(self, path: str = 'enhanced_models.pkl'):
        """Cargar modelos"""
        with open(path, 'rb') as f:
            data = pickle.load(f)

        self.models = data['models']
        self.stats = data['stats']
        self.ENHANCED_FEATURE_COLUMNS = data['feature_columns']
        self.training_results = data.get('training_results', {})

        print("Modelos mejorados cargados exitosamente!")
