"""
Train Building Occupancy Model
Using Chicago Building Footprints via API
Project Trishul
"""

import requests
import pandas as pd
import numpy as np
import pickle
import math
from pathlib import Path
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

from population_model import PopulationDensityModel


# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

DATASET_ID = "syp8-uezg"  # replace with real dataset id
BASE_URL = f"https://data.cityofchicago.org/api/v3/views/syp8-uezg/query.json"

LIMIT = 50000
MODEL_DIR = Path(".ml_models")
MODEL_DIR.mkdir(exist_ok=True)

MODEL_PATH = MODEL_DIR / "building_population_model.pkl"
SCALER_PATH = MODEL_DIR / "building_population_scaler.pkl"


# ------------------------------------------------------------
# Fetch Building Data Using Pagination
# ------------------------------------------------------------

def fetch_all_buildings():

    print("=" * 70)
    print("Fetching Building Footprints via API")
    print("=" * 70)

    offset = 0
    all_rows = []

    while True:

        params = {
            "$limit": LIMIT,
            "$offset": offset
        }

        response = requests.get(BASE_URL, params=params)

        if response.status_code != 200:
            print("API error:", response.text)
            break

        data = response.json()

        if not data:
            break

        print(f"Fetched {len(data)} rows (offset={offset})")

        all_rows.extend(data)
        offset += LIMIT

    print(f"Total rows fetched: {len(all_rows)}")

    return pd.DataFrame(all_rows)


# ------------------------------------------------------------
# Feature Engineering
# ------------------------------------------------------------

def build_features(df, census):

    X = []
    y = []

    for zipcode, group in df.groupby("zip"):

        if zipcode not in census:
            continue

        zip_population = census[zipcode]["total"]

        residential = group[
            group["building"].isin(["residential", "apartments", "house"])
        ]

        residential_count = len(residential)

        if residential_count == 0:
            continue

        avg_population = zip_population / residential_count

        for _, row in residential.iterrows():

            footprint = float(row.get("footprint_m2", 150))

            building_type = row.get("building", "residential")

            one_hot = [
                1 if building_type == "residential" else 0,
                1 if building_type == "apartments" else 0,
                1 if building_type == "house" else 0,
            ]

            lat = float(row.get("latitude", 0))
            lon = float(row.get("longitude", 0))

            features = one_hot + [
                footprint,
                zip_population,
                (lat + 90) / 180,
                (lon + 180) / 360
            ]

            X.append(features)
            y.append(avg_population)

    return np.array(X), np.array(y)


# ------------------------------------------------------------
# Train Model
# ------------------------------------------------------------

def train_model():

    density_model = PopulationDensityModel(use_ml=False)
    census = density_model.load_census_data("chi_pop.csv")

    df = fetch_all_buildings()

    print("Building feature matrix...")

    X, y = build_features(df, census)

    print(f"Training on {len(X)} buildings")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = MLPRegressor(
        hidden_layer_sizes=(128, 64),
        max_iter=1000,
        random_state=42,
        verbose=True
    )

    model.fit(X_scaled, y)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)

    print("✓ Model trained successfully")
    print(f"✓ R² Score: {model.score(X_scaled, y):.4f}")


# ------------------------------------------------------------

if __name__ == "__main__":
    train_model()