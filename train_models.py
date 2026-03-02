#!/usr/bin/env python3
"""
ML Model Training Script

Reads model input/output specifications from JSON-LD registry
and trains models accordingly. Single source of truth.

Supports different JSON-LD configurations - trains models based on
the provided registry file.
"""

import pandas as pd
import numpy as np
import pickle
import json
import os
import argparse
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_absolute_error
import warnings
warnings.filterwarnings('ignore')

# Configuration
DATA_PATH = 'ml_data/daily_unified_data.csv'


def get_model_dir(registry_path):
    """Derive registry-specific model directory.
    Each JSON-LD config gets its own model directory so different
    configurations with different inputs don't overwrite each other.
    e.g., ml_model_registry.jsonld -> ml_models/ml_model_registry/
    """
    registry_name = os.path.splitext(os.path.basename(registry_path))[0]
    return os.path.join('ml_models', registry_name)


def resolve_model_path(original_path, model_dir):
    """Replace ml_models/ prefix with registry-specific directory"""
    filename = os.path.basename(original_path)
    return os.path.join(model_dir, filename)


def load_registry(registry_path):
    """Load model specs from JSON-LD"""
    with open(registry_path, 'r') as f:
        registry = json.load(f)

    models = {}
    for entity in registry['@graph']:
        if entity['type'] == 'MLModel':
            model_id = entity['id']
            models[model_id] = {
                'name': entity['name']['value'],
                'inputs': entity['inputs']['value'],
                'output': entity['outputs']['value'][0]['name'],
                'modelPath': entity['modelPath']['value'],
                'scalerPath': entity.get('scalerPath', {}).get('value'),
                'dependsOn': entity.get('dependsOn', {}).get('object'),
            }
    return models, registry


def prepare_features(df):
    """Create all derived and synthetic features"""
    # Existing derived features
    df['power_lag1'] = df['total_power'].shift(1)
    df['power_lag7'] = df['total_power'].shift(7)
    df['power_rolling_3d'] = df['total_power'].rolling(window=3).mean()
    df['power_rolling_7d'] = df['total_power'].rolling(window=7).mean()
    df['temp_lag1'] = df['Kitchen_temperature'].shift(1)
    df['temp_rolling_3d'] = df['Kitchen_temperature'].rolling(3).mean()
    df['occ_lag1'] = df['avg_occupancy'].shift(1)
    df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)

    # Synthetic targets for new models
    # CO2: Based on occupancy (400-1000 PPM range)
    df['synthetic_co2'] = 400 + df['avg_occupancy'] * 600 + np.random.normal(0, 50, len(df))

    # Lighting: Based on occupancy (0-1 scale)
    df['synthetic_lighting'] = df['avg_occupancy'] * 0.8 + np.random.normal(0, 0.1, len(df))
    df['synthetic_lighting'] = df['synthetic_lighting'].clip(0, 1)

    # Comfort Index: Based on temperature and humidity (0-1 scale, optimal around 22°C and 45%)
    temp_comfort = 1 - abs(df['Kitchen_temperature'] - 22) / 10
    humidity_comfort = 1 - abs(df['avg_humidity'] - 45) / 30
    df['synthetic_comfort_index'] = (temp_comfort * 0.6 + humidity_comfort * 0.4).clip(0, 1)

    # Anomaly Score: Detect unusual energy patterns (0-1 scale)
    energy_mean = df['total_power'].rolling(7).mean()
    energy_std = df['total_power'].rolling(7).std()
    df['synthetic_anomaly'] = ((df['total_power'] - energy_mean).abs() / (energy_std + 1)).clip(0, 1)
    df['synthetic_anomaly'] = (df['synthetic_anomaly'] > 0.5).astype(float)  # Binary: 0=normal, 1=anomaly

    # HVAC Setpoint: Based on comfort (18-26°C range)
    df['synthetic_hvac_setpoint'] = 22 - (df['synthetic_comfort_index'] - 0.5) * 4 + np.random.normal(0, 0.5, len(df))
    df['synthetic_hvac_setpoint'] = df['synthetic_hvac_setpoint'].clip(18, 26)

    # Air Quality Index: Combination of CO2, humidity, temp (0-1 scale, 1=best)
    co2_quality = 1 - (df['synthetic_co2'] - 400) / 600
    temp_quality = 1 - abs(df['Kitchen_temperature'] - 22) / 10
    humidity_quality = 1 - abs(df['avg_humidity'] - 45) / 30
    df['synthetic_air_quality'] = (co2_quality * 0.5 + temp_quality * 0.3 + humidity_quality * 0.2).clip(0, 1)

    return df


def update_registry_metrics(registry, model_id, r2, mae, samples):
    """Update model metrics in registry"""
    for entity in registry['@graph']:
        if entity.get('id') == model_id:
            entity['metrics'] = {
                'type': 'Property',
                'value': {'r2_score': round(r2, 3), 'mae': round(mae, 3), 'trainingSamples': samples}
            }
    return registry


def compute_training_order(model_specs):
    """
    Compute training order using topological sort.
    Models with no dependencies train first, then models that depend on them.
    """
    # Build dependency graph
    deps_graph = {}
    for model_id, spec in model_specs.items():
        deps = spec.get('dependsOn') or []
        deps_graph[model_id] = deps

    # Topological sort (Kahn's algorithm)
    in_degree = {model_id: 0 for model_id in model_specs}
    for model_id, deps in deps_graph.items():
        for dep in deps:
            if dep in in_degree:
                in_degree[model_id] += 1

    queue = [m for m in model_specs if in_degree[m] == 0]
    order = []

    while queue:
        current = queue.pop(0)
        order.append(current)

        # Reduce in-degree for models that depend on current
        for model_id, deps in deps_graph.items():
            if current in deps:
                in_degree[model_id] -= 1
                if in_degree[model_id] == 0:
                    queue.append(model_id)

    return order


def main():
    parser = argparse.ArgumentParser(description='Train ML models from JSON-LD registry')
    parser.add_argument('--registry', type=str, default='ml_model_registry.jsonld',
                        help='Path to JSON-LD registry file (default: ml_model_registry.jsonld)')
    args = parser.parse_args()

    registry_path = args.registry

    # Derive model directory from registry name
    model_dir = get_model_dir(registry_path)
    os.makedirs(model_dir, exist_ok=True)

    print("="*70)
    print("ML MODEL TRAINING FROM JSON-LD REGISTRY")
    print("="*70)
    print(f"Registry: {registry_path}")
    print(f"Model directory: {model_dir}/\n")

    model_specs, registry = load_registry(registry_path)
    print(f"Models in registry: {len(model_specs)}")

    df = pd.read_csv(DATA_PATH)
    df['date'] = pd.to_datetime(df['date'])
    df = df.replace(-1, np.nan)
    df = prepare_features(df)
    print(f"Data: {len(df)} days (after feature engineering)")

    # Target mapping: output_name → dataset column name
    # This maps model outputs to training targets in the dataset
    output_to_target = {
        'predicted_occupancy': 'avg_occupancy',
        'predicted_temperature': 'Kitchen_temperature',
        'predicted_humidity': 'avg_humidity',
        'predicted_energy': 'total_power',
        'predicted_co2': 'synthetic_co2',
        'predicted_lighting': 'synthetic_lighting',
        'predicted_comfort_index': 'synthetic_comfort_index',
        'predicted_anomaly': 'synthetic_anomaly',
        'anomaly_score': 'synthetic_anomaly',
        'hvac_setpoint': 'synthetic_hvac_setpoint',
        'air_quality_index': 'synthetic_air_quality',
    }

    trained_models = {}

    # Compute training order respecting dependencies (topological sort)
    train_order = compute_training_order(model_specs)

    print("\nTraining order (respecting dependencies):")
    for i, model_id in enumerate(train_order, 1):
        if model_id in model_specs:
            print(f"  {i}. {model_specs[model_id]['name']}")

    for model_id in train_order:
        spec = model_specs[model_id]

        # Find target column from output name (not model ID)
        output_name = spec['output']
        target = output_to_target.get(output_name)

        # If not in known mapping, try to find in dataset columns
        if not target:
            if output_name in df.columns:
                target = output_name
            else:
                # Try synthetic_ prefix
                synthetic_name = f"synthetic_{output_name.replace('predicted_', '')}"
                if synthetic_name in df.columns:
                    target = synthetic_name

        if not target:
            print(f"\nSkipping {spec['name']} - no target column found for output '{output_name}'")
            continue

        print(f"\n{'='*70}")
        print(f"Training: {spec['name']}")
        print(f"Target: {target}")

        # Get feature names from JSON-LD
        feature_names = [inp['name'] for inp in spec['inputs']]
        print(f"Inputs (from JSON-LD): {feature_names}")

        # Build feature dataframe
        df_features = pd.DataFrame()

        for inp in spec['inputs']:
            name = inp['name']

            if inp.get('fromModel'):
                # Use prediction from dependent model
                dep_model_id = inp['source']
                if dep_model_id in trained_models:
                    dep_model = trained_models[dep_model_id]['model']
                    dep_features = trained_models[dep_model_id]['features']
                    dep_scaler = trained_models[dep_model_id].get('scaler')

                    # Build feature matrix for dependent model
                    dep_feature_data = []
                    for feat in dep_features:
                        if feat in df.columns:
                            dep_feature_data.append(df[feat])
                        else:
                            # Feature might be from another model - skip for now
                            print(f"  Warning: Dependency feature {feat} not found")
                            dep_feature_data.append(pd.Series([0] * len(df)))

                    X_dep = pd.concat(dep_feature_data, axis=1)
                    X_dep.columns = dep_features
                    X_dep = X_dep.dropna()

                    if len(X_dep) > 0:
                        if dep_scaler:
                            X_dep_scaled = dep_scaler.transform(X_dep)
                            preds = dep_model.predict(X_dep_scaled)
                        else:
                            preds = dep_model.predict(X_dep)

                        # Align predictions with original dataframe
                        pred_series = pd.Series(index=X_dep.index, data=preds)
                        df_features[name] = pred_series
                        print(f"  {name}: from {model_specs[dep_model_id]['name']} (interconnected)")
                    else:
                        print(f"  Warning: No valid data for dependency {dep_model_id}")
                        df_features[name] = 0
                else:
                    print(f"  Warning: Dependency {dep_model_id} not trained yet")
                    df_features[name] = 0

            elif name in df.columns:
                df_features[name] = df[name]
            else:
                print(f"  Warning: Feature {name} not found in data, using 0")
                df_features[name] = 0

        if target not in df.columns:
            print(f"  ERROR: Target column '{target}' not found in dataset. Skipping.")
            continue

        df_features[target] = df[target]
        df_model = df_features.dropna()

        if len(df_model) < 20:
            print(f"  ERROR: Only {len(df_model)} samples after dropna. Skipping.")
            continue

        X = df_model[feature_names]
        y = df_model[target]

        print(f"  Samples: {len(df_model)}")

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        scaler = None
        if spec['scalerPath']:
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
        else:
            X_train_scaled = X_train.values
            X_test_scaled = X_test.values

        model = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=5)
        model.fit(X_train_scaled, y_train)

        y_pred = model.predict(X_test_scaled)
        r2 = r2_score(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        print(f"  R²: {r2:.3f}, MAE: {mae:.3f}")

        # Save model to registry-specific directory
        model_path = resolve_model_path(spec['modelPath'], model_dir)
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        print(f"  ✓ Saved: {model_path}")

        scaler_path = None
        if scaler and spec['scalerPath']:
            scaler_path = resolve_model_path(spec['scalerPath'], model_dir)
            with open(scaler_path, 'wb') as f:
                pickle.dump(scaler, f)
            print(f"  ✓ Saved: {scaler_path}")

        # Store for dependent models
        trained_models[model_id] = {
            'model': model,
            'scaler': scaler,
            'features': feature_names
        }

        registry = update_registry_metrics(registry, model_id, r2, mae, len(df_model))

    # Save updated registry with metrics
    with open(registry_path, 'w') as f:
        json.dump(registry, f, indent=2)

    print(f"\n{'='*70}")
    print(f"✓ Training complete!")
    print(f"  Total models trained: {len(trained_models)}")
    print(f"  Model directory: {model_dir}/")
    print(f"  Registry updated: {registry_path}")
    print("="*70)


if __name__ == '__main__':
    main()
