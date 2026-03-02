#!/usr/bin/env python
"""Train and test the ML-based population model"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from population_ml_model import PopulationMLModel, create_sample_training_data
except ImportError:
    print("[ERROR] sklearn not installed. Install with: pip install scikit-learn")
    sys.exit(1)

from population_model import PopulationDensityModel

print("=" * 80)
print("NEURAL NETWORK ML MODEL - TRAINING & TESTING")
print("=" * 80)

# Step 1: Train the ML model
print("\nStep 1: Training Neural Network Model")
print("-" * 80)

ml_model = PopulationMLModel()

if ml_model.model is None:
    print("Creating and training new ML model...")
    training_data = create_sample_training_data()
    ml_model.train(training_data)
else:
    print("Model already trained. Skipping training step.")

# Step 2: Test with formula-based model
print("\n\n" + "=" * 80)
print("Step 2: Comparison - Formula vs ML Model")
print("=" * 80)

model_formula = PopulationDensityModel(chi_factor=1.0, use_ml=False)
model_ml = PopulationDensityModel(chi_factor=1.0, use_ml=True)

csv_path = Path(__file__).parent / 'chi_pop.csv'
model_formula.load_census_data(str(csv_path))
model_ml.load_census_data(str(csv_path))

# Test location: Lincoln Park, Chicago
print("\nTest Location: Lincoln Park, Chicago (41.9212, -87.6567)")
print("-" * 80)

lat, lon = 41.9212, -87.6567

print("\n[Formula-Based Estimation]")
result_formula = model_formula.estimate_for_location(lat, lon, radius_meters=1000)

print("\n\n[Neural Network ML Estimation]")
result_ml = model_ml.estimate_for_location(lat, lon, radius_meters=1000)

# Compare results
if result_formula and result_ml:
    print("\n" + "=" * 80)
    print("COMPARISON RESULTS")
    print("=" * 80)
    
    print(f"\nLocation: ({lat}, {lon})")
    print(f"ZIP Code: {result_formula['zipcode']}")
    print(f"Total Buildings: {result_formula['total_buildings']}")
    print(f"Search Area: {result_formula['area_km2']:.2f} km²")
    
    print(f"\n{'Method':<25} {'Population':<15} {'Density':<15} {'Error %':<10}")
    print("-" * 80)
    
    if 'actual_population' in result_formula:
        print(f"{'Formula-Based':<25} {result_formula['total_population']:<15,} "
              f"{result_formula['density']:<15.2f} {result_formula.get('percent_error', 'N/A'):<10}")
        
        print(f"{'Neural Network ML':<25} {result_ml['total_population']:<15,} "
              f"{result_ml['density']:<15.2f} {result_ml.get('percent_error', 'N/A'):<10}")
        
        print(f"{'Census Data':<25} {result_formula['actual_population']:<15,}")
        
        print("\n[Accuracy Analysis]")
        formula_error = result_formula.get('percent_error', 0)
        ml_error = result_ml.get('percent_error', 0)
        improvement = formula_error - ml_error
        
        print(f"  Formula-Based Error: {formula_error:.2f}%")
        print(f"  ML Model Error: {ml_error:.2f}%")
        print(f"  Improvement: {improvement:+.2f}% {'(Better)' if improvement > 0 else '(Worse)'}")
    else:
        print(f"{'Formula-Based':<25} {result_formula['total_population']:<15,} "
              f"{result_formula['density']:<15.2f}")
        print(f"{'Neural Network ML':<25} {result_ml['total_population']:<15,} "
              f"{result_ml['density']:<15.2f}")

print("\n" + "=" * 80)
print("Testing complete!")
print("=" * 80 + "\n")
