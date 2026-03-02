#!/usr/bin/env python3
"""
NGSI-LD Data Producer - Simulation Mode
Streams sensor/device data from CSV files to Orion-LD in real-time simulation
"""

import requests
import csv
import sys
import time
import signal
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
import argparse

# Configuration
ORION_URL = "http://localhost:1026/ngsi-ld/v1"
CONTEXT = "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"
BASE_DIR = Path(__file__).parent
DATASET_DIR = BASE_DIR / "Dataset-of-IoT-Based-Energy"
ML_DATA_DIR = BASE_DIR / "ml_data"

# Import configurations from create_entities.py
from create_entities import ENERGY_DEVICES_CONFIG, SENSOR_CONFIG

# Global flag for graceful shutdown
running = True


@dataclass
class DataEvent:
    """Represents a single sensor/device reading at a specific timestamp"""
    timestamp: datetime
    entity_id: str
    entity_type: str
    property_name: str
    value: float
    unit_code: str

    def __lt__(self, other):
        """For sorting events by timestamp"""
        return self.timestamp < other.timestamp


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global running
    print("\n\n[SHUTDOWN] Stopping producer...")
    running = False


def clean_ml_data():
    """Clean existing ML data CSV files before starting"""
    if ML_DATA_DIR.exists():
        csv_files = list(ML_DATA_DIR.glob("*.csv"))
        if csv_files:
            for csv_file in csv_files:
                csv_file.unlink()
            logging.info(f"Cleaned {len(csv_files)} existing ML data CSV files")
        else:
            logging.info("No existing ML data CSV files to clean")
    else:
        logging.info("ML data directory does not exist yet")


def parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Parse timestamp from CSV and strip timezone info (keep local time only)"""
    try:
        # Try ISO format first
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        # STRIP timezone - keep local time as naive datetime
        if dt.tzinfo is not None:
            # Get local time components without UTC conversion
            dt = dt.replace(tzinfo=None)
        return dt
    except:
        try:
            # Try common formats
            for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S']:
                try:
                    return datetime.strptime(ts_str, fmt)
                except:
                    continue
        except:
            pass
    return None


def read_device_csv(device_id: str, room: str, csv_file: str, property_name: str, unit_code: str) -> List[DataEvent]:
    """Read energy device CSV and return list of events"""
    events = []
    csv_path = DATASET_DIR / csv_file

    if not csv_path.exists():
        logging.warning(f"CSV not found: {csv_path}")
        return events

    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Try to find timestamp column
                ts_col = None
                for col in ['_time', 'time', 'timestamp', 'Time']:
                    if col in row:
                        ts_col = col
                        break

                if not ts_col:
                    continue

                timestamp = parse_timestamp(row[ts_col])
                if not timestamp:
                    continue

                # Try to find value column
                value = None
                # Try specific column names first, then any column ending with .mean_value
                possible_cols = ['_value', 'value', 'Value', device_id]
                # Add columns that end with .mean_value (W.mean_value, kWh.mean_value, VA.mean_value)
                possible_cols.extend([col for col in row.keys() if col.endswith('.mean_value')])

                for col in possible_cols:
                    if col in row and row[col]:
                        try:
                            value = float(row[col])
                            break
                        except:
                            continue

                if value is not None:
                    events.append(DataEvent(
                        timestamp=timestamp,
                        entity_id=f"urn:ngsi-ld:EnergyDevice:{room}:{device_id}",
                        entity_type="EnergyDevice",
                        property_name=property_name,
                        value=value,
                        unit_code=unit_code
                    ))

    except Exception as e:
        logging.error(f"Error reading {csv_path}: {e}")

    return events


def read_sensor_csv(sensor_id: str, csv_file: str, column: str, property_name: str, unit_code: str) -> List[DataEvent]:
    """Read sensor CSV and return list of events"""
    events = []
    csv_path = DATASET_DIR / csv_file

    if not csv_path.exists():
        logging.warning(f"CSV not found: {csv_path}")
        return events

    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Find timestamp
                ts_col = None
                for col in ['_time', 'time', 'timestamp', 'Time']:
                    if col in row:
                        ts_col = col
                        break

                if not ts_col:
                    continue

                timestamp = parse_timestamp(row[ts_col])
                if not timestamp:
                    continue

                # Get value from specified column
                if column in row and row[column]:
                    try:
                        value = float(row[column])
                        events.append(DataEvent(
                            timestamp=timestamp,
                            entity_id=f"urn:ngsi-ld:Sensor:{sensor_id}",
                            entity_type="Sensor",
                            property_name=property_name,
                            value=value,
                            unit_code=unit_code
                        ))
                    except:
                        continue

    except Exception as e:
        logging.error(f"Error reading {csv_path}: {e}")

    return events


def load_all_events() -> List[DataEvent]:
    """Load all events from CSV files"""
    all_events = []

    logging.info("Loading events from CSV files...")

    # Load energy device events
    for device_id, config in ENERGY_DEVICES_CONFIG.items():
        logging.info(f"  Loading {device_id}...")

        # Active Power (Watt)
        events = read_device_csv(device_id, config['room'], config['csv_files']['watt'], 'activePower', 'WTT')
        all_events.extend(events)
        logging.info(f"    - activePower: {len(events)} events")

        # Daily Energy (KWh)
        events = read_device_csv(device_id, config['room'], config['csv_files']['kwh'], 'dailyEnergyConsumed', 'KWH')
        all_events.extend(events)
        logging.info(f"    - dailyEnergyConsumed: {len(events)} events")

        # Apparent Power (VA)
        events = read_device_csv(device_id, config['room'], config['csv_files']['va'], 'apparentPower', 'VA')
        all_events.extend(events)
        logging.info(f"    - apparentPower: {len(events)} events")

    # Load sensor events
    for sensor_id, config in SENSOR_CONFIG.items():
        logging.info(f"  Loading {sensor_id}...")
        events = read_sensor_csv(
            sensor_id,
            config['csv'],
            config['column'],
            config['attribute'],
            config['unit_code']
        )
        all_events.extend(events)
        logging.info(f"    - {config['attribute']}: {len(events)} events")

    # Sort all events by timestamp
    all_events.sort()

    logging.info(f"\nTotal events loaded: {len(all_events)}")
    if all_events:
        logging.info(f"Time range: {all_events[0].timestamp} → {all_events[-1].timestamp}")

    return all_events


def update_entity_property(event: DataEvent) -> bool:
    """Update entity property in Orion-LD via PATCH"""
    url = f"{ORION_URL}/entities/{event.entity_id}/attrs/{event.property_name}"

    # Keep original timestamp with timezone (don't convert to UTC)
    # ML analysis needs consistent local time, not UTC conversion
    timestamp_str = event.timestamp.isoformat()
    # Handle Z suffix for naive datetimes
    if event.timestamp.tzinfo is None:
        timestamp_str = timestamp_str + 'Z'

    payload = {
        "type": "Property",
        "value": event.value,
        "observedAt": timestamp_str
    }

    # Only add unitCode if it's not None/empty
    if event.unit_code:
        payload["unitCode"] = event.unit_code

    headers = {
        "Content-Type": "application/json",
        "Link": f'<{CONTEXT}>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"'
    }

    try:
        response = requests.patch(url, json=payload, headers=headers, timeout=5)

        if response.status_code == 204:
            return True
        else:
            logging.error(f"Failed to update {event.entity_id}/{event.property_name}: {response.status_code} - {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        logging.error(f"Connection error updating {event.entity_id}: {e}")
        return False


def run_simulation(events: List[DataEvent], speed_factor: float = 1.0, fast_mode: bool = False, throttle: float = 0.0):
    """Run simulation by replaying events at their timestamps"""
    global running

    if not events:
        logging.error("No events to simulate!")
        return

    mode_desc = "FAST MODE (no delays)" if fast_mode else f"Simulation (speed: {speed_factor}x)"
    logging.info(f"\n{'='*60}")
    logging.info(f"Starting {mode_desc}")
    logging.info(f"{'='*60}\n")

    start_real_time = time.time()
    start_sim_time = events[0].timestamp

    updates_sent = 0
    updates_success = 0

    for i, event in enumerate(events):
        if not running:
            break

        # Fast mode: no timestamp-based delays
        if not fast_mode:
            # Calculate how long to wait (simulation time)
            elapsed_sim = (event.timestamp - start_sim_time).total_seconds()
            elapsed_real = time.time() - start_real_time
            target_real = elapsed_sim / speed_factor

            sleep_time = target_real - elapsed_real
            if sleep_time > 0:
                time.sleep(sleep_time)
        elif throttle > 0:
            # Optional throttle in fast mode to avoid overwhelming Orion-LD
            time.sleep(throttle)

        # Send update
        success = update_entity_property(event)
        updates_sent += 1
        if success:
            updates_success += 1

        # Progress logging (every 100 events in fast mode, every 10 in normal mode)
        log_interval = 100 if fast_mode else 10
        if updates_sent % log_interval == 0:
            progress = (i + 1) / len(events) * 100
            logging.info(
                f"[{progress:5.1f}%] {event.timestamp} | "
                f"{event.entity_id.split(':')[-1]:20} | "
                f"{event.property_name:20} = {event.value:8.2f} {event.unit_code}"
            )

    # Summary
    logging.info(f"\n{'='*60}")
    logging.info(f"Simulation {'interrupted' if not running else 'completed'}")
    logging.info(f"{'='*60}")
    logging.info(f"Updates sent: {updates_sent}")
    logging.info(f"Updates successful: {updates_success}")
    logging.info(f"Success rate: {updates_success/updates_sent*100:.1f}%")
    logging.info(f"Real time elapsed: {time.time() - start_real_time:.1f}s")


def main():
    """Main entry point"""
    global running

    parser = argparse.ArgumentParser(
        description='NGSI-LD Data Producer - Stream CSV data to Orion-LD',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fast mode (no delays, ~10 seconds for 6 months of data)
  python3 producer.py --fast

  # First 1000 events only (testing)
  python3 producer.py --fast --limit 1000

  # Simulation mode with 1000x speed
  python3 producer.py --speed 1000

  # Fast mode with small throttle to avoid overwhelming Orion-LD
  python3 producer.py --fast --throttle 0.001
        """
    )
    parser.add_argument(
        '--speed',
        type=float,
        default=1.0,
        help='Simulation speed multiplier (default: 1.0 = real-time)'
    )
    parser.add_argument(
        '--fast',
        action='store_true',
        help='Fast mode: send data as quickly as possible (ignores --speed)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=0,
        help='Limit to first N events (0 = all events)'
    )
    parser.add_argument(
        '--throttle',
        type=float,
        default=0.0,
        help='Throttle delay in seconds between updates in fast mode (default: 0.0)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # Setup signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Banner
    print("=" * 60)
    print("NGSI-LD Data Producer - University of Sharjah M5 Building")
    print("=" * 60)
    if args.fast:
        print(f"Mode: FAST (no delays)")
        if args.throttle > 0:
            print(f"Throttle: {args.throttle}s between updates")
    else:
        print(f"Mode: Simulation ({args.speed}x speed)")
    print(f"Target: {ORION_URL}")
    if args.limit > 0:
        print(f"Limit: First {args.limit} events")
    print("=" * 60)
    print("\nPress Ctrl+C to stop\n")

    # Clean existing ML data CSV files
    clean_ml_data()
    print()

    # Load all events
    events = load_all_events()

    if not events:
        logging.error("No events loaded! Check CSV files.")
        sys.exit(1)

    # Apply limit if specified
    if args.limit > 0 and args.limit < len(events):
        print(f"Limiting to first {args.limit} events (out of {len(events)} total)\n")
        events = events[:args.limit]

    # Run simulation
    run_simulation(events, speed_factor=args.speed, fast_mode=args.fast, throttle=args.throttle)

    print("\nProducer stopped.")


if __name__ == "__main__":
    main()
