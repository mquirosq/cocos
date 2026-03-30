from unittest.mock import patch

from django.test import TestCase

from prediction.registry import (
    MODEL_REGISTRY,
    get_model_adapter_class,
    list_registered_models,
    register_model,
)


class RegistryTests(TestCase):
    def setUp(self):
        self._registry_backup = dict(MODEL_REGISTRY)
        MODEL_REGISTRY.clear()

    def tearDown(self):
        MODEL_REGISTRY.clear()
        MODEL_REGISTRY.update(self._registry_backup)

    def test_register_and_lookup_model_case_insensitive(self):
        @register_model("test_model")
        class DummyAdapter:
            def __init__(self, antibiotic: str):
                self.antibiotic = antibiotic

        self.assertIs(get_model_adapter_class("test_model"), DummyAdapter)
        self.assertIs(get_model_adapter_class("TEST_MODEL"), DummyAdapter)
        self.assertIn("test_model", list_registered_models())

    def test_register_uses_class_name_when_alias_missing(self):
        @register_model()
        class NamedAdapter:
            def __init__(self, antibiotic: str):
                self.antibiotic = antibiotic

        self.assertIs(get_model_adapter_class("namedadapter"), NamedAdapter)

    def test_get_model_adapter_class_returns_none_for_missing_name(self):
        self.assertIsNone(get_model_adapter_class(None))
        self.assertIsNone(get_model_adapter_class("unknown"))

    def test_register_model_requires_antibiotic_parameter(self):
        with self.assertRaises(TypeError):
            @register_model("invalid_adapter")
            class InvalidAdapter:
                def __init__(self):
                    pass

    @patch("prediction.registry.inspect.signature", side_effect=TypeError("boom"))
    def test_register_model_raises_when_signature_cannot_be_inspected(self, _mock_signature):
        with self.assertRaisesRegex(TypeError, "Cannot inspect __init__ of adapter"):
            @register_model("broken_adapter")
            class BrokenAdapter:
                def __init__(self, antibiotic: str):
                    self.antibiotic = antibiotic
