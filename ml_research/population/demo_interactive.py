#!/usr/bin/env python
"""Demo script showing interactive location input"""

# Simulate user input for interactive mode
interactive_demo = """
42.3601
-71.0589
500
"""

import subprocess
import sys
from pathlib import Path

print("=" * 70)
print("INTERACTIVE MODE DEMO - Boston Location")
print("=" * 70)
print("\nSimulating user input:")
print("  Latitude: 42.3601 (Boston)")
print("  Longitude: -71.0589")
print("  Radius: 500 meters")
print("\n" + "-" * 70 + "\n")

try:
    # Run interactive mode with simulated input
    result = subprocess.run(
        [sys.executable, "population_model.py", "--interactive"],
        input=interactive_demo,
        capture_output=True,
        text=True,
        timeout=60
    )
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
except subprocess.TimeoutExpired:
    print("Process timed out")
except Exception as e:
    print(f"Error: {e}")
