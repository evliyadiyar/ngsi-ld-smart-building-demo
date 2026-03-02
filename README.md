# NGSI-LD Smart Building ML Pipeline
### University of Sharjah — M5 Building

A real-world NGSI-LD implementation for the M5 Building, built on 6 months of actual IoT sensor data (January–June 2024). The project combines a FIWARE Orion-LD digital twin with a flexible ML pipeline where **JSON-LD acts as the single source of truth** — model inputs, outputs, dependencies and file paths are all declared in the registry, not hardcoded in Python.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
  - [Full Pipeline (IoT → ML)](#full-pipeline-iot--ml)
  - [ML Only (skip IoT)](#ml-only-skip-iot)
- [Detailed Walkthrough](#detailed-walkthrough)
  - [1. Infrastructure (Docker)](#1-infrastructure-docker)
  - [2. Create NGSI-LD Entities](#2-create-ngsi-ld-entities)
  - [3. Data Ingestion Pipeline](#3-data-ingestion-pipeline)
  - [4. Create Daily Dataset](#4-create-daily-dataset)
  - [5. Train ML Models](#5-train-ml-models)
  - [6. Run the Orchestrator](#6-run-the-orchestrator)
- [JSON-LD as Single Source of Truth](#json-ld-as-single-source-of-truth)
- [Graceful Degradation Demo](#graceful-degradation-demo)
- [NGSI-LD Entity Model](#ngsi-ld-entity-model)
- [Querying the Context Broker](#querying-the-context-broker)
- [Troubleshooting](#troubleshooting)
- [References](#references)

## Overview

The system is built in two layers. The first is an IoT data pipeline: historical sensor data is streamed into an Orion-LD context broker through a producer-subscription-listener pattern, and exported as ML-ready CSVs. The second is an ML orchestration engine: 10 interconnected models are defined in a JSON-LD registry and executed recursively — when you request a prediction, all dependencies are resolved and run automatically.

Swapping the registry file (`ml_model_registry.jsonld` → `ml_model_registry_alt.jsonld`) gives a completely different set of models and dependency graph with no code changes. This is the main architectural point the project demonstrates.

## Architecture

```
Dataset-of-IoT-Based-Energy/   ← Raw IoT CSVs (6 months, 9,815 events)
        │
        ▼
   producer.py  ──PATCH──►  Orion-LD (port 1026)
                                  │
                         subscriptions (create_subscriptions.py)
                                  │
                                  ▼ HTTP notifications
                            listener.py (port 5001)
                                  │
                                  ▼
                         ml_data/*.csv  (one file per property)
                                  │
                        create_daily_dataset.py
                                  │
                                  ▼
                    ml_data/daily_unified_data.csv
                                  │
                          train_models.py
                         (reads JSON-LD registry)
                                  │
                                  ▼
                         ml_models/*.pkl
                                  │
                          orchestrator.py
                         (reads JSON-LD registry)
                                  │
                                  ▼
                    Predictions + Graceful Degradation
```

## Prerequisites

- **Docker** and **Docker Compose** — for running Orion-LD and MongoDB
- **Python 3.9+**

```bash
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Project Structure

```
ngsi-ld-smart-building-demo/
│
├── docker-compose.yml              Orion-LD + MongoDB containers
├── requirements.txt                Python dependencies
│
├── create_entities.py              Creates 22 NGSI-LD entities in Orion-LD
├── producer.py                     Streams CSV data into Orion-LD (9,815 events)
├── create_subscriptions.py         Sets up property-change subscriptions
├── listener.py                     Flask server — receives notifications → CSV export
├── create_daily_dataset.py         Aggregates raw CSVs into daily ML dataset
│
├── train_models.py                 Trains ML models from JSON-LD registry specs
├── orchestrator.py                 Recursive model orchestration engine
├── test_graceful_degradation.py    Automated test for the degradation scenario
├── remove_outliers.py              Utility — removes ±3σ outliers from the daily dataset
│
├── ml_model_registry.jsonld        Primary registry — 10 models, 4 dependency levels
├── ml_model_registry_alt.jsonld    Alternative registry — 6 models, different structure
│
├── Dataset-of-IoT-Based-Energy/    Source IoT dataset (CSV files from Chronograf)
│   ├── Watt W/                     Active power (W) per device
│   ├── KWh/                        Daily energy consumption (KWh)
│   ├── Apperent power VA/          Apparent power (VA)
│   ├── Temperature/                Temperature per room (°C)
│   ├── Humidity/                   Humidity per room (%)
│   └── Motion/                     Occupancy and door state
│
├── ml_data/                        Generated by listener + aggregation scripts
│   ├── activePower_data.csv
│   ├── dailyEnergyConsumed_data.csv
│   ├── apparentPower_data.csv
│   ├── temperature_data.csv
│   ├── relativeHumidity_data.csv
│   ├── occupancy_data.csv
│   ├── doorState_data.csv
│   └── daily_unified_data.csv      ← Primary ML dataset (173 days × 25 features)
│
└── ml_models/                      Trained model files (generated, git-ignored)
```

## Quick Start

### Full Pipeline (IoT → ML)

```bash
# Terminal 1 — start infrastructure
docker compose up -d
sleep 5

# Terminal 2 — create entities and start listener
python3 create_entities.py --verify
python3 listener.py                  # keep this running

# Terminal 3 — ingest data
python3 create_subscriptions.py
python3 producer.py --fast           # streams ~9,815 events in ~20 seconds
python3 create_daily_dataset.py

# train and run
python3 train_models.py
python3 orchestrator.py
```

### ML Only (skip IoT)

`ml_data/daily_unified_data.csv` is already in the repository. You can skip Docker and the data pipeline entirely:

```bash
python3 train_models.py
python3 orchestrator.py
```

## Detailed Walkthrough

### 1. Infrastructure (Docker)

```bash
docker compose up -d
```

Starts Orion-LD on port `1026` and MongoDB on port `27017`. Verify with:

```bash
curl http://localhost:1026/ngsi-ld/v1/entities/
```

### 2. Create NGSI-LD Entities

```bash
python3 create_entities.py --verify
```

Creates 22 entities representing the M5 Building:

| Type | Count | Examples |
|------|-------|---------|
| Building | 1 | M5Building |
| Floor | 1 | M5Floor |
| Room | 3 | Lab, Kitchen, Mailroom |
| EnergyDevice | 7 | Fridge, CoffeeMachine, Desktop, Printer... |
| Sensor | 10 | Temperature (×3), Humidity (×3), Motion (×3), Door (×1) |

### 3. Data Ingestion Pipeline

Start the listener first — it must be running before subscriptions fire:

```bash
python3 listener.py
```

Then create subscriptions and stream the data:

```bash
python3 create_subscriptions.py

python3 producer.py --fast              # all 9,815 events (~20 seconds)
python3 producer.py --fast --limit 200  # quick test with 200 events
python3 producer.py --speed 1000        # 1000× real-time speed
```

The flow is: `producer.py` sends PATCH requests to Orion-LD → subscriptions fire → `listener.py` receives HTTP notifications → writes to `ml_data/*.csv`. Each property (activePower, temperature, occupancy, etc.) gets its own CSV file to avoid timestamp mismatches between sensors that update at different rates.

### 4. Create Daily Dataset

```bash
python3 create_daily_dataset.py
# output: ml_data/daily_unified_data.csv
```

Aggregates the raw per-property CSVs into daily averages. The result is 173 rows × 25 columns covering energy, temperature, humidity, occupancy and temporal features. Missing values use `-1` as a sentinel (different from `0.0`, which means a device was idle but present).

If needed, `remove_outliers.py` can clean statistical outliers (±3σ) from this file before training.

### 5. Train ML Models

```bash
python3 train_models.py
# trains all 10 models from ml_model_registry.jsonld

python3 train_models.py --registry ml_model_registry_alt.jsonld
# trains the alternative 6-model configuration
```

The script reads each model's input/output specification from the registry, resolves the training order with a topological sort (dependencies first), trains a `RandomForestRegressor` for each model, saves `.pkl` files under `ml_models/<registry-name>/`, and writes the R² and MAE metrics back into the registry.

Models trained from the primary registry:

```
Level 0 (Base):
  OccupancyDetector     Kitchen/Lab occupancy → predicted_occupancy
  TemperaturePredictor  Humidity + occupancy  → predicted_temperature
  HumidityPredictor     Appliances + occupancy → predicted_humidity

Level 1:
  EnergyPredictor       Occupancy + appliances → predicted_energy
  CO2Predictor          Temperature + occupancy → predicted_co2
  LightingController    Occupancy + time → predicted_lighting

Level 2:
  ComfortIndexPredictor Temperature + humidity → predicted_comfort_index
  AnomalyDetector       Power + environment → predicted_anomaly

Level 3:
  HVACOptimizer         Comfort + sensors → hvac_setpoint
  AirQualityIndex       CO2 + humidity + comfort → predicted_air_quality
```

### 6. Run the Orchestrator

```bash
python3 orchestrator.py
# uses ml_model_registry.jsonld (10 models)

python3 orchestrator.py --registry ml_model_registry_alt.jsonld
# uses the alternative registry (6 models)
```

An interactive menu groups models by dependency level. Selecting a model triggers recursive execution — all dependencies are resolved and run first. The orchestrator then shows the execution chain, result, and any fallback values that were used.

Output markers:
- `[+]` — ran with all inputs available
- `[~]` — ran but used one or more fallback values
- `[!]` — could not load (`.pkl` file missing or corrupted)

Example output (HVAC Optimizer):

```
  ML Orchestrator | ml_model_registry | 10 models

  Base:
    [1] Humidity Predictor → predicted_humidity
    [2] Occupancy Detector → predicted_occupancy
    [3] Temperature Predictor → predicted_temperature
  Level 1:
    [4] CO2 Predictor → predicted_co2
    [5] Energy Predictor → predicted_energy  (uses: Occupancy Detector)
    ...
  Level 3:
    [9] HVAC Optimizer → hvac_setpoint  (uses: Comfort Index Predictor)

  > 9

Execution:
  [+] Temperature Predictor → 22.541
  [+] Humidity Predictor → 60.317
  [+] Comfort Index Predictor → 0.832
  [+] HVAC Optimizer → 21.800

  Result:
    hvac_setpoint = 21.8 °C

  Fallbacks used: 0
```

## JSON-LD as Single Source of Truth

`ml_model_registry.jsonld` is a valid NGSI-LD document that fully describes each ML model — its inputs, outputs, dependencies, and file paths — using a custom smart building ontology. Both `train_models.py` and `orchestrator.py` read this file at startup and adapt their behavior to whatever is declared there.

Example entry for EnergyPredictor:

```json
{
  "id": "urn:ngsi-ld:MLModel:EnergyPredictor",
  "type": "MLModel",
  "dependsOn": {
    "type": "Relationship",
    "object": ["urn:ngsi-ld:MLModel:OccupancyDetector"]
  },
  "inputs": {
    "type": "Property",
    "value": [
      {
        "name": "predicted_occupancy",
        "fromModel": true,
        "source": "urn:ngsi-ld:MLModel:OccupancyDetector",
        "attribute": "predicted_occupancy"
      },
      { "name": "Desktop_power", "source": "urn:ngsi-ld:EnergyDevice:Office:Desktop" }
    ]
  },
  "outputs": {
    "type": "Property",
    "value": [{ "name": "predicted_energy", "unit": "W" }]
  },
  "modelPath": { "type": "Property", "value": "ml_models/energy_predictor.pkl" }
}
```

`train_models.py` reads this and trains EnergyPredictor after OccupancyDetector. `orchestrator.py` reads the same file and knows to execute OccupancyDetector first, then pass its output as input. The Python scripts contain no hardcoded model names.

`ml_model_registry_alt.jsonld` uses the same engine but with a different set of models and dependencies, demonstrating that the registry is genuinely configuration-driven.

## Graceful Degradation Demo

When a dependency model's `.pkl` file is missing at runtime, the system does not crash. It skips the broken model, uses a domain-appropriate fallback value for its output, and informs the user clearly.

Setup:

```bash
# train all 6 models in the alternative registry
python3 train_models.py --registry ml_model_registry_alt.jsonld

# simulate a runtime failure by deleting OccupancyDetector's .pkl
rm ml_models/ml_model_registry_alt/occupancy_detector.pkl

# run the orchestrator
python3 orchestrator.py --registry ml_model_registry_alt.jsonld
```

At startup you see:

```
Warning: Model file not found for Occupancy Detector (ml_models/ml_model_registry_alt/occupancy_detector.pkl)

  ML Orchestrator | ml_model_registry_alt | 5 models    ← 5 instead of 6
```

OccupancyDetector does not appear in the menu. When you select Energy Predictor (which depends on it):

```
Execution:
  [!] Occupancy Detector not loaded (.pkl missing), skipping
  [~] Energy Predictor → 331.4

  Result:
    predicted_energy = 331.4 W

  Fallbacks used: 1
    Energy Predictor: predicted_occupancy = 0.3 (default)
```

Models that have no dependency on OccupancyDetector (HVAC Optimizer, Comfort Index) continue running normally with `[+]`.

Fallback priority:
1. Last-known value — most recent successfully read value, cached during operation
2. Domain default — static reasonable default per feature (e.g. `predicted_occupancy = 0.3`, `avg_temperature = 22.0`)
3. Zero — final fallback

The automated test runs both the normal and degraded scenarios and prints a pass/fail comparison:

```bash
python3 test_graceful_degradation.py
```

## NGSI-LD Entity Model

```
urn:ngsi-ld:Building:M5Building
  └── urn:ngsi-ld:Floor:M5Floor
        ├── urn:ngsi-ld:Room:Lab
        │     ├── urn:ngsi-ld:EnergyDevice:Lab:Desktop
        │     ├── urn:ngsi-ld:EnergyDevice:Lab:Printer
        │     ├── urn:ngsi-ld:Sensor:Lab_Temperature
        │     ├── urn:ngsi-ld:Sensor:Lab_Humidity
        │     ├── urn:ngsi-ld:Sensor:Lab_Motion
        │     └── urn:ngsi-ld:Sensor:Lab_Door
        ├── urn:ngsi-ld:Room:Kitchen
        │     ├── urn:ngsi-ld:EnergyDevice:Kitchen:CoffeeMachine
        │     ├── urn:ngsi-ld:EnergyDevice:Kitchen:Fridge
        │     ├── urn:ngsi-ld:EnergyDevice:Kitchen:Kettle
        │     ├── urn:ngsi-ld:EnergyDevice:Kitchen:Microwave
        │     ├── urn:ngsi-ld:Sensor:Kitchen_Temperature
        │     ├── urn:ngsi-ld:Sensor:Kitchen_Humidity
        │     └── urn:ngsi-ld:Sensor:Kitchen_Motion
        └── urn:ngsi-ld:Room:Mailroom
              ├── urn:ngsi-ld:EnergyDevice:Mailroom:WaterDispenser
              ├── urn:ngsi-ld:Sensor:Mailroom_Temperature
              ├── urn:ngsi-ld:Sensor:Mailroom_Humidity
              └── urn:ngsi-ld:Sensor:Mailroom_Motion
```

All entities follow the NGSI-LD property/relationship model. Every sensor reading carries an `observedAt` timestamp using local time with the timezone stripped — this prevents UTC conversion from shifting dates when the data was originally recorded at UTC+4.

## Querying the Context Broker

```bash
# list all entity IDs
curl -s "http://localhost:1026/ngsi-ld/v1/entities/" | jq '.[].id'

# all energy devices
curl -s "http://localhost:1026/ngsi-ld/v1/entities/?type=EnergyDevice" | jq .

# a specific entity
curl -s "http://localhost:1026/ngsi-ld/v1/entities/urn:ngsi-ld:EnergyDevice:Kitchen:Fridge" | jq .

# all entities linked to a room
curl -s "http://localhost:1026/ngsi-ld/v1/entities/?q=refRoom==%22urn:ngsi-ld:Room:Kitchen%22" | jq '.[].id'

# check active subscriptions
python3 create_subscriptions.py --list
```

## Troubleshooting

**Port 5000 already in use (macOS)**
Port 5000 is taken by AirPlay Receiver on macOS. The listener already defaults to 5001. You can also disable AirPlay Receiver in System Settings → General → AirDrop & Handoff.

**Listener not receiving notifications**
```bash
curl http://localhost:5001/stats           # check the listener is running
python3 create_subscriptions.py --list    # verify subscriptions exist
python3 create_subscriptions.py           # recreate if missing
```

**Models not showing in the orchestrator menu**
The menu only lists models whose `.pkl` files were found. Run training first:
```bash
python3 train_models.py
```

**Docker containers fail to start**
```bash
docker ps
docker logs fiware-orion-ld
docker compose down && docker compose up -d
```

**numpy / sklearn not found**
Make sure you are running the Python environment where you installed the dependencies:
```bash
which python3
pip list | grep scikit
```

## System Ports

| Port | Service | Description |
|------|---------|-------------|
| 1026 | Orion-LD | NGSI-LD Context Broker API |
| 27017 | MongoDB | Data persistence for Orion-LD |
| 5001 | Listener | Flask server — receives notifications, exports CSV |

## References

- [ETSI NGSI-LD Specification (GS CIM 009)](https://www.etsi.org/deliver/etsi_gs/CIM/001_099/009/01.08.01_60/gs_CIM009v010801p.pdf)
- [FIWARE Orion-LD Context Broker](https://github.com/FIWARE/context.Orion-LD)
- [Sharjah IoT Dataset Repository](https://github.com/adel8641/Dataset-of-IoT-Based-Energy-and-Environmental-Parameters-in-a-Smart-Building-Infrastructure)
- [Dataset Research Paper — Adel et al., University of Sharjah, 2024](https://www.researchgate.net/publication/382666251_Dataset_of_IoT-Based_Energy_and_Environmental_Parameters_in_a_Smart_Building_Infrastructure)

Dataset credit: Sharjah IoT Dataset by Adel et al., University of Sharjah, 2024.
