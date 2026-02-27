from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Disaster, FireStation, Hospital
from .serializers import DisasterSerializer, FireStationSerializer

@api_view(['POST'])
def report_disaster(request):
    """Report a new disaster"""
    serializer = DisasterSerializer(data=request.data)
    if serializer.is_valid():
        disaster = serializer.save()

        from .tasks import analyze_disaster
        analyze_disaster.delay(disaster.id) # Basically triggers the ml analysis in the background

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
