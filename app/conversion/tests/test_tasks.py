from types import SimpleNamespace
from unittest.mock import call, patch

from celery.exceptions import MaxRetriesExceededError
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase

from conversion.models import ConversionTask, FileUpload
from conversion.tasks import (
    _cleanup_temp_fastq_inputs,
    _ensure_in_app_notification,
    _persist_annotation_json_output,
    _persist_assembly_fasta_output,
    poll_annotation_from_assembly_start,
    poll_annotation_start,
    poll_assembly_start,
    poll_conversion_status,
)
from notifications.models import TaskNotification

User = get_user_model()

FASTQ = b"@r\nATGC\n+\n~~~~\n"
FASTA = b">seq\nATGC\n"


def make_user(username="testuser"):
    return User.objects.create_user(username=username, password="pass")


def make_task(user, task_type="annotation", job_id="job-1", status="running",
              input_path="uploads/temp/u/reads.fastq.gz"):
    return ConversionTask.objects.create(
        external_job_id=job_id, status=status,
        input_path=input_path, task_type=task_type, user=user,
    )


class PollConversionStatusTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def poll(self, task, **kw):
        poll_conversion_status(task.id, **kw)
        task.refresh_from_db()

    @patch("conversion.tasks.notify_user_conversion_failed")
    @patch("conversion.tasks.get_job_status", return_value=(None, 404))
    def test_404_marks_failed_notifies_and_creates_in_app_notification(self, _, mock_notify):
        task = make_task(self.user)
        self.poll(task)
        self.assertEqual(task.status, "failed")
        mock_notify.assert_called_once_with(self.user, task)
        self.assertTrue(TaskNotification.objects.filter(task=task, event_type=TaskNotification.EVENT_FAILED).exists())

    @patch("conversion.tasks.get_job_status")
    def test_missing_task_stops_without_calling_api(self, mock_status):
        poll_conversion_status(task_id=999999)
        mock_status.assert_not_called()

    @patch.object(poll_conversion_status, "retry")
    @patch("conversion.tasks.get_job_status", return_value=("running", 200))
    def test_running_retries_after_60s(self, _, mock_retry):
        self.poll(make_task(self.user))
        mock_retry.assert_called_once_with(countdown=60)

    @patch.object(poll_conversion_status, "retry", side_effect=MaxRetriesExceededError())
    @patch("conversion.tasks.notify_user_conversion_failed")
    @patch("conversion.tasks.get_job_status", return_value=("running", 200))
    def test_max_retries_marks_failed(self, _, mock_notify, __):
        task = make_task(self.user)
        self.poll(task)
        self.assertEqual(task.status, "failed")
        mock_notify.assert_called_once_with(self.user, task)

    @patch("conversion.tasks.notify_user_conversion_failed")
    @patch("conversion.tasks.get_job_status", return_value=("failed", 200))
    def test_external_failure_notifies_and_creates_in_app_notification(self, _, mock_notify):
        task = make_task(self.user)
        self.poll(task)
        self.assertEqual(task.status, "failed")
        mock_notify.assert_called_once_with(self.user, task)
        self.assertTrue(TaskNotification.objects.filter(task=task, event_type=TaskNotification.EVENT_FAILED).exists())

    @patch("conversion.tasks.notify_user_conversion_complete")
    @patch("conversion.tasks._cleanup_temp_fastq_inputs")
    @patch("conversion.tasks._persist_assembly_fasta_output")
    @patch("conversion.tasks.get_job_status")
    def test_assembled_and_annotated_map_to_completed(self, mock_status, mock_persist, _, __):
        for incoming in ("assembled", "annotated"):
            with self.subTest(incoming=incoming):
                task = make_task(self.user, task_type="assembly_ont", job_id=f"j-{incoming}")
                mock_status.return_value = (incoming, 200)
                self.poll(task)
                self.assertEqual(task.status, "completed")
                mock_persist.reset_mock()

    @patch("conversion.tasks.notify_user_conversion_complete")
    @patch("conversion.tasks._cleanup_temp_fastq_inputs")
    @patch("conversion.tasks._persist_annotation_json_output")
    @patch("conversion.tasks._persist_assembly_fasta_output")
    @patch("conversion.tasks.get_job_status")
    def test_completion_calls_correct_helpers(self, mock_status, mock_fasta, mock_json, _, mock_notify):
        cases = [
            # task_type,                   incoming,    fasta, json
            ("assembly_ont",               "assembled", True,  False),
            ("assembly_illumina",          "completed", True,  False),
            ("assembly_ont_annotated",     "annotated", True,  True),
            ("assembly_illumina_annotated","annotated", True,  True),
            ("annotation",                "annotated", False, True),
        ]
        for task_type, incoming, exp_fasta, exp_json in cases:
            with self.subTest(task_type=task_type):
                task = make_task(self.user, task_type=task_type, job_id=f"j-{task_type}")
                mock_status.return_value = (incoming, 200)
                self.poll(task)
                self.assertEqual(task.status, "completed")
                self.assertEqual(mock_fasta.called, exp_fasta)
                self.assertEqual(mock_json.called, exp_json)
                mock_notify.assert_called_once_with(self.user, task)
                mock_fasta.reset_mock(); mock_json.reset_mock(); mock_notify.reset_mock()

    @patch("conversion.tasks.notify_user_conversion_complete")
    @patch("conversion.tasks._cleanup_temp_fastq_inputs")
    @patch("conversion.tasks._persist_annotation_json_output")
    @patch("conversion.tasks._persist_assembly_fasta_output")
    @patch("conversion.tasks.get_job_status", return_value=("completed", 200))
    def test_completion_creates_in_app_notification(self, _, __, ___, ____, _____):
        task = make_task(self.user, task_type="assembly_ont")
        self.poll(task)
        self.assertTrue(TaskNotification.objects.filter(task=task, event_type=TaskNotification.EVENT_COMPLETED).exists())

    @patch("conversion.tasks.notify_user_conversion_complete")
    @patch("conversion.tasks._cleanup_temp_fastq_inputs")
    @patch("conversion.tasks._persist_annotation_json_output")
    @patch("conversion.tasks._persist_assembly_fasta_output")
    @patch("conversion.tasks.get_job_status", return_value=("annotated", 200))
    def test_complete_version_forwarded_to_persist_json(self, _, __, mock_json, ___, ____):
        task = make_task(self.user, task_type="annotation")
        self.poll(task, complete_version=True)
        mock_json.assert_called_once_with(task, complete_version=True)

    @patch("conversion.tasks.notify_user_conversion_failed")
    @patch("conversion.tasks._persist_assembly_fasta_output", side_effect=ValueError("empty"))
    @patch("conversion.tasks.get_job_status", return_value=("assembled", 200))
    def test_fasta_persist_failure_marks_failed_when_retries_exhausted(self, _, __, mock_notify):
        task = make_task(self.user, task_type="assembly_ont")
        with patch.object(poll_conversion_status, "retry", side_effect=MaxRetriesExceededError()):
            self.poll(task)
        self.assertEqual(task.status, "failed")
        mock_notify.assert_called_once_with(self.user, task)

    @patch("conversion.tasks.notify_user_conversion_warning")
    @patch("conversion.tasks.notify_user_conversion_complete")
    @patch("conversion.tasks._cleanup_temp_fastq_inputs")
    @patch("conversion.tasks._persist_annotation_json_output", side_effect=Exception("fail"))
    @patch("conversion.tasks._persist_assembly_fasta_output")
    @patch("conversion.tasks.get_job_status", return_value=("completed", 200))
    def test_annotation_persist_failure_warns_but_still_completes(self, _, __, ___, ____, mock_complete, mock_warn):
        for task_type in ("assembly_ont_annotated", "annotation"):
            with self.subTest(task_type=task_type):
                task = make_task(self.user, task_type=task_type, job_id=f"j-warn-{task_type}")
                self.poll(task)
                self.assertEqual(task.status, "completed")
                mock_warn.assert_called_once()
                mock_complete.assert_called_once_with(self.user, task)
                mock_warn.reset_mock(); mock_complete.reset_mock()


class CleanupTempFastqInputsTests(TestCase):
    def setUp(self):
        self.user = make_user()

    @patch("conversion.tasks.delete_file_safely")
    def test_deletes_temp_paths_for_assembly(self, mock_delete):
        cases = [
            ("assembly_ont",      "uploads/temp/u/a.fastq.gz",                            ["uploads/temp/u/a.fastq.gz"]),
            ("assembly_illumina", "uploads/temp/u/a.fastq.gz, uploads/temp/u/b.fastq.gz", ["uploads/temp/u/a.fastq.gz", "uploads/temp/u/b.fastq.gz"]),
        ]
        for task_type, input_path, expected in cases:
            with self.subTest(task_type=task_type):
                task = make_task(self.user, task_type=task_type, job_id=f"j-{task_type}",
                                 status="completed", input_path=input_path)
                _cleanup_temp_fastq_inputs(task)
                mock_delete.assert_has_calls([call(p) for p in expected])
                self.assertEqual(mock_delete.call_count, len(expected))
                mock_delete.reset_mock()

    @patch("conversion.tasks.delete_file_safely")
    def test_no_op_cases(self, mock_delete):
        u2, u3 = make_user("u2"), make_user("u3")
        cases = [
            ("none task",      None),
            ("empty input",    SimpleNamespace(input_path="",   task_type="assembly_ont")),
            ("none input",     SimpleNamespace(input_path=None, task_type="assembly_ont")),
            ("annotation",     make_task(u2, task_type="annotation", job_id="j-noop-ann")),
            ("non-temp path",  make_task(u3, task_type="assembly_ont", job_id="j-noop-perm",
                                         input_path="uploads/permanent/file.fastq.gz")),
        ]
        for label, task in cases:
            with self.subTest(label=label):
                _cleanup_temp_fastq_inputs(task)
                mock_delete.assert_not_called()
                mock_delete.reset_mock()


class PersistAssemblyFastaOutputTests(TestCase):
    def setUp(self):
        self.user = make_user()

    @patch("conversion.tasks.download_assembly_fasta_result", return_value=FASTA)
    def test_creates_upload_and_sets_output_path(self, _):
        task = make_task(self.user, task_type="assembly_ont", status="completed", input_path="/tmp/in.fastq")
        _persist_assembly_fasta_output(task)
        task.refresh_from_db()
        self.assertTrue(FileUpload.objects.filter(user=self.user).exists())
        self.assertIsNotNone(task.output_path)

    @patch("conversion.tasks.download_assembly_fasta_result")
    def test_no_op_cases(self, mock_download):
        cases = [
            ("none task",      None),
            ("no external id", SimpleNamespace(external_job_id=None, task_type="assembly_ont", user_id=self.user.id)),
            ("annotation",     make_task(self.user, task_type="annotation", status="completed", input_path="/tmp/in.fasta")),
        ]
        for label, task in cases:
            with self.subTest(label=label):
                _persist_assembly_fasta_output(task)
                mock_download.assert_not_called()

    @patch("conversion.tasks.download_assembly_fasta_result", return_value=b"")
    def test_raises_on_empty_content(self, _):
        task = make_task(self.user, task_type="assembly_ont", status="completed", input_path="/tmp/in.fastq")
        with self.assertRaises(ValueError):
            _persist_assembly_fasta_output(task)

    @patch("conversion.tasks.download_assembly_fasta_result")
    @patch("conversion.tasks.find_latest_persisted_upload", return_value=object())
    def test_skips_when_already_persisted(self, _, mock_download):
        task = make_task(self.user, task_type="assembly_ont", status="completed", input_path="/tmp/in.fastq")
        _persist_assembly_fasta_output(task)
        mock_download.assert_not_called()


class PersistAnnotationJsonOutputTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def _task(self, **kw):
        return make_task(self.user, task_type="annotation", status="completed",
                         input_path="/tmp/in.fasta", **kw)

    @patch("conversion.tasks.parse_file")
    @patch("conversion.tasks.download_bakta_json_result")
    @patch("conversion.tasks.find_latest_persisted_upload", return_value=None)
    def test_accepts_dict_and_list_payloads(self, _, mock_download, mock_parse):
        for payload in ({"feature": 1}, [{"feature": 1}]):
            with self.subTest(type=type(payload).__name__):
                mock_download.return_value = payload
                _persist_annotation_json_output(self._task(job_id=f"j-{type(payload).__name__}"))
                mock_parse.assert_called_once()
                mock_parse.reset_mock()

    @patch("conversion.tasks.parse_file")
    @patch("conversion.tasks.download_bakta_json_result", return_value=[{"f": 1}])
    @patch("conversion.tasks.find_latest_persisted_upload", return_value=None)
    def test_list_payload_wrapped_in_features_key(self, _, __, mock_parse):
        _persist_annotation_json_output(self._task())
        self.assertIsInstance(mock_parse.call_args[0][1].get("features"), list)

    @patch("conversion.tasks.download_bakta_json_result", return_value="bad")
    @patch("conversion.tasks.find_latest_persisted_upload", return_value=None)
    def test_raises_on_invalid_payload(self, _, __):
        with self.assertRaises(ValueError):
            _persist_annotation_json_output(self._task())

    @patch("conversion.tasks.download_bakta_json_result")
    def test_no_op_cases(self, mock_download):
        cases = [
            ("none task",      None),
            ("no external id", SimpleNamespace(external_job_id=None, task_type="annotation", user_id=self.user.id)),
            ("assembly task",  make_task(self.user, task_type="assembly_ont", job_id="j-asm", input_path="/tmp/in.fastq")),
        ]
        for label, task in cases:
            with self.subTest(label=label):
                _persist_annotation_json_output(task)
                mock_download.assert_not_called()

    @patch("conversion.tasks.download_bakta_json_result")
    @patch("conversion.tasks.find_latest_persisted_upload", return_value=True)
    def test_skips_when_already_persisted(self, _, mock_download):
        _persist_annotation_json_output(self._task())
        mock_download.assert_not_called()

    @patch("conversion.tasks.parse_file")
    @patch("conversion.tasks.download_bakta_json_result", return_value={"f": 1})
    @patch("conversion.tasks.find_latest_persisted_upload", return_value=None)
    def test_complete_version_forwarded(self, _, __, mock_parse):
        _persist_annotation_json_output(self._task(), complete_version=True)
        self.assertTrue(mock_parse.call_args[1].get("options", {}).get("complete_version"))


class EnsureInAppNotificationTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.task = make_task(self.user, task_type="annotation", status="completed", input_path="/tmp/in.fasta")

    def test_creates_notification(self):
        _ensure_in_app_notification(self.task, TaskNotification.EVENT_COMPLETED, "done")
        self.assertEqual(TaskNotification.objects.filter(task=self.task, event_type=TaskNotification.EVENT_COMPLETED).count(), 1)

    def test_does_not_duplicate(self):
        TaskNotification.objects.create(
            user_id=self.task.user_id, task=self.task,
            event_type=TaskNotification.EVENT_COMPLETED, message="done",
            channels=[TaskNotification.CHANNEL_IN_APP],
        )
        _ensure_in_app_notification(self.task, TaskNotification.EVENT_COMPLETED, "again")
        self.assertEqual(TaskNotification.objects.filter(task=self.task, event_type=TaskNotification.EVENT_COMPLETED).count(), 1)

    def test_no_op_cases(self):
        before = TaskNotification.objects.count()
        for label, task in [("none", None), ("no user_id", SimpleNamespace(user_id=None))]:
            with self.subTest(label=label):
                _ensure_in_app_notification(task, "ev", "msg")
                self.assertEqual(TaskNotification.objects.count(), before)

    def test_uses_in_app_channel(self):
        _ensure_in_app_notification(self.task, TaskNotification.EVENT_FAILED, "oops")
        notif = TaskNotification.objects.get(task=self.task, event_type=TaskNotification.EVENT_FAILED)
        self.assertIn(TaskNotification.CHANNEL_IN_APP, notif.channels)


class PollAnnotationStartTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def _task(self, status="pending", job_id="old-job"):
        return make_task(self.user, task_type="annotation", job_id=job_id,
                         status=status, input_path="/tmp/fasta.fasta")

    @patch("conversion.tasks.poll_conversion_status")
    @patch("conversion.tasks.notify_user_conversion_started")
    @patch("conversion.tasks.annotate_from_fasta")
    def test_starts_annotation_and_polls(self, mock_annotate, mock_started, mock_poll):
        for ext_status, job_id in [("running", "j-run"), ("annotation_pending", "j-pend")]:
            with self.subTest(ext_status=ext_status):
                task = self._task()
                mock_annotate.return_value = {"job_id": job_id, "status": ext_status}
                poll_annotation_start(fasta_bytes=FASTA, task_id=task.id)
                task.refresh_from_db()
                self.assertEqual(task.external_job_id, job_id)
                self.assertEqual(task.status, "running")
                mock_started.assert_called_once_with(self.user, task)
                mock_poll.delay.assert_called_once_with(task.id, complete_version=False)
                mock_annotate.reset_mock(); mock_started.reset_mock(); mock_poll.reset_mock()

    @patch("conversion.tasks.poll_conversion_status")
    @patch("conversion.tasks.notify_user_conversion_started")
    @patch("conversion.tasks.annotate_from_fasta", return_value={"job_id": "j", "status": "running"})
    def test_already_running_skips_started_notification(self, _, mock_started, __):
        poll_annotation_start(fasta_bytes=FASTA, task_id=self._task(status="running").id)
        mock_started.assert_not_called()

    @patch("conversion.tasks.notify_user_conversion_failed")
    @patch("conversion.tasks.annotate_from_fasta")
    def test_missing_task_notifies_and_stops(self, mock_annotate, mock_notify):
        poll_annotation_start(fasta_bytes=FASTA, task_id=999999)
        mock_notify.assert_called_once()
        mock_annotate.assert_not_called()

    @patch("conversion.tasks.notify_user_server_busy")
    @patch.object(poll_annotation_start, "retry")
    @patch("conversion.tasks.annotate_from_fasta", return_value={"status": "pending"})
    def test_busy_retries_then_notifies_on_exhaustion(self, _, mock_retry, mock_notify):
        for i, (effect, expect_notify) in enumerate([(None, False), (MaxRetriesExceededError(), True)]):
            with self.subTest(exhausted=expect_notify):
                mock_retry.side_effect = effect
                poll_annotation_start(fasta_bytes=FASTA, task_id=self._task(job_id=f"old-job-{i}").id)
                if expect_notify:
                    mock_notify.assert_called_once()
                else:
                    mock_retry.assert_called_once_with(countdown=60)
                mock_retry.reset_mock(); mock_notify.reset_mock()

    @patch("conversion.tasks.poll_conversion_status")
    @patch("conversion.tasks.notify_user_conversion_started")
    @patch("conversion.tasks.annotate_from_fasta", return_value={"job_id": "j-cv", "status": "running"})
    def test_complete_version_forwarded(self, _, __, mock_poll):
        task = self._task()
        poll_annotation_start(fasta_bytes=FASTA, task_id=task.id, complete_version=True)
        mock_poll.delay.assert_called_once_with(task.id, complete_version=True)


class PollAssemblyStartTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def _task(self, task_type="assembly_ont", job_id="existing-job", status="pending"):
        return make_task(self.user, task_type=task_type, job_id=job_id, status=status)

    def _open(self, mock_open, content=FASTQ):
        mock_open.return_value.__enter__.return_value.read.return_value = content

    @patch("conversion.tasks.poll_conversion_status")
    @patch("conversion.tasks.notify_user_conversion_started")
    @patch("builtins.open", create=True)
    @patch("conversion.tasks.sequence_ont", return_value={"job_id": "seq-1", "status": "running"})
    def test_ont_updates_existing_task(self, _, mock_open, mock_started, mock_poll):
        self._open(mock_open)
        task = self._task()
        poll_assembly_start(assembly_type="ont", dest_path="/tmp/R1.fastq.gz",
                            task_id=task.id, user_id=self.user.id)
        task.refresh_from_db()
        self.assertEqual(task.status, "running")
        self.assertEqual(task.external_job_id, "seq-1")
        mock_started.assert_called_once_with(self.user, task)
        mock_poll.delay.assert_called_once_with(task.id, complete_version=False)

    @patch("conversion.tasks.poll_conversion_status")
    @patch("conversion.tasks.notify_user_conversion_started")
    @patch("builtins.open", create=True)
    @patch("conversion.tasks.sequence_ont", return_value={"job_id": "seq-new", "status": "running"})
    def test_ont_creates_task_when_none_provided(self, _, mock_open, mock_started, __):
        self._open(mock_open)
        poll_assembly_start(assembly_type="ont", dest_path="/tmp/R1.fastq.gz", user_id=self.user.id)
        task = ConversionTask.objects.filter(external_job_id="seq-new").first()
        self.assertIsNotNone(task)
        self.assertEqual(task.task_type, "assembly_ont")
        mock_started.assert_called_once()

    @patch("conversion.tasks.poll_conversion_status")
    @patch("conversion.tasks.notify_user_conversion_started")
    @patch("builtins.open", create=True)
    @patch("conversion.tasks.sequence_illumina", return_value={"job_id": "seq-ill", "status": "running"})
    def test_illumina_creates_correct_task_type(self, _, mock_open, __, ___):
        self._open(mock_open)
        poll_assembly_start(assembly_type="illumina", dest_path="/tmp/R1.fastq.gz",
                            dest_path_2="/tmp/R2.fastq.gz", user_id=self.user.id)
        self.assertEqual(ConversionTask.objects.get(external_job_id="seq-ill").task_type, "assembly_illumina")

    @patch("conversion.tasks.poll_conversion_status")
    @patch("conversion.tasks.notify_user_conversion_started")
    @patch("builtins.open", create=True)
    @patch("conversion.tasks.sequence_ont", return_value={"job_id": "seq-ann", "status": "running"})
    def test_annotated_flag_sets_correct_task_type(self, _, mock_open, __, ___):
        self._open(mock_open)
        poll_assembly_start(assembly_type="ont", dest_path="/tmp/R1.fastq.gz",
                            annotate=True, user_id=self.user.id)
        self.assertEqual(ConversionTask.objects.get(external_job_id="seq-ann").task_type, "assembly_ont_annotated")

    @patch("conversion.tasks.poll_conversion_status")
    @patch("conversion.tasks.notify_user_conversion_started")
    @patch("builtins.open", create=True)
    @patch("conversion.tasks.sequence_ont", return_value={"job_id": "seq-run", "status": "running"})
    def test_already_running_skips_started_notification(self, _, mock_open, mock_started, __):
        self._open(mock_open)
        task = self._task(status="running")
        poll_assembly_start(assembly_type="ont", dest_path="/tmp/R1.fastq.gz",
                            task_id=task.id, user_id=self.user.id)
        mock_started.assert_not_called()

    @patch("conversion.tasks.notify_user_conversion_failed")
    def test_error_paths(self, mock_notify):
        cases = [
            ("invalid type",   dict(assembly_type="invalid",   dest_path="/tmp/R1.fastq.gz"), None,            "Invalid assembly type"),
            ("missing R1",     dict(assembly_type="ont",        dest_path="/missing.fastq"),   IOError("gone"), "Failed to read fastq file"),
            ("missing R2 arg", dict(assembly_type="illumina",   dest_path="/tmp/R1.fastq.gz"), None,            "Missing second FASTQ"),
        ]
        for label, kwargs, open_error, expected_msg in cases:
            with self.subTest(label=label):
                if open_error:
                    with patch("builtins.open", side_effect=open_error):
                        poll_assembly_start(**kwargs, user_id=self.user.id)
                else:
                    with patch("builtins.open", create=True) as m:
                        self._open(m)
                        poll_assembly_start(**kwargs, user_id=self.user.id)
                mock_notify.assert_called()
                self.assertIn(expected_msg, str(mock_notify.call_args))
                mock_notify.reset_mock()

    @patch("conversion.tasks.notify_user_conversion_failed")
    @patch("builtins.open", create=True)
    def test_unreadable_second_illumina_fastq_notifies(self, mock_open, mock_notify):
        call_count = [0]
        def _open(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                self._open(mock_open)
                return mock_open.return_value
            raise IOError("R2 missing")
        with patch("builtins.open", side_effect=_open):
            poll_assembly_start(assembly_type="illumina", dest_path="/tmp/R1.fastq.gz",
                                dest_path_2="/tmp/R2.fastq.gz", user_id=self.user.id)
        mock_notify.assert_called_once()
        self.assertIn("Failed to read second fastq", str(mock_notify.call_args))

    @patch("conversion.tasks.notify_user_server_busy")
    @patch("conversion.tasks.poll_conversion_status")
    @patch("builtins.open", create=True)
    @patch("conversion.tasks.sequence_ont", return_value={"status": "busy"})
    def test_busy_retries_then_notifies_on_exhaustion(self, _, mock_open, __, mock_notify):
        self._open(mock_open)
        for effect, expect_notify in [(None, False), (MaxRetriesExceededError(), True)]:
            with self.subTest(exhausted=expect_notify):
                with patch.object(poll_assembly_start, "retry", side_effect=effect) as mock_retry:
                    task = self._task(job_id=f"j-{expect_notify}")
                    poll_assembly_start(assembly_type="ont", dest_path="/tmp/R1.fastq.gz", task_id=task.id)
                if expect_notify:
                    mock_notify.assert_called_once()
                else:
                    mock_retry.assert_called_once_with(countdown=60)
                mock_notify.reset_mock()

    @patch("conversion.tasks.poll_conversion_status")
    @patch("conversion.tasks.notify_user_conversion_started")
    @patch("builtins.open", create=True)
    @patch("conversion.tasks.sequence_ont", return_value={"job_id": "seq-cv", "status": "running"})
    def test_complete_version_forwarded(self, _, mock_open, __, mock_poll):
        self._open(mock_open)
        poll_assembly_start(assembly_type="ont", dest_path="/tmp/R1.fastq.gz",
                            user_id=self.user.id, complete_version=True)
        task = ConversionTask.objects.get(external_job_id="seq-cv")
        mock_poll.delay.assert_called_once_with(task.id, complete_version=True)


class PollAnnotationFromAssemblyStartTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def _prev(self, job_id="seq-1"):
        return ConversionTask.objects.create(
            external_job_id=job_id, status="completed",
            input_path="/tmp/reads.fastq.gz", task_type="assembly_ont", user=self.user,
        )

    def _pending(self):
        return ConversionTask.objects.create(
            external_job_id=None, status="pending",
            input_path="/tmp/reads.fastq.gz", task_type="annotation", user=self.user,
        )

    def _upload_fasta(self, task, content=FASTA):
        u = FileUpload.objects.create(user=self.user)
        u.file.save(f"assembly_{task.external_job_id}.fasta", ContentFile(content), save=True)

    @patch("conversion.tasks.poll_annotation_start.delay")
    def test_happy_path(self, mock_delay):
        prev, pending = self._prev("seq-ok"), self._pending()
        self._upload_fasta(prev)
        poll_annotation_from_assembly_start(job_id=prev.external_job_id,
                                            user_id=self.user.id, new_task_id=pending.id)
        mock_delay.assert_called_once_with(fasta_bytes=FASTA, task_id=pending.id,
                                           user_id=self.user.id, complete_version=False)

    @patch("conversion.tasks.poll_annotation_start.delay")
    def test_complete_version_forwarded(self, mock_delay):
        prev, pending = self._prev("seq-cv"), self._pending()
        self._upload_fasta(prev)
        poll_annotation_from_assembly_start(job_id=prev.external_job_id,
                                            user_id=self.user.id, new_task_id=pending.id,
                                            complete_version=True)
        self.assertTrue(mock_delay.call_args[1].get("complete_version"))

    @patch("conversion.tasks.notify_user_conversion_failed")
    @patch("conversion.tasks.poll_annotation_start.delay")
    def test_failure_paths(self, mock_delay, mock_notify):
        cases = [
            ("missing previous task", "no-such-job", False, False),
            ("no fasta file",         "seq-no-file",  True,  False),
            ("empty fasta",           "seq-empty",    True,  True),
        ]
        for label, job_id, create_prev, upload_empty in cases:
            with self.subTest(label=label):
                pending = self._pending()
                if create_prev:
                    prev = self._prev(job_id)
                    if upload_empty:
                        self._upload_fasta(prev, content=b"")
                poll_annotation_from_assembly_start(job_id=job_id, user_id=self.user.id,
                                                    new_task_id=pending.id)
                mock_notify.assert_called_once()
                mock_delay.assert_not_called()
                mock_notify.reset_mock()

    @patch("conversion.tasks.notify_user_conversion_failed")
    @patch("conversion.tasks.poll_annotation_start.delay")
    def test_user_mismatch_cannot_access_other_users_assembly(self, mock_delay, mock_notify):
        other = make_user(username="other")
        prev = ConversionTask.objects.create(
            external_job_id="seq-other", status="completed",
            input_path="/tmp/reads.fastq.gz", task_type="assembly_ont", user=other,
        )
        poll_annotation_from_assembly_start(job_id=prev.external_job_id,
                                            user_id=self.user.id, new_task_id=self._pending().id)
        mock_notify.assert_called_once()
        mock_delay.assert_not_called()