import os
import shutil
import tempfile
import zipfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import File
from core.utils import create_file_zip, upload_file

User = get_user_model()


class UtilsTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_dir)
        self.media_override.enable()
        self.user = User.objects.create_user(username="user", password="pass1234")

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_dir, ignore_errors=True)

    def test_upload_file_requires_a_file(self):
        with self.assertRaises(ValueError):
            upload_file(None, self.user, File.FileType.FASTA)

    def test_upload_file_stores_content_under_user_and_type(self):
        upload = upload_file(SimpleUploadedFile("sample.fasta", b">a\nACGT\n"), self.user, File.FileType.FASTA)

        self.assertEqual(upload.user, self.user)
        self.assertEqual(upload.file_type, File.FileType.FASTA)
        self.assertIn(f"user_{self.user.id}/fasta/", upload.file.name.replace("\\", "/"))
        with upload.file.open("rb") as f:
            self.assertEqual(f.read(), b">a\nACGT\n")

    def test_upload_file_keeps_both_files_on_name_collision(self):
        first = upload_file(SimpleUploadedFile("sample.fasta", b"first"), self.user, File.FileType.FASTA)
        second = upload_file(SimpleUploadedFile("sample.fasta", b"second"), self.user, File.FileType.FASTA)

        self.assertNotEqual(first.file.name, second.file.name)
        with first.file.open("rb") as f:
            self.assertEqual(f.read(), b"first")
        with second.file.open("rb") as f:
            self.assertEqual(f.read(), b"second")

    def test_create_file_zip_contains_every_upload(self):
        uploads = [
            upload_file(SimpleUploadedFile("r1.fastq.gz", b"R1"), self.user, File.FileType.FASTQ),
            upload_file(SimpleUploadedFile("r2.fastq.gz", b"R2"), self.user, File.FileType.FASTQ),
        ]
        zip_path = create_file_zip(uploads)
        try:
            with zipfile.ZipFile(zip_path) as archive:
                self.assertEqual(sorted(archive.namelist()), ["r1.fastq.gz", "r2.fastq.gz"])
                self.assertEqual(archive.read("r1.fastq.gz"), b"R1")
        finally:
            os.unlink(zip_path)
