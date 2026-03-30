import os
import shutil
import tempfile

from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from conversion.utils import delete_file_safely, get_upload_dir, upload_file


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
