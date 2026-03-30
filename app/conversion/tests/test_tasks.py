from types import SimpleNamespace
from unittest.mock import patch

from celery.exceptions import MaxRetriesExceededError
from django.contrib.auth import get_user_model
from django.test import TestCase

from conversion.models import ConversionTask, FileUpload
from conversion.tasks import (
    _cleanup_temp_fastq_inputs,
    _persist_sequencing_fasta_output,
    poll_conversion_status,
    poll_annotation_start,
    poll_sequencing_start,
)

User = get_user_model()


class PollConversionStatusTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pass1234")

    def _task(self, task_type="annotation", external_job_id="job-123"):
        return ConversionTask.objects.create(
            external_job_id=external_job_id,
            status="running",
            input_path="uploads/temp/user_1/fastq/reads.fastq.gz",
            task_type=task_type,
            user=self.user,
        )

    @patch("conversion.tasks.notify_user_conversion_failed")
    @patch("conversion.tasks.get_job_status", return_value=(None, 404))
    def test_404_marks_failed_and_notifies(self, _, mock_notify):
        task = self._task()
        poll_conversion_status(task.id)
        task.refresh_from_db()
        self.assertEqual(task.status, "failed")
        mock_notify.assert_called_once_with(self.user, task)

    @patch.object(poll_conversion_status, "retry")
    @patch("conversion.tasks.get_job_status", return_value=("running", 200))
    def test_running_status_retries(self, _, mock_retry):
        poll_conversion_status(self._task().id)
        mock_retry.assert_called_once_with(countdown=60)

    @patch("conversion.tasks.notify_user_conversion_complete")
    @patch("conversion.tasks._cleanup_temp_fastq_inputs")
    @patch("conversion.tasks._persist_sequencing_fasta_output")
    @patch("conversion.tasks.get_job_status")
    def test_sequencing_completion_paths(self, mock_status, mock_persist, mock_cleanup, mock_notify):
        cases = [
            ("sequencing_ont", "assembled", True),
            ("sequencing_ont", "completed", True),
            ("sequencing_ont", "annotated", True),
            ("annotation", "annotated", False),
        ]
        for task_type, incoming, should_persist in cases:
            with self.subTest(task_type=task_type, incoming=incoming):
                task = self._task(task_type=task_type, external_job_id=f"job-{task_type}-{incoming}")
                mock_status.return_value = (incoming, 200)
                poll_conversion_status(task.id)
                task.refresh_from_db()
                self.assertEqual(task.status, "completed")
                self.assertEqual(mock_persist.called, should_persist)
                self.assertTrue(mock_cleanup.called)
                self.assertTrue(mock_notify.called)
                mock_persist.reset_mock()
                mock_cleanup.reset_mock()
                mock_notify.reset_mock()

    @patch("conversion.tasks.notify_user_conversion_failed")
    @patch("conversion.tasks._persist_sequencing_fasta_output", side_effect=ValueError("empty"))
    @patch("conversion.tasks.get_job_status", return_value=("assembled", 200))
    def test_persist_failure_marks_failed_when_retries_exhausted(self, _, __, mock_notify):
        task = self._task(task_type="sequencing_ont")
        with patch.object(poll_conversion_status, "retry", side_effect=MaxRetriesExceededError()):
            poll_conversion_status(task.id)
        task.refresh_from_db()
        self.assertEqual(task.status, "failed")
        self.assertTrue(mock_notify.called)


class HelperTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pass1234")

    @patch("conversion.tasks.delete_file_safely")
    def test_cleanup_temp_fastq_inputs(self, mock_delete):
        cases = [
            ("sequencing_ont", "uploads/temp/user_1/fastq/a.fastq.gz", 1),
            ("sequencing_illumina", "uploads/temp/user_1/fastq/a.fastq.gz, uploads/temp/user_1/fastq/b.fastq.gz", 2),
            ("annotation", "uploads/temp/user_1/fastq/a.fastq.gz", 0),
        ]
        for task_type, input_path, expected_calls in cases:
            with self.subTest(task_type=task_type):
                task = ConversionTask.objects.create(
                    external_job_id=f"job-{task_type}",
                    status="completed",
                    input_path=input_path,
                    task_type=task_type,
                    user=self.user,
                )
                _cleanup_temp_fastq_inputs(task)
                self.assertEqual(mock_delete.call_count, expected_calls)
                mock_delete.reset_mock()

    @patch("conversion.tasks.delete_file_safely")
    def test_cleanup_temp_fastq_inputs_early_return(self, mock_delete):
        cases = [
            ("none task", None),
            ("empty input path", SimpleNamespace(input_path="", task_type="sequencing_ont")),
        ]
        for label, task in cases:
            with self.subTest(label=label):
                _cleanup_temp_fastq_inputs(task)
                mock_delete.assert_not_called()
                mock_delete.reset_mock()

    @patch("conversion.tasks.download_assembly_fasta_result")
    def test_persist_sequencing_fasta_output(self, mock_download):
        cases = [
            ("annotation", False, False),
            ("sequencing_ont", True, True),
        ]
        for task_type, should_download, should_create in cases:
            with self.subTest(task_type=task_type):
                task = ConversionTask.objects.create(
                    external_job_id=f"job-{task_type}",
                    status="completed",
                    input_path="/tmp/input.fastq",
                    task_type=task_type,
                    user=self.user,
                )
                mock_download.return_value = b">x\nATG\n"
                before = FileUpload.objects.filter(user=self.user).count()
                _persist_sequencing_fasta_output(task)
                after = FileUpload.objects.filter(user=self.user).count()
                self.assertEqual(mock_download.called, should_download)
                self.assertEqual(after > before, should_create)
                mock_download.reset_mock()

    @patch("conversion.tasks.download_assembly_fasta_result")
    def test_persist_sequencing_fasta_output_early_return(self, mock_download):
        before = FileUpload.objects.filter(user=self.user).count()
        cases = [
            ("none task", None),
            ("missing external id", SimpleNamespace(external_job_id=None, task_type="sequencing_ont", user_id=self.user.id)),
        ]
        for label, task in cases:
            with self.subTest(label=label):
                _persist_sequencing_fasta_output(task)
                self.assertEqual(FileUpload.objects.filter(user=self.user).count(), before)
                mock_download.assert_not_called()
                mock_download.reset_mock()

    @patch("conversion.tasks.download_assembly_fasta_result", return_value=b"")
    def test_persist_empty_content_raises(self, _):
        task = ConversionTask.objects.create(
            external_job_id="job-empty",
            status="completed",
            input_path="/tmp/input.fastq",
            task_type="sequencing_ont",
            user=self.user,
        )
        with self.assertRaises(ValueError):
            _persist_sequencing_fasta_output(task)


class AnnotationStartTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser3", password="pass1234")

    def _mock_annotate_response(self, status="running"):
        return {"job_id": "ann-job-123", "status": status}

    def _create_task(self):
        return ConversionTask.objects.create(
            external_job_id="old-job",
            status="pending",
            input_path="/tmp/fasta.fasta",
            task_type="annotation",
            user=self.user,
        )
    
    @patch("conversion.tasks.poll_conversion_status")
    @patch("conversion.tasks.annotate_from_fasta")
    def test_annotation_starts_for_existing_task(self, mock_annotate, mock_poll):
        fasta_bytes = b">seq1\nATGC\n"
        cases = [
            ("running status", "running", "ann-job-running"),
            ("pending status", "annotation_pending", "ann-job-pending"),
        ]
        for label, external_status, job_id in cases:
            with self.subTest(label=label):
                task = self._create_task()
                mock_annotate.return_value = {"job_id": job_id, "status": external_status}

                poll_annotation_start(fasta_bytes=fasta_bytes, task_id=task.id)

                task.refresh_from_db()
                self.assertEqual(task.external_job_id, job_id)
                self.assertEqual(task.status, "running")
                mock_poll.delay.assert_called_once_with(task.id)
                mock_annotate.assert_called_once_with(fasta_bytes)
                mock_annotate.reset_mock()
                mock_poll.reset_mock()

    @patch("conversion.tasks.notify_user_conversion_failed")
    @patch("conversion.tasks.poll_conversion_status")
    @patch("conversion.tasks.annotate_from_fasta")
    def test_missing_task_id_notifies_and_stops(self, mock_annotate, mock_poll, mock_notify):
        poll_annotation_start(fasta_bytes=b">seq1\nATGC\n", task_id=999999)

        mock_notify.assert_called_once()
        mock_annotate.assert_not_called()
        mock_poll.delay.assert_not_called()

    @patch("conversion.tasks.notify_user_server_busy")
    @patch.object(poll_annotation_start, "retry")
    @patch("conversion.tasks.annotate_from_fasta")
    def test_annotation_start_retries(self, mock_annotate, mock_retry, mock_notify):
        cases = [
            (None, "Retries if not started", "busy-job-1"),
            (MaxRetriesExceededError(), "Notifies on max retries", "busy-job-2"),
        ]
        for retry_side_effect, label, job_id in cases:
            with self.subTest(label=label):
                task = ConversionTask.objects.create(
                    external_job_id=job_id,
                    status="pending",
                    input_path="/tmp/fasta.fasta",
                    task_type="annotation",
                    user=self.user,
                )
                mock_annotate.return_value = {"status": "pending"}
                if retry_side_effect:
                    mock_retry.side_effect = retry_side_effect
                else:
                    mock_retry.side_effect = None
                
                poll_annotation_start(fasta_bytes=b">seq\nATGC\n", task_id=task.id)

                if retry_side_effect:
                    mock_notify.assert_called()
                else:
                    mock_retry.assert_called_with(countdown=60)
                task.delete()
                mock_retry.reset_mock()
                mock_notify.reset_mock()


class SequencingStartTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pass1234")
        self.temp_fastq1 = "/tmp/test_R1.fastq.gz"
        self.temp_fastq2 = "/tmp/test_R2.fastq.gz"

    def _mock_sequencing_response(self, status="running"):
        return {"job_id": "seq-job", "status": status}

    def _set_open_bytes(self, mock_open, content=b"@read_id\nATGC\n+\n~~~~\n"):
        mock_open.return_value.__enter__.return_value.read.return_value = content

    def _create_task(self, external_job_id="existing-seq-job"):
        return ConversionTask.objects.create(
            external_job_id=external_job_id,
            status="pending",
            input_path="/tmp/fastq.gz",
            task_type="sequencing_ont",
            user=self.user,
        )

    @patch("conversion.tasks.poll_conversion_status")
    @patch("builtins.open", create=True)
    @patch("conversion.tasks.sequence_ont")
    @patch("conversion.tasks.sequence_illumina")
    def test_sequencing_start_works(self, mock_illumina, mock_ont, mock_open, mock_poll):
        self._set_open_bytes(mock_open)
        mock_ont.return_value = self._mock_sequencing_response()
        mock_illumina.return_value = self._mock_sequencing_response()

        cases = [
            ("create ont", "ont", None, False, "sequencing_ont", False),
            ("create illumina", "illumina", self.temp_fastq2, False, "sequencing_illumina", False),
            ("create annotated", "ont", None, True, "sequencing_ont_annotated", False),
            ("update existing", "ont", None, False, "sequencing_ont", True),
        ]
        for desc, seq_type, dest_2, annotate, expected_type, use_existing_task in cases:
            with self.subTest(label=desc):
                existing_task = self._create_task() if use_existing_task else None
                poll_sequencing_start(
                    sequencing_type=seq_type,
                    dest_path=self.temp_fastq1,
                    dest_path_2=dest_2,
                    annotate=annotate,
                    user_id=self.user.id,
                    task_id=existing_task.id if existing_task else None,
                )
                task = existing_task
                if task:
                    task.refresh_from_db()
                else:
                    task = ConversionTask.objects.filter(external_job_id="seq-job").first()
                self.assertIsNotNone(task)
                self.assertEqual(task.task_type, expected_type)
                self.assertEqual(task.status, "running")
                self.assertEqual(task.external_job_id, "seq-job")
                mock_poll.delay.assert_called_once_with(task.id)
                ConversionTask.objects.all().delete()
                mock_poll.reset_mock()

    @patch("conversion.tasks.notify_user_conversion_failed")
    @patch("builtins.open", create=True)
    def test_error_paths(self, mock_open, mock_notify):
        cases = [
            ("invalid type", "invalid", self.temp_fastq1, None, None, "Invalid sequencing type"),
            ("miss first fastq", "ont", "/missing.fastq", None, IOError("Missing"), "Failed to read fastq file"),
            ("miss second fastq", "illumina", self.temp_fastq1, None, None, "Missing second FASTQ"),
        ]
        for desc, seq_type, path1, path2, read_error, expected_msg in cases:
            with self.subTest(label=desc):
                if read_error and "first" in desc:
                    with patch("builtins.open", side_effect=read_error):
                        poll_sequencing_start(sequencing_type=seq_type, dest_path=path1, user_id=self.user.id)
                else:
                    if "second" in desc:
                        self._set_open_bytes(mock_open, b"@read\nATGC\n+\n~~~~\n")
                    poll_sequencing_start(
                        sequencing_type=seq_type,
                        dest_path=path1,
                        dest_path_2=path2,
                        user_id=self.user.id,
                    )
                mock_notify.assert_called()
                self.assertIn(expected_msg, str(mock_notify.call_args))
                mock_notify.reset_mock()

    @patch("conversion.tasks.notify_user_server_busy")
    @patch("conversion.tasks.poll_conversion_status")
    @patch("builtins.open", create=True)
    @patch.object(poll_sequencing_start, "retry")
    @patch("conversion.tasks.sequence_ont")
    def test_retry_paths(self, mock_ont, mock_retry, mock_open, mock_poll, mock_notify):
        self._set_open_bytes(mock_open, b"@read\nATGC\n+\n~~~~\n")
        mock_ont.return_value = {"status": "busy"}

        cases = [
            ("server busy", None, "retries on 503"),
            ("max retries", MaxRetriesExceededError(), "notifies on exhaustion"),
        ]
        for label, retry_effect in cases:
            with self.subTest(label=label):
                task = self._create_task(external_job_id="seq-job")
                mock_retry.side_effect = retry_effect

                poll_sequencing_start(sequencing_type="ont", dest_path=self.temp_fastq1, task_id=task.id)

                if retry_effect:
                    mock_notify.assert_called_once()
                else:
                    mock_retry.assert_called_once_with(countdown=60)
                task.delete()
                mock_retry.reset_mock()
                mock_notify.reset_mock()