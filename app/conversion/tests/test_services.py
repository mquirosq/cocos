from unittest.mock import patch
from types import SimpleNamespace
from django.test import TestCase

from cocos.app.conversion.services import status

class ServiceTests(TestCase):
    def test_is_auto_annotated_assembly(self):
        cases = [
            ('assembly_ont_annotated', True),
            ('assembly_illumina_annotated', True),
            ('assembly_ont', False),
            (None, False),
        ]
        for task_type, expected in cases:
            with self.subTest(task_type=task_type):
                t = SimpleNamespace(task_type=task_type, task_type_original=task_type)
                self.assertEqual(status.is_auto_annotated_assembly(t), expected)

    def test_get_effective_annotation(self):
        a1 = SimpleNamespace(id=1, status='pending', external_job_id='job-1')
        a2 = SimpleNamespace(id=2, status='completed', external_job_id='job-2')
        a3 = SimpleNamespace(id=3, status='failed', external_job_id='job-3')
        cases = [
            ([a1, a2, a3], a2),
            ([a1, a3], a1),
            ([], None),
        ]
        for inputs, expected in cases:
            with self.subTest(inputs=[getattr(x, 'external_job_id', None) for x in inputs]):
                self.assertEqual(status.get_effective_annotation(inputs), expected)

    @patch('conversion.services.source_filename')
    def test_derive_process_name(self, mock_source_filename):
        t = SimpleNamespace(previous_task_id=None, previous_task=None, process_name='foo', input_path='bar')
        self.assertEqual(status.derive_process_name(t), 'foo')

        # When process_name is None, fall back to source_filename
        t.process_name = None
        mock_source_filename.return_value = 'baz'
        self.assertEqual(status.derive_process_name(t), 'baz')

        # When previous task exists, use its process_name
        t.previous_task_id = 1
        t.previous_task = SimpleNamespace(process_name='prev')
        self.assertEqual(status.derive_process_name(t), 'prev')

        # If fallback_name provided, it should be returned when process_name missing
        self.assertEqual(status.derive_process_name(t, fallback_name='fb'), 'fb')




