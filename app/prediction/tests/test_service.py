from unittest.mock import MagicMock, patch, sentinel

from django.test import TestCase

from prediction.service import get_prediction, get_prediction_matrix


def make_mock_adapter(predict_return_value=0.73):
    """Helper to build a mock adapter + class pair."""
    fake_adapter = MagicMock()
    fake_adapter.predict.return_value = predict_return_value
    fake_cls = MagicMock(return_value=fake_adapter)
    return fake_cls, fake_adapter


GET_MODEL_ADAPTER = "prediction.service.get_model_adapter_class"


class GetPredictionTests(TestCase):

    @patch(GET_MODEL_ADAPTER)
    def test_returns_adapter_prediction(self, mock_get_model_adapter_class):
        fake_cls, fake_adapter = make_mock_adapter(predict_return_value=0.73)
        mock_get_model_adapter_class.return_value = fake_cls

        result = get_prediction("base_bakta_50", "amikacin", file_upload=sentinel.upload)

        self.assertEqual(result, 0.73)

    @patch(GET_MODEL_ADAPTER)
    def test_adapter_instantiated_with_antibiotic(self, mock_get_model_adapter_class):
        fake_cls, _ = make_mock_adapter()
        mock_get_model_adapter_class.return_value = fake_cls

        get_prediction("base_bakta_50", "amikacin", file_upload=sentinel.upload)

        fake_cls.assert_called_once_with(antibiotic="amikacin")

    @patch(GET_MODEL_ADAPTER)
    def test_load_called_before_predict(self, mock_get_model_adapter_class):
        fake_cls, fake_adapter = make_mock_adapter()
        mock_get_model_adapter_class.return_value = fake_cls
        call_order = []
        fake_adapter.load.side_effect = lambda: call_order.append("load")
        fake_adapter.predict.side_effect = lambda _: call_order.append("predict")

        get_prediction("base_bakta_50", "amikacin", file_upload=sentinel.upload)

        self.assertEqual(call_order, ["load", "predict"])

    @patch(GET_MODEL_ADAPTER)
    def test_predict_receives_file_upload(self, mock_get_model_adapter_class):
        fake_cls, fake_adapter = make_mock_adapter()
        mock_get_model_adapter_class.return_value = fake_cls

        get_prediction("base_bakta_50", "amikacin", file_upload=sentinel.upload)

        fake_adapter.predict.assert_called_once_with(sentinel.upload)

    @patch(GET_MODEL_ADAPTER)
    def test_registry_queried_with_model_name(self, mock_get_model_adapter_class):
        fake_cls, _ = make_mock_adapter()
        mock_get_model_adapter_class.return_value = fake_cls

        get_prediction("base_bakta_50", "amikacin", file_upload=sentinel.upload)

        mock_get_model_adapter_class.assert_called_once_with("base_bakta_50")

    @patch(GET_MODEL_ADAPTER, return_value=None)
    def test_raises_value_error_when_model_not_in_registry(self, _):
        with self.assertRaisesRegex(ValueError, "not found in registry"):
            get_prediction("does_not_exist", "amikacin", file_upload=None)

    @patch(GET_MODEL_ADAPTER, return_value=None)
    def test_error_message_includes_model_name(self, _):
        with self.assertRaisesRegex(ValueError, "does_not_exist"):
            get_prediction("does_not_exist", "amikacin", file_upload=None)


class GetPredictionMatrixTests(TestCase):

    @patch(GET_MODEL_ADAPTER)
    def test_returns_nested_dict_keyed_by_antibiotic_then_model(self, mock_get_model_adapter_class):
        fake_cls, fake_adapter = make_mock_adapter(predict_return_value=0.5)
        mock_get_model_adapter_class.return_value = fake_cls

        result = get_prediction_matrix(["model_a"], ["amikacin"], file_upload=sentinel.upload)

        self.assertIn("amikacin", result)
        self.assertIn("model_a", result["amikacin"])

    @patch(GET_MODEL_ADAPTER)
    def test_all_combinations_computed(self, mock_get_model_adapter_class):
        fake_cls, fake_adapter = make_mock_adapter(predict_return_value=0.5)
        mock_get_model_adapter_class.return_value = fake_cls

        result = get_prediction_matrix(
            ["model_a", "model_b"],
            ["amikacin", "amoxicillin"],
            file_upload=sentinel.upload,
        )

        self.assertEqual(set(result.keys()), {"amikacin", "amoxicillin"})
        for antibiotic in ("amikacin", "amoxicillin"):
            self.assertEqual(set(result[antibiotic].keys()), {"model_a", "model_b"})

    @patch(GET_MODEL_ADAPTER)
    def test_prediction_values_populated(self, mock_get_model_adapter_class):
        fake_cls, fake_adapter = make_mock_adapter(predict_return_value=0.9)
        mock_get_model_adapter_class.return_value = fake_cls

        result = get_prediction_matrix(["model_a"], ["amikacin"], file_upload=sentinel.upload)

        self.assertEqual(result["amikacin"]["model_a"], 0.9)

    @patch(GET_MODEL_ADAPTER)
    def test_failed_prediction_stored_as_no_result(self, mock_get_model_adapter_class):
        mock_get_model_adapter_class.return_value = None  # triggers ValueError

        result = get_prediction_matrix(["bad_model"], ["amikacin"], file_upload=sentinel.upload)

        self.assertEqual(result["amikacin"]["bad_model"], "NO_RESULT")

    @patch(GET_MODEL_ADAPTER)
    def test_one_failure_does_not_affect_other_predictions(self, mock_get_model_adapter_class):
        fake_cls, fake_adapter = make_mock_adapter(predict_return_value=0.8)

        def adapter_side_effect(model_name):
            return None if model_name == "bad_model" else fake_cls

        mock_get_model_adapter_class.side_effect = adapter_side_effect

        result = get_prediction_matrix(
            ["good_model", "bad_model"],
            ["amikacin"],
            file_upload=sentinel.upload,
        )

        self.assertEqual(result["amikacin"]["good_model"], 0.8)
        self.assertEqual(result["amikacin"]["bad_model"], "NO_RESULT")

    @patch(GET_MODEL_ADAPTER)
    def test_empty_inputs_return_empty_dict(self, mock_get_model_adapter_class):
        result = get_prediction_matrix([], [], file_upload=sentinel.upload)
        self.assertEqual(result, {})

    @patch(GET_MODEL_ADAPTER)
    def test_empty_models_list_returns_empty_rows(self, mock_get_model_adapter_class):
        result = get_prediction_matrix([], ["amikacin"], file_upload=sentinel.upload)
        self.assertEqual(result, {"amikacin": {}})