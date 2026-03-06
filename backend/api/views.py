from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Disaster, FireStation, Hospital
from .serializers import DisasterSerializer, FireStationSerializer
from .ml.priority_model import calculate_priority
import math


def _haversine_km(lat1, lon1, lat2, lon2):
    """Return great-circle distance in kilometers between two points."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def _estimate_response_time_minutes(lat, lon, response_type):
    """Estimate response time by nearest resource using simple geo distance."""
    response_type = (response_type or "").strip().lower()

    if response_type in ("fire", "fire_truck", "fire truck"):
        candidates = FireStation.objects.filter(operational=True)
        speed_km_per_min = 0.5  # ~30 km/h
        dispatch_buffer = 2.0
    elif response_type in ("ambulance", "medical"):
        candidates = Hospital.objects.filter(operational=True)
        speed_km_per_min = 0.6  # ~36 km/h
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

    travel = nearest_distance / max(speed_km_per_min, 0.1)
    return round(dispatch_buffer + travel, 2)


def _default_severity(disaster_type):
    """Fallback severity when caller does not provide a score."""
    key = (disaster_type or "").strip().lower()
    mapping = {
        "fire": 3.0,
        "flood": 2.6,
        "earthquake": 4.0,
    }
    return mapping.get(key, 2.5)


def _estimate_population(lat, lon):
    """Estimate affected population around location using existing model."""
    try:
        from .ml.population_model import PopulationDensityModel

        pop_model = PopulationDensityModel()
        pop_model.load_census_data("chi_pop.csv")
        result = pop_model.estimate_for_location(lat, lon, radius_meters=500)
        if not result:
            return 0
        return int(result.get("total_population", 0))
    except Exception:
        return 0


@api_view(['POST'])
def report_disaster(request):
    """Report a new disaster"""
    data = request.data.copy()
    data['disaster_type'] = data.get('disaster_type', 'fire').lower()
    serializer = DisasterSerializer(data=data)
    if serializer.is_valid():
        disaster = serializer.save()
        from .tasks import analyze_disaster
        analyze_disaster.delay(disaster.id)
        return Response({
            'disaster_id': disaster.id,
            'status': 'reported'
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_disaster(request, disaster_id):
    """Get disaster details"""
    try:
        disaster = Disaster.objects.get(id=disaster_id)
        serializer = DisasterSerializer(disaster)
        return Response(serializer.data)
    except Disaster.DoesNotExist:
        return Response({'error': 'Disaster not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def get_active_disasters(request):
    """Get all active disasters"""
    disasters = Disaster.objects.exclude(status='resolved')
    serializer = DisasterSerializer(disasters, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def get_fire_stations(request):
    """Get all fire stations"""
    stations = FireStation.objects.filter(operational=True)
    serializer = FireStationSerializer(stations, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def resolve_disaster(request, disaster_id):
    """Resolve a disaster"""
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
    """Get all resolved disasters"""
    disasters = Disaster.objects.filter(status='resolved')
    serializer = DisasterSerializer(disasters, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def batch_priority_calculation(request):
    """Calculate ranked priorities for multiple locations.

    Expected payload:
    {
      "incidents": [
        {
          "location": "233 S Wacker Dr, Chicago",
          "disaster_type": "fire",
          "response_type": "fire",
          "severity_score": 3.5
        }
      ]
    }
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
        if lat is None or lon is None:
            if geolocator:
                try:
                    geo = geolocator.geocode(f'{location}, Chicago, IL')
                except Exception:
                    geo = None
                if geo:
                    lat = geo.latitude
                    lon = geo.longitude

        if lat is None or lon is None:
            results.append({
                'index': idx,
                'location': location,
                'disaster_type': disaster_type,
                'response_type': response_type,
                'severity_score': severity_score,
                'error': 'could not geocode location',
            })
            continue

        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            results.append({'index': idx, 'location': location, 'error': 'latitude/longitude must be numeric'})
            continue

        if item.get('population_affected') is not None:
            try:
                population_affected = int(item.get('population_affected'))
            except (TypeError, ValueError):
                population_affected = 0
        else:
            population_affected = _estimate_population(lat, lon)

        if item.get('response_time_minutes') is not None:
            try:
                response_time_minutes = float(item.get('response_time_minutes'))
            except (TypeError, ValueError):
                response_time_minutes = _estimate_response_time_minutes(lat, lon, response_type)
        else:
            response_time_minutes = _estimate_response_time_minutes(lat, lon, response_type)

        priority_score = calculate_priority(severity_score, population_affected, response_time_minutes)

        results.append({
            'index': idx,
            'location': location,
            'disaster_type': disaster_type,
            'response_type': response_type,
            'latitude': lat,
            'longitude': lon,
            'severity_score': severity_score,
            'population_affected': population_affected,
            'response_time_minutes': response_time_minutes,
            'priority_score': round(priority_score, 4),
        })

    ranked = sorted(
        [r for r in results if 'priority_score' in r],
        key=lambda x: x['priority_score'],
        reverse=True,
    )

    for rank, row in enumerate(ranked, start=1):
        row['rank'] = rank

    return Response({
        'count': len(results),
        'ranked_count': len(ranked),
        'results': ranked,
        'errors': [r for r in results if 'error' in r],
    })