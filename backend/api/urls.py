from django.urls import path
from . import views

urlpatterns = [
    path('disasters/', views.report_disaster, name='report_disaster'),
    path('disasters/active/', views.get_active_disasters, name='active_disasters'),
    path('disasters/resolved/', views.get_resolved_disasters, name='resolved_disasters'),
    path('disasters/<int:disaster_id>/', views.get_disaster, name='get_disaster'),
    path('disasters/<int:disaster_id>/resolve/', views.resolve_disaster, name='resolve_disaster'),
    path('disasters/<int:disaster_id>/dispatch/', views.get_dispatch, name='get_dispatch'),
    path('fire-stations/', views.get_fire_stations, name='fire_stations'),
    path('analytics/', views.get_analytics, name='analytics'),
    path('priority/batch/', views.batch_priority_calculation, name='batch_priority_calculation'),
]