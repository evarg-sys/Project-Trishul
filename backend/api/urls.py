from django.urls import path
from . import views

urlpatterns = [
    path('disasters/', views.report_disaster, name='report_disaster'),
    path('disasters/<int:disaster_id>/', views.get_disaster, name='get_disaster'),
    path('disasters/active/', views.get_active_disasters, name='active_disasters'),
    path('fire-stations/', views.get_fire_stations, name='fire_stations'),
]
