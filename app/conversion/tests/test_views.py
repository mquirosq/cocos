import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from conversion.models import ConversionTask, FileUpload

User = get_user_model()


class ConversionViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='view-user', password='pass1234')
        self.client.login(username='view-user', password='pass1234')

    def test_assembly_ui_renders(self):
        response = self.client.get(reverse('conversion:assembly_ui'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Assembly', response.content)

    def test_annotation_ui_renders(self):
        response = self.client.get(reverse('conversion:annotation_ui'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Annotation', response.content)

    def test_annotation_task_upload_fasta(self):
        fasta = SimpleUploadedFile('test.fasta', b'>seq1\nATGC\n', content_type='text/plain')
        response = self.client.post(reverse('conversion:annotation_task'), {'fasta_file': fasta}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Annotation task started', response.content)

    def test_assembly_task_upload_fastq(self):
        fastq = SimpleUploadedFile('test.fastq', b'@seq1\nATGC\n+\n!!!!\n', content_type='text/plain')
        response = self.client.post(reverse('conversion:assembly_task'), {'fastq_file': fastq, 'assembly_type': 'ont'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Assembly task started', response.content)

    def test_task_status_view(self):
        task = ConversionTask.objects.create(
            external_job_id='seq-1',
            status='completed',
            process_name='ATCC Process',
            input_path='uploads/temp/user_1/fastq/reads.fastq.gz',
            task_type='assembly_ont',
            user=self.user,
        )
        response = self.client.get(reverse('conversion:task_status', args=[task.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'ATCC Process', response.content)

    @patch('conversion.views.parse_file')
    def test_parse_feature_file_creates_from_json_task(self, mock_parse_file):
        mock_parse_file.return_value = FileUpload.objects.create(
            user=self.user,
            file=SimpleUploadedFile('parsed.json', b'{"genome": "x"}', content_type='application/json'),
        )
        payload = SimpleUploadedFile('example.json', b'{"genome": "x", "features": []}', content_type='application/json')

        response = self.client.post(
            reverse('conversion:annotation_from_json'),
            data={'feature_file': payload},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        task = ConversionTask.objects.filter(user=self.user, task_type='from_json').order_by('-id').first()
        self.assertIsNotNone(task)
        self.assertEqual(task.status, 'completed')
        self.assertEqual(task.process_name, 'example.json')

    def test_download_json_uses_original_json_for_from_json_task(self):
        upload = FileUpload.objects.create(
            user=self.user,
            file=SimpleUploadedFile('original.json', b'{"hello": "world"}', content_type='application/json'),
        )
        task = ConversionTask.objects.create(
            external_job_id=None,
            status='completed',
            process_name='original.json',
            input_path=upload.file.name,
            task_type='from_json',
            user=self.user,
        )

        response = self.client.get(reverse('conversion:download_json', args=[task.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertRegex(response['Content-Disposition'], r'attachment; filename="original.*\.json"')
        self.assertEqual(json.loads(response.content.decode('utf-8')), {'hello': 'world'})

    def test_download_fasta_uses_uploaded_annotation_input(self):
        fasta_dir = os.path.join(settings.BASE_DIR, 'uploads', 'persistent', f'user_{self.user.id}', 'fasta')
        os.makedirs(fasta_dir, exist_ok=True)
        fasta_filename = 'input_test.fasta'
        fasta_path = os.path.join(fasta_dir, fasta_filename)
        with open(fasta_path, 'wb') as fasta_tmp:
            fasta_tmp.write(b'>seq1\nATGC\n')

        # The input_path should be the RELATIVE path as expected by resolve_uploaded_fasta_input_path
        relative_path = os.path.relpath(fasta_path, settings.BASE_DIR)

        try:
            task = ConversionTask.objects.create(
                external_job_id=None,
                status='pending',
                process_name='input.fasta',
                input_path=relative_path,
                task_type='annotation',
                user=self.user,
                previous_task=None,
            )

            # Mark as completed to pass the view's status check
            task.status = 'completed'
            task.save(update_fields=['status'])

            response = self.client.get(reverse('conversion:download_fasta', args=[task.id]))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/octet-stream')
            self.assertIn('attachment; filename="', response['Content-Disposition'])
            self.assertEqual(response.content, b'>seq1\nATGC\n')
        finally:
            try:
                os.remove(fasta_path)
            except OSError:
                pass


class ConversionTaskViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='view-user', password='pass1234')
        self.client.login(username='view-user', password='pass1234')

    def test_task_list_view_returns_grouped_rows(self):
        assembly = ConversionTask.objects.create(
            external_job_id='seq-1',
            status='completed',
            process_name='ATCC Process',
            input_path='uploads/temp/user_1/fastq/reads.fastq.gz',
            task_type='assembly_ont',
            user=self.user,
        )
        ConversionTask.objects.create(
            external_job_id='ann-1',
            status='failed',
            process_name='ATCC Process',
            input_path='uploads/temp/user_1/fastq/reads.fastq.gz',
            task_type='annotation',
            user=self.user,
            previous_task=assembly,
        )
        ConversionTask.objects.create(
            external_job_id=None,
            status='completed',
            process_name='Standalone JSON',
            input_path='uploads/persistent/user_1/json/sample.json',
            task_type='from_json',
            user=self.user,
        )

        response = self.client.get(reverse('conversion:task_list'))

        self.assertEqual(response.status_code, 200)
        rows = list(response.context['page_obj'].object_list)
        self.assertEqual(len(rows), 2)
        self.assertTrue(any(row['kind'] == 'assembly' for row in rows))
        self.assertTrue(any(row['kind'] == 'json' for row in rows))

    def test_rename_process_updates_related_assembly_and_annotation(self):
        assembly = ConversionTask.objects.create(
            external_job_id='seq-rename',
            status='completed',
            process_name='Old Name',
            input_path='uploads/temp/user_1/fastq/r.fastq.gz',
            task_type='assembly_ont',
            user=self.user,
        )
        annotation = ConversionTask.objects.create(
            external_job_id='ann-rename',
            status='running',
            process_name='Old Name',
            input_path='uploads/temp/user_1/fastq/r.fastq.gz',
            task_type='annotation',
            user=self.user,
            previous_task=assembly,
        )

        response = self.client.post(
            reverse('conversion:rename_process', args=[annotation.id]),
            data={'process_name': 'New Name'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        assembly.refresh_from_db()
        annotation.refresh_from_db()
        self.assertEqual(assembly.process_name, 'New Name')
        self.assertEqual(annotation.process_name, 'New Name')

    @patch('conversion.views.poll_annotation_from_assembly_start.delay')
    def test_annotation_from_job_redirects_to_task_status(self, mock_delay):
        assembly = ConversionTask.objects.create(
            external_job_id='seq-annotate',
            status='completed',
            process_name='Assembly job',
            input_path='uploads/temp/user_1/fastq/job.fastq.gz',
            task_type='assembly_ont',
            user=self.user,
        )

        response = self.client.post(
            reverse('conversion:annotation_from_job', args=[assembly.external_job_id]),
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        created_task = ConversionTask.objects.filter(user=self.user, task_type='annotation', previous_task=assembly).first()
        self.assertIsNotNone(created_task)
        self.assertEqual(response['Location'], reverse('conversion:task_status', args=[created_task.id]))
        mock_delay.assert_called_once()
