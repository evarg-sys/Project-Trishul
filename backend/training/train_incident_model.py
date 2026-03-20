"""
train_incident_model.py
=======================
Trains the supervised classifier inside DisasterEnsembleSystem on a
comprehensive, manually-curated dataset covering all incident categories
that Trishul's dispatch pipeline handles.

Run from the `backend/` directory:

    python training/train_incident_model.py

The trained model is saved to  api/ml/disaster_models/supervised_model.pkl
and is automatically loaded by DisasterEnsembleSystem on the next startup.

HOW THE ML WORKS
----------------
The supervised model is a TF-IDF + Logistic Regression pipeline:

1. **TF-IDF Vectorizer** (max 1 000 n-grams, 1-3 tokens)
   Converts raw incident text into a sparse feature vector where each
   dimension represents how distinctive a word/phrase is for a document
   compared to the whole corpus.

2. **Logistic Regression classifier**
   Learns a decision boundary for each class (fire, flood, earthquake,
   traffic_collision, chemical_spill, medical_emergency, none).
   Returns class probabilities — the highest becomes the `confidence`
   score in the dispatch pipeline.

3. **Severity Regression**
   A second Logistic Regression maps the same TF-IDF vector to a
   discrete severity level (1-5).  The ensemble vote in
   DisasterEnsembleSystem then combines this with the rule-based and
   (optionally) transformer models.

TO RETRAIN
----------
• Add more rows to TRAINING_DATA below.
• Run this script again — it overwrites supervised_model.pkl.
• The rule-based and transformer models need no retraining; they are
  always-on and stateless.

IMPROVING ACCURACY
------------------
• More data: 50-100 examples per class is a good target.
• Data augmentation: paraphrase existing examples with small word changes.
• Fine-tuned transformer: replace Logistic Regression with a BERT
  fine-tune using HuggingFace Trainer — higher accuracy but requires a
  GPU and labelled data in the hundreds.
• Active learning: log incidents where ensemble_agreement is LOW in
  production, have an operator label them, then retrain monthly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ── resolve backend package root ──────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from api.ml.disaster_detection import DisasterEnsembleSystem  # noqa: E402

# ── training corpus ─────────────────────────────────────────────────────────
# Format: (text, label, severity 1-5)
# Labels must match the incident_category values used in incident_analysis.py

DEFAULT_RESPONSE_BUNDLES = {
    "fire": ["fire"],
    "flood": ["ambulance", "fire"],
    "earthquake": ["ambulance", "fire", "police"],
    "traffic_collision": ["ambulance", "fire", "police"],
    "chemical_spill": ["fire", "ambulance", "police"],
    "medical_emergency": ["ambulance"],
    "none": [],
}

TRAINING_DATA: list[tuple[str, str, int]] = [
    # ── fire ─────────────────────────────────────────────────────────────────
    ("Apartment building on fire, residents trapped on upper floors", "fire", 5),
    ("Restaurant fire spreading to neighboring buildings downtown", "fire", 4),
    ("House fire on the west side, flames visible from the street", "fire", 4),
    ("Smoke and flames coming from a warehouse on industrial row", "fire", 4),
    ("Major blaze at a commercial building, multiple units responding", "fire", 5),
    ("High rise building burning, evacuations underway, ladder trucks needed", "fire", 5),
    ("Gas explosion caused fire in a residential area, gas main ruptured", "fire", 5),
    ("Fire at school building, students evacuated to parking lot", "fire", 5),
    ("Multiple cars on fire in a downtown parking garage", "fire", 4),
    ("Brush fire spreading toward homes in the northern suburbs", "fire", 4),
    ("Wildfire jumped the firebreak, 200 acres burning", "fire", 5),
    ("Kitchen fire reported, heavy smoke filling the apartment", "fire", 3),
    ("Electrical fire in a server room, halon suppression activated", "fire", 3),
    ("Garage fire with propane tanks on site, explosion risk", "fire", 5),
    ("Fire in a three-story townhouse, one person unaccounted for", "fire", 5),

    # ── flood ────────────────────────────────────────────────────────────────
    ("River overflowed after heavy rain, neighborhoods inundated", "flood", 4),
    ("Flash flood warning issued, water rising rapidly on main street", "flood", 4),
    ("Water entering homes after storm drain failure", "flood", 3),
    ("Streets underwater after overnight storm, vehicles stranded", "flood", 3),
    ("Heavy rain caused flash floods in low-lying areas near the creek", "flood", 4),
    ("Dam failure upstream, evacuation ordered for riverside communities", "flood", 5),
    ("Basement flooding in dozens of buildings after pipe burst", "flood", 2),
    ("Coastal storm surge flooding boardwalk and first-floor businesses", "flood", 4),
    ("Record rainfall overnight; several roads impassable due to flooding", "flood", 3),
    ("Sewage backup flooding streets near water treatment plant", "flood", 3),

    # ── earthquake ───────────────────────────────────────────────────────────
    ("Strong earthquake felt across the city, buildings shaking", "earthquake", 5),
    ("Tremor shook buildings for 20 seconds, some structural damage reported", "earthquake", 3),
    ("Earthquake damaged several houses in older residential district", "earthquake", 4),
    ("Magnitude 6 earthquake detected, multiple aftershocks expected", "earthquake", 5),
    ("Buildings cracked after quake, one collapsed in downtown area", "earthquake", 5),
    ("Seismic event, gas leaks reported in several blocks", "earthquake", 5),
    ("Minor earthquake, no injuries but residents are panicked", "earthquake", 2),
    ("Aftershock caused partial roof collapse in a damaged building", "earthquake", 4),
    ("Landslide triggered by earthquake blocking main highway", "earthquake", 4),
    ("Earthquake knocked out power to 50,000 homes", "earthquake", 4),

    # ── traffic_collision ────────────────────────────────────────────────────
    ("10 car pile-up on I-90 near downtown, multiple injuries reported", "traffic_collision", 5),
    ("Head-on collision on Highway 41, two vehicles involved, airbags deployed", "traffic_collision", 4),
    ("Multi-vehicle crash on the interstate, traffic at a standstill", "traffic_collision", 4),
    ("Rollover accident on Route 66, driver trapped inside the vehicle", "traffic_collision", 5),
    ("Semi-truck jackknifed blocking all northbound lanes, fuel spill possible", "traffic_collision", 5),
    ("Three car accident at the intersection of Oak and Main, injuries unknown", "traffic_collision", 3),
    ("Bus collision with multiple passengers injured downtown", "traffic_collision", 5),
    ("Motorcycle crash on the highway, rider ejected, critical condition", "traffic_collision", 5),
    ("Pedestrian struck by vehicle at crosswalk, unresponsive", "traffic_collision", 5),
    ("Chain reaction crash on the bridge, 6 vehicles involved", "traffic_collision", 4),
    ("Hit and run accident, victim on the sidewalk, police en route", "traffic_collision", 3),
    ("Vehicle into a storefront, structural damage, possible casualties inside", "traffic_collision", 5),
    ("Two vehicles collide at an intersection, minor injuries", "traffic_collision", 2),
    ("Truck overturned on the ramp, blocking emergency lane", "traffic_collision", 4),
    ("Pileup in fog on the freeway, unknown number of vehicles and victims", "traffic_collision", 5),

    # ── chemical_spill ───────────────────────────────────────────────────────
    ("Chemical tanker overturned on the highway, unknown substance leaking", "chemical_spill", 5),
    ("Hazmat situation at factory, chlorine gas release detected", "chemical_spill", 5),
    ("Pipeline rupture releasing toxic fumes, evacuation underway", "chemical_spill", 5),
    ("Laboratory explosion with possible chemical release, workers evacuating", "chemical_spill", 4),
    ("Ammonia leak at refrigeration plant, strong odor reported blocks away", "chemical_spill", 4),
    ("Industrial spill of unknown liquid into the river, fish kill observed", "chemical_spill", 4),
    ("Overturned truck leaking paint solvent on the highway", "chemical_spill", 3),
    ("Gas leak from broken main, entire block evacuated", "chemical_spill", 4),
    ("Mercury spill in school classroom, hazmat team requested", "chemical_spill", 4),
    ("Chemical fire at warehouse, toxic smoke billowing", "chemical_spill", 5),

    # ── medical_emergency ────────────────────────────────────────────────────
    ("Cardiac arrest reported at the office building, AED on site", "medical_emergency", 5),
    ("Person collapsed in the street, unresponsive, bystanders performing CPR", "medical_emergency", 5),
    ("Mass casualty event at the stadium, dozens injured after stampede", "medical_emergency", 5),
    ("Overdose victim found unresponsive in apartment, call for EMS", "medical_emergency", 4),
    ("Elderly patient having stroke symptoms, slurred speech, face drooping", "medical_emergency", 5),
    ("Allergic reaction with throat swelling, patient cannot breathe", "medical_emergency", 5),
    ("Child fell from second floor, suspected broken bones and head injury", "medical_emergency", 4),
    ("Gunshot wound victim at convenience store, police and EMS requested", "medical_emergency", 5),
    ("Diabetic emergency, patient unconscious at the park", "medical_emergency", 4),
    ("Multiple people ill after eating at the restaurant, possible food poisoning", "medical_emergency", 3),

    # ── none (non-emergency / noise) ─────────────────────────────────────────
    ("Sunny day at the beach, people enjoying the weather", "none", 1),
    ("Going to school today, traffic is normal", "none", 1),
    ("Nice weather outside, park is crowded", "none", 1),
    ("Had lunch with friends at the cafe downtown", "none", 1),
    ("Watching a movie tonight at home", "none", 1),
    ("Local sports team won the championship last night", "none", 1),
    ("Festival in the park this weekend, road closures expected", "none", 1),
    ("Street cleaning scheduled for Monday morning", "none", 1),
    ("Noise complaint from a neighbor playing loud music", "none", 1),
    ("Possible shoplifting at the mall — security handling it", "none", 1),
]


def main() -> None:
    # -- load feedback collected from the CLI --------------------------------
    feedback_path = BACKEND_DIR / "training" / "feedback_data.json"
    feedback_data: list[tuple[str, str, int, list[str]]] = []
    if feedback_path.exists():
        try:
            raw = json.loads(feedback_path.read_text(encoding="utf-8"))
            feedback_data = [
                (
                    r["text"],
                    r["label"],
                    int(r["severity"]),
                    list(r.get("response_types") or DEFAULT_RESPONSE_BUNDLES.get(r["label"], [])),
                )
                for r in raw
                if "text" in r and "label" in r and "severity" in r
            ]
            print(f"Loaded {len(feedback_data)} feedback example(s) from CLI sessions.")
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Could not load feedback data: {exc}")

    base_response_bundles = [DEFAULT_RESPONSE_BUNDLES[label] for _, label, _ in TRAINING_DATA]
    all_data = [(text, label, severity, DEFAULT_RESPONSE_BUNDLES[label]) for text, label, severity in TRAINING_DATA]
    all_data.extend(feedback_data)
    texts = [t for t, _, _, _ in all_data]
    labels = [label for _, label, _, _ in all_data]
    severities = [sev for _, _, sev, _ in all_data]
    response_bundles = [bundle for _, _, _, bundle in all_data]

    label_counts: dict[str, int] = {}
    for label in labels:
        label_counts[label] = label_counts.get(label, 0) + 1

    print("=" * 70)
    print("TRISHUL – Training Incident Classification Model")
    print("=" * 70)
    print(f"\nTotal training samples : {len(texts)} ({len(TRAINING_DATA)} base + {len(feedback_data)} from feedback)")
    print("Class distribution:")
    for label, count in sorted(label_counts.items()):
        print(f"  {label:<25} {count:>3} examples")
    print()

    model_dir = str(BACKEND_DIR / "api" / "ml" / "disaster_models")
    system = DisasterEnsembleSystem(model_dir=model_dir)
    success = system.train_supervised(texts, labels, severities, response_bundles=response_bundles)

    if success:
        print("\nModel saved to:", model_dir)
        print("\nQuick sanity check:")
        samples = [
            ("Large building fire with people trapped", "fire"),
            ("10-car pile-up on the highway", "traffic_collision"),
            ("Chemical tanker overturned, toxic leak", "chemical_spill"),
            ("Person unresponsive after cardiac arrest", "medical_emergency"),
            ("River flooded after heavy rain", "flood"),
            ("Nice day, going to the park", "none"),
        ]
        for text, expected in samples:
            result = system._detect_supervised(text)  # noqa: SLF001
            predicted = result.get("disaster_type", "unknown")
            conf = result.get("confidence", 0)
            responses = ",".join(result.get("response_types") or []) or "-"
            status = "OK" if predicted == expected else "MISMATCH"
            print(f"  [{status}] expected={expected:<22} got={predicted:<22} conf={conf:.1f}% responses={responses}")
    else:
        print("\nTraining failed. Check that scikit-learn is installed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
