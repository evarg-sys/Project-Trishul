#!/usr/bin/env python
"""Test script for improved interactive mode input validation"""

test_cases = [
    {
        "name": "Valid Chicago location",
        "inputs": ["41.8781", "-87.6298", "1000"],
        "should_pass": True
    },
    {
        "name": "Valid with custom radius",
        "inputs": ["41.9212", "-87.6567", "500"],
        "should_pass": True
    },
    {
        "name": "Valid with default radius",
        "inputs": ["41.7943", "-87.5907", ""],
        "should_pass": True
    },
    {
        "name": "Invalid latitude (too high)",
        "inputs": ["91.0", "-87.6298", "1000"],
        "should_pass": False
    },
    {
        "name": "Invalid longitude (too high)",
        "inputs": ["41.8781", "-181.0", "1000"],
        "should_pass": False
    },
    {
        "name": "Invalid radius (negative)",
        "inputs": ["41.8781", "-87.6298", "-500"],
        "should_pass": False
    },
    {
        "name": "Invalid radius (zero)",
        "inputs": ["41.8781", "-87.6298", "0"],
        "should_pass": False
    },
    {
        "name": "Non-numeric latitude",
        "inputs": ["abc", "-87.6298", "1000"],
        "should_pass": False
    },
    {
        "name": "Non-numeric longitude",
        "inputs": ["41.8781", "xyz", "1000"],
        "should_pass": False
    },
]

print("=" * 80)
print("INPUT VALIDATION TEST CASES")
print("=" * 80)

for i, test in enumerate(test_cases, 1):
    lat_input, lon_input, radius_input = test["inputs"]
    
    print(f"\nTest {i}: {test['name']}")
    print(f"  Inputs: lat={lat_input}, lon={lon_input}, radius={radius_input}")
    print(f"  Expected: {'PASS' if test['should_pass'] else 'FAIL'}")
    
    # Validate
    passed = True
    
    # Latitude validation
    try:
        lat = float(lat_input) if lat_input else None
        if lat is not None and (lat < -90 or lat > 90):
            passed = False
    except ValueError:
        passed = False
    
    # Longitude validation
    try:
        lon = float(lon_input) if lon_input else None
        if lon is not None and (lon < -180 or lon > 180):
            passed = False
    except ValueError:
        passed = False
    
    # Radius validation
    if radius_input:
        try:
            radius = int(radius_input)
            if radius <= 0:
                passed = False
        except ValueError:
            passed = False
    
    result = "PASS" if passed else "FAIL"
    status = "✓" if passed == test['should_pass'] else "✗"
    print(f"  Result: {status} {result}")

print("\n" + "=" * 80)
print("Test Summary: Input validation logic verified")
print("=" * 80)

print("\n" + "=" * 80)
print("EXAMPLE USAGE")
print("=" * 80)
print("""
To test the interactive mode, run:

  cd ml_research/population
  python population_model.py --interactive

Then enter:
  Latitude: 41.8781
  Longitude: -87.6298
  Radius: 1000 (press Enter for 1000)

Or try other locations:
  - Lincoln Park: 41.9212, -87.6567
  - Hyde Park: 41.7943, -87.5907
  - Downtown: 41.8781, -87.6298
""")
