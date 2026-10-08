from unittest.mock import MagicMock, patch, sentinel

from django.test import TestCase

from prediction.prediction import get_prediction, get_prediction_matrix, prepare_prediction_csv

GET_MODEL_ADAPTER = "prediction.prediction.get_model_adapter_class"


def make_mock_adapter(predict_return_value=0.73):
    fake_adapter = MagicMock()
    fake_adapter.predict.return_value = predict_return_value
    fake_cls = MagicMock(return_value=fake_adapter)
    return fake_cls, fake_adapter


class GetPredictionTests(TestCase):
    @patch(GET_MODEL_ADAPTER)
    def test_builds_adapter_loads_and_predicts(self, mock_get_adapter):
        fake_cls, fake_adapter = make_mock_adapter(0.73)
        mock_get_adapter.return_value = fake_cls
        call_order = []
        fake_adapter.load.side_effect = lambda: call_order.append("load")
        fake_adapter.predict.side_effect = lambda _: call_order.append("predict") or 0.73

        result = get_prediction("base_bakta_50", "amikacin", file=sentinel.upload)

        self.assertEqual(result, 0.73)
        mock_get_adapter.assert_called_once_with("base_bakta_50")
        fake_cls.assert_called_once_with(antibiotic="amikacin")
        fake_adapter.predict.assert_called_once_with(sentinel.upload)
        self.assertEqual(call_order, ["load", "predict"])

    @patch(GET_MODEL_ADAPTER, return_value=None)
    def test_unknown_model_raises_with_its_name(self, _):
        with self.assertRaisesRegex(ValueError, "does_not_exist"):
            get_prediction("does_not_exist", "amikacin", file=None)


class GetPredictionMatrixTests(TestCase):
    @patch(GET_MODEL_ADAPTER)
    def test_rows_are_antibiotics_and_columns_are_models(self, mock_get_adapter):
        values = {("model_a", "amikacin"): 0.1, ("model_b", "amikacin"): 0.2,
                  ("model_a", "ampicillin"): 0.3, ("model_b", "ampicillin"): 0.4}

        def adapter_for(model_name):
            def build(antibiotic):
                adapter = MagicMock()
                adapter.predict.return_value = values[(model_name, antibiotic)]
                return adapter
            return build

        mock_get_adapter.side_effect = adapter_for

        result = get_prediction_matrix(["model_a", "model_b"], ["amikacin", "ampicillin"], file=sentinel.upload)

        self.assertEqual(result, {
            "models": ["model_a", "model_b"],
            "antibiotics": ["amikacin", "ampicillin"],
            "data": [[0.1, 0.2], [0.3, 0.4]],
        })

    @patch(GET_MODEL_ADAPTER)
    def test_one_failure_gives_no_result_without_affecting_others(self, mock_get_adapter):
        fake_cls, _ = make_mock_adapter(0.8)
        mock_get_adapter.side_effect = lambda name: None if name == "bad_model" else fake_cls

        result = get_prediction_matrix(["good_model", "bad_model"], ["amikacin"], file=sentinel.upload)

        self.assertEqual(result["data"], [[0.8, "NO_RESULT"]])

    def test_empty_inputs(self):
        self.assertEqual(get_prediction_matrix([], [], file=None)["data"], [])
        self.assertEqual(get_prediction_matrix([], ["amikacin"], file=None)["data"], [[]])


class PreparePredictionCsvTests(TestCase):
    def test_rounds_values_blanks_missing_and_averages(self):
        matrix = {
            "models": ["a", "b"],
            "antibiotics": ["amikacin", "ampicillin", "colistin"],
            "data": [[0.123456, 0.5], [0.2, "NO_RESULT"], ["NO_RESULT", None]],
        }

        models, rows = prepare_prediction_csv(matrix)

        self.assertEqual(models, ["a", "b"])
        self.assertEqual(rows, [
            ["amikacin", 0.1235, 0.5, 0.3117],
            ["ampicillin", 0.2, "", 0.2],
            ["colistin", "", "", ""],
        ])

    def test_rejects_malformed_matrices(self):
        cases = [
            ("not a dict", []),
            ("missing keys", {"models": ["a"]}),
            ("row count mismatch", {"models": ["a"], "antibiotics": ["x", "y"], "data": [[0.1]]}),
            ("column count mismatch", {"models": ["a", "b"], "antibiotics": ["x"], "data": [[0.1]]}),
        ]
        for label, matrix in cases:
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    prepare_prediction_csv(matrix)
