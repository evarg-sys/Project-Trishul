#!/usr/bin/env python
"""Test backend population model"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path.cwd() / 'backend'))

from api.ml.population_model import PopulationDensityModel

print("Testing Backend Population Model")
print("=" * 70)

try:
    model = PopulationDensityModel()
    model.load_census_data('chi_pop.csv')
    
    assert len(model.census_data) == 59, f"Expected 59 ZIPs, got {len(model.census_data)}"
    print(f"✓ Loaded {len(model.census_data)} ZIP codes from backend")
    
    sample_zip = '60601'
    pop = model.census_data[sample_zip]['total']
    print(f"✓ Sample: ZIP {sample_zip} = {pop:,} people")
    
    # Test calculation
    result = model.estimate_population(2.0, {'residential': 100})
    print(f"✓ Estimation: {result['total_population']} people estimated")
    
    print("\n✅ BACKEND MODEL WORKS PROPERLY!")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
