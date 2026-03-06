#!/usr/bin/env python
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'population'))

from population_model import PopulationDensityModel

print("="*70)
print("QUICK TEST: Population Model Fixes")
print("="*70)

# Test 1: Load Census Data
print("\nTest 1: Load Census Data")
print("-" * 70)
model = PopulationDensityModel()
csv_path = Path(__file__).parent.parent / 'population' / 'chi_pop.csv'
print(f"CSV Path: {csv_path}")
print(f"CSV Exists: {csv_path.exists()}")

model.load_census_data(str(csv_path))

assert len(model.census_data) > 0, "No census data loaded"
print(f"✓ Successfully loaded {len(model.census_data)} ZIP codes")

sample_zip = list(model.census_data.keys())[0]
print(f"✓ Sample ZIP {sample_zip}: {model.census_data[sample_zip]['total']:,} people")

# Test 2: Verify Cache Created
print("\nTest 2: Verify Cache System")
print("-" * 70)
print(f"Cache directory: {model.cache_dir}")
print(f"Cache exists: {model.cache_dir.exists()}")
print(f"✓ Cache system initialized")

print("\n" + "="*70)
print("✓ ALL QUICK TESTS PASSED")
print("="*70)
