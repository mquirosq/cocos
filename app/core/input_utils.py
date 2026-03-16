import pickle
from pathlib import Path

# Utility functions for processing model input features and loading model metadata.
def presence_from_list(model_features, file_upload):
    present_features = set()
    genes = getattr(file_upload, 'genes', None)
    if genes is None:
        return [0] * len(list(model_features))

    for gene in genes.all():
        ids = gene.identifiers_list() or []
        for gid in ids:
            present_features.add(str(gid).strip().lower())

    model_features_norm = [str(f).strip().lower() for f in model_features]
    return [1 if feat in present_features else 0 for feat in model_features_norm]

def get_columns_from_pickle(model_name: str, column_file_name: str) -> list:
    base_dir = Path(__file__).resolve().parents[1]
    pkl_path = base_dir / 'ai_models' / model_name / column_file_name
    with open(pkl_path, 'rb') as f:
        columns = pickle.load(f)
    return columns

def get_model_weights_path(antibiotic: str, model_name: str) -> str:
    base_dir = Path(__file__).resolve().parents[1]
    pesos_dir = base_dir / 'ai_models' / model_name / 'pesos'
    candidate = pesos_dir / f"{antibiotic}.pt"
    if not candidate.exists():
        raise FileNotFoundError(f"Weights file not found: {candidate}")
    return str(candidate)
