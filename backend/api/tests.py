from django.test import TestCase
from rest_framework.test import APIClient
from django.core.management import call_command
from io import StringIO
from .models import Disaster, FireStation, Hospital
from .ml.text_priority_parser import parse_incident_text
from .ml.incident_analysis import analyze_and_plan_incident

# Create your tests here.

class PriorityModelTests(TestCase):
    def test_compute_priority_without_response_time(self):
        d = Disaster.objects.create(
            disaster_type='fire',
            address='123 Main St',
            severity_score=2.5,
            population_affected=1000,
        )
        score = d.compute_priority()
        self.assertEqual(score, 2.5 * 1000)
        self.assertEqual(d.priority_score, score)

    def test_compute_priority_with_response_time(self):
        d = Disaster.objects.create(
            disaster_type='flood',
            address='456 Elm St',
            severity_score=1.0,
            population_affected=500,
        )
        score = d.compute_priority(response_time_minutes=5)
        self.assertAlmostEqual(score, (1.0 * 500) / 5)
        self.assertAlmostEqual(d.priority_score, score)

    def test_priority_model_module(self):
        # verify the standalone calculation function behaves identically
        from .ml.priority_model import calculate_priority
        a = calculate_priority(2.0, 1000)
        b = calculate_priority(2.0, 1000, response_time=10)
        self.assertEqual(a, 2000)
        self.assertEqual(b, 2000 / 10)

    def test_priority_ordering_highest_first(self):
        low = Disaster.objects.create(
            disaster_type='fire',
            address='A',
            severity_score=1.0,
            population_affected=100,
        )
        high = Disaster.objects.create(
            disaster_type='flood',
            address='B',
            severity_score=3.0,
            population_affected=200,
        )
        low.compute_priority()
        high.compute_priority()
        low.save()
        high.save()

        ordered = list(Disaster.objects.all())
        self.assertEqual(ordered[0].id, high.id)
        self.assertEqual(ordered[1].id, low.id)


class BatchPriorityApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_batch_priority_returns_ranked_results(self):
        payload = {
            'incidents': [
                {
                    'location': 'Location A',
                    'disaster_type': 'fire',
                    'response_type': 'fire',
                    'severity_score': 3,
                    'latitude': 41.88,
                    'longitude': -87.63,
                    'population_affected': 500,
                    'response_time_minutes': 10,
                },
                {
                    'location': 'Location B',
                    'disaster_type': 'flood',
                    'response_type': 'ambulance',
                    'severity_score': 4,
                    'latitude': 41.90,
                    'longitude': -87.65,
                    'population_affected': 1200,
                    'response_time_minutes': 8,
                },
            ]
        }

        res = self.client.post('/api/priority/batch/', payload, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['ranked_count'], 2)
        self.assertEqual(len(res.data['results']), 2)
        # Result B should rank first: 4*1200/8 = 600 > 3*500/10 = 150
        self.assertEqual(res.data['results'][0]['location'], 'Location B')
        self.assertEqual(res.data['results'][0]['rank'], 1)
        self.assertEqual(res.data['results'][1]['rank'], 2)

    def test_batch_priority_rejects_empty_payload(self):
        res = self.client.post('/api/priority/batch/', {'incidents': []}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('error', res.data)


class TextPriorityInputTests(TestCase):
    def test_parse_incident_text_extracts_core_fields(self):
        text = "Big fire at 55 W Illinois St lots of people hurt need fire truck"
        parsed = parse_incident_text(text)

        self.assertEqual(parsed['disaster_type'], 'fire')
        self.assertEqual(parsed['response_type'], 'fire')
        self.assertEqual(parsed['response_types'], ['fire', 'ambulance'])
        self.assertIn('55 W Illinois', parsed['location'])
        self.assertGreater(parsed['severity_score'], 3.0)
        self.assertGreater(parsed['population_affected'], 100)

    def test_priority_from_text_command_ranks_multiple_inputs(self):
        out = StringIO()
        call_command(
            'priority_from_text',
            '--text', 'small fire at 1 Main St few people hurt',
            '--text', 'major fire at 200 Lake Shore Dr lots of people hurt urgent',
            stdout=out,
        )
        output = out.getvalue()

        self.assertIn('Priority Ranking', output)
        self.assertIn('#1 | priority=', output)
        self.assertIn('major fire at 200 Lake Shore Dr', output)

    def test_parse_incident_text_pileup_maps_to_ambulance(self):
        parsed = parse_incident_text('10 car pile up on I-90 near downtown')
        self.assertEqual(parsed['disaster_type'], 'traffic_collision')
        self.assertEqual(parsed['response_type'], 'ambulance')
        self.assertEqual(parsed['response_types'], ['ambulance', 'fire', 'police'])
        self.assertGreaterEqual(parsed['population_affected'], 20)


class IncidentPlanningTests(TestCase):
    def setUp(self):
        FireStation.objects.create(
            name='Central Station',
            address='100 Main St',
            latitude=41.88,
            longitude=-87.63,
            available_trucks=4,
            operational=True,
        )
        Hospital.objects.create(
            name='Metro Hospital',
            latitude=41.89,
            longitude=-87.62,
            available_ambulances=3,
            operational=True,
        )

    def test_multi_vehicle_pileup_requires_ambulance(self):
        result = analyze_and_plan_incident(
            text='10 car pile up on I-90 near downtown',
            latitude=41.88,
            longitude=-87.63,
        )

        analysis = result['analysis']
        capability = result['capability_match']

        self.assertEqual(analysis['response_type'], 'ambulance')
        self.assertEqual(analysis['response_types'], ['ambulance', 'fire', 'police'])
        self.assertEqual(analysis['incident_category'], 'traffic_collision')
        self.assertGreaterEqual(capability['required_roles'].get('ems', 0), 2)
        self.assertIn('ems', capability['eligible_units'])

    def test_low_confidence_triggers_downgrade_and_review(self):
        result = analyze_and_plan_incident(
            text='there is something strange happening near the river please help',
            latitude=41.88,
            longitude=-87.63,
        )

        self.assertTrue(result['cases']['low_confidence_input'])
        self.assertTrue(result['actions']['downgrade_plan'])
        self.assertTrue(result['actions']['escalate_to_operator_review'])
        self.assertGreaterEqual(len(result['alerts']), 1)
