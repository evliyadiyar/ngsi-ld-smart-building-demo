#!/usr/bin/env python3
"""
Remove Outliers from Daily Unified Dataset
Applies ±3 standard deviation method to clean extreme values
"""

import pandas as pd
import numpy as np
from pathlib import Path

INPUT_FILE = Path("ml_data/daily_unified_data.csv")
OUTPUT_FILE = Path("ml_data/daily_unified_data_clean.csv")

def remove_outliers():
    """Apply ±3 std outlier removal to power columns"""
    print("\n" + "="*70)
    print("OUTLIER REMOVAL - ±3 Standard Deviation Method")
    print("="*70 + "\n")

    # Load data
    df = pd.read_csv(INPUT_FILE)
    df['date'] = pd.to_datetime(df['date'])

    print(f"Original dataset: {len(df)} days")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")

    # Get power columns (including total_power)
    power_cols = [col for col in df.columns if col.endswith('_power')]

    print(f"\nAnalyzing {len(power_cols)} power columns for outliers...")
    print("="*70)

    # Track statistics
    outlier_stats = {}

    # Create mask to track rows to keep (start with all True)
    rows_to_keep = pd.Series([True] * len(df), index=df.index)

    for col in power_cols:
        print(f"\n{col}:")

        # Calculate statistics
        mean = df[col].mean()
        std = df[col].std()
        lower_bound = mean - 3 * std
        upper_bound = mean + 3 * std

        # Find outliers
        outliers = (df[col] < lower_bound) | (df[col] > upper_bound)
        n_outliers = outliers.sum()

        print(f"  Mean: {mean:.2f} W")
        print(f"  Std:  {std:.2f} W")
        print(f"  Range: [{lower_bound:.2f}, {upper_bound:.2f}] W")
        print(f"  Outliers detected: {n_outliers} values ({n_outliers/len(df)*100:.1f}%)")

        if n_outliers > 0:
            # Show outlier values
            outlier_values = df.loc[outliers, [col, 'date']]
            print(f"  Outlier dates:")
            for idx, row in outlier_values.iterrows():
                print(f"    {row['date'].date()}: {row[col]:.2f} W")

            # Mark rows with outliers for removal
            rows_to_keep = rows_to_keep & ~outliers

            print(f"  ✓ Marked {n_outliers} rows for removal")
        else:
            print(f"  ✓ No outliers")

        outlier_stats[col] = {
            'mean': mean,
            'std': std,
            'lower_bound': lower_bound,
            'upper_bound': upper_bound,
            'n_outliers': n_outliers,
            'outlier_pct': n_outliers/len(df)*100
        }

    # Remove all rows that have any outlier
    print("\n" + "="*70)
    print("Removing rows with outliers...")
    print("="*70)

    rows_removed = (~rows_to_keep).sum()
    df_clean = df[rows_to_keep].copy()

    print(f"  Original rows: {len(df)}")
    print(f"  Rows with outliers: {rows_removed}")
    print(f"  Rows remaining: {len(df_clean)}")
    print(f"  Data loss: {rows_removed/len(df)*100:.1f}%")

    # Recalculate total_power (in case it was affected)
    device_power_cols = [col for col in power_cols if col != 'total_power']
    df_clean['total_power'] = df_clean[device_power_cols].sum(axis=1)

    print(f"\n✓ Total power recalculated from {len(device_power_cols)} devices")

    # Compare before/after
    print("\n" + "="*70)
    print("BEFORE vs AFTER COMPARISON")
    print("="*70)

    comparison = []
    for col in power_cols:
        before_mean = df[col].mean()
        after_mean = df_clean[col].mean()
        before_std = df[col].std()
        after_std = df_clean[col].std()
        before_max = df[col].max()
        after_max = df_clean[col].max()

        comparison.append({
            'column': col.replace('_power', ''),
            'before_mean': before_mean,
            'after_mean': after_mean,
            'before_std': before_std,
            'after_std': after_std,
            'before_max': before_max,
            'after_max': after_max,
            'std_reduction_pct': (before_std - after_std) / before_std * 100
        })

    df_comparison = pd.DataFrame(comparison)

    print(f"\n{'Device':<20} {'Mean Before':<15} {'Mean After':<15} {'Std Before':<15} {'Std After':<15} {'Std Reduction':<15}")
    print("-" * 100)
    for _, row in df_comparison.iterrows():
        print(f"{row['column']:<20} "
              f"{row['before_mean']:>12.2f} W "
              f"{row['after_mean']:>12.2f} W "
              f"{row['before_std']:>12.2f} W "
              f"{row['after_std']:>12.2f} W "
              f"{row['std_reduction_pct']:>12.1f}%")

    # Save cleaned dataset
    print("\n" + "="*70)
    print("SAVING CLEANED DATASET")
    print("="*70)

    df_clean.to_csv(OUTPUT_FILE, index=False)

    print(f"\n✓ Cleaned dataset saved: {OUTPUT_FILE}")
    print(f"  Rows: {len(df_clean)} (unchanged)")
    print(f"  Columns: {len(df_clean.columns)}")

    # Summary statistics
    print("\n" + "="*70)
    print("OUTLIER SUMMARY")
    print("="*70)

    total_outliers = sum(s['n_outliers'] for s in outlier_stats.values())
    total_values = len(df) * len(power_cols)

    print(f"\nTotal outliers detected: {total_outliers} / {total_values} values ({total_outliers/total_values*100:.2f}%)")
    print(f"Method: Row Removal (±3σ outlier detection)")
    print(f"Rows removed: {rows_removed} / {len(df)} ({rows_removed/len(df)*100:.1f}%)")
    print(f"\nDevices with most outliers:")

    sorted_stats = sorted(outlier_stats.items(), key=lambda x: x[1]['n_outliers'], reverse=True)
    for col, stats in sorted_stats[:5]:
        if stats['n_outliers'] > 0:
            print(f"  {col.replace('_power', '')}: {stats['n_outliers']} outliers ({stats['outlier_pct']:.1f}%)")

    print("\n" + "="*70)
    print("✓ Outlier removal complete!")
    print("="*70)
    print(f"\nOriginal file: {INPUT_FILE}")
    print(f"Cleaned file:  {OUTPUT_FILE}")
    print("\nNext: Re-run ML analyses with cleaned data")
    print("="*70 + "\n")

    return df_clean, outlier_stats


if __name__ == "__main__":
    try:
        df_clean, stats = remove_outliers()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
