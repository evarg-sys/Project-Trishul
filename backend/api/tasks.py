from celery import shared_task
from .models import Disaster, FireStation, Hospital, DispatchDecision
import sys
import os
import logging
import math
from .ml.incident_analysis import analyze_and_plan_incident

logger = logging.getLogger(__name__)

# ── Cached road network (persists across Celery tasks in same worker process)
_router_cache = None

def _get_router():
    """Return a cached DisasterRouting instance, loading network only once per worker."""
    global _router_cache
    if _router_cache is not None and _router_cache.graph is not None:
        logger.warning("🗺️ Using cached road network")
        return _router_cache
    sys.path.append(os.path.join(os.path.dirname(__file__), 'ml'))
    from disaster_routing import DisasterRouting
    logger.warning("🗺️ Loading road network for dispatch...")
    router = DisasterRouting(city="Chicago, Illinois, USA")
    router.load_network()
    _router_cache = router
    return router


def _haversine_km(lat1, lon1, lat2, lon2):
    """Straight-line distance in km between two lat/lng points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


@shared_task
def analyze_disaster(disaster_id):
    try:
        disaster = Disaster.objects.get(id=disaster_id)

        # ── Step 1: Geocode address (skip if coords already provided) ────
        try:
            if disaster.latitude and disaster.longitude:
                logger.warning(f"✅ Coords already set: {disaster.latitude}, {disaster.longitude} — skipping geocode")
            else:
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

        # ── Step 2: Run hybrid incident analysis + capability matching ────
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
            logger.warning(f"✅ Incident planning complete for disaster {disaster.id}")
        except Exception as e:
            logger.warning(f"❌ Incident planning error: {e}")

        # ── Step 3: Run ensemble detection (secondary confidence check) ───
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

        # ── Step 4: Run population model ─────────────────────────────────
        try:
            if disaster.latitude and disaster.longitude:
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

        # ── Step 5: Compute priority score ───────────────────────────────
        try:
            disaster.compute_priority()
            logger.warning(f"🟠 Priority score set to {disaster.priority_score}")
        except Exception as e:
            logger.warning(f"❌ Priority calculation error: {e}")

        # ── Step 6: OSM routing dispatch ──────────────────────────────────
        if disaster.latitude and disaster.longitude:
            try:
                _run_dispatch(disaster)
            except Exception as e:
                logger.warning(f"❌ Dispatch error: {e}")
        else:
            logger.warning("⚠️ Skipping dispatch - no coordinates available")

        # ── Step 7: Mark as analyzed (after dispatch so UI updates together)
        disaster.status = 'analyzed'
        disaster.save()

        return {'success': True, 'disaster_id': disaster_id}

    except Exception as e:
        logger.warning(f"❌ Fatal error analyzing disaster {disaster_id}: {e}")
        return {'success': False, 'error': str(e)}


def _run_dispatch(disaster):
    """
    Run road routing and create DispatchDecision records.
    Uses cached road network + pre-filters by straight-line distance
    to only route the closest N candidates instead of all 100+.
    """
    disaster_coords = (disaster.latitude, disaster.longitude)
    CANDIDATES = 8  # only route closest N by straight-line distance

    try:
        router = _get_router()
    except Exception as e:
        logger.warning(f"❌ Failed to load road network: {e}")
        return

    # ── Fire station dispatch ─────────────────────────────────────────────
    try:
        stations = list(FireStation.objects.filter(operational=True))
        if not stations:
            logger.warning("⚠️ No operational fire stations in DB — run seed_chicago_resources")
        else:
            # Pre-filter: sort by straight-line distance, keep closest N
            stations_sorted = sorted(
                stations,
                key=lambda s: _haversine_km(disaster.latitude, disaster.longitude, s.latitude, s.longitude)
            )
            candidates = stations_sorted[:CANDIDATES]
            logger.warning(f"🚒 Routing {len(candidates)} nearest fire stations (of {len(stations)} total)")

            best_fire = None
            best_fire_dist = float('inf')
            best_fire_route = None

            for station in candidates:
                try:
                    route = router.find_shortest_route(
                        (station.latitude, station.longitude),
                        disaster_coords
                    )
                    if route['success'] and route['distance'] < best_fire_dist:
                        best_fire_dist = route['distance']
                        best_fire = station
                        best_fire_route = route
                except Exception:
                    continue

            if best_fire and best_fire_route:
                distance_km = best_fire_dist / 1000
                eta_minutes = round((distance_km / 30) * 60 + 2, 1)

                route_coords = []
                try:
                    route_coords = [
                        [router.graph.nodes[n]['y'], router.graph.nodes[n]['x']]
                        for n in best_fire_route.get('route_nodes', [])
                    ]
                except Exception:
                    pass

                DispatchDecision.objects.create(
                    disaster=disaster,
                    dispatch_type='fire',
                    fire_station=best_fire,
                    distance_km=distance_km,
                    estimated_arrival_minutes=eta_minutes,
                    route_data={
                        'route_coords': route_coords,
                        'source': 'db_routing',
                    },
                )
                logger.warning(
                    f"✅ Fire dispatch: {best_fire.name} | "
                    f"{distance_km:.2f} km | ETA {eta_minutes} min"
                )
            else:
                logger.warning("⚠️ No reachable fire station found")

    except Exception as e:
        logger.warning(f"❌ Fire dispatch error: {e}")

    # ── Ambulance dispatch ────────────────────────────────────────────────
    try:
        hospitals = list(Hospital.objects.filter(operational=True))
        if not hospitals:
            logger.warning("⚠️ No operational hospitals in DB — run seed_chicago_resources")
        else:
            # Pre-filter: sort by straight-line distance, keep closest N
            hospitals_sorted = sorted(
                hospitals,
                key=lambda h: _haversine_km(disaster.latitude, disaster.longitude, h.latitude, h.longitude)
            )
            candidates = hospitals_sorted[:CANDIDATES]
            logger.warning(f"🏥 Routing {len(candidates)} nearest hospitals (of {len(hospitals)} total)")

            best_hosp = None
            best_hosp_dist = float('inf')
            best_hosp_route = None

            for hospital in candidates:
                try:
                    route = router.find_shortest_route(
                        (hospital.latitude, hospital.longitude),
                        disaster_coords
                    )
                    if route['success'] and route['distance'] < best_hosp_dist:
                        best_hosp_dist = route['distance']
                        best_hosp = hospital
                        best_hosp_route = route
                except Exception:
                    continue

            if best_hosp and best_hosp_route:
                distance_km = best_hosp_dist / 1000
                eta_minutes = round((distance_km / 36) * 60 + 2, 1)

                route_coords = []
                try:
                    route_coords = [
                        [router.graph.nodes[n]['y'], router.graph.nodes[n]['x']]
                        for n in best_hosp_route.get('route_nodes', [])
                    ]
                except Exception:
                    pass

                DispatchDecision.objects.create(
                    disaster=disaster,
                    dispatch_type='ambulance',
                    hospital=best_hosp,
                    distance_km=distance_km,
                    estimated_arrival_minutes=eta_minutes,
                    route_data={
                        'route_coords': route_coords,
                        'source': 'db_routing',
                    },
                )
                logger.warning(
                    f"✅ Ambulance dispatch: {best_hosp.name} | "
                    f"{distance_km:.2f} km | ETA {eta_minutes} min"
                )
            else:
                logger.warning("⚠️ No reachable hospital found")

    except Exception as e:
        logger.warning(f"❌ Ambulance dispatch error: {e}")