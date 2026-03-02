#!/usr/bin/env python3
"""
Test script for Graceful Degradation — Model File Missing Scenario

Uses the alternative JSON-LD registry (ml_model_registry_alt.jsonld).
Simulates a real-world scenario where a dependency model's .pkl file
is corrupted or missing, forcing downstream models to use fallback values.

Alt registry structure:
  Level 0: Temperature Predictor, Humidity Predictor, Comfort Index Predictor, Occupancy Detector
  Level 1: Energy Predictor (depends on OccupancyDetector), HVAC Optimizer (depends on HumidityPredictor)

Test scenario:
  OccupancyDetector's .pkl is removed from memory after loading.
  → Energy Predictor can't get predicted_occupancy from the model
  → Falls back to default value (0.3)
  → System continues operating and informs the user
"""

import sys
import os
from orchestrator import MLOrchestrator, format_value

REGISTRY = 'ml_model_registry_alt.jsonld'
OCCUPANCY_MODEL_ID = 'urn:ngsi-ld:MLModel:OccupancyDetector'


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def run_prediction(orch, output_name, label):
    """Run a prediction and display results"""
    results, inputs, order, missing = orch.predict([output_name])

    if output_name in results:
        print(f"\n  Result: {output_name} = {format_value(output_name, results[output_name])}")
    else:
        print(f"\n  ERROR: No result for {output_name}")
        return None, None

    # Show execution chain
    print(f"  Chain: {' → '.join(orch.model_specs[m]['name'] for m in order)}")

    # Show fallbacks
    if missing:
        total = sum(len(m) for m in missing.values())
        print(f"\n  Fallbacks used: {total}")
        for mid, missing_list in missing.items():
            mname = orch.model_specs[mid]['name']
            for miss in missing_list:
                fb_type = "last-known" if miss.get('fallback_type') == 'last-known' else "default"
                print(f"    {mname}: {miss['name']} = {miss['fallback']} ({fb_type})")
    else:
        print(f"  Fallbacks used: 0 (all inputs available)")

    return results, missing


def main():
    print_section("GRACEFUL DEGRADATION TEST")
    print(f"\n  Registry: {REGISTRY}")
    print(f"  Scenario: OccupancyDetector .pkl file missing")
    print(f"  Impact:   EnergyPredictor uses fallback for predicted_occupancy")

    # --- Load orchestrator normally ---
    try:
        orch = MLOrchestrator(registry_path=REGISTRY)
    except FileNotFoundError:
        print(f"\n  ERROR: {REGISTRY} not found!")
        print(f"  Run first: python3 train_models.py --registry {REGISTRY}")
        sys.exit(1)

    loaded = list(orch.models.keys())
    print(f"\n  Models loaded: {len(loaded)}")
    for mid in loaded:
        print(f"    - {orch.model_specs[mid]['name']}")

    # --- TEST 1: Normal operation (all models available) ---
    print_section("TEST 1: Normal Operation (all models loaded)")
    print(f"\n  Running Energy Predictor with all dependencies available...")

    r1, m1 = run_prediction(orch, 'predicted_energy', 'Energy normal')
    normal_result = r1.get('predicted_energy') if r1 else None

    # --- Simulate model failure ---
    print_section("SIMULATING FAILURE")

    if OCCUPANCY_MODEL_ID not in orch.models:
        print(f"\n  ERROR: OccupancyDetector not loaded. Train first:")
        print(f"  python3 train_models.py --registry {REGISTRY}")
        sys.exit(1)

    # Remove OccupancyDetector from loaded models (simulates .pkl missing/corrupted)
    del orch.models[OCCUPANCY_MODEL_ID]
    if OCCUPANCY_MODEL_ID in orch.scalers:
        del orch.scalers[OCCUPANCY_MODEL_ID]

    print(f"\n  Removed: OccupancyDetector (.pkl simulated as missing)")
    print(f"  Models remaining: {len(orch.models)}")
    for mid in orch.models:
        print(f"    - {orch.model_specs[mid]['name']}")

    print(f"\n  Impact chain:")
    print(f"    OccupancyDetector (MISSING)")
    print(f"      └→ Energy Predictor needs predicted_occupancy → will use fallback")

    # --- TEST 2: Energy with missing dependency ---
    print_section("TEST 2: Energy Predictor (OccupancyDetector missing)")
    print(f"\n  Running Energy Predictor without OccupancyDetector...")

    r2, m2 = run_prediction(orch, 'predicted_energy', 'Energy degraded')
    degraded_result = r2.get('predicted_energy') if r2 else None

    # --- TEST 3: HVAC Optimizer (independent, should be unaffected) ---
    print_section("TEST 3: HVAC Optimizer (no dependency on OccupancyDetector)")
    print(f"\n  Running HVAC Optimizer (should be unaffected)...")

    r3, m3 = run_prediction(orch, 'hvac_setpoint', 'HVAC')

    # --- TEST 4: Comfort Index (independent, should be unaffected) ---
    print_section("TEST 4: Comfort Index (no dependency on OccupancyDetector)")
    print(f"\n  Running Comfort Index Predictor (should be unaffected)...")

    r4, m4 = run_prediction(orch, 'predicted_comfort_index', 'Comfort')

    # --- Summary ---
    print_section("TEST SUMMARY")

    print(f"\n  Normal Energy result:   {format_value('predicted_energy', normal_result) if normal_result else 'N/A'}")
    print(f"  Degraded Energy result: {format_value('predicted_energy', degraded_result) if degraded_result else 'N/A'}")

    if normal_result and degraded_result:
        diff = abs(normal_result - degraded_result)
        print(f"  Difference:             {diff:.1f} W (due to fallback occupancy)")

    has_fallbacks = bool(m2)
    hvac_ok = r3 and 'hvac_setpoint' in r3
    comfort_ok = r4 and 'predicted_comfort_index' in r4

    print()
    if has_fallbacks:
        print(f"  [PASS] Energy Predictor used fallback when OccupancyDetector was missing")
    else:
        print(f"  [FAIL] Expected fallback usage but none detected")

    if hvac_ok:
        print(f"  [PASS] HVAC Optimizer was unaffected (no dependency on OccupancyDetector)")

    if comfort_ok:
        print(f"  [PASS] Comfort Index was unaffected (no dependency on OccupancyDetector)")

    print(f"  [PASS] System did not crash — graceful degradation works")
    print(f"\n{'='*60}")


if __name__ == '__main__':
    main()
