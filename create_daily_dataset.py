#!/usr/bin/env python3
"""
Create Daily Aggregated Dataset from NGSI-LD ML Export
Converts property-based CSV files to daily aggregated dataset for ML analysis
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

ML_DATA_DIR = Path("ml_data")
OUTPUT_FILE = ML_DATA_DIR / "daily_unified_data.csv"


def parse_entity_id(entity_id: str) -> dict:
    """Parse NGSI-LD entity ID to extract type, room, and name

    Examples:
        urn:ngsi-ld:EnergyDevice:Kitchen:Fridge -> {type: EnergyDevice, room: Kitchen, name: Fridge}
        urn:ngsi-ld:Sensor:Lab_Temperature -> {type: Sensor, room: Lab, name: Temperature}
    """
    parts = entity_id.split(':')

    if len(parts) < 3:
        return {'type': 'Unknown', 'room': 'Unknown', 'name': 'Unknown'}

    entity_type = parts[2]  # EnergyDevice or Sensor

    if entity_type == 'EnergyDevice' and len(parts) == 5:
        # urn:ngsi-ld:EnergyDevice:Kitchen:Fridge
        # parts = ['urn', 'ngsi-ld', 'EnergyDevice', 'Kitchen', 'Fridge']
        room = parts[3]
        device = parts[4]
        return {'type': entity_type, 'room': room, 'name': device}

    elif entity_type == 'Sensor' and len(parts) == 4:
        # urn:ngsi-ld:Sensor:Lab_Temperature
        # parts = ['urn', 'ngsi-ld', 'Sensor', 'Lab_Temperature']
        sensor_name = parts[3]
        # Parse room from sensor name (Lab_Temperature -> Lab)
        room = sensor_name.split('_')[0]
        sensor_type = '_'.join(sensor_name.split('_')[1:])
        return {'type': entity_type, 'room': room, 'name': sensor_type}

    return {'type': entity_type, 'room': 'Unknown', 'name': 'Unknown'}


def load_and_aggregate_energy_data():
    """Load activePower data and aggregate to daily averages per device"""
    print("\n1. Processing Energy Device Data (activePower)")
    print("-" * 70)

    file_path = ML_DATA_DIR / "activePower_data.csv"

    if not file_path.exists():
        print(f"   ⚠️  File not found: {file_path}")
        return pd.DataFrame()

    df = pd.read_csv(file_path)
    print(f"   ✓ Loaded {len(df)} rows")

    # Parse entity IDs
    df['parsed'] = df['entity_id'].apply(parse_entity_id)
    df['device'] = df['parsed'].apply(lambda x: x['name'])
    df['room'] = df['parsed'].apply(lambda x: x['room'])

    # Remove duplicate header rows that got mixed into data
    df = df[df['observedAt'] != 'observedAt']

    # Convert activePower to numeric (was read as string due to mixed headers)
    df['activePower'] = pd.to_numeric(df['activePower'])

    # Convert timestamp to date
    df['observedAt'] = pd.to_datetime(df['observedAt'])
    df['date'] = df['observedAt'].dt.date

    # Remove duplicates (keep last notification for each timestamp)
    df = df.sort_values('observedAt').groupby(['entity_id', 'date']).last().reset_index()

    # Daily average power per device
    daily = df.groupby(['date', 'device'])['activePower'].mean().reset_index()

    # Pivot to wide format (each device as a column)
    wide = daily.pivot(index='date', columns='device', values='activePower')
    wide.columns = [f'{col}_power' for col in wide.columns]
    wide = wide.reset_index()

    print(f"   ✓ Aggregated to {len(wide)} days")
    print(f"   ✓ Devices: {', '.join([col.replace('_power', '') for col in wide.columns if col != 'date'])}")

    return wide


def load_and_aggregate_temperature():
    """Load temperature data and aggregate to daily averages per room"""
    print("\n2. Processing Temperature Data")
    print("-" * 70)

    file_path = ML_DATA_DIR / "temperature_data.csv"

    if not file_path.exists():
        print(f"   ⚠️  File not found: {file_path}")
        return pd.DataFrame()

    df = pd.read_csv(file_path)
    print(f"   ✓ Loaded {len(df)} rows")

    # Parse entity IDs to get room
    df['parsed'] = df['entity_id'].apply(parse_entity_id)
    df['room'] = df['parsed'].apply(lambda x: x['room'])

    # Remove duplicate header rows that got mixed into data
    df = df[df['observedAt'] != 'observedAt']

    # Convert temperature to numeric (was read as string due to mixed headers)
    df['temperature'] = pd.to_numeric(df['temperature'])

    # Convert timestamp to date
    df['observedAt'] = pd.to_datetime(df['observedAt'])
    df['date'] = df['observedAt'].dt.date

    # Remove duplicates
    df = df.sort_values('observedAt').groupby(['entity_id', 'date']).last().reset_index()

    # Daily average per room (pivot to wide format)
    daily = df.groupby(['date', 'room'])['temperature'].mean().reset_index()
    wide = daily.pivot(index='date', columns='room', values='temperature')
    wide.columns = [f'{col}_temperature' for col in wide.columns]
    wide = wide.reset_index()

    # Also add overall average
    wide['avg_temperature'] = df.groupby('date')['temperature'].mean().values

    print(f"   ✓ Aggregated to {len(wide)} days")
    print(f"   ✓ Rooms: {', '.join(df['room'].unique())}")

    return wide


def load_and_aggregate_humidity():
    """Load humidity data and aggregate to daily averages per room"""
    print("\n3. Processing Humidity Data")
    print("-" * 70)

    file_path = ML_DATA_DIR / "relativeHumidity_data.csv"

    if not file_path.exists():
        print(f"   ⚠️  File not found: {file_path}")
        return pd.DataFrame()

    df = pd.read_csv(file_path)
    print(f"   ✓ Loaded {len(df)} rows")

    # Parse entity IDs to get room
    df['parsed'] = df['entity_id'].apply(parse_entity_id)
    df['room'] = df['parsed'].apply(lambda x: x['room'])

    # Remove duplicate header rows that got mixed into data
    df = df[df['observedAt'] != 'observedAt']

    # Convert relativeHumidity to numeric (was read as string due to mixed headers)
    df['relativeHumidity'] = pd.to_numeric(df['relativeHumidity'])

    # Convert timestamp to date
    df['observedAt'] = pd.to_datetime(df['observedAt'])
    df['date'] = df['observedAt'].dt.date

    # Remove duplicates
    df = df.sort_values('observedAt').groupby(['entity_id', 'date']).last().reset_index()

    # Daily average per room (pivot to wide format)
    daily = df.groupby(['date', 'room'])['relativeHumidity'].mean().reset_index()
    wide = daily.pivot(index='date', columns='room', values='relativeHumidity')
    wide.columns = [f'{col}_humidity' for col in wide.columns]
    wide = wide.reset_index()

    # Also add overall average
    wide['avg_humidity'] = df.groupby('date')['relativeHumidity'].mean().values

    print(f"   ✓ Aggregated to {len(wide)} days")
    print(f"   ✓ Rooms: {', '.join(df['room'].unique())}")

    return wide


def load_and_aggregate_occupancy():
    """Load occupancy data and aggregate to daily averages per room"""
    print("\n4. Processing Occupancy Data")
    print("-" * 70)

    file_path = ML_DATA_DIR / "occupancy_data.csv"

    if not file_path.exists():
        print(f"   ⚠️  File not found: {file_path}")
        return pd.DataFrame()

    df = pd.read_csv(file_path)
    print(f"   ✓ Loaded {len(df)} rows")

    # Parse entity IDs to get room
    df['parsed'] = df['entity_id'].apply(parse_entity_id)
    df['room'] = df['parsed'].apply(lambda x: x['room'])

    # Remove duplicate header rows that got mixed into data
    df = df[df['observedAt'] != 'observedAt']

    # Convert occupancy to numeric (was read as string due to mixed headers)
    df['occupancy'] = pd.to_numeric(df['occupancy'])

    # Convert timestamp to date
    df['observedAt'] = pd.to_datetime(df['observedAt'])
    df['date'] = df['observedAt'].dt.date

    # Remove duplicates
    df = df.sort_values('observedAt').groupby(['entity_id', 'date']).last().reset_index()

    # Daily average per room (pivot to wide format)
    daily = df.groupby(['date', 'room'])['occupancy'].mean().reset_index()
    wide = daily.pivot(index='date', columns='room', values='occupancy')
    wide.columns = [f'{col}_occupancy' for col in wide.columns]
    wide = wide.reset_index()

    # Also add overall average
    wide['avg_occupancy'] = df.groupby('date')['occupancy'].mean().values

    print(f"   ✓ Aggregated to {len(wide)} days")
    print(f"   ✓ Rooms: {', '.join(df['room'].unique())}")

    return wide


def create_daily_unified_dataset():
    """Create unified daily aggregated dataset"""
    print("\n" + "=" * 70)
    print("Creating Daily Aggregated Dataset from NGSI-LD ML Export")
    print("=" * 70)

    # Load and aggregate all data sources
    df_energy = load_and_aggregate_energy_data()
    df_temp = load_and_aggregate_temperature()
    df_hum = load_and_aggregate_humidity()
    df_occ = load_and_aggregate_occupancy()

    # Merge all dataframes
    print("\n" + "=" * 70)
    print("Merging All Data Sources")
    print("=" * 70)

    if df_energy.empty:
        print("✗ No energy data available!")
        return None

    df_unified = df_energy.copy()

    if not df_temp.empty:
        df_unified = df_unified.merge(df_temp, on='date', how='outer')
        print("   ✓ Merged temperature data")

    if not df_hum.empty:
        df_unified = df_unified.merge(df_hum, on='date', how='outer')
        print("   ✓ Merged humidity data")

    if not df_occ.empty:
        df_unified = df_unified.merge(df_occ, on='date', how='outer')
        print("   ✓ Merged occupancy data")

    # Sort by date
    df_unified['date'] = pd.to_datetime(df_unified['date'])
    df_unified = df_unified.sort_values('date').reset_index(drop=True)

    # Add temporal features
    print("\n" + "=" * 70)
    print("Adding Temporal Features")
    print("=" * 70)

    df_unified['day_of_week'] = df_unified['date'].dt.dayofweek
    df_unified['day_name'] = df_unified['date'].dt.day_name()
    df_unified['is_weekend'] = (df_unified['day_of_week'] >= 5).astype(int)
    df_unified['month'] = df_unified['date'].dt.month
    df_unified['day_of_month'] = df_unified['date'].dt.day

    # Calculate total daily power consumption
    power_columns = [col for col in df_unified.columns if col.endswith('_power')]
    df_unified['total_power'] = df_unified[power_columns].sum(axis=1)

    print(f"   ✓ Added temporal features")
    print(f"   ✓ Calculated total_power from {len(power_columns)} devices")

    # Handle missing values
    print("\n" + "=" * 70)
    print("Handling Missing Values")
    print("=" * 70)

    missing_before = df_unified.isnull().sum().sum()
    print(f"   Missing values before: {missing_before}")

    # Strategy: Fill missing values with -1 (sentinel value for "no data")
    # -1 is meaningful: 0W = idle device, -1 = missing sensor data
    # ML models can learn to handle -1 as a special case
    df_unified = df_unified.fillna(-1)

    missing_after = df_unified.isnull().sum().sum()
    print(f"   Missing values after: {missing_after}")
    print(f"   Strategy: Filled NaN with -1 (sentinel for missing data)")
    print(f"   Note: 0 = idle/off, -1 = no data available")

    # Save dataset
    df_unified.to_csv(OUTPUT_FILE, index=False)

    # Print summary
    print("\n" + "=" * 70)
    print("Dataset Summary")
    print("=" * 70)
    print(f"\n✓ Total days: {len(df_unified)}")
    print(f"✓ Date range: {df_unified['date'].min().date()} to {df_unified['date'].max().date()}")
    print(f"✓ Total columns: {len(df_unified.columns)}")

    print(f"\nEnergy Devices ({len(power_columns)} devices):")
    for col in power_columns:
        device = col.replace('_power', '')
        avg = df_unified[col].mean()
        std = df_unified[col].std()
        print(f"  - {device:20s}: {avg:6.2f} ± {std:5.2f} W")

    print(f"\nEnvironmental Sensors:")

    # Temperature by room
    temp_columns = [col for col in df_unified.columns if col.endswith('_temperature') and col != 'avg_temperature']
    if temp_columns:
        print(f"  Temperature by room:")
        for col in sorted(temp_columns):
            room = col.replace('_temperature', '')
            avg = df_unified[col].mean()
            print(f"    - {room:15s}: {avg:6.2f}°C")
        if 'avg_temperature' in df_unified.columns:
            print(f"    - {'Average':15s}: {df_unified['avg_temperature'].mean():6.2f}°C")

    # Humidity by room
    humidity_columns = [col for col in df_unified.columns if col.endswith('_humidity') and col != 'avg_humidity']
    if humidity_columns:
        print(f"  Humidity by room:")
        for col in sorted(humidity_columns):
            room = col.replace('_humidity', '')
            avg = df_unified[col].mean()
            print(f"    - {room:15s}: {avg:6.2f}%")
        if 'avg_humidity' in df_unified.columns:
            print(f"    - {'Average':15s}: {df_unified['avg_humidity'].mean():6.2f}%")

    # Occupancy by room
    occupancy_columns = [col for col in df_unified.columns if col.endswith('_occupancy') and col != 'avg_occupancy']
    if occupancy_columns:
        print(f"  Occupancy by room:")
        for col in sorted(occupancy_columns):
            room = col.replace('_occupancy', '')
            avg = df_unified[col].mean()
            print(f"    - {room:15s}: {avg:6.2f}")
        if 'avg_occupancy' in df_unified.columns:
            print(f"    - {'Average':15s}: {df_unified['avg_occupancy'].mean():6.2f}")

    print(f"\nTotal Daily Power:")
    print(f"  - Mean: {df_unified['total_power'].mean():.2f} W")
    print(f"  - Std:  {df_unified['total_power'].std():.2f} W")
    print(f"  - Min:  {df_unified['total_power'].min():.2f} W")
    print(f"  - Max:  {df_unified['total_power'].max():.2f} W")

    print("\n" + "=" * 70)
    print(f"✓ Dataset saved: {OUTPUT_FILE}")
    print("=" * 70 + "\n")

    # Show sample
    print("Sample (first 5 days):")
    sample_cols = ['date', 'total_power', 'avg_temperature', 'avg_occupancy', 'day_name', 'is_weekend']
    sample_cols = [col for col in sample_cols if col in df_unified.columns]
    print(df_unified[sample_cols].head().to_string(index=False))

    return df_unified


if __name__ == "__main__":
    try:
        df = create_daily_unified_dataset()
        if df is not None:
            print("\n✓ Daily unified dataset ready for ML analysis!")
            print(f"  Use: {OUTPUT_FILE}")
        else:
            print("\n✗ Failed to create dataset (no data available)")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
