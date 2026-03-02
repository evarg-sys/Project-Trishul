from django.contrib import admin
from .models import Disaster, FireStation, Hospital, DispatchDecision

admin.site.register(Disaster)
admin.site.register(FireStation)
admin.site.register(Hospital)
admin.site.register(DispatchDecision)