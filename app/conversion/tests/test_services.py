from unittest.mock import patch
from types import SimpleNamespace
from django.test import TestCase

from conversion import services

class ServiceTests(TestCase):
    def test_is_auto_annotated_assembly(self):
        cases = [
            ('sequencing_ont_annotated', True),
            ('sequencing_illumina_annotated', True),
            ('sequencing_ont', False),
            (None, False),
        ]
        for task_type, expected in cases:
            with self.subTest(task_type=task_type):
                t = SimpleNamespace(task_type=task_type, task_type_original=task_type)
                self.assertEqual(services.is_auto_annotated_assembly(t), expected)

    def test_annotation_process_key(self):
        t = SimpleNamespace(process_name='foo', input_path='bar')
        self.assertEqual(services.annotation_process_key(t), 'foo::bar')

    def test_find_latest_completed_annotation(self):
        a1 = SimpleNamespace(id=1, status='pending')
        a2 = SimpleNamespace(id=2, status='completed')
        a3 = SimpleNamespace(id=3, status='failed')
        self.assertEqual(services.find_latest_completed_annotation([a1, a2, a3]), a2)
        self.assertIsNone(services.find_latest_completed_annotation([a1, a3]))

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
                self.assertEqual(services.get_effective_annotation(inputs), expected)

    @patch('conversion.services.resolve_uploaded_fasta_input_path')
    def test_find_annotation_with_uploaded_fasta(self, mock_resolve):
        a1 = SimpleNamespace(id=1, external_job_id='ann-1')
        a2 = SimpleNamespace(id=2, external_job_id='ann-2')
        # Case: second has uploaded fasta
        mock_resolve.side_effect = [None, 'path/to/assembly_ann-2.fasta']
        self.assertEqual(services.find_annotation_with_uploaded_fasta([a1, a2]), a2)
        # Case: none have uploaded fasta
        mock_resolve.side_effect = [None, None]
        self.assertIsNone(services.find_annotation_with_uploaded_fasta([a1, a2]))

    @patch('conversion.services.source_filename')
    def test_derive_process_name(self, mock_source_filename):
        t = SimpleNamespace(previous_task_id=None, previous_task=None, process_name='foo', input_path='bar')
        self.assertEqual(services.derive_process_name(t), 'foo')

        # When process_name is None, fall back to source_filename
        t.process_name = None
        mock_source_filename.return_value = 'baz'
        self.assertEqual(services.derive_process_name(t), 'baz')

        # When previous task exists, use its process_name
        t.previous_task_id = 1
        t.previous_task = SimpleNamespace(process_name='prev')
        self.assertEqual(services.derive_process_name(t), 'prev')

        # If fallback_name provided, it should be returned when process_name missing
        self.assertEqual(services.derive_process_name(t, fallback_name='fb'), 'fb')




