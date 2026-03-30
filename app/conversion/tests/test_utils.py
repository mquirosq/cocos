import os
import shutil
import tempfile

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from conversion.models import FileUpload
from conversion.utils import (
    delete_file_safely,
    get_upload_dir,
    upload_file,
    get_result_filename_stem,
    read_persisted_upload_bytes,
)


User = get_user_model()


class UtilsTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @override_settings(UPLOADS_TEMP_SUBDIR="uploads/temp", UPLOADS_PERSISTENT_SUBDIR="uploads/persistent")
    def test_get_upload_dir_selects_temp_or_persistent(self):
        cases = [
            (False, "uploads/temp", "fasta"),
            (True, "uploads/persistent", "fastq"),
        ]
        for persistent, expected_part, file_kind in cases:
            with self.subTest(persistent=persistent):
                out = get_upload_dir(user_id=1, file_kind=file_kind, persistent=persistent)
                self.assertIn(expected_part, out)
                self.assertIn("user_1", out)
                self.assertIn(file_kind, out)

    def test_upload_file_validates_inputs(self):
        error_cases = [
            (None, {"upload_dir": self.tmp_dir}, "None file"),
            (SimpleUploadedFile("x.txt", b"x"), {}, "No upload_dir or user_id/file_kind"),
            (SimpleUploadedFile("x.txt", b"x"), {"user_id": 1}, "No file_kind"),
            (SimpleUploadedFile("x.txt", b"x"), {"file_kind": "fasta"}, "No user_id"),
        ]
        for file_arg, kwargs, desc in error_cases:
            with self.subTest(desc=desc):
                with self.assertRaises(ValueError):
                    upload_file(file_arg, **kwargs)

    def test_upload_file_writes_and_handles_collision(self):
        first = upload_file(SimpleUploadedFile("sample.txt", b"first"), upload_dir=self.tmp_dir)
        second = upload_file(SimpleUploadedFile("sample.txt", b"second"), upload_dir=self.tmp_dir)

        self.assertTrue(os.path.exists(first))
        self.assertTrue(os.path.exists(second))
        self.assertNotEqual(first, second)

        with open(first, "rb") as f:
            self.assertEqual(f.read(), b"first")
        with open(second, "rb") as f:
            self.assertEqual(f.read(), b"second")

    def test_delete_file_safely_success(self):
        target = os.path.join(self.tmp_dir, "x.txt")
        with open(target, "wb") as f:
            f.write(b"x")

        delete_file_safely(target)
        self.assertFalse(os.path.exists(target))

    def test_delete_file_safely_invalid_inputs(self):
        cases = [
            (None, "None path"),
            ("", "empty string path"),
        ]
        for invalid, desc in cases:
            with self.subTest(desc=desc):
                with self.assertRaises(ValueError):
                    delete_file_safely(invalid)

    def test_read_persisted_assembly_fasta_bytes(self):
        with override_settings(MEDIA_ROOT=self.tmp_dir):
            user = User.objects.create_user(username="util_user_fasta", password="pass1234")
            upload = FileUpload.objects.create(user=user)
            upload.file.save(
                f"{get_result_filename_stem('assembly', 'job-1')}.fasta",
                ContentFile(b">seq\nATGC\n"),
                save=True,
            )

            out = read_persisted_upload_bytes(
                user_id=user.id,
                filename_stem=get_result_filename_stem("assembly", "job-1"),
            )
            self.assertEqual(out, b">seq\nATGC\n")

    def test_read_persisted_annotation_json_bytes(self):
        with override_settings(MEDIA_ROOT=self.tmp_dir):
            user = User.objects.create_user(username="util_user_json", password="pass1234")
            upload = FileUpload.objects.create(user=user)
            upload.file.save(
                f"{get_result_filename_stem('annotation', 'ann-1')}.json",
                ContentFile(b'{"status":"ok"}'),
                save=True,
            )

            out = read_persisted_upload_bytes(
                user_id=user.id,
                filename_stem=get_result_filename_stem("annotation", "ann-1"),
            )
            self.assertEqual(out, b'{"status":"ok"}')

    def test_persisted_result_helpers_return_none_when_missing(self):
        user = User.objects.create_user(username="util_user_none", password="pass1234")
        self.assertIsNone(read_persisted_upload_bytes(user_id=user.id, filename_stem=get_result_filename_stem("assembly", "missing")))
        self.assertIsNone(read_persisted_upload_bytes(user_id=user.id, filename_stem=get_result_filename_stem("annotation", "missing")))
