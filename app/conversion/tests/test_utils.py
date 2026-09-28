import shutil
import tempfile

from django.test import TestCase
from django.contrib.auth import get_user_model


User = get_user_model()


class UtilsTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)