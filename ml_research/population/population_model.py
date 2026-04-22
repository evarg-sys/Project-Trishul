import numpy as np
import json
from pathlib import Path
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
import pickle

class PopulationMLModel:
    """Machine Learning based population estimation using Neural Network"""
    
    def __init__(self, model_path=None):
        """Initialize ML model"""
        self.model = None
        self.scaler = None
        self.model_path = model_path or Path(__file__).parent / '.ml_models' / 'population_model.pkl'
        self.scaler_path = model_path or Path(__file__).parent / '.ml_models' / 'scaler.pkl'
        self.training_data = []
        
        # Create directory if doesn't exist
        self.model_path.parent.mkdir(exist_ok=True, parents=True)
        
        # Try to load existing model
        self._load_model()
    
    def _save_model(self):
        """Save trained model to disk"""
        if self.model is not None:
            try:
                with open(self.model_path, 'wb') as f:
                    pickle.dump(self.model, f)
                with open(self.scaler_path, 'wb') as f:
                    pickle.dump(self.scaler, f)
                print(f"✓ Model saved to {self.model_path}")
            except Exception as e:
                print(f"Error saving model: {e}")
    
    def _load_model(self):
        """Load trained model from disk"""
        try:
            if self.model_path.exists() and self.scaler_path.exists():
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
                with open(self.scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                print(f"✓ Model loaded from {self.model_path}")
                return True
        except Exception as e:
            print(f"Error loading model: {e}")
        
        return False
    
    def _extract_features(self, building_data, area_km2, zipcode=None, lat=None, lon=None):
        """Extract features from building data for ML model"""
        features = []
        
        # Feature 1-9: Building counts by type
        building_types = ['residential', 'apartments', 'commercial', 'office', 
                         'industrial', 'retail', 'hotel', 'house', 'public']
        
        for btype in building_types:
            features.append(building_data.get(btype, 0))
        
        # Feature 10: Total buildings
        total_buildings = sum(building_data.values())
        features.append(total_buildings)
        
        # Feature 11: Area in km²
        features.append(area_km2)
        
        # Feature 12: Building density (buildings per km²)
        density = total_buildings / area_km2 if area_km2 > 0 else 0
        features.append(density)
        
        # Feature 13: Residential ratio
        residential = building_data.get('residential', 0) + building_data.get('apartments', 0) + building_data.get('house', 0)
        residential_ratio = residential / total_buildings if total_buildings > 0 else 0
        features.append(residential_ratio)
        
        # Feature 14: Commercial ratio
        commercial = building_data.get('commercial', 0) + building_data.get('office', 0) + building_data.get('retail', 0)
        commercial_ratio = commercial / total_buildings if total_buildings > 0 else 0
        features.append(commercial_ratio)
        
        # Feature 15-16: Location (if provided, normalized)
        if lat is not None and lon is not None:
            # Normalize to 0-1 range roughly
            features.append((lat + 90) / 180)  # Latitude normalized
            features.append((lon + 180) / 360)  # Longitude normalized
        else:
            features.append(0.5)
            features.append(0.5)
        
        return np.array([features])
    
    def train(self, training_samples):
        """
        Train the neural network model
        
        Args:
            training_samples: List of dicts with keys:
                - building_data: dict of building counts by type
                - area_km2: area in square kilometers
                - actual_population: ground truth population
                - zipcode: (optional) ZIP code
                - lat: (optional) latitude
                - lon: (optional) longitude
        """
        if len(training_samples) < 5:
            print(f"Warning: Only {len(training_samples)} samples. Recommend at least 10 for good training.")
        
        X = []
        y = []
        
        print(f"\nTraining ML model with {len(training_samples)} samples...")
        print("-" * 70)
        
        for sample in training_samples:
            features = self._extract_features(
                sample['building_data'],
                sample['area_km2'],
                sample.get('zipcode'),
                sample.get('lat'),
                sample.get('lon')
            )
            X.append(features[0])
            y.append(sample['actual_population'])
            
            print(f"  Sample {len(y)}: {sample['actual_population']:,} people")
        
        X = np.array(X)
        y = np.array(y)
        
        # Normalize features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Create and train neural network
        self.model = MLPRegressor(
            hidden_layer_sizes=(128, 64, 32),  # 3 hidden layers
            max_iter=1000,
            learning_rate_init=0.001,
            random_state=42,
            verbose=True
        )
        
        self.model.fit(X_scaled, y)
        
        # Save the trained model
        self._save_model()
        
        # Calculate R² score
        score = self.model.score(X_scaled, y)
        print(f"\n✓ Model trained successfully")
        print(f"✓ R² Score: {score:.4f} (1.0 is perfect)")
        
        return self.model
    
    def predict(self, building_data, area_km2, zipcode=None, lat=None, lon=None):
        """
        Predict population using trained ML model
        
        Returns: predicted population or None if model not trained
        """
        if self.model is None or self.scaler is None:
            print("[WARNING] ML model not trained. Using formula-based estimation.")
            return None
        
        try:
            features = self._extract_features(building_data, area_km2, zipcode, lat, lon)
            features_scaled = self.scaler.transform(features)
            prediction = self.model.predict(features_scaled)[0]
            
            # Ensure non-negative prediction
            return max(0, round(prediction))
        
        except Exception as e:
            print(f"[ERROR] Prediction failed: {e}")
            return None


# Example usage and helper functions
def create_sample_training_data():
    """Create synthetic training data from typical Chicago neighborhoods"""
    training_data = [
        {
            'building_data': {'residential': 150, 'apartments': 20, 'commercial': 30},
            'area_km2': 1.5,
            'actual_population': 850,
            'zipcode': '60601',
            'lat': 41.8781,
            'lon': -87.6298
        },
        {
            'building_data': {'residential': 200, 'apartments': 50, 'commercial': 15},
            'area_km2': 2.0,
            'actual_population': 1500,
            'zipcode': '60614',
            'lat': 41.9212,
            'lon': -87.6567
        },
        {
            'building_data': {'residential': 120, 'apartments': 15, 'commercial': 20},
            'area_km2': 1.2,
            'actual_population': 650,
            'zipcode': '60605',
            'lat': 41.7943,
            'lon': -87.5907
        },
        {
            'building_data': {'residential': 180, 'apartments': 30, 'commercial': 25},
            'area_km2': 1.8,
            'actual_population': 1100,
            'zipcode': '60610',
            'lat': 41.8912,
            'lon': -87.6127
        },
        {
            'building_data': {'residential': 250, 'apartments': 60, 'commercial': 40},
            'area_km2': 2.5,
            'actual_population': 2000,
            'zipcode': '60602',
            'lat': 41.8850,
            'lon': -87.6350
        },
        {
            'building_data': {'residential': 100, 'apartments': 10, 'commercial': 10},
            'area_km2': 1.0,
            'actual_population': 500,
            'zipcode': '60604',
            'lat': 41.8750,
            'lon': -87.6400
        },
        {
            'building_data': {'residential': 300, 'apartments': 80, 'commercial': 50},
            'area_km2': 3.0,
            'actual_population': 2500,
            'zipcode': '60611',
            'lat': 41.9050,
            'lon': -87.6200
        },
        {
            'building_data': {'residential': 160, 'apartments': 25, 'commercial': 20},
            'area_km2': 1.6,
            'actual_population': 900,
            'zipcode': '60603',
            'lat': 41.8790,
            'lon': -87.6480
        }
    ]
    return training_data


if __name__ == "__main__":
    print("=" * 70)
    print("POPULATION ML MODEL - STANDALONE TEST")
    print("=" * 70)
    
    # Create and train model
    ml_model = PopulationMLModel()
    
    # Check if already trained
    if ml_model.model is None:
        print("\nNo trained model found. Creating training data...")
        training_samples = create_sample_training_data()
        ml_model.train(training_samples)
    else:
        print("\nModel already trained. Ready for predictions.")
    
    # Test predictions
    print("\n" + "=" * 70)
    print("TEST PREDICTIONS")
    print("=" * 70)
    
    test_cases = [
        {'building_data': {'residential': 140, 'apartments': 18, 'commercial': 28}, 'area_km2': 1.4},
        {'building_data': {'residential': 210, 'apartments': 55, 'commercial': 12}, 'area_km2': 2.1},
        {'building_data': {'residential': 280, 'apartments': 70, 'commercial': 45}, 'area_km2': 2.8},
    ]
    
    for i, test in enumerate(test_cases, 1):
        pred = ml_model.predict(**test)
        print(f"Test {i}: Predicted Population = {pred:,} people")
