#!/usr/bin/env python3
"""
ML Model Orchestration Engine - RECURSIVE VERSION
Smart Building - NGSI-LD Integration

Uses recursive function to execute interconnected models.
When a model is requested, all its dependencies are resolved recursively.
"""

import json
import os
import pickle
import numpy as np
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False


class MLOrchestrator:

    def __init__(self, registry_path='ml_model_registry.jsonld'):
        self.models = {}
        self.scalers = {}
        self.model_specs = {}
        self.applications = {}
        self.dependency_graph = {}
        self.output_to_model = {}
        self.registry_path = registry_path

        # Derive model directory from registry name
        registry_name = os.path.splitext(os.path.basename(registry_path))[0]
        self.model_dir = os.path.join('ml_models', registry_name)

        self._load_registry(registry_path)
        self._load_models()
        self._build_dependency_graph()

        # Default sensor values (simulating real-time data)
        # NOTE: If a sensor is down/unavailable, remove it from here or set to None
        self.default_inputs = {
            'Kitchen_occupancy': 0.5, 'Lab_occupancy': 0.3, 'Mailroom_occupancy': 0.4,
            'occ_lag1': 0.4, 'avg_temperature': 22.0, 'avg_humidity': 45.0,
            'Kitchen_humidity': 45.0, 'Kettle_power': 100.0, 'Fridge_power': 50.0,
            'CoffeeMachine_power': 30.0, 'Microwave_power': 0.0,
            'Desktop_power': 15.0, 'Printer_power': 10.0, 'WaterDispenser_power': 40.0,
            'power_lag1': 1200.0, 'power_lag7': 1100.0,
            'power_rolling_3d': 1150.0, 'power_rolling_7d': 1180.0,
            'temp_lag1': 21.5, 'temp_rolling_3d': 21.8,
        }

        # Fallback values for missing inputs (used when sensor is down or JSON-LD changes)
        self.fallback_values = {
            # Occupancy fallbacks (0-1 scale)
            'Kitchen_occupancy': 0.3, 'Lab_occupancy': 0.2, 'Mailroom_occupancy': 0.2,
            'avg_occupancy': 0.25, 'occ_lag1': 0.25, 'predicted_occupancy': 0.3,

            # Temperature fallbacks (Celsius)
            'Kitchen_temperature': 22.0, 'avg_temperature': 22.0,
            'temp_lag1': 22.0, 'temp_rolling_3d': 22.0, 'predicted_temperature': 22.0,

            # Humidity fallbacks (%)
            'Kitchen_humidity': 45.0, 'avg_humidity': 45.0, 'predicted_humidity': 45.0,

            # Power fallbacks (Watts)
            'Kettle_power': 0.0, 'Fridge_power': 50.0, 'CoffeeMachine_power': 0.0,
            'Microwave_power': 0.0, 'Desktop_power': 15.0, 'Printer_power': 10.0,
            'WaterDispenser_power': 40.0, 'total_power': 200.0, 'predicted_energy': 1000.0,
            'power_lag1': 1000.0, 'power_lag7': 1000.0,
            'power_rolling_3d': 1000.0, 'power_rolling_7d': 1000.0,

            # CO2 fallback (PPM)
            'predicted_co2': 500.0,

            # Lighting fallback (0-1 scale)
            'predicted_lighting': 0.5,

            # Comfort Index fallback (0-1 scale)
            'predicted_comfort_index': 0.7,

            # Anomaly Score fallback (0-1 scale)
            'predicted_anomaly': 0.0,

            # HVAC fallback (Celsius)
            'predicted_hvac_setpoint': 22.0,

            # Temporal fallbacks
            'day_of_week': 2, 'is_weekend': 0, 'day_sin': 0.0, 'day_cos': 1.0,
        }

        # Execution tracking
        self.execution_order = []
        self.recursion_depth = 0

        # Last known good values (cache for sensor down scenarios)
        self.last_known_values = {}

    def _load_registry(self, path):
        with open(path, 'r') as f:
            registry = json.load(f)

        for entity in registry['@graph']:
            if entity['type'] == 'MLModel':
                model_id = entity['id']
                self.model_specs[model_id] = {
                    'name': entity['name']['value'],
                    'inputs': entity['inputs']['value'],
                    'outputs': entity['outputs']['value'],
                    'modelPath': entity['modelPath']['value'],
                    'scalerPath': entity.get('scalerPath', {}).get('value'),
                    'dependsOn': entity.get('dependsOn', {}).get('object'),
                    'metrics': entity.get('metrics', {}).get('value', {}),
                }
                for output in entity['outputs']['value']:
                    self.output_to_model[output['name']] = model_id

            elif entity['type'] == 'MLApplication':
                self.applications[entity['id']] = {
                    'name': entity['name']['value'],
                    'outputs': entity['requiredOutputs']['value']
                }

    def _resolve_path(self, original_path):
        """Resolve model path to registry-specific directory"""
        filename = os.path.basename(original_path)
        return os.path.join(self.model_dir, filename)

    def _load_models(self):
        for model_id, spec in self.model_specs.items():
            model_path = self._resolve_path(spec['modelPath'])
            try:
                with open(model_path, 'rb') as f:
                    self.models[model_id] = pickle.load(f)
                if spec['scalerPath']:
                    scaler_path = self._resolve_path(spec['scalerPath'])
                    with open(scaler_path, 'rb') as f:
                        self.scalers[model_id] = pickle.load(f)
            except FileNotFoundError:
                print(f"Warning: Model file not found for {spec['name']} ({model_path})")

    def _build_dependency_graph(self):
        """Build dependency graph from JSON-LD relationships"""
        for model_id, spec in self.model_specs.items():
            deps = []

            # Add explicit dependencies
            if spec['dependsOn']:
                if isinstance(spec['dependsOn'], list):
                    deps.extend(spec['dependsOn'])
                else:
                    deps.append(spec['dependsOn'])

            # Add implicit dependencies from inputs
            for inp in spec['inputs']:
                if inp.get('fromModel'):
                    source = inp.get('source')
                    if source and source.startswith('urn:ngsi-ld:MLModel:') and source not in deps:
                        deps.append(source)

            self.dependency_graph[model_id] = deps

    def execute_model(self, model_id, cache, model_inputs, missing_inputs_tracker=None, verbose=True):
        """
        RECURSIVE FUNCTION - Core of the orchestration engine

        Executes a model and all its dependencies recursively.
        """
        if missing_inputs_tracker is None:
            missing_inputs_tracker = {}

        # BASE CASE: Model already executed
        if model_id in cache:
            return cache[model_id]

        # Check if model exists
        if model_id not in self.models:
            if verbose:
                name = self.model_specs[model_id]['name'] if model_id in self.model_specs else model_id
                print(f"  [!] {name} not loaded (.pkl missing), skipping")
            cache[model_id] = {}
            return {}

        spec = self.model_specs[model_id]

        # RECURSIVE CASE: Execute dependencies first
        self.recursion_depth += 1
        dependencies = self.dependency_graph.get(model_id, [])

        for dep_id in dependencies:
            self.execute_model(dep_id, cache, model_inputs, missing_inputs_tracker, verbose)

        self.recursion_depth -= 1

        # Prepare input features
        model = self.models[model_id]
        scaler = self.scalers.get(model_id)
        features, names = [], []
        missing_inputs = []  # Track missing inputs for this model
        now = datetime.now()

        for inp in spec['inputs']:
            name = inp['name']
            names.append(name)
            value = None
            input_source = "unknown"

            # Check if input comes from another model
            if inp.get('fromModel'):
                source_model = inp.get('source')
                attr_name = inp['attribute']
                input_source = f"model:{source_model}"

                # Get value from cache (dependency already executed)
                if source_model in cache and attr_name in cache[source_model]:
                    value = cache[source_model][attr_name]
                else:
                    value = None  # Will use fallback

            # Temporal features
            elif inp.get('source') == 'temporal':
                input_source = "temporal"
                if name == 'day_of_week':
                    value = now.weekday()
                elif name == 'is_weekend':
                    value = 1 if now.weekday() >= 5 else 0
                elif name == 'day_sin':
                    value = np.sin(2 * np.pi * now.weekday() / 7)
                elif name == 'day_cos':
                    value = np.cos(2 * np.pi * now.weekday() / 7)
                else:
                    value = None  # Will use fallback

            # Sensor values
            else:
                input_source = inp.get('source', 'sensor')
                if name in self.default_inputs:
                    value = self.default_inputs[name]
                else:
                    value = None  # Will use fallback

            # Use fallback if value is None
            if value is None:
                # Try fallbacks in order:
                # 1. Last known good value (most recent real data)
                # 2. Domain-specific fallback (reasonable default)
                # 3. Generic default (0)
                if name in self.last_known_values:
                    fallback = self.last_known_values[name]
                    fallback_type = "last-known"
                else:
                    fallback = self.fallback_values.get(name, self.default_inputs.get(name, 0))
                    fallback_type = "default"

                missing_inputs.append({
                    'name': name,
                    'source': input_source,
                    'fallback': fallback,
                    'fallback_type': fallback_type
                })
                value = fallback
            else:
                # Cache this value for future fallback (last known good value)
                self.last_known_values[name] = value

            features.append(value)

        # Store for XAI
        model_inputs[model_id] = {'features': features.copy(), 'names': names.copy()}

        # Store missing inputs
        if missing_inputs:
            missing_inputs_tracker[model_id] = missing_inputs

        # Run prediction
        X = np.array([features])
        if scaler:
            X = scaler.transform(X)
        pred = model.predict(X)[0]

        # Store outputs in cache
        result = {}
        for out in spec['outputs']:
            result[out['name']] = pred

        cache[model_id] = result
        self.execution_order.append(model_id)

        # Show result
        if verbose:
            mark = "~" if missing_inputs else "+"
            print(f"  [{mark}] {spec['name']} → {pred:.3f}")

        return result

    def predict(self, requested_outputs, verbose=True):
        """
        Execute models needed for requested outputs using RECURSIVE execution

        Returns:
            results, model_inputs, execution_order, missing_inputs_tracker
        """
        # Reset execution tracking
        self.execution_order = []
        self.recursion_depth = 0
        cache = {}
        model_inputs = {}
        missing_inputs_tracker = {}

        # Find which models produce the requested outputs
        target_models = []
        for output_name in requested_outputs:
            if output_name in self.output_to_model:
                target_models.append(self.output_to_model[output_name])
            elif verbose:
                print(f"  [!] No model produces '{output_name}'")

        if verbose:
            print(f"\nExecution:")

        # RECURSIVE EXECUTION
        for model_id in target_models:
            self.execute_model(model_id, cache, model_inputs, missing_inputs_tracker, verbose)

        # Collect final results
        results = {}
        for output_name in requested_outputs:
            for model_results in cache.values():
                if output_name in model_results:
                    results[output_name] = model_results[output_name]

        return results, model_inputs, self.execution_order, missing_inputs_tracker

    def explain(self, model_inputs, results):
        """Generate XAI explanations using SHAP"""
        if not SHAP_AVAILABLE:
            print("SHAP not installed.")
            return

        print("\n" + "="*70)
        print("XAI - Explainable AI Analysis")
        print("="*70)

        for model_id, data in model_inputs.items():
            spec = self.model_specs[model_id]
            model = self.models[model_id]
            scaler = self.scalers.get(model_id)
            output_name = spec['outputs'][0]['name']

            print(f"\n{spec['name']}:")

            try:
                X = np.array([data['features']])
                if scaler: X = scaler.transform(X)

                explainer = shap.TreeExplainer(model)
                shap_values = explainer.shap_values(X)
                if isinstance(shap_values, list): shap_values = shap_values[0]
                shap_values = shap_values.flatten()

                contrib = [(data['names'][i], data['features'][i], shap_values[i])
                          for i in range(len(data['names']))]
                contrib.sort(key=lambda x: abs(x[2]), reverse=True)

                print(f"\n  Top contributing factors:")
                for name, val, shap_val in contrib[:3]:
                    direction = "increases" if shap_val > 0 else "decreases"

                    # Format value
                    if "power" in name.lower():
                        val_str = f"{val:.0f}W"
                    elif "temp" in name.lower():
                        val_str = f"{val:.1f}°C"
                    elif "humidity" in name.lower() or "occupancy" in name.lower():
                        val_str = f"{val*100:.0f}%" if val <= 1 else f"{val:.1f}"
                    else:
                        val_str = f"{val:.2f}"

                    # Format impact
                    if "energy" in output_name:
                        impact = f"{abs(shap_val):.0f}W"
                    elif "temp" in output_name:
                        impact = f"{abs(shap_val):.2f}°C"
                    else:
                        impact = f"{abs(shap_val):.3f}"

                    print(f"  • {name} = {val_str} → {direction} prediction by {impact}")

            except Exception as e:
                print(f"  Could not generate SHAP explanation: {e}")


def compute_model_levels(dependency_graph):
    """Compute dependency level for each model (0=base, 1=depends on base, etc.)"""
    levels = {}

    def get_level(model_id, visited=None):
        if visited is None:
            visited = set()
        if model_id in visited:
            return 0  # Circular dependency, treat as base
        if model_id in levels:
            return levels[model_id]

        deps = dependency_graph.get(model_id, [])
        if not deps:
            levels[model_id] = 0
            return 0

        visited.add(model_id)
        max_dep_level = max((get_level(dep, visited.copy()) for dep in deps), default=-1)
        levels[model_id] = max_dep_level + 1
        return levels[model_id]

    for model_id in dependency_graph:
        get_level(model_id)

    return levels


def format_value(name, val):
    """Format a prediction value with appropriate unit"""
    if "occupancy" in name:
        return f"{val*100:.1f}%"
    elif "energy" in name:
        return f"{val:.1f} W"
    elif "temp" in name or "hvac" in name:
        return f"{val:.1f} °C"
    elif "humidity" in name:
        return f"{val:.1f}%"
    elif "co2" in name:
        return f"{val:.0f} PPM"
    elif "anomaly" in name:
        return f"{'NORMAL' if val < 0.5 else 'ANOMALY'} ({val:.2f})"
    elif "comfort" in name or "quality" in name or "lighting" in name:
        return f"{val:.3f}"
    return f"{val:.3f}"


def main():
    import argparse
    parser = argparse.ArgumentParser(description='ML Orchestration Engine')
    parser.add_argument('--registry', type=str, default='ml_model_registry.jsonld',
                        help='Path to JSON-LD registry file')
    args = parser.parse_args()

    registry_name = os.path.splitext(os.path.basename(args.registry))[0]
    orch = MLOrchestrator(registry_path=args.registry)

    # Compute dependency levels
    model_levels = compute_model_levels(orch.dependency_graph)

    # Build menu dynamically from JSON-LD
    menu_items = []
    for model_id in orch.model_specs:
        if model_id in orch.models:
            level = model_levels.get(model_id, 0)
            name = orch.model_specs[model_id]['name']
            menu_items.append((model_id, name, level))

    menu_items.sort(key=lambda x: (x[2], x[1]))

    # Startup info
    print(f"\n  ML Orchestrator | {registry_name} | {len(orch.models)} models")
    print(f"  {'─' * 50}")

    while True:
        # Menu
        print()
        current_level = None
        for i, (model_id, name, level) in enumerate(menu_items, 1):
            if level != current_level:
                label = "Base" if level == 0 else f"Level {level}"
                print(f"  {label}:")
                current_level = level

            output = orch.model_specs[model_id]['outputs'][0]['name']
            deps = orch.dependency_graph.get(model_id, [])
            if deps:
                dep_names = ', '.join(orch.model_specs[d]['name'] for d in deps if d in orch.model_specs)
                print(f"    [{i}] {name} → {output}  (uses: {dep_names})")
            else:
                print(f"    [{i}] {name} → {output}")

        print(f"\n    [q] Quit")

        sel = input("\n  > ").strip()
        if sel == 'q':
            break

        try:
            idx = int(sel) - 1
            if idx < 0 or idx >= len(menu_items): raise ValueError()
        except ValueError:
            print("  Invalid selection.")
            continue

        model_id, _, level = menu_items[idx]
        spec = orch.model_specs[model_id]
        requested_output = spec['outputs'][0]['name']

        # Run prediction
        results, model_inputs, order, missing_tracker = orch.predict([requested_output])

        # Execution chain
        print(f"\n  Chain:")
        for i, mid in enumerate(order):
            s = orch.model_specs[mid]
            deps = orch.dependency_graph.get(mid, [])
            if deps:
                dep_names = ', '.join([orch.model_specs[d]['name'] if d in orch.model_specs else '?' for d in deps])
                print(f"    {i+1}. {s['name']} <- {dep_names}")
            else:
                print(f"    {i+1}. {s['name']}")

        # Result
        print(f"\n  Result:")
        for name, val in results.items():
            print(f"    {name} = {format_value(name, val)}")

        # Missing inputs warning
        if missing_tracker:
            total = sum(len(m) for m in missing_tracker.values())
            print(f"\n  Fallbacks used: {total}")
            for mid, missing_list in missing_tracker.items():
                mname = orch.model_specs[mid]['name']
                for miss in missing_list:
                    label = "last-known" if miss.get('fallback_type') == 'last-known' else "default"
                    print(f"    {mname}: {miss['name']} = {miss['fallback']} ({label})")

        print(f"  {'─' * 50}")

        # XAI
        xai = input("  XAI explanation? (y/n): ").strip().lower()
        if xai == 'y':
            orch.explain(model_inputs, results)


if __name__ == '__main__':
    main()
