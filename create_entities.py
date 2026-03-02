#!/usr/bin/env python3
"""
NGSI-LD Entity Creator for University of Sharjah M5 Building
Creates hierarchical building model with energy devices and sensors
"""

import requests
import csv
import json
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
from datetime import datetime

# Configuration
ORION_URL = "http://localhost:1026/ngsi-ld/v1"
CONTEXT = "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"
BASE_DIR = Path(__file__).parent
DATASET_DIR = BASE_DIR / "Dataset-of-IoT-Based-Energy"

# Energy Devices Configuration
ENERGY_DEVICES_CONFIG = {
    'CoffeeMachine': {
        'room': 'Kitchen',
        'name': 'Coffee Machine',
        'category': 'Appliance',
        'csv_files': {
            'watt': 'Watt W/2024-06-21-16-57 Chronograf Data Coffee Machine.csv',
            'kwh': 'KWh/Today/2024-06-21-16-50 Chronograf Data Coffee Machine.csv',
            'va': 'Apperent power VA/2024-06-21-17-01 Chronograf Data Coffee Machine.csv',
        }
    },
    'Fridge': {
        'room': 'Kitchen',
        'name': 'Fridge',
        'category': 'Appliance',
        'csv_files': {
            'watt': 'Watt W/2024-06-21-17-00 Chronograf Data Fridge.csv',
            'kwh': 'KWh/Today/2024-06-21-16-51 Chronograf Data Fridge.csv',
            'va': 'Apperent power VA/2024-06-21-17-02 Chronograf Data Fridge.csv',
        }
    },
    'Kettle': {
        'room': 'Kitchen',
        'name': 'Kettle',
        'category': 'Appliance',
        'csv_files': {
            'watt': 'Watt W/2024-06-21-17-00 Chronograf Data Kettle.csv',
            'kwh': 'KWh/Today/2024-06-21-16-51 Chronograf Data Kettle.csv',
            'va': 'Apperent power VA/2024-06-21-17-02 Chronograf Data Kettle.csv',
        }
    },
    'Microwave': {
        'room': 'Kitchen',
        'name': 'Microwave',
        'category': 'Appliance',
        'csv_files': {
            'watt': 'Watt W/2024-06-21-16-58 Chronograf Data Microwave.csv',
            'kwh': 'KWh/Today/2024-06-21-16-51 Chronograf Data Microwave.csv',
            'va': 'Apperent power VA/2024-06-21-17-02 Chronograf Data Microwave.csv',
        }
    },
    'Desktop': {
        'room': 'Lab',
        'name': 'Desktop Computer',
        'category': 'Electronics',
        'csv_files': {
            'watt': 'Watt W/2024-06-21-17-00 Chronograf Data Desktop.csv',
            'kwh': 'KWh/Today/2024-06-21-16-52 Chronograf Data Desktop.csv',
            'va': 'Apperent power VA/2024-06-21-17-02 Chronograf Data Desktop.csv',
        }
    },
    'Printer': {
        'room': 'Lab',
        'name': 'Printer',
        'category': 'Electronics',
        'csv_files': {
            'watt': 'Watt W/2024-06-21-16-58 Chronograf Data Printer.csv',
            'kwh': 'KWh/Today/2024-06-21-16-51 Chronograf Data Printer.csv',
            'va': 'Apperent power VA/2024-06-21-17-02 Chronograf Data Printer.csv',
        }
    },
    'WaterDispenser': {
        'room': 'Mailroom',
        'name': 'Water Dispenser',
        'category': 'Appliance',
        'csv_files': {
            'watt': 'Watt W/2024-06-21-17-00 Chronograf Data Water Dispenser.csv',
            'kwh': 'KWh/Today/2024-06-21-16-52 Chronograf Data Water Dispenser.csv',
            'va': 'Apperent power VA/2024-06-21-17-02 Chronograf Data Water Dispenser.csv',
        }
    }
}

# Sensor Configuration
SENSOR_CONFIG = {
    'Lab_Temperature': {
        'room': 'Lab',
        'name': 'Lab Temperature Sensor',
        'sensor_type': 'Temperature',
        'attribute': 'temperature',
        'csv': 'Temperature/2024-06-21-16-31 Chronograf Data Lab.csv',
        'column': '°C.mean_value',
        'unit_code': 'CEL'
    },
    'Lab_Humidity': {
        'room': 'Lab',
        'name': 'Lab Humidity Sensor',
        'sensor_type': 'Humidity',
        'attribute': 'relativeHumidity',
        'csv': 'Humidity/2024-06-21-16-44 Chronograf Data Lab.csv',
        'column': '%.mean_value',
        'unit_code': 'P1'
    },
    'Lab_Motion': {
        'room': 'Lab',
        'name': 'Lab Motion Sensor',
        'sensor_type': 'Motion',
        'attribute': 'occupancy',
        'csv': 'Motion/2024-06-21-16-35 Chronograf Data Lab Motion.csv',
        'column': 'state.mean_value',
        'unit_code': None
    },
    'Lab_Door': {
        'room': 'Lab',
        'name': 'Lab Door Sensor',
        'sensor_type': 'Door',
        'attribute': 'doorState',
        'csv': 'Motion/2024-06-21-16-36 Chronograf Data Lab Open colsed door.csv',
        'column': 'state.mean_value',
        'unit_code': None
    },
    'Kitchen_Temperature': {
        'room': 'Kitchen',
        'name': 'Kitchen Temperature Sensor',
        'sensor_type': 'Temperature',
        'attribute': 'temperature',
        'csv': 'Temperature/2024-06-21-16-31 Kitchen.csv',
        'column': '°C.mean_value',
        'unit_code': 'CEL'
    },
    'Kitchen_Humidity': {
        'room': 'Kitchen',
        'name': 'Kitchen Humidity Sensor',
        'sensor_type': 'Humidity',
        'attribute': 'relativeHumidity',
        'csv': 'Humidity/2024-06-21-16-45 Chronograf Data Kitchen.csv',
        'column': '%.mean_value',
        'unit_code': 'P1'
    },
    'Kitchen_Motion': {
        'room': 'Kitchen',
        'name': 'Kitchen Motion Sensor',
        'sensor_type': 'Motion',
        'attribute': 'occupancy',
        'csv': 'Motion/2024-06-21-16-39 Chronograf Data Kitchen.csv',
        'column': 'state.mean_value',
        'unit_code': None
    },
    'Mailroom_Temperature': {
        'room': 'Mailroom',
        'name': 'Mailroom Temperature Sensor',
        'sensor_type': 'Temperature',
        'attribute': 'temperature',
        'csv': 'Temperature/2024-06-21-16-32 Chronograf Data Mailroom.csv',
        'column': '°C.mean_value',
        'unit_code': 'CEL'
    },
    'Mailroom_Humidity': {
        'room': 'Mailroom',
        'name': 'Mailroom Humidity Sensor',
        'sensor_type': 'Humidity',
        'attribute': 'relativeHumidity',
        'csv': 'Humidity/2024-06-21-16-43 Chronograf Data Mailroom.csv',
        'column': '%.mean_value',
        'unit_code': 'P1'
    },
    'Mailroom_Motion': {
        'room': 'Mailroom',
        'name': 'Mailroom Motion Sensor',
        'sensor_type': 'Motion',
        'attribute': 'occupancy',
        'csv': 'Motion/2024-06-21-16-39 Chronograf Data Mailroom.csv',
        'column': 'state.mean_value',
        'unit_code': None
    }
}


def setup_logging(verbose: bool) -> logging.Logger:
    """Configure logging with appropriate level and format"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


def read_first_valid_csv_value(csv_path: Path, value_column: str) -> Tuple[Optional[float], Optional[str]]:
    """Read first non-empty value from CSV file"""
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                value_str = row.get(value_column, '').strip()
                timestamp_str = row.get('time', '').strip()

                if value_str and timestamp_str:
                    try:
                        value = float(value_str)
                        # Validate ISO8601 timestamp format
                        datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        return value, timestamp_str
                    except (ValueError, TypeError):
                        continue
        return None, None
    except Exception as e:
        logging.error(f"Error reading CSV {csv_path}: {e}")
        return None, None


def create_entity(entity: Dict[str, Any], entity_id: str) -> bool:
    """Create entity in Orion-LD context broker"""
    url = f"{ORION_URL}/entities/"
    headers = {"Content-Type": "application/ld+json"}

    try:
        response = requests.post(url, json=entity, headers=headers, timeout=10)

        if response.status_code == 201:
            logging.info(f"✓ Created: {entity_id}")
            return True
        elif response.status_code == 409:
            logging.warning(f"⚠ Already exists: {entity_id}")
            return True
        else:
            logging.error(f"✗ Failed to create {entity_id}: {response.status_code} - {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logging.error(f"✗ Connection error creating {entity_id}: {e}")
        return False


def delete_entity(entity_id: str) -> bool:
    """DELETE entity from Orion-LD"""
    url = f"{ORION_URL}/entities/{entity_id}"

    try:
        response = requests.delete(url, timeout=10)

        if response.status_code == 204:
            logging.debug(f"✓ Deleted: {entity_id}")
            return True
        elif response.status_code == 404:
            logging.debug(f"⚠ Not found (already deleted): {entity_id}")
            return True
        else:
            logging.error(f"✗ Failed to delete {entity_id}: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        logging.error(f"✗ Connection error deleting {entity_id}: {e}")
        return False


def entity_exists(entity_id: str) -> bool:
    """Check if entity exists in Orion-LD"""
    url = f"{ORION_URL}/entities/{entity_id}"

    try:
        response = requests.get(url, timeout=10)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def get_entity(entity_id: str) -> Optional[Dict[str, Any]]:
    """Get entity from Orion-LD"""
    url = f"{ORION_URL}/entities/{entity_id}"
    headers = {"Accept": "application/ld+json"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def clean_all_entities() -> bool:
    """Delete ALL entities from Orion-LD (not just our entities)"""
    logging.info("Cleaning existing entities...")

    try:
        # Query all entity types
        all_types = ['Building', 'Floor', 'Room', 'EnergyDevice', 'Sensor']
        deleted_count = 0

        for entity_type in all_types:
            url = f"{ORION_URL}/entities/?type={entity_type}"
            headers = {"Accept": "application/ld+json"}

            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                entities = response.json()
                for entity in entities:
                    entity_id = entity.get('id')
                    if entity_id:
                        delete_entity(entity_id)
                        deleted_count += 1

        logging.info(f"✓ Cleanup completed (deleted {deleted_count} entities)")
        return True

    except requests.exceptions.RequestException as e:
        logging.error(f"✗ Cleanup failed: {e}")
        return False


def create_building() -> bool:
    """Create Building:M5Building entity"""
    entity = {
        "id": "urn:ngsi-ld:Building:M5Building",
        "type": "Building",
        "name": {
            "type": "Property",
            "value": "University of Sharjah - M5 Building"
        },
        "address": {
            "type": "Property",
            "value": "University City, Sharjah, UAE"
        },
        "description": {
            "type": "Property",
            "value": "M5 Building - Interdisciplinary Research and IoT Lab"
        },
        "@context": [CONTEXT]
    }

    return create_entity(entity, entity['id'])


def create_floor() -> bool:
    """Create Floor:M5Floor entity with refBuilding relationship"""
    entity = {
        "id": "urn:ngsi-ld:Floor:M5Floor",
        "type": "Floor",
        "level": {
            "type": "Property",
            "value": 1
        },
        "name": {
            "type": "Property",
            "value": "M5 Main Floor"
        },
        "refBuilding": {
            "type": "Relationship",
            "object": "urn:ngsi-ld:Building:M5Building"
        },
        "@context": [CONTEXT]
    }

    return create_entity(entity, entity['id'])


def create_rooms() -> bool:
    """Create 3 Room entities (Lab, Kitchen, Mailroom)"""
    rooms = {
        'Lab': {
            'name': 'Interdisciplinary Lab',
            'description': 'Research laboratory space'
        },
        'Kitchen': {
            'name': 'Kitchen',
            'description': 'Staff kitchen and break area'
        },
        'Mailroom': {
            'name': 'Mailroom',
            'description': 'Mail and package handling area'
        }
    }

    success = True
    for room_id, room_data in rooms.items():
        entity = {
            "id": f"urn:ngsi-ld:Room:{room_id}",
            "type": "Room",
            "name": {
                "type": "Property",
                "value": room_data['name']
            },
            "description": {
                "type": "Property",
                "value": room_data['description']
            },
            "refFloor": {
                "type": "Relationship",
                "object": "urn:ngsi-ld:Floor:M5Floor"
            },
            "@context": [CONTEXT]
        }

        if not create_entity(entity, entity['id']):
            success = False

    return success


def create_energy_devices() -> Dict[str, int]:
    """Create 7 EnergyDevice entities with initial sensor readings"""
    stats = {'created': 0, 'failed': 0, 'missing_data': 0}

    for device_id, config in ENERGY_DEVICES_CONFIG.items():
        # Read initial values from CSVs
        watt_csv = DATASET_DIR / config['csv_files']['watt']
        kwh_csv = DATASET_DIR / config['csv_files']['kwh']
        va_csv = DATASET_DIR / config['csv_files']['va']

        watt_value, watt_time = read_first_valid_csv_value(watt_csv, 'W.mean_value')
        kwh_value, kwh_time = read_first_valid_csv_value(kwh_csv, 'kWh.mean_value')
        va_value, va_time = read_first_valid_csv_value(va_csv, 'VA.mean_value')

        # Handle missing data
        if watt_value is None:
            watt_value = 0.0
            watt_time = datetime.utcnow().isoformat() + 'Z'
            stats['missing_data'] += 1

        if kwh_value is None:
            kwh_value = 0.0
            kwh_time = datetime.utcnow().isoformat() + 'Z'
            stats['missing_data'] += 1

        if va_value is None:
            va_value = 0.0
            va_time = datetime.utcnow().isoformat() + 'Z'
            stats['missing_data'] += 1

        # Create entity
        entity = {
            "id": f"urn:ngsi-ld:EnergyDevice:{config['room']}:{device_id}",
            "type": "EnergyDevice",
            "name": {
                "type": "Property",
                "value": config['name']
            },
            "deviceCategory": {
                "type": "Property",
                "value": config['category']
            },
            "activePower": {
                "type": "Property",
                "value": watt_value,
                "unitCode": "WTT",
                "observedAt": watt_time
            },
            "dailyEnergyConsumed": {
                "type": "Property",
                "value": kwh_value,
                "unitCode": "KWH",
                "observedAt": kwh_time
            },
            "apparentPower": {
                "type": "Property",
                "value": va_value,
                "unitCode": "VA",
                "observedAt": va_time
            },
            "refRoom": {
                "type": "Relationship",
                "object": f"urn:ngsi-ld:Room:{config['room']}"
            },
            "@context": [CONTEXT]
        }

        if create_entity(entity, entity['id']):
            stats['created'] += 1
            logging.debug(f"  → {config['name']}: W={watt_value:.2f}, KWh={kwh_value:.2f}, VA={va_value:.2f}")
        else:
            stats['failed'] += 1

    return stats


def create_sensors() -> Dict[str, int]:
    """Create 10 environmental sensors"""
    stats = {'created': 0, 'failed': 0, 'missing_data': 0}

    for sensor_id, config in SENSOR_CONFIG.items():
        # Read initial value from CSV
        csv_path = DATASET_DIR / config['csv']
        value, timestamp = read_first_valid_csv_value(csv_path, config['column'])

        # Handle missing data
        if value is None:
            value = 0.0
            timestamp = datetime.utcnow().isoformat() + 'Z'
            stats['missing_data'] += 1

        # Create entity
        entity = {
            "id": f"urn:ngsi-ld:Sensor:{sensor_id}",
            "type": "Sensor",
            "name": {
                "type": "Property",
                "value": config['name']
            },
            "sensorType": {
                "type": "Property",
                "value": config['sensor_type']
            },
            config['attribute']: {
                "type": "Property",
                "value": value,
                "observedAt": timestamp
            },
            "refRoom": {
                "type": "Relationship",
                "object": f"urn:ngsi-ld:Room:{config['room']}"
            },
            "@context": [CONTEXT]
        }

        # Add unitCode if specified
        if config['unit_code']:
            entity[config['attribute']]['unitCode'] = config['unit_code']

        if create_entity(entity, entity['id']):
            stats['created'] += 1
            unit = f" {config['unit_code']}" if config['unit_code'] else ""
            logging.debug(f"  → {config['name']}: {value:.2f}{unit}")
        else:
            stats['failed'] += 1

    return stats


def verify_relationships() -> bool:
    """Verify all relationships are valid"""
    checks = [
        # (entity_id, relationship_attribute, expected_target)
        ("urn:ngsi-ld:Floor:M5Floor", "refBuilding", "urn:ngsi-ld:Building:M5Building"),
        ("urn:ngsi-ld:Room:Lab", "refFloor", "urn:ngsi-ld:Floor:M5Floor"),
        ("urn:ngsi-ld:Room:Kitchen", "refFloor", "urn:ngsi-ld:Floor:M5Floor"),
        ("urn:ngsi-ld:Room:Mailroom", "refFloor", "urn:ngsi-ld:Floor:M5Floor"),
    ]

    # Add energy devices
    for device_id, config in ENERGY_DEVICES_CONFIG.items():
        checks.append((
            f"urn:ngsi-ld:EnergyDevice:{config['room']}:{device_id}",
            "refRoom",
            f"urn:ngsi-ld:Room:{config['room']}"
        ))

    # Add sensors
    for sensor_id, config in SENSOR_CONFIG.items():
        checks.append((
            f"urn:ngsi-ld:Sensor:{sensor_id}",
            "refRoom",
            f"urn:ngsi-ld:Room:{config['room']}"
        ))

    all_valid = True
    for entity_id, rel_attr, target in checks:
        # 1. Check entity exists
        if not entity_exists(entity_id):
            logging.error(f"✗ Entity not found: {entity_id}")
            all_valid = False
            continue

        # 2. Get entity and check relationship
        entity = get_entity(entity_id)
        if not entity:
            logging.error(f"✗ Could not retrieve entity: {entity_id}")
            all_valid = False
            continue

        if rel_attr not in entity:
            logging.error(f"✗ Relationship {rel_attr} missing in {entity_id}")
            all_valid = False
            continue

        # 3. Check target exists
        actual_target = entity[rel_attr].get('object')
        if actual_target != target:
            logging.error(f"✗ Relationship mismatch: {entity_id}.{rel_attr} -> {actual_target} (expected {target})")
            all_valid = False
            continue

        if not entity_exists(target):
            logging.error(f"✗ Target entity not found: {target}")
            all_valid = False
            continue

        logging.debug(f"✓ Valid: {entity_id}.{rel_attr} -> {target}")

    return all_valid


def main():
    """Main orchestration function"""
    parser = argparse.ArgumentParser(
        description='Create NGSI-LD entities for University of Sharjah M5 Building'
    )
    parser.add_argument('--skip-clean', action='store_true',
                        help='Skip deleting existing entities (default: always clean)')
    parser.add_argument('--verify', action='store_true',
                        help='Verify all relationships after creation')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose logging')

    args = parser.parse_args()
    logger = setup_logging(args.verbose)

    logger.info("=" * 60)
    logger.info("NGSI-LD Entity Creator - University of Sharjah M5 Building")
    logger.info("=" * 60)

    # Step 1: Clean existing entities (default behavior, unless --skip-clean)
    if not args.skip_clean:
        logger.info("\n[1/6] Cleaning existing entities...")
        if not clean_all_entities():
            logger.error("Failed to clean entities")
            sys.exit(1)
    else:
        logger.info("\n[1/6] Skipping cleanup (existing entities will cause warnings)...")

    # Step 2: Create Building
    logger.info("\n[2/6] Creating Building entity...")
    if not create_building():
        logger.error("Failed to create building")
        sys.exit(1)

    # Step 3: Create Floor
    logger.info("\n[3/6] Creating Floor entity...")
    if not create_floor():
        logger.error("Failed to create floor")
        sys.exit(1)

    # Step 4: Create Rooms
    logger.info("\n[4/6] Creating Room entities...")
    if not create_rooms():
        logger.error("Failed to create rooms")
        sys.exit(1)

    # Step 5: Create Energy Devices
    logger.info("\n[5/6] Creating Energy Device entities...")
    device_stats = create_energy_devices()
    logger.info(f"Devices - Created: {device_stats['created']}, "
                f"Failed: {device_stats['failed']}, "
                f"Missing Data: {device_stats['missing_data']}")

    # Step 6: Create Sensors
    logger.info("\n[6/6] Creating Sensor entities...")
    sensor_stats = create_sensors()
    logger.info(f"Sensors - Created: {sensor_stats['created']}, "
                f"Failed: {sensor_stats['failed']}, "
                f"Missing Data: {sensor_stats['missing_data']}")

    # Step 7: Verify if requested
    if args.verify:
        logger.info("\n[Verification] Checking relationships...")
        if verify_relationships():
            logger.info("✓ All relationships verified successfully")
        else:
            logger.error("✗ Relationship verification failed")
            sys.exit(1)

    # Summary
    total_created = device_stats['created'] + sensor_stats['created'] + 5  # +5 for Building, Floor, 3 Rooms
    logger.info("\n" + "=" * 60)
    logger.info(f"✓ Entity creation completed successfully!")
    logger.info(f"Total Entities: {total_created} (1 Building + 1 Floor + 3 Rooms + {device_stats['created']} Devices + {sensor_stats['created']} Sensors)")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
