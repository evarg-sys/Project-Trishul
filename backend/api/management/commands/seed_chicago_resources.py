"""
Management command to seed all real Chicago fire stations and hospitals
from OpenStreetMap into the database.

Run once:
    python3 manage.py seed_chicago_resources

This populates the FireStation and Hospital tables with every real
resource in Chicago so dispatch never needs to query OSM at incident time.
"""

from django.core.management.base import BaseCommand
from api.models import FireStation, Hospital


class Command(BaseCommand):
    help = "Seed all Chicago fire stations and hospitals from OpenStreetMap"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing records before seeding",
        )

    def handle(self, *args, **options):
        try:
            import osmnx as ox
        except ImportError:
            self.stderr.write("osmnx is not installed. Run: pip install osmnx")
            return

        # Use the faster Overpass endpoint
        ox.settings.overpass_endpoint = "https://overpass.kumi.systems/api/interpreter"
        ox.settings.timeout = 60

        city = "Chicago, Illinois, USA"

        if options["clear"]:
            FireStation.objects.all().delete()
            Hospital.objects.all().delete()
            self.stdout.write("Cleared existing records.")

        # ── Fire Stations ─────────────────────────────────────────────────
        self.stdout.write("Querying OSM for Chicago fire stations...")
        try:
            gdf = ox.features_from_place(city, tags={"amenity": "fire_station"})
            stations_added = 0
            stations_skipped = 0

            for _, row in gdf.iterrows():
                try:
                    geom = row.geometry
                    if geom is None or geom.is_empty:
                        continue
                    centroid = geom.centroid
                    lat = centroid.y
                    lng = centroid.x
                    name = row.get("name") or "Unnamed Fire Station"

                    # Skip if already exists by name+coords
                    exists = FireStation.objects.filter(
                        name=name,
                        latitude__range=(lat - 0.001, lat + 0.001),
                        longitude__range=(lng - 0.001, lng + 0.001),
                    ).exists()

                    if exists:
                        stations_skipped += 1
                        continue

                    FireStation.objects.create(
                        name=name,
                        address=row.get("addr:full") or row.get("addr:street") or name,
                        latitude=lat,
                        longitude=lng,
                        available_trucks=3,
                        operational=True,
                    )
                    stations_added += 1
                    self.stdout.write(f"  ✅ Fire station: {name}")

                except Exception as e:
                    self.stdout.write(f"  ⚠️ Skipping row: {e}")
                    continue

            self.stdout.write(
                self.style.SUCCESS(
                    f"Fire stations: {stations_added} added, {stations_skipped} already existed"
                )
            )

        except Exception as e:
            self.stderr.write(f"❌ Failed to fetch fire stations: {e}")

        # ── Hospitals ─────────────────────────────────────────────────────
        self.stdout.write("\nQuerying OSM for Chicago hospitals...")
        try:
            gdf = ox.features_from_place(city, tags={"amenity": "hospital"})
            hospitals_added = 0
            hospitals_skipped = 0

            for _, row in gdf.iterrows():
                try:
                    geom = row.geometry
                    if geom is None or geom.is_empty:
                        continue
                    centroid = geom.centroid
                    lat = centroid.y
                    lng = centroid.x
                    name = row.get("name") or "Unnamed Hospital"

                    exists = Hospital.objects.filter(
                        name=name,
                        latitude__range=(lat - 0.001, lat + 0.001),
                        longitude__range=(lng - 0.001, lng + 0.001),
                    ).exists()

                    if exists:
                        hospitals_skipped += 1
                        continue

                    Hospital.objects.create(
                        name=name,
                        latitude=lat,
                        longitude=lng,
                        available_ambulances=5,
                        operational=True,
                    )
                    hospitals_added += 1
                    self.stdout.write(f"  ✅ Hospital: {name}")

                except Exception as e:
                    self.stdout.write(f"  ⚠️ Skipping row: {e}")
                    continue

            self.stdout.write(
                self.style.SUCCESS(
                    f"Hospitals: {hospitals_added} added, {hospitals_skipped} already existed"
                )
            )

        except Exception as e:
            self.stderr.write(f"❌ Failed to fetch hospitals: {e}")

        # ── Summary ───────────────────────────────────────────────────────
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. DB now has:\n"
                f"  {FireStation.objects.count()} fire stations\n"
                f"  {Hospital.objects.count()} hospitals"
            )
        )