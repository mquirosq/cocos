from unittest.mock import MagicMock, patch

from django.test import TestCase

from prediction.service import get_prediction


class PredictionServiceTests(TestCase):
    
    @patch("prediction.service.get_model_adapter_class")
    def test_get_prediction_calls_load_and_predict(self, mock_get_model_adapter_class):
        fake_adapter = MagicMock()
        fake_adapter.predict.return_value = 0.73
        fake_cls = MagicMock(return_value=fake_adapter)

        mock_get_model_adapter_class.return_value = fake_cls
        out = get_prediction("base_bakta_50", "ampicillin", file_upload=object())

        fake_cls.assert_called_once_with(antibiotic="ampicillin")
        fake_adapter.load.assert_called_once_with()
        fake_adapter.predict.assert_called_once()
        self.assertEqual(out, 0.73)

    @patch("prediction.service.get_model_adapter_class", return_value=None)
    def test_get_prediction_raises_when_model_missing(self, _mock_get_model_adapter_class):
        with self.assertRaisesRegex(ValueError, "not found in registry"):
            get_prediction("does_not_exist", "ampicillin", file_upload=None)
