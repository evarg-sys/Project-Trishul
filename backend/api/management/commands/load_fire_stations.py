from django.core.management.base import BaseCommand
from api.models import FireStation

class Command(BaseCommand):
    help = 'Load Chicago fire stations into database'

    def handle(self, *args, **kwargs):
        stations = [
            {"name": "Engine 42", "address": "55 W Illinois St", "latitude": 41.8906, "longitude": -87.6311, "available_trucks": 3},
            {"name": "Engine 13", "address": "201 S Dearborn St", "latitude": 41.8781, "longitude": -87.6298, "available_trucks": 2},
            {"name": "Engine 78", "address": "1052 W Columbia Ave", "latitude": 41.9207, "longitude": -87.6567, "available_trucks": 4},
            {"name": "Engine 5", "address": "214 W Erie St", "latitude": 41.8937, "longitude": -87.6350, "available_trucks": 3},
        ]
        
        for s in stations:
            FireStation.objects.get_or_create(
                name=s["name"],
                defaults=s
            )
        
        self.stdout.write(self.style.SUCCESS(f'✅ Loaded {len(stations)} fire stations'))
