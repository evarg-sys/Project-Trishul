import sys
sys.path.append('../..')  # Go up two levels to reach disaster_routing.py
from disaster_routing import DisasterRouting

# Initialize routing system
print("Initializing routing system...")
router = DisasterRouting("Chicago, Illinois, USA")

# Load the network (this will take a minute)
print("Loading Chicago road network from OSM...")
router.load_network()

print("\nSetup complete! Ready to calculate routes.")