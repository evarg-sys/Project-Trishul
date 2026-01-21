from django.db import models

class Disaster(models.Model):
    """Main disaster record"""
    DISASTER_TYPES = [
        ('fire', 'Fire'),
        ('earthquake', 'Earthquake'),
        ('flood', 'Flood'),
    ]
    
    # Input data
    disaster_type = models.CharField(max_length=20, choices=DISASTER_TYPES)
    address = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True)
    
    # ML-calculated data
    severity_score = models.FloatField(default=0)
    confidence_score = models.FloatField(default=0)
    population_affected = models.IntegerField(default=0)
    priority_score = models.FloatField(default=0)
    
    # Status
    status = models.CharField(max_length=20, default='reported')
    reported_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-priority_score', '-reported_at']
    
    def __str__(self):
        return f"{self.disaster_type.upper()} at {self.address}"


class FireStation(models.Model):
    """Fire station"""
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    available_trucks = models.IntegerField(default=3)
    operational = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name


class Hospital(models.Model):
    """Hospital"""
    name = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    available_ambulances = models.IntegerField(default=5)
    operational = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name


class DispatchDecision(models.Model):
    """Records dispatch decisions"""
    DISPATCH_TYPES = [
        ('fire', 'Fire Truck'),
        ('ambulance', 'Ambulance'),
    ]
    
    disaster = models.ForeignKey(Disaster, on_delete=models.CASCADE, related_name='dispatches')
    dispatch_type = models.CharField(max_length=20, choices=DISPATCH_TYPES)
    fire_station = models.ForeignKey(FireStation, on_delete=models.SET_NULL, null=True, blank=True)
    hospital = models.ForeignKey(Hospital, on_delete=models.SET_NULL, null=True, blank=True)
    distance_km = models.FloatField()
    estimated_arrival_minutes = models.FloatField()
    route_data = models.JSONField()
    dispatched_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        station = self.fire_station.name if self.fire_station else self.hospital.name
        return f"{self.dispatch_type} from {station}"