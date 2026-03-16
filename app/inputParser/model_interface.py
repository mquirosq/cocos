"""AI Model interface and registry.

Provides `ModelInterface` base class and a simple registry to register
model implementations by name. Use `@register_model()` on a subclass
to make it discoverable.
"""

class ModelInterface:
    """
    Model interface for predicting antibiotic resistance from a `FileUpload`.

    Implementations should provide:
      - `features()` -> Input features for the model (e.g. genes)
      - `load()` -> None
      - `predict(file_upload)` -> float

    file_upload is expected to be an identifier for a bakta-annotated file in the database (FileUpload instance))
    """

    def features(self, file_upload) -> list:
        """
        Return the features needed by the model (e.g. gene identifiers).
        """
        raise NotImplementedError()

    def load(self) -> None:
        """
        Load model weights and prepare for prediction.
        """
        raise NotImplementedError()

    def predict(self, file_upload) -> float:
        """
        Predict the probability of resistance for a given json bakta file.
        """ 
        raise NotImplementedError()