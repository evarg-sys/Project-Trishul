from django.test import TestCase
from rest_framework.test import APIClient
from .models import Disaster

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
