import csv
import requests
import json
import os
from collections import Counter
from pathlib import Path

# Try to import ML model (optional dependency)
try:
    from population_ml_model import PopulationMLModel
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("[INFO] ML model not available. Install sklearn for ML-based estimation.")


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

    def __init__(self, chi_factor=1.0, cache_dir=None, use_ml=False):
        self.chi_factor = chi_factor
        self.census_data = {}
        self.cache_dir = cache_dir or Path(__file__).parent / '.cache'
        self.cache_dir.mkdir(exist_ok=True)
        self.api_cache = self._load_api_cache()

        # ML Model integration
        self.use_ml = use_ml and ML_AVAILABLE
        self.ml_model = None
        if self.use_ml:
            try:
                self.ml_model = PopulationMLModel()
                if self.ml_model.model is None:
                    print("[INFO] ML model not trained yet. Will use formula-based estimation.")
                    self.use_ml = False
            except Exception as e:
                print(f"[INFO] ML model initialization failed: {e}")
                self.use_ml = False

    def _get_cache_path(self):
        return self.cache_dir / 'api_cache.json'

    def _load_api_cache(self):
        cache_path = self._get_cache_path()
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_api_cache(self):
        cache_path = self._get_cache_path()
        with open(cache_path, 'w') as f:
            json.dump(self.api_cache, f, indent=2)

    def _get_cache_key(self, key_type, *args):
        return f"{key_type}::{':'.join(str(arg) for arg in args)}"

    def load_census_data(self, csv_file_path):
        """Load census data from CSV file with proper CSV parsing"""
        csv_path = Path(csv_file_path)

        # If relative path, try to find it relative to this file first
        if not csv_path.is_absolute() and not csv_path.exists():
            csv_path = Path(__file__).parent.parent.parent / 'data' / csv_file_path

        if not csv_path.exists():
            print(f"ERROR: CSV file not found at {csv_path}")
            return {}

        count = 0
        print(f"Loading census data from {csv_path}")
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    geo_type = row.get('Geography Type', '').strip()
                    geography = row.get('Geography', '').strip()
                    if geo_type == 'ZIP Code' and len(geography) == 5 and geography.isdigit():
                        try:
                            zipcode = geography
                            total_pop = int(row.get('Population - Total', '0').replace(',', ''))
                            age_data = {
                                'total': total_pop,
                                'age_0_17': int(row.get('Population - Age 0-17', '0').replace(',', '')),
                                'age_18_29': int(row.get('Population - Age 18-29', '0').replace(',', '')),
                                'age_30_39': int(row.get('Population - Age 30-39', '0').replace(',', '')),
                                'age_40_49': int(row.get('Population - Age 40-49', '0').replace(',', '')),
                                'age_50_59': int(row.get('Population - Age 50-59', '0').replace(',', '')),
                                'age_60_69': int(row.get('Population - Age 60-69', '0').replace(',', '')),
                                'age_70_79': int(row.get('Population - Age 70-79', '0').replace(',', '')),
                                'age_80_plus': int(row.get('Population - Age 80+', '0').replace(',', '')),
                            }
                            self.census_data[zipcode] = age_data
                            count += 1
                            if count <= 5:
                                print(f"  Loaded ZIP {zipcode}: {total_pop:,} people")
                        except (ValueError, KeyError) as e:
                            continue
        except Exception as e:
            print(f"ERROR reading CSV: {e}")
            return {}

        print(f"\nTotal: {len(self.census_data)} ZIP codes loaded\n")
        return self.census_data

    def get_buildings_from_osm(self, lat, lon, radius_meters=1000):
        """Query OSM for buildings with caching"""
        cache_key = self._get_cache_key('buildings', lat, lon, radius_meters)

        if cache_key in self.api_cache:
            cached = self.api_cache[cache_key]
            print(f"\nQuerying OSM for buildings around ({lat}, {lon})... (cached)")
            print(f"Found {cached['total']} buildings")
            if cached['counts']:
                print(f"Building type breakdown: {cached['counts']}")
            return cached['counts'], cached['total']

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
            result_dict = dict(building_counts)
            total = len(buildings)

            self.api_cache[cache_key] = {'counts': result_dict, 'total': total}
            self._save_api_cache()
            print(f"Found {total} buildings")
            if result_dict:
                print(f"Building type breakdown: {result_dict}")
            return result_dict, total
        except Exception as e:
            print(f"Error querying OSM: {e}")
            self.api_cache[cache_key] = {'counts': {}, 'total': 0}
            self._save_api_cache()
            return {}, 0

    def get_zipcode_from_location(self, lat, lon):
        """Get zipcode from location coordinates with caching"""
        cache_key = self._get_cache_key('zipcode', lat, lon)

        if cache_key in self.api_cache:
            cached = self.api_cache[cache_key]
            if cached:
                print(f"Zipcode (cached): {cached}")
            else:
                print("No ZIP code found for this location (cached)")
            return cached

        nominatim_url = "https://nominatim.openstreetmap.org/reverse"
        params = {'lat': lat, 'lon': lon, 'format': 'json', 'addressdetails': 1}
        headers = {'User-Agent': 'PopulationDensityModel/1.0'}
        print(f"\nGetting ZIP code for location ({lat}, {lon})...")
        try:
            response = requests.get(nominatim_url, params=params, headers=headers, timeout=10)
            data = response.json()
            address = data.get('address', {})
            zipcode = address.get('postcode', '')
            self.api_cache[cache_key] = zipcode or None
            self._save_api_cache()
            if zipcode:
                print(f"Found ZIP code: {zipcode}")
                return zipcode
            else:
                print("No ZIP code found for this location")
                return None
        except Exception as e:
            print(f"Error getting ZIP code: {e}")
            self.api_cache[cache_key] = None
            self._save_api_cache()
            return None

    def estimate_population(self, area_km2, buildings_data, location=None):
        """Estimate population using ML model (if available) or formula-based approach"""
        if not buildings_data:
            print("No building data available")
            return None

        lat = location.get('lat') if location else None
        lon = location.get('lon') if location else None
        zipcode = location.get('zipcode') if location else None

        # Try ML prediction first if enabled
        if self.use_ml and self.ml_model is not None:
            print("\n[Using Neural Network ML Model]")
            ml_prediction = self.ml_model.predict(buildings_data, area_km2, zipcode, lat, lon)
            if ml_prediction is not None:
                total_population = ml_prediction
                density = total_population / area_km2 if area_km2 > 0 else 0
                breakdown = {}
                for building_type, count in buildings_data.items():
                    occupancy = self.BUILDING_OCCUPANCY.get(building_type, 2.5)
                    pop = count * occupancy * self.chi_factor
                    breakdown[building_type] = {
                        'count': count,
                        'occupancy': occupancy,
                        'population': round(pop, 1)
                    }
                return {
                    'total_population': total_population,
                    'density': round(density, 2),
                    'breakdown': breakdown,
                    'total_buildings': sum(buildings_data.values()),
                    'area_km2': area_km2,
                    'estimation_method': 'Neural Network ML'
                }

        # Fall back to formula-based approach
        print("\n[Using Formula-Based Estimation]")
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
            'area_km2': area_km2,
            'estimation_method': 'Formula-Based'
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
        location = {'lat': lat, 'lon': lon, 'zipcode': zipcode}
        result = self.estimate_population(area_km2, buildings_data, location)
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


def run_interactive():
    print("\n" + "="*70)
    print("POPULATION DENSITY MODEL - INTERACTIVE MODE")
    print("="*70)
    model = PopulationDensityModel(chi_factor=1.0)
    csv_path = Path(__file__).parent / 'chi_pop.csv'
    model.load_census_data(str(csv_path))

    valid_input = False
    lat = None
    lon = None
    radius_meters = 1000

    while not valid_input:
        try:
            lat_input = input("Enter Latitude (e.g., 41.8781): ").strip()
            if not lat_input:
                print("[ERROR] Latitude cannot be empty.")
                continue
            lon_input = input("Enter Longitude (e.g., -87.6298): ").strip()
            if not lon_input:
                print("[ERROR] Longitude cannot be empty.")
                continue
            lat = float(lat_input)
            lon = float(lon_input)
            if lat < -90 or lat > 90:
                print(f"[ERROR] Latitude must be between -90 and 90.")
                lat = None
                lon = None
                continue
            if lon < -180 or lon > 180:
                print(f"[ERROR] Longitude must be between -180 and 180.")
                lat = None
                lon = None
                continue
            radius_input = input("Enter Radius in meters (default 1000): ").strip()
            if radius_input:
                radius_meters = int(radius_input)
                if radius_meters <= 0:
                    print("[ERROR] Radius must be greater than 0.")
                    lat = None
                    lon = None
                    continue
            valid_input = True
        except ValueError as e:
            print(f"[ERROR] Invalid input: {e}")
            continue
        except KeyboardInterrupt:
            print("\n\nExiting...")
            return

    result = model.estimate_for_location(lat, lon, radius_meters=radius_meters)
    if result:
        print(f"\nEstimated Population: {result['total_population']:,}")
        print(f"Estimation Method: {result.get('estimation_method', 'Formula-Based')}")


def run_test():
    print("\n")
    print("="*70)
    print("POPULATION DENSITY MODEL - TEST MODE")
    print("="*70)
    model = PopulationDensityModel(chi_factor=1.0)
    csv_path = Path(__file__).parent / 'chi_pop.csv'
    model.load_census_data(str(csv_path))

    lat = 41.8781
    lon = -87.6298
    result = model.estimate_for_location(lat, lon, radius_meters=1000)
    if result:
        print(f"\nEstimated Population: {result['total_population']:,}")
        if 'actual_population' in result:
            print(f"Census Population: {result['actual_population']:,}")
            print(f"Accuracy: {result['accuracy']}%")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1].lower() == '--interactive':
        run_interactive()
    else:
        run_test()