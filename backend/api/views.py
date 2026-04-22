from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Disaster, FireStation, Hospital, DispatchDecision
from .serializers import DisasterSerializer, FireStationSerializer, DispatchDecisionSerializer
from .ml.priority_model import calculate_priority
from .models import Disaster, FireStation, Hospital, DispatchDecision
from django.db import models
import math


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _estimate_response_time_minutes(lat, lon, response_type):
    response_type = (response_type or "").strip().lower()
    if response_type in ("fire", "fire_truck", "fire truck"):
        candidates = FireStation.objects.filter(operational=True)
        speed_km_per_min = 0.5
        dispatch_buffer = 2.0
    elif response_type in ("ambulance", "medical"):
        candidates = Hospital.objects.filter(operational=True)
        speed_km_per_min = 0.6
        dispatch_buffer = 2.0
    else:
        return 15.0

    nearest_distance = None
    for c in candidates:
        dist = _haversine_km(lat, lon, c.latitude, c.longitude)
        if nearest_distance is None or dist < nearest_distance:
            nearest_distance = dist

    if nearest_distance is None:
        return 20.0
    return round(dispatch_buffer + nearest_distance / max(speed_km_per_min, 0.1), 2)


def _default_severity(disaster_type):
    key = (disaster_type or "").strip().lower()
    return {"fire": 3.0, "flood": 2.6, "earthquake": 4.0}.get(key, 2.5)


def _estimate_population(lat, lon):
    try:
        from .ml.population_model import PopulationDensityModel
        pop_model = PopulationDensityModel()
        pop_model.load_census_data("chi_pop.csv")
        result = pop_model.estimate_for_location(lat, lon, radius_meters=500)
        return int(result.get("total_population", 0)) if result else 0
    except Exception:
        return 0


# ── Disaster endpoints ────────────────────────────────────────────────────────

@api_view(['POST'])
def report_disaster(request):
    data = request.data.copy()
    data['disaster_type'] = data.get('disaster_type', 'fire').lower()
    serializer = DisasterSerializer(data=data)
    if serializer.is_valid():
        disaster = serializer.save()
        from .tasks import analyze_disaster
        analyze_disaster.delay(disaster.id)
        return Response({'disaster_id': disaster.id, 'status': 'reported'}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_disaster(request, disaster_id):
    try:
        disaster = Disaster.objects.get(id=disaster_id)
        serializer = DisasterSerializer(disaster)
        return Response(serializer.data)
    except Disaster.DoesNotExist:
        return Response({'error': 'Disaster not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def get_active_disasters(request):
    disasters = Disaster.objects.exclude(status='resolved')
    return Response(DisasterSerializer(disasters, many=True).data)


@api_view(['GET'])
def get_fire_stations(request):
    stations = FireStation.objects.filter(operational=True)
    return Response(FireStationSerializer(stations, many=True).data)


@api_view(['POST'])
def resolve_disaster(request, disaster_id):
    try:
        disaster = Disaster.objects.get(id=disaster_id)
        from django.utils import timezone
        disaster.status = 'resolved'
        disaster.resolution_notes = request.data.get('resolution_notes', '')
        disaster.resolved_at = timezone.now()
        disaster.save()
        return Response({'success': True, 'message': 'Incident resolved'})
    except Disaster.DoesNotExist:
        return Response({'error': 'Disaster not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def get_resolved_disasters(request):
    disasters = Disaster.objects.filter(status='resolved')
    return Response(DisasterSerializer(disasters, many=True).data)


# ── NEW: Dispatch results endpoint ────────────────────────────────────────────

@api_view(['GET'])
def get_dispatch(request, disaster_id):
    """
    Return all DispatchDecision records for a given disaster.

    Response shape:
    {
      "disaster_id": 5,
      "dispatched": true,
      "decisions": [
        {
          "dispatch_type": "fire",
          "station_name": "Engine 42",
          "distance_km": 1.3,
          "estimated_arrival_minutes": 4.6,
          "route_data": { ... }
        },
        ...
      ]
    }
    """
    try:
        disaster = Disaster.objects.get(id=disaster_id)
    except Disaster.DoesNotExist:
        return Response({'error': 'Disaster not found'}, status=status.HTTP_404_NOT_FOUND)

    decisions = DispatchDecision.objects.filter(disaster=disaster)

    result = []
    for d in decisions:
        entry = {
            'id': d.id,
            'dispatch_type': d.dispatch_type,
            'distance_km': round(d.distance_km, 2),
            'estimated_arrival_minutes': round(d.estimated_arrival_minutes, 1),
            'dispatched_at': d.dispatched_at,
            'route_data': d.route_data,
        }
        if d.fire_station:
            entry['station_name'] = d.fire_station.name
            entry['station_address'] = d.fire_station.address
            entry['station_coords'] = [d.fire_station.latitude, d.fire_station.longitude]
        if d.hospital:
            entry['station_name'] = d.hospital.name
            entry['station_coords'] = [d.hospital.latitude, d.hospital.longitude]

        result.append(entry)

    return Response({
        'disaster_id': disaster_id,
        'dispatched': len(result) > 0,
        'decisions': result,
    })


# ── Batch priority endpoint ───────────────────────────────────────────────────

@api_view(['POST'])
def batch_priority_calculation(request):
    """
    Calculate ranked priorities for multiple locations.
    Expected payload: { "incidents": [ { "location": "...", ... } ] }
    """
    incidents = request.data.get('incidents')
    if not isinstance(incidents, list) or not incidents:
        return Response(
            {'error': 'incidents must be a non-empty list'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent='trishul_batch_priority_v1', timeout=10)
    except Exception:
        geolocator = None

    results = []
    for idx, item in enumerate(incidents):
        location = (item.get('location') or '').strip()
        if not location:
            results.append({'index': idx, 'location': '', 'error': 'location is required'})
            continue

        disaster_type = (item.get('disaster_type') or 'fire').strip().lower()
        response_type = (item.get('response_type') or 'fire').strip().lower()

        try:
            severity_score = float(item.get('severity_score', _default_severity(disaster_type)))
        except (TypeError, ValueError):
            severity_score = _default_severity(disaster_type)

        lat = item.get('latitude')
        lon = item.get('longitude')
        if (lat is None or lon is None) and geolocator:
            try:
                geo = geolocator.geocode(f'{location}, Chicago, IL')
            except Exception:
                geo = None
            if geo:
                lat, lon = geo.latitude, geo.longitude

        if lat is None or lon is None:
            results.append({
                'index': idx, 'location': location,
                'disaster_type': disaster_type, 'response_type': response_type,
                'severity_score': severity_score, 'error': 'could not geocode location',
            })
            continue

        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            results.append({'index': idx, 'location': location, 'error': 'lat/lon must be numeric'})
            continue

        population_affected = int(item['population_affected']) if item.get('population_affected') is not None else _estimate_population(lat, lon)
        response_time_minutes = float(item['response_time_minutes']) if item.get('response_time_minutes') is not None else _estimate_response_time_minutes(lat, lon, response_type)
        priority_score = calculate_priority(severity_score, population_affected, response_time_minutes)

        results.append({
            'index': idx, 'location': location,
            'disaster_type': disaster_type, 'response_type': response_type,
            'latitude': lat, 'longitude': lon,
            'severity_score': severity_score,
            'population_affected': population_affected,
            'response_time_minutes': response_time_minutes,
            'priority_score': round(priority_score, 4),
        })

    ranked = sorted(
        [r for r in results if 'priority_score' in r],
        key=lambda x: x['priority_score'], reverse=True,
    )
    for rank, row in enumerate(ranked, start=1):
        row['rank'] = rank

    return Response({
        'count': len(results),
        'ranked_count': len(ranked),
        'results': ranked,
        'errors': [r for r in results if 'error' in r],
    })


@api_view(['GET'])
def get_analytics(request):
    """
    Return real analytics data computed from the database.
    """
    from django.db.models import Avg, Count, Q
    from .models import Disaster, DispatchDecision, Hospital, FireStation

    # ── Active vs resolved counts ─────────────────────────────────────────
    active_count   = Disaster.objects.filter(status='analyzed').count()
    resolved_count = Disaster.objects.filter(status='resolved').count()
    total_count    = active_count + resolved_count

    # ── Average severity (all analyzed + resolved) ────────────────────────
    severity_agg = Disaster.objects.filter(
        status__in=['analyzed', 'resolved'],
        severity_score__gt=0
    ).aggregate(avg=Avg('severity_score'))
    avg_severity = round(severity_agg['avg'] or 0, 2)

    # ── Average AI confidence (use as AI accuracy proxy) ─────────────────
    confidence_agg = Disaster.objects.filter(
        status__in=['analyzed', 'resolved'],
        confidence_score__gt=0
    ).aggregate(avg=Avg('confidence_score'))
    avg_confidence = round(confidence_agg['avg'] or 0, 1)

    # ── Average response time from dispatch decisions ─────────────────────
    response_agg = DispatchDecision.objects.aggregate(
        avg=Avg('estimated_arrival_minutes')
    )
    avg_response_time = round(response_agg['avg'] or 0, 1)

    # ── Dispatch counts by type ───────────────────────────────────────────
    fire_dispatches      = DispatchDecision.objects.filter(dispatch_type='fire').count()
    ambulance_dispatches = DispatchDecision.objects.filter(dispatch_type='ambulance').count()

    # ── Resource availability ─────────────────────────────────────────────
    total_trucks     = FireStation.objects.filter(operational=True).aggregate(
        total=models.Sum('available_trucks')
    )['total'] or 0
    total_ambulances = Hospital.objects.filter(operational=True).aggregate(
        total=models.Sum('available_ambulances')
    )['total'] or 0

    # ── Incident type breakdown ───────────────────────────────────────────
    type_breakdown = list(
        Disaster.objects.values('disaster_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    return Response({
        'incidents': {
            'active':   active_count,
            'resolved': resolved_count,
            'total':    total_count,
        },
        'avg_severity':       avg_severity,
        'avg_confidence_pct': avg_confidence,
        'avg_response_time_minutes': avg_response_time,
        'dispatches': {
            'fire':      fire_dispatches,
            'ambulance': ambulance_dispatches,
            'total':     fire_dispatches + ambulance_dispatches,
        },
        'resources': {
            'fire_trucks':  total_trucks,
            'ambulances':   total_ambulances,
        },
        'type_breakdown': type_breakdown,
    })


@api_view(['GET'])
def get_hospitals(request):
    hospitals = Hospital.objects.all()
    data = [{
        'id': h.id,
        'name': h.name,
        'latitude': h.latitude,
        'longitude': h.longitude,
        'available_ambulances': h.available_ambulances,
        'operational': h.operational,
    } for h in hospitals]
    return Response({'count': len(data), 'hospitals': data})