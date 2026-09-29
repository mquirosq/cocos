from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from conversion.models import ConversionTask
from core.models import File, Gene

User = get_user_model()

class ConversionTaskModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="pass1234")

    def test_conversion_task_external_id_validation(self):
        cases = [
            ("pending", None, False),
            ("pending", "job-0", False),
            ("running", None, True),
            ("running", "job-1", False),
            ("completed", "job-2", False),
        ]
        for status, job_id, should_raise in cases:
            with self.subTest(status=status, job_id=job_id):
                task = ConversionTask(
                    external_job_id=job_id,
                    status=status,
                    input_files=[File.objects.create(file="/tmp/input")],
                    output_files=[File.objects.create(file="/tmp/output")],
                    task_type="annotation",
                    user=self.user,
                )
                if should_raise:
                    with self.assertRaises(ValidationError):
                        task.save()
                else:
                    task.save()
                    self.assertEqual(task.status, status)
