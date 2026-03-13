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
    resolution_notes = models.TextField(blank=True, default='')
    resolved_at = models.DateTimeField(null=True, blank=True)
    reported_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-priority_score', '-reported_at']
    
    def __str__(self):
        return f"{self.disaster_type.upper()} at {self.address}"

    def compute_priority(self, response_time_minutes: float | None = None) -> float:
        """Calculate and store a priority score for the disaster.

        The base score is simply ``severity_score * population_affected``.
        If a response time is provided we divide by it so that incidents
        which can be reached quickly are elevated in priority.

        The value is written back to :attr:`priority_score` and also
        returned so callers can use it without querying the database
        again.

        :param response_time_minutes: Estimated arrival time in minutes
                                       for the closest resource. If not
                                       provided the score is just the
                                       product of severity and population.
        :returns: the calculated priority score
        """
        # Keep the formula in one dedicated module so model/task code stay
        # consistent if the scoring logic evolves.
        from .ml.priority_model import calculate_priority

        self.priority_score = calculate_priority(
            self.severity_score,
            self.population_affected,
            response_time_minutes,
        )
        # don't save automatically in case the caller wants to make other
        # modifications first, but the common path in ``analyze_disaster``
        # will explicitly save immediately after calling this method.
        return self.priority_score


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