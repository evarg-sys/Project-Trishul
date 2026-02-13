from rest_framework import serializers
from .models import Disaster, FireStation, Hospital, DispatchDecision

class FireStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FireStation
        fields = '__all__'

class HospitalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hospital
        fields = '__all__'

class DispatchDecisionSerializer(serializers.ModelSerializer):
    fire_station = FireStationSerializer(read_only=True)
    hospital = HospitalSerializer(read_only=True)
    
    class Meta:
        model = DispatchDecision
        fields = '__all__'

class DisasterSerializer(serializers.ModelSerializer):
    dispatches = DispatchDecisionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Disaster
        fields = '__all__'
