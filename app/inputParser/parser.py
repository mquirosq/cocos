import pickle
from pathlib import Path
import torch
from typing import Optional, Iterable

from ai_model.model_classes import BaselineMLP, TowerMLP, TwoTowerMLP


def presence_from_list(model_features, file_upload):
    """Create presence/absence vector for `model_features` based on a single `file_upload`.

    Args:
        model_features: iterable of feature names expected by the model (e.g. gene identifiers)
        file_upload: a single `FileUpload` instance with a `genes` related manager
    Returns:
        A list of 0/1 values indicating absence/presence of each feature in `model_features`.
    """

    # If file_upload is None or doesn't have genes, return all zeros
    present_features = set()
    genes = getattr(file_upload, 'genes', None)
    if genes is None:
        return [0] * len(list(model_features))

    # Iterate genes and gather identifier lists
    gene_iter = genes.all()

    for gene in gene_iter:
        ids = gene.identifiers_list() or []

        for gid in ids:
            present_features.add(str(gid).strip().lower())

    # Normalize
    model_features_norm = [str(f).strip().lower() for f in model_features]

    presence_vector = [1 if feat in present_features else 0 for feat in model_features_norm]

    return presence_vector

# Get column names from columns.pkl
def get_model_features_from_columns(column_file_name):
    
    base_dir = Path(__file__).resolve().parents[1]
    pkl_path = base_dir / 'ai_model' / column_file_name

    with open(pkl_path, 'rb') as f:
        columns = pickle.load(f)

    feature_index = {feat: i for i, feat in enumerate(columns)}
    n_features = len(columns)

    return columns, feature_index, n_features

# Modify column names to ensure they match the format expected by the model
def process_column_names(names: Iterable[str]) -> list[str]:
    """Ensure each column name starts with the UniRef50 prefix and delete antibiotic prediction columns.

    Args:
        names: iterable of column name strings

    Returns:
        List of normalized column names.
    """
    # Delete columns starting with a_
    names = [n for n in names if not str(n).startswith("a_")]

    out = [n if n.startswith("UniRef:UniRef50_") else f"UniRef:UniRef50_{n}" for n in names]
    # Add prefix if missing
    print(f"Processed column names: (total {len(out)})")  # Debug print
    return out

# Main function to load model and get prediction for testing
def load_model(model_name: str, antibiotic: Optional[str] = None):
    """Instantiate `model_name` and load weights.

    Args:
        model_name: 'BaselineMLP' | 'TowerMLP' | 'TwoTowerMLP'
        antibiotic: name of the antibiotic model file (used when `weights_path` is not given)
        weights_path: explicit path to the .pt file; overrides `antibiotic` if provided
        column_file_name: name of the column file (default is 'columns.pkl')

    Returns:
        A PyTorch model in `eval()` mode with weights loaded.
    """
    resolved_path = _resolve_weights_path(antibiotic, None)

    print(f"Resolved weights path: {resolved_path}")  # Debug print

    if model_name == "BaselineMLP":
        # Determine input dimension from the saved columns (columns.pkl)
        input_dim = _get_meta("input_dim")
        
        print(f"Determined input dimension for BaselineMLP: {input_dim}")  # Debug print
        model = BaselineMLP(input_dim=input_dim, hidden_dims=[512, 256], dropout=0.2)
    elif model_name == "TowerMLP":
        input_dim = _get_meta("input_dim")
        model = TowerMLP(input_dim=input_dim, hidden_dims=[512, 256], dropout=0.2)
    elif model_name == "TwoTowerMLP":
        raise ValueError("TwoTowerMLP is not supported in this version of the input parsing service")
    else:
        raise ValueError(f"Unknown model name: {model_name}")

    checkpoint = torch.load(resolved_path, map_location="cpu")
    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        state_dict = checkpoint["state_dict"]
    else:
        state_dict = checkpoint

    model.load_state_dict(state_dict)
    model.eval()
    return model

# Helper functions
def _resolve_weights_path(antibiotic: Optional[str], explicit_path: Optional[str]):
    if explicit_path:
        return explicit_path
    if not antibiotic:
        raise ValueError("Either `antibiotic` or `explicit_path` must be provided to locate weights")
    
    # TODO: Actually use de metadata (should be defined in the database)
    base_dir = Path(__file__).resolve().parents[1]
    pesos_dir = base_dir / 'ai_model' / 'pesos' / 'BAKTA50'
    candidate = pesos_dir / f"{antibiotic}.pt"
    if not candidate.exists():
        raise FileNotFoundError(f"Weights file not found: {candidate}")
    
    return str(candidate)

def _get_meta(key: str, default=None):
    # TODO: Implement metadata
    if key == "input_dim":
        columns = get_model_features_from_columns('bakta50_columns.pkl')
        columns = process_column_names(columns[0])  # Get the list of features (column names) and process them
        return len(columns)

    return None


# Get prediction from model
def get_prediction_for_antibiotic(model_name: str, antibiotic: Optional[str] = None, weights_path: Optional[str] = None, file_upload=None):
    """Helper function to load a model and get its prediction for testing."""
    model = load_model(model_name, antibiotic)

    print(f"Model {model_name} loaded successfully. Preparing input vector...")

    # Get and process model features to create input vector
    feature_list = get_model_features_from_columns('bakta50_columns.pkl')[0]
    feature_list = process_column_names(feature_list)
    input = presence_from_list(feature_list, file_upload)
    input_tensor = torch.FloatTensor([input])

    with torch.no_grad():
        raw_prediction = model(input_tensor)
        probability = torch.sigmoid(raw_prediction).squeeze().item() # TODO: Maybe?

    return probability