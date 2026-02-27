from celery import shared_task
from .models import Disaster
import sys
import os
import logging

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

        # Step 2: Run ensemble detection
        try:
            sys.path.append(os.path.join(os.path.dirname(__file__), 'ml'))
            from disaster_detection import DisasterEnsembleSystem
            ensemble = DisasterEnsembleSystem(
                model_dir=os.path.join(os.path.dirname(__file__), 'ml', 'disaster_models')
            )
            text = f"{disaster.disaster_type} {disaster.description}"
            result = ensemble.detect(text)
            logger.warning(f"✅ Ensemble result: {result}")
            if result['detected']:
                disaster.confidence_score = result['confidence']
                disaster.severity_score = result['severity']
                disaster.save()
        except Exception as e:
            logger.warning(f"❌ Ensemble error: {e}")

        # Step 3: Run population model
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
                    disaster.save()
            else:
                logger.warning("⚠️ Skipping population model - no lat/lon")
        except Exception as e:
            logger.warning(f"❌ Population model error: {e}")

        # Step 4: Mark as analyzed
        disaster.status = 'analyzed'
        disaster.save()
        return {'success': True, 'disaster_id': disaster_id}

    except Exception as e:
        logger.warning(f"❌ Fatal error analyzing disaster {disaster_id}: {e}")
        return {'success': False, 'error': str(e)}