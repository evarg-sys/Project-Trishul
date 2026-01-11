from population_model import PopulationDensityModel

def test_load_census_data():
    print("="*70)
    print("TEST 1: Load Census Data")
    print("="*70)
    
    model = PopulationDensityModel()
    model.load_census_data('chi_pop.csv')
    
    assert len(model.census_data) > 0, "No census data loaded"
    print(f"✓ Successfully loaded {len(model.census_data)} ZIP codes")
    
    sample_zip = list(model.census_data.keys())[0]
    print(f"✓ Sample ZIP {sample_zip}: {model.census_data[sample_zip]['total']:,} people")
    print()

def test_downtown_chicago():
    print("="*70)
    print("TEST 2: Downtown Chicago (Loop)")
    print("="*70)
    
    model = PopulationDensityModel(chi_factor=1.0)
    model.load_census_data('chi_pop.csv')
    
    lat, lon = 41.8781, -87.6298
    print(f"Testing location: ({lat}, {lon})")
    
    result = model.estimate_for_location(lat, lon, radius_meters=1000)
    
    if result:
        print(f"\n✓ ZIP Code: {result['zipcode']}")
        print(f"✓ Buildings: {result['total_buildings']}")
        print(f"✓ Estimated Population: {result['total_population']:,}")
        print(f"✓ Density: {result['density']:.2f} people/km²")
        
        if 'actual_population' in result:
            print(f"✓ Actual Population: {result['actual_population']:,}")
            print(f"✓ Accuracy: {result['accuracy']}%")
    else:
        print("✗ Test failed - no result")
    print()

def test_lincoln_park():
    print("="*70)
    print("TEST 3: Lincoln Park (Residential)")
    print("="*70)
    
    model = PopulationDensityModel(chi_factor=1.0)
    model.load_census_data('chi_pop.csv')
    
    lat, lon = 41.9212, -87.6567
    print(f"Testing location: ({lat}, {lon})")
    
    result = model.estimate_for_location(lat, lon, radius_meters=800)
    
    if result:
        print(f"\n✓ ZIP Code: {result['zipcode']}")
        print(f"✓ Buildings: {result['total_buildings']}")
        print(f"✓ Estimated Population: {result['total_population']:,}")
        
        if 'actual_population' in result:
            print(f"✓ Accuracy: {result['accuracy']}%")
    print()

def test_hyde_park():
    print("="*70)
    print("TEST 4: Hyde Park (University Area)")
    print("="*70)
    
    model = PopulationDensityModel(chi_factor=1.0)
    model.load_census_data('chi_pop.csv')
    
    lat, lon = 41.7943, -87.5907
    print(f"Testing location: ({lat}, {lon})")
    
    result = model.estimate_for_location(lat, lon, radius_meters=1000)
    
    if result:
        print(f"\n✓ ZIP Code: {result['zipcode']}")
        print(f"✓ Buildings: {result['total_buildings']}")
        print(f"✓ Estimated Population: {result['total_population']:,}")
    print()

def test_wicker_park():
    print("="*70)
    print("TEST 5: Wicker Park (Mixed Use)")
    print("="*70)
    
    model = PopulationDensityModel(chi_factor=1.0)
    model.load_census_data('chi_pop.csv')
    
    lat, lon = 41.9095, -87.6773
    print(f"Testing location: ({lat}, {lon})")
    
    result = model.estimate_for_location(lat, lon, radius_meters=800)
    
    if result:
        print(f"\n✓ ZIP Code: {result['zipcode']}")
        print(f"✓ Buildings: {result['total_buildings']}")
        print(f"✓ Estimated Population: {result['total_population']:,}")
    print()

def test_pilsen():
    print("="*70)
    print("TEST 6: Pilsen (Dense Residential)")
    print("="*70)
    
    model = PopulationDensityModel(chi_factor=1.0)
    model.load_census_data('chi_pop.csv')
    
    lat, lon = 41.8563, -87.6598
    print(f"Testing location: ({lat}, {lon})")
    
    result = model.estimate_for_location(lat, lon, radius_meters=1000)
    
    if result:
        print(f"\n✓ ZIP Code: {result['zipcode']}")
        print(f"✓ Buildings: {result['total_buildings']}")
        print(f"✓ Estimated Population: {result['total_population']:,}")
        
        if 'actual_population' in result:
            print(f"✓ Accuracy: {result['accuracy']}%")
    print()

def test_chi_factor_comparison():
    print("="*70)
    print("TEST 7: Chi Factor Comparison")
    print("="*70)
    
    lat, lon = 41.8781, -87.6298
    
    for chi in [0.8, 1.0, 1.2, 1.5]:
        print(f"\nTesting with chi_factor = {chi}")
        model = PopulationDensityModel(chi_factor=chi)
        model.load_census_data('chi_pop.csv')
        
        result = model.estimate_for_location(lat, lon, radius_meters=1000)
        
        if result:
            print(f"  Estimated Population: {result['total_population']:,}")
            if 'actual_population' in result:
                print(f"  Actual: {result['actual_population']:,}")
                print(f"  Accuracy: {result['accuracy']}%")
    print()

def test_manual_buildings():
    print("="*70)
    print("TEST 8: Manual Building Input (No OSM Query)")
    print("="*70)
    
    model = PopulationDensityModel(chi_factor=1.0)
    model.load_census_data('chi_pop.csv')
    
    buildings_data = {
        'residential': 500,
        'apartments': 30,
        'commercial': 15
    }
    
    area_km2 = 2.0
    
    result = model.estimate_population(area_km2, buildings_data)
    
    if result:
        print(f"\nManual Input:")
        print(f"  Buildings: {result['total_buildings']}")
        print(f"  Area: {result['area_km2']} km²")
        print(f"  Estimated Population: {result['total_population']:,}")
        print(f"  Density: {result['density']:.2f} people/km²")
        
        print(f"\nBreakdown:")
        for btype, data in result['breakdown'].items():
            print(f"  {btype}: {data['count']} × {data['occupancy']} = {data['population']:.0f} people")
    print()

def test_different_radii():
    print("="*70)
    print("TEST 9: Different Search Radii")
    print("="*70)
    
    lat, lon = 41.8781, -87.6298
    
    for radius in [500, 1000, 1500]:
        print(f"\nRadius: {radius}m")
        model = PopulationDensityModel(chi_factor=1.0)
        model.load_census_data('chi_pop.csv')
        
        result = model.estimate_for_location(lat, lon, radius_meters=radius)
        
        if result:
            print(f"  Buildings: {result['total_buildings']}")
            print(f"  Area: {result['area_km2']:.2f} km²")
            print(f"  Population: {result['total_population']:,}")
            print(f"  Density: {result['density']:.2f} people/km²")
    print()

def test_multiple_locations():
    print("="*70)
    print("TEST 10: Multiple Chicago Locations")
    print("="*70)
    
    locations = [
        ("Downtown", 41.8781, -87.6298),
        ("North Side", 41.9212, -87.6567),
        ("South Side", 41.7943, -87.5907),
        ("West Side", 41.8781, -87.7298),
    ]
    
    model = PopulationDensityModel(chi_factor=1.0)
    model.load_census_data('chi_pop.csv')
    
    print(f"\n{'Area':<15} {'ZIP':<8} {'Buildings':<12} {'Estimated Pop':<15} {'Density'}")
    print("-"*70)
    
    for name, lat, lon in locations:
        result = model.estimate_for_location(lat, lon, radius_meters=1000)
        
        if result:
            print(f"{name:<15} {result['zipcode']:<8} {result['total_buildings']:<12} "
                  f"{result['total_population']:<15,} {result['density']:.1f}")
    print()

def run_all_tests():
    print("\n")
    print("#"*70)
    print("# RUNNING ALL TEST CASES")
    print("#"*70)
    print("\n")
    
    try:
        test_load_census_data()
    except Exception as e:
        print(f"✗ Test 1 failed: {e}\n")
    
    try:
        test_downtown_chicago()
    except Exception as e:
        print(f"✗ Test 2 failed: {e}\n")
    
    try:
        test_lincoln_park()
    except Exception as e:
        print(f"✗ Test 3 failed: {e}\n")
    
    try:
        test_hyde_park()
    except Exception as e:
        print(f"✗ Test 4 failed: {e}\n")
    
    try:
        test_wicker_park()
    except Exception as e:
        print(f"✗ Test 5 failed: {e}\n")
    
    try:
        test_pilsen()
    except Exception as e:
        print(f"✗ Test 6 failed: {e}\n")
    
    try:
        test_chi_factor_comparison()
    except Exception as e:
        print(f"✗ Test 7 failed: {e}\n")
    
    try:
        test_manual_buildings()
    except Exception as e:
        print(f"✗ Test 8 failed: {e}\n")
    
    try:
        test_different_radii()
    except Exception as e:
        print(f"✗ Test 9 failed: {e}\n")
    
    try:
        test_multiple_locations()
    except Exception as e:
        print(f"✗ Test 10 failed: {e}\n")
    
    print("#"*70)
    print("# ALL TESTS COMPLETE")
    print("#"*70)

if __name__ == "__main__":
    run_all_tests()