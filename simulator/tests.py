import json
from django.test import TestCase, Client
from django.urls import reverse
from .models import Process, SimulationState, SimulationLog
from .services import SimulationEngine
from .memory_manager import MemoryManager


class MemoryManagerTestCase(TestCase):
    def setUp(self):
        self.mgr = MemoryManager(total_memory=1024)

    def test_empty_memory_layout(self):
        blocks = self.mgr.get_memory_layout([])
        self.assertEqual(len(blocks), 1)
        self.assertTrue(blocks[0].is_free)
        self.assertEqual(blocks[0].size, 1024)

    def test_allocation_first_fit(self):
        allocated, start, end = self.mgr.allocate(256, [], 'FIRST_FIT')
        self.assertTrue(allocated)
        self.assertEqual(start, 0)
        self.assertEqual(end, 256)

    def test_allocation_exceeds_memory(self):
        allocated, start, end = self.mgr.allocate(2048, [], 'FIRST_FIT')
        self.assertFalse(allocated)
        self.assertIsNone(start)


class SimulationEngineTestCase(TestCase):
    def setUp(self):
        self.engine = SimulationEngine()
        self.engine.reset_simulation()

    def test_create_process_admits_when_ram_available(self):
        proc = self.engine.create_process(name="TestProc1", required_memory=256, duration=10)
        self.assertEqual(proc.status, 'RUNNING')
        self.assertEqual(proc.memory_start_address, 0)
        self.assertEqual(proc.memory_end_address, 256)

        stats = self.engine.memory_mgr.get_memory_stats(self.engine.get_running_processes())
        self.assertEqual(stats['used_mb'], 256)
        self.assertEqual(stats['free_mb'], 768)

    def test_process_queued_when_out_of_memory(self):
        # Fill RAM with 512 + 512 = 1024 MB
        p1 = self.engine.create_process(name="Proc1", required_memory=512, duration=10)
        p2 = self.engine.create_process(name="Proc2", required_memory=512, duration=10)
        self.assertEqual(p1.status, 'RUNNING')
        self.assertEqual(p2.status, 'RUNNING')

        # Third process must be queued
        p3 = self.engine.create_process(name="Proc3_Queued", required_memory=256, duration=5)
        self.assertEqual(p3.status, 'WAITING')
        self.assertIsNone(p3.memory_start_address)

        waiting = list(self.engine.get_waiting_processes())
        self.assertEqual(len(waiting), 1)
        self.assertEqual(waiting[0].pid, p3.pid)

    def test_concurrent_execution_and_tick(self):
        p1 = self.engine.create_process(name="Proc1", required_memory=128, duration=5)
        p2 = self.engine.create_process(name="Proc2", required_memory=128, duration=5)

        # Tick 1
        res = self.engine.tick()
        self.assertEqual(res['tick'], 1)

        p1.refresh_from_db()
        p2.refresh_from_db()
        # Both processes must have advanced concurrently
        self.assertEqual(p1.remaining_time, 4)
        self.assertEqual(p2.remaining_time, 4)

    def test_memory_release_and_queue_promotion(self):
        # p1 (512 MB, 2s) and p2 (512 MB, 10s) take all 1024 MB
        p1 = self.engine.create_process(name="ShortProc", required_memory=512, duration=2)
        p2 = self.engine.create_process(name="LongProc", required_memory=512, duration=10)
        # p3 is queued (256 MB)
        p3 = self.engine.create_process(name="QueuedProc", required_memory=256, duration=5)
        self.assertEqual(p3.status, 'WAITING')

        # Tick 1
        self.engine.tick()
        p1.refresh_from_db()
        p3.refresh_from_db()
        self.assertEqual(p1.remaining_time, 1)
        self.assertEqual(p3.status, 'WAITING')

        # Tick 2: p1 finishes, frees 512 MB, p3 should be promoted to RUNNING!
        self.engine.tick()
        p1.refresh_from_db()
        p3.refresh_from_db()

        self.assertEqual(p1.status, 'COMPLETED')
        self.assertIsNone(p1.memory_start_address)
        self.assertEqual(p3.status, 'RUNNING')
        self.assertIsNotNone(p3.memory_start_address)

    def test_manual_termination(self):
        p1 = self.engine.create_process(name="KillMe", required_memory=512, duration=20)
        self.assertEqual(p1.status, 'RUNNING')

        success, msg = self.engine.terminate_process(p1.pid)
        self.assertTrue(success)

        p1.refresh_from_db()
        self.assertEqual(p1.status, 'TERMINATED')
        self.assertIsNone(p1.memory_start_address)

        stats = self.engine.memory_mgr.get_memory_stats(self.engine.get_running_processes())
        self.assertEqual(stats['used_mb'], 0)
        self.assertEqual(stats['free_mb'], 1024)


class ApiEndpointsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.engine = SimulationEngine()
        self.engine.reset_simulation()

    def test_api_status(self):
        response = self.client.get(reverse('simulator:api_status'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('state', data)
        self.assertIn('memory', data)
        self.assertEqual(data['memory']['total_mb'], 1024)

    def test_api_create_process(self):
        response = self.client.post(
            reverse('simulator:api_create_process'),
            data=json.dumps({'name': 'API_App', 'required_memory': 256, 'duration': 8}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status']['counts']['running'], 1)

    def test_api_tick(self):
        self.engine.create_process(name='App1', required_memory=128, duration=5)
        response = self.client.post(reverse('simulator:api_tick'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status']['state']['current_tick'], 1)

    def test_api_reset(self):
        self.engine.create_process(name='App1', required_memory=128, duration=5)
        response = self.client.post(reverse('simulator:api_reset'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status']['counts']['total'], 0)
