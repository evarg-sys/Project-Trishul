from celery import shared_task
from .models import Disaster
import sys
import os
import logging
from .ml.incident_analysis import analyze_and_plan_incident

logger = logging.getLogger(__name__)

@shared_task
def analyze_disaster(disaster_id):
    try:
        disaster = Disaster.objects.get(id=disaster_id)

        # Step 1: Geocode address
        try:
            from geopy.geocoders import Nominatim
            import time
            geolocator = Nominatim(user_agent="trishul_v1", timeout=10)
            time.sleep(1)
            location = geolocator.geocode(f"{disaster.address}, Chicago, IL")
            if location:
                disaster.latitude = location.latitude
                disaster.longitude = location.longitude
                disaster.save()
                logger.warning(f"✅ Geocoded: {location.latitude}, {location.longitude}")
            else:
                logger.warning(f"⚠️ Geocoding failed for: {disaster.address}")
        except Exception as e:
            logger.warning(f"❌ Geocoding error: {e}")

        text = f"{disaster.disaster_type} {disaster.description}".strip()

        # Step 2: Run hybrid incident analysis + capability matching + escalation
        try:
            planning = analyze_and_plan_incident(
                text=text,
                latitude=disaster.latitude,
                longitude=disaster.longitude,
                population_hint=disaster.population_affected,
            )
            analysis = planning.get('analysis', {})
            disaster.confidence_score = float(analysis.get('confidence') or disaster.confidence_score or 0)
            disaster.severity_score = float(analysis.get('severity_score') or disaster.severity_score or 0)
            disaster.analysis_details = analysis
            disaster.capability_match = planning.get('capability_match', {})
            disaster.final_plan = planning.get('final_plan', {})
            disaster.alerts = planning.get('alerts', [])
            disaster.needs_mutual_aid = bool(planning.get('actions', {}).get('request_mutual_aid'))
            disaster.needs_operator_review = bool(planning.get('actions', {}).get('escalate_to_operator_review'))
            logger.warning(f"✅ Incident planning result ready for disaster {disaster.id}")
        except Exception as e:
            logger.warning(f"❌ Incident planning error: {e}")

        # Step 3: Run ensemble detection as secondary confidence check
        try:
            sys.path.append(os.path.join(os.path.dirname(__file__), 'ml'))
            from disaster_detection import DisasterEnsembleSystem
            ensemble = DisasterEnsembleSystem(
                model_dir=os.path.join(os.path.dirname(__file__), 'ml', 'disaster_models')
            )
            result = ensemble.detect(text)
            logger.warning(f"✅ Ensemble result: {result}")
            if result.get('detected'):
                ensemble_confidence = float(result.get('confidence') or 0)
                ensemble_severity = float(result.get('severity') or disaster.severity_score or 0)
                disaster.confidence_score = max(disaster.confidence_score or 0, ensemble_confidence)
                disaster.severity_score = max(disaster.severity_score or 0, ensemble_severity)
        except Exception as e:
            logger.warning(f"❌ Ensemble error: {e}")

        # Step 4: Run population model
        try:
            if disaster.latitude and disaster.longitude:
                sys.path.append(os.path.join(os.path.dirname(__file__), 'ml'))
                from population_model import PopulationDensityModel
                pop_model = PopulationDensityModel()
                csv_path = os.path.join(
                    os.path.dirname(__file__),
                    '..', 'data', 'chi_pop.csv'
                )
                pop_model.load_census_data(csv_path)
                pop_result = pop_model.estimate_for_location(
                    disaster.latitude,
                    disaster.longitude,
                    radius_meters=500
                )
                logger.warning(f"✅ Population result: {pop_result}")
                if pop_result:
                    disaster.population_affected = pop_result['total_population']
            else:
                logger.warning("⚠️ Skipping population model - no lat/lon")
        except Exception as e:
            logger.warning(f"❌ Population model error: {e}")

        # Step 5: Compute priority score
        try:
            disaster.compute_priority()
            logger.warning(f"🟠 Priority score set to {disaster.priority_score}")
        except Exception as e:
            logger.warning(f"❌ Priority calculation error: {e}")

        # Step 6: Mark as analyzed
        disaster.status = 'analyzed'
        disaster.save()
        return {'success': True, 'disaster_id': disaster_id}

    except Exception as e:
        logger.warning(f"❌ Fatal error analyzing disaster {disaster_id}: {e}")
        return {'success': False, 'error': str(e)}