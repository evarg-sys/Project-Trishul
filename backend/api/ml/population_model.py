import csv
import requests
from collections import Counter

class PopulationDensityModel:
    
    BUILDING_OCCUPANCY = {
        'residential': 2.5,
        'apartments': 4.0,
        'house': 2.5,
        'detached': 2.3,
        'semidetached_house': 2.5,
        'terrace': 2.7,
        'commercial': 0.1,
        'retail': 0.0,
        'industrial': 0.0,
    }
    
    def __init__(self, chi_factor=1.0):
        self.chi_factor = chi_factor
        self.census_data = {}
    
    def load_census_data(self, csv_file_path):
        count = 0
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.strip().split('\n')
            
            headers = lines[0].split('\t')
            print(f"Headers found: {headers[:5]}...")
            
            for line in lines[1:]:
                parts = line.split('\t')
                if len(parts) < 4:
                    continue
                
                geo_type = parts[0].strip()
                geography = parts[2].strip()
                
                if geo_type == 'ZIP Code' and len(geography) == 5 and geography.isdigit():
                    try:
                        zipcode = geography
                        total_pop = int(parts[3].replace(',', ''))
                        
                        age_data = {
                            'total': total_pop,
                            'age_0_17': int(parts[4].replace(',', '')),
                            'age_18_29': int(parts[5].replace(',', '')),
                            'age_30_39': int(parts[6].replace(',', '')),
                            'age_40_49': int(parts[7].replace(',', '')),
                            'age_50_59': int(parts[8].replace(',', '')),
                            'age_60_69': int(parts[9].replace(',', '')),
                            'age_70_79': int(parts[10].replace(',', '')),
                            'age_80_plus': int(parts[11].replace(',', '')),
                        }
                        
                        self.census_data[zipcode] = age_data
                        count += 1
                        if count <= 5:
                            print(f"  Loaded ZIP {zipcode}: {total_pop:,} people")
                        
                    except (ValueError, IndexError) as e:
                        continue
        
        print(f"\nTotal: {len(self.census_data)} ZIP codes loaded")
        return self.census_data
    
    def get_buildings_from_osm(self, lat, lon, radius_meters=1000):
        overpass_url = "http://overpass-api.de/api/interpreter"
        
        overpass_query = f"""
        [out:json];
        (
          way["building"](around:{radius_meters},{lat},{lon});
          relation["building"](around:{radius_meters},{lat},{lon});
        );
        out body;
        """
        
        print(f"\nQuerying OSM for buildings around ({lat}, {lon})...")
        
        try:
            response = requests.get(overpass_url, params={'data': overpass_query}, timeout=30)
            data = response.json()
            
            buildings = data.get('elements', [])
            building_types = []
            
            for building in buildings:
                tags = building.get('tags', {})
                building_type = tags.get('building', 'residential')
                
                if building_type == 'yes':
                    building_type = 'residential'
                elif building_type == 'apartment':
                    building_type = 'apartments'
                
                building_types.append(building_type)
            
            building_counts = Counter(building_types)
            
            print(f"Found {len(buildings)} buildings")
            print(f"Building type breakdown: {dict(building_counts)}")
            
            return dict(building_counts), len(buildings)
            
        except Exception as e:
            print(f"Error querying OSM: {e}")
            return {}, 0
    
    def get_zipcode_from_location(self, lat, lon):
        nominatim_url = "https://nominatim.openstreetmap.org/reverse"
        
        params = {
            'lat': lat,
            'lon': lon,
            'format': 'json',
            'addressdetails': 1
        }
        
        headers = {
            'User-Agent': 'PopulationDensityModel/1.0'
        }
        
        print(f"\nGetting ZIP code for location ({lat}, {lon})...")
        
        try:
            response = requests.get(nominatim_url, params=params, headers=headers, timeout=10)
            data = response.json()
            
            address = data.get('address', {})
            zipcode = address.get('postcode', '')
            
            if zipcode:
                print(f"Found ZIP code: {zipcode}")
                return zipcode
            else:
                print("No ZIP code found for this location")
                return None
                
        except Exception as e:
            print(f"Error getting ZIP code: {e}")
            return None
    
    def estimate_population(self, area_km2, buildings_data):
        if not buildings_data:
            print("No building data available")
            return None
        
        total_population = 0
        total_buildings = 0
        breakdown = {}
        
        for building_type, count in buildings_data.items():
            occupancy = self.BUILDING_OCCUPANCY.get(building_type, 2.5)
            pop = count * occupancy * self.chi_factor
            
            breakdown[building_type] = {
                'count': count,
                'occupancy': occupancy,
                'population': round(pop, 1)
            }
            
            total_population += pop
            total_buildings += count
        
        density = total_population / area_km2 if area_km2 > 0 else 0
        
        return {
            'total_population': round(total_population),
            'density': round(density, 2),
            'breakdown': breakdown,
            'total_buildings': total_buildings,
            'area_km2': area_km2
        }
    
    def estimate_for_location(self, lat, lon, radius_meters=1000):
        print("\n" + "="*70)
        print("POPULATION DENSITY ESTIMATION WORKFLOW")
        print("="*70)
        
        zipcode = self.get_zipcode_from_location(lat, lon)
        
        if not zipcode:
            print("Cannot proceed without ZIP code")
            return None
        
        buildings_data, total_buildings = self.get_buildings_from_osm(lat, lon, radius_meters)
        
        if not buildings_data:
            print("No buildings found in this area")
            return None
        
        area_km2 = (3.14159 * (radius_meters/1000) ** 2)
        
        result = self.estimate_population(area_km2, buildings_data)
        
        if not result:
            return None
        
        result['zipcode'] = zipcode
        result['location'] = {'lat': lat, 'lon': lon}
        result['radius_meters'] = radius_meters
        
        if zipcode in self.census_data:
            census = self.census_data[zipcode]
            result['actual_population'] = census['total']
            result['difference'] = result['total_population'] - census['total']
            result['percent_error'] = round(abs(result['difference']) / census['total'] * 100, 2) if census['total'] > 0 else 0
            result['accuracy'] = round(100 - result['percent_error'], 2)
            
            print(f"\nCensus data found for ZIP {zipcode}")
            print(f"  Actual population: {census['total']:,}")
        else:
            print(f"\nNo census data available for ZIP {zipcode}")
        
        return result


def run_test():
    print("="*70)
    print("POPULATION DENSITY MODEL - PROPER WORKFLOW")
    print("="*70)
    
    model = PopulationDensityModel(chi_factor=1.0)
    
    print("\nStep 1: Load Census Data")
    print("-"*70)
    model.load_census_data('chi_pop.csv')
    
    print("\n\nStep 2: Get Location from User (using Chicago coordinates as example)")
    print("-"*70)
    lat = 41.8781
    lon = -87.6298
    print(f"Location: ({lat}, {lon})")
    
    print("\n\nStep 3: Complete Estimation Workflow")
    print("-"*70)
    result = model.estimate_for_location(lat, lon, radius_meters=1000)
    
    if result:
        print("\n" + "="*70)
        print("FINAL RESULTS")
        print("="*70)
        print(f"Location: ({result['location']['lat']}, {result['location']['lon']})")
        print(f"ZIP Code: {result['zipcode']}")
        print(f"Search Radius: {result['radius_meters']}m")
        print(f"Area: {result['area_km2']:.2f} km²")
        print(f"\nBuildings Found: {result['total_buildings']}")
        print(f"Estimated Population: {result['total_population']:,}")
        print(f"Population Density: {result['density']:.2f} people/km²")
        
        if 'actual_population' in result:
            print(f"\nComparison with Census:")
            print(f"  Actual: {result['actual_population']:,}")
            print(f"  Error: {result['percent_error']}%")
            print(f"  Accuracy: {result['accuracy']}%")

if __name__ == "__main__":
    run_test()