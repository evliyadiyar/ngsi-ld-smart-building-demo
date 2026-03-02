# NGSI-LD Smart Building ML Pipeline
### University of Sharjah — M5 Building

A real-world demonstration of NGSI-LD as the backbone for a smart building IoT system, with a flexible ML pipeline that uses JSON-LD as its **single source of truth**. Built on 6 months of actual sensor data from the M5 Building (January–June 2024).

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
  - [Path A: Full Pipeline (IoT → ML)](#path-a-full-pipeline-iot--ml)
  - [Path B: ML Only (skip IoT)](#path-b-ml-only-skip-iot)
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

---

## Overview

This project integrates three concepts into a unified system:

1. **NGSI-LD Digital Twin** — A live digital twin of the M5 Building managed by FIWARE Orion-LD. All physical entities (building, rooms, devices, sensors) are modeled as NGSI-LD entities with properties and relationships.

2. **IoT Data Pipeline** — Historical sensor data is streamed into the context broker via a producer-subscription-listener pattern, generating ML-ready CSV exports in real time.

3. **Flexible ML Orchestration** — 10 interconnected ML models are defined in a JSON-LD registry. The registry drives training, dependency resolution, and inference — meaning you can change model behavior by editing the JSON-LD file, without touching Python code.

**Key contribution:** The ML pipeline uses **JSON-LD as single source of truth**. A model's inputs, outputs, dependencies, and paths are all declared in the registry. Swapping registries (e.g., `ml_model_registry.jsonld` vs `ml_model_registry_alt.jsonld`) produces a completely different pipeline with zero code changes.

---

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

---

## Prerequisites

- **Docker** and **Docker Compose** (for Orion-LD + MongoDB)
- **Python 3.9+** with a virtual environment
- **pip** packages (see `requirements.txt`)

Install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

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
├── remove_outliers.py              (Utility) Removes statistical outliers from dataset
│
├── ml_model_registry.jsonld        PRIMARY model registry — 10 models, 4 dependency levels
├── ml_model_registry_alt.jsonld    ALTERNATIVE registry — 6 models, different structure
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
│   └── daily_unified_data.csv      ← PRIMARY ML dataset (173 days × 25 features)
│
└── ml_models/                      Trained model files (generated by train_models.py, git-ignored)
```

---

## Quick Start

### Path A: Full Pipeline (IoT → ML)

Run the complete system end-to-end, from raw IoT CSV to ML predictions.

```bash
# Terminal 1 — Start infrastructure
docker compose up -d
sleep 5

# Terminal 2 — Create entities and start listener
python3 create_entities.py --verify
python3 listener.py                  # Keep this running

# Terminal 3 — Ingest data
python3 create_subscriptions.py
python3 producer.py --fast           # Streams ~9,815 events in ~20 seconds
python3 create_daily_dataset.py      # Aggregates to ml_data/daily_unified_data.csv

# Train and run
python3 train_models.py
python3 orchestrator.py
```

### Path B: ML Only (skip IoT)

`ml_data/daily_unified_data.csv` is already included in the repository. You can skip the IoT pipeline entirely and go straight to ML:

```bash
# Train models directly (reads daily_unified_data.csv)
python3 train_models.py

# Run the interactive orchestrator
python3 orchestrator.py
```

---

## Detailed Walkthrough

### 1. Infrastructure (Docker)

```bash
docker compose up -d
```

Starts two services:
- **Orion-LD** on port `1026` — NGSI-LD Context Broker
- **MongoDB** on port `27017` — Data persistence for Orion-LD

Verify:
```bash
curl http://localhost:1026/ngsi-ld/v1/entities/   # Should return []
```

---

### 2. Create NGSI-LD Entities

```bash
python3 create_entities.py --verify
```

Creates **22 entities** in Orion-LD representing the M5 Building hierarchy:

| Type | Count | Examples |
|------|-------|---------|
| Building | 1 | M5Building |
| Floor | 1 | M5Floor |
| Room | 3 | Lab, Kitchen, Mailroom |
| EnergyDevice | 7 | Fridge, CoffeeMachine, Desktop, Printer... |
| Sensor | 10 | Temperature (×3), Humidity (×3), Motion (×3), Door (×1) |

---

### 3. Data Ingestion Pipeline

The pipeline moves data from CSV files into Orion-LD and back out as ML-ready exports.

**Start the listener first** (must be running before subscriptions fire):

```bash
python3 listener.py
# Flask server on port 5001 — receives notifications and writes to ml_data/
```

**Create subscriptions:**

```bash
python3 create_subscriptions.py
# Creates 2 subscriptions: one for energy devices, one for sensors
```

**Stream historical data:**

```bash
python3 producer.py --fast              # Stream all 9,815 events (~20 seconds)
python3 producer.py --fast --limit 200  # Test with 200 events only
python3 producer.py --speed 1000        # Simulate at 1000x real-time speed
```

The producer sends PATCH requests to Orion-LD → subscriptions trigger → listener receives notifications → writes `ml_data/*.csv`.

**How it works:**
```
producer.py  ──PATCH──►  Orion-LD  ──notification──►  listener.py  ──►  ml_data/*.csv
```

---

### 4. Create Daily Dataset

Aggregate the raw per-property CSVs into a single daily dataset for ML training:

```bash
python3 create_daily_dataset.py
# Output: ml_data/daily_unified_data.csv
```

The output has **173 rows** (days) × **25 columns**:

| Feature Group | Columns |
|--------------|---------|
| Energy devices | CoffeeMachine_power, Fridge_power, Kettle_power, Microwave_power, Desktop_power, Printer_power, WaterDispenser_power, total_power |
| Temperature | Kitchen_temperature, Lab_temperature, Mailroom_temperature, avg_temperature |
| Humidity | Kitchen_humidity, Lab_humidity, Mailroom_humidity, avg_humidity |
| Occupancy | Kitchen_occupancy, Lab_occupancy, Mailroom_occupancy, avg_occupancy |
| Temporal | day_of_week, is_weekend, month, day_of_month, day_name |

> **Note:** Missing values are stored as `-1` (distinct from `0.0` which means the device was idle/off).

---

### 5. Train ML Models

```bash
python3 train_models.py
# Trains all 10 models defined in ml_model_registry.jsonld

python3 train_models.py --registry ml_model_registry_alt.jsonld
# Trains the alternative 6-model configuration
```

The script reads every model's input/output specification from the JSON-LD registry, resolves the training order using topological sort (dependencies first), trains each model as a `RandomForestRegressor`, saves `.pkl` files to `ml_models/<registry-name>/`, and writes R² and MAE metrics back into the registry file.

**Models trained (primary registry, 4 dependency levels):**

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

---

### 6. Run the Orchestrator

```bash
python3 orchestrator.py
# Uses ml_model_registry.jsonld (primary, 10 models)

python3 orchestrator.py --registry ml_model_registry_alt.jsonld
# Uses alternative registry (6 models)
```

An interactive menu shows all loaded models grouped by dependency level. When you select a model, the orchestrator:

1. Resolves all dependencies recursively
2. Executes dependencies first, then the selected model
3. Shows the execution chain and result
4. Reports any missing inputs and the fallback values used

**Output markers:**
- `[+]` — Model ran with all inputs available
- `[~]` — Model ran but used one or more fallback values
- `[!]` — Model could not load (`.pkl` file missing or corrupted)

**Example output (HVAC Optimizer):**
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

---

## JSON-LD as Single Source of Truth

The entire ML pipeline is driven by `ml_model_registry.jsonld`. This file is a valid NGSI-LD document that defines each model's inputs, outputs, dependencies, and file paths using a custom smart building ontology.

**Example: EnergyPredictor in the registry**
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

**What this means in practice:**
- `train_models.py` reads this and knows to train EnergyPredictor *after* OccupancyDetector
- `orchestrator.py` reads this and knows to execute OccupancyDetector first, then feed its output as input
- Changing the registry file changes the pipeline — no Python changes needed

**Alternative registry (`ml_model_registry_alt.jsonld`)** demonstrates the same engine with a different model set and different dependency structure, showing the registry is truly configuration-driven.

---

## Graceful Degradation Demo

This demo shows what happens when a dependency model's `.pkl` file is missing at runtime — the system continues operating and informs the user.

**Setup:**

```bash
# 1. Train the alternative registry (trains all 6 models including OccupancyDetector)
python3 train_models.py --registry ml_model_registry_alt.jsonld

# 2. Simulate OccupancyDetector failure — delete its .pkl file
rm ml_models/ml_model_registry_alt/occupancy_detector.pkl

# 3. Run the orchestrator
python3 orchestrator.py --registry ml_model_registry_alt.jsonld
```

**What you see:**

At startup:
```
Warning: Model file not found for Occupancy Detector (ml_models/ml_model_registry_alt/occupancy_detector.pkl)

  ML Orchestrator | ml_model_registry_alt | 5 models    ← 5 instead of 6
```

When you select **Energy Predictor** (option 4):
```
Execution:
  [!] Occupancy Detector not loaded (.pkl missing), skipping
  [~] Energy Predictor → 331.4

  Result:
    predicted_energy = 331.4 W

  Fallbacks used: 1
    Energy Predictor: predicted_occupancy = 0.3 (default)
```

OccupancyDetector is completely absent from the menu (not loaded), EnergyPredictor still runs using a domain-default fallback for `predicted_occupancy = 0.3`. HVAC Optimizer and Comfort Index (no dependency on OccupancyDetector) run normally with `[+]`.

**Automated test:**

```bash
python3 test_graceful_degradation.py
# Runs normal vs degraded comparison automatically and prints pass/fail summary
```

**Fallback priority:**
1. **Last-known value** — most recent successfully received sensor reading (cached during operation)
2. **Domain default** — reasonable static default (e.g., `predicted_occupancy = 0.3`, `avg_temperature = 22.0°C`)
3. **Zero** — final fallback if no other value is available

---

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

All entities use NGSI-LD `Properties` and `Relationships`. Every sensor reading includes an `observedAt` timestamp (local time, timezone-stripped to prevent UTC date shifts).

---

## Querying the Context Broker

```bash
# List all entities
curl -s "http://localhost:1026/ngsi-ld/v1/entities/" | jq '.[].id'

# Get all energy devices
curl -s "http://localhost:1026/ngsi-ld/v1/entities/?type=EnergyDevice" | jq .

# Get a specific entity
curl -s "http://localhost:1026/ngsi-ld/v1/entities/urn:ngsi-ld:EnergyDevice:Kitchen:Fridge" | jq .

# Get all entities in a room
curl -s "http://localhost:1026/ngsi-ld/v1/entities/?q=refRoom==%22urn:ngsi-ld:Room:Kitchen%22" | jq '.[].id'

# Check subscriptions
python3 create_subscriptions.py --list
```

---

## Troubleshooting

**Port 5000 already in use (macOS)**
Port 5000 conflicts with AirPlay Receiver on macOS. The listener already defaults to port 5001. Alternatively, disable AirPlay Receiver in System Settings → General → AirDrop & Handoff.

**Listener not receiving notifications**
```bash
curl http://localhost:5001/stats           # Check listener is running
python3 create_subscriptions.py --list    # Verify subscriptions exist
python3 create_subscriptions.py           # Recreate if missing
```

**Models not showing in orchestrator menu**
The orchestrator only shows models whose `.pkl` files were found. Run training first:
```bash
python3 train_models.py
```

**Docker containers fail to start**
```bash
docker ps                         # Check running containers
docker logs fiware-orion-ld       # View Orion-LD logs
docker compose down && docker compose up -d   # Restart
```

**numpy / sklearn not found**
Ensure you are using the correct Python environment (the one where you ran `pip install -r requirements.txt`):
```bash
which python3
pip list | grep scikit
```

---

## System Ports

| Port | Service | Description |
|------|---------|-------------|
| 1026 | Orion-LD | NGSI-LD Context Broker API |
| 27017 | MongoDB | Data persistence for Orion-LD |
| 5001 | Listener | Flask server — receives notifications, exports CSV |

---

## References

- [ETSI NGSI-LD Specification (GS CIM 009)](https://www.etsi.org/deliver/etsi_gs/CIM/001_099/009/01.08.01_60/gs_CIM009v010801p.pdf)
- [FIWARE Orion-LD Context Broker](https://github.com/FIWARE/context.Orion-LD)
- [Sharjah IoT Dataset Repository](https://github.com/adel8641/Dataset-of-IoT-Based-Energy-and-Environmental-Parameters-in-a-Smart-Building-Infrastructure)
- [Dataset Research Paper — Adel et al., University of Sharjah, 2024](https://www.researchgate.net/publication/382666251_Dataset_of_IoT-Based_Energy_and_Environmental_Parameters_in_a_Smart_Building_Infrastructure)

---

**Dataset credit:** Sharjah IoT Dataset by Adel et al., University of Sharjah, 2024.
**License:** Provided for educational and research purposes.
