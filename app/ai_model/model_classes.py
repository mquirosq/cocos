"""
Neural network architectures for the antibiotic resistance baseline.

- BaselineMLP:   single-tower feed-forward network (for single feature source)
- TowerMLP:      encoder branch used inside the two-tower model
- TwoTowerMLP:   two parallel encoding branches + fusion head (for combined datasets)
"""
from typing import List

import torch
import torch.nn as nn


class BaselineMLP(nn.Module):
    """
    Simple feed-forward MLP for binary classification.

    Architecture: [Linear -> ReLU -> Dropout] x N  ->  Linear(last_dim, 1)
    Output: raw logits (use BCEWithLogitsLoss for training).
    """

    def __init__(self, input_dim: int, hidden_dims: List[int], dropout: float):
        super().__init__()
        layers: List[nn.Module] = []
        last_dim = input_dim
        for h in hidden_dims:
            layers.append(nn.Linear(last_dim, h))
            layers.append(nn.ReLU(inplace=True))
            if dropout and dropout > 0:
                layers.append(nn.Dropout(dropout))
            last_dim = h
        layers.append(nn.Linear(last_dim, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)

# TODO: delete
class TowerMLP(nn.Module):
    """
    Simple feed-forward MLP for binary classification.

    Architecture: [Linear -> ReLU -> Dropout] x N  ->  Linear(last_dim, 1)
    Output: raw logits (use BCEWithLogitsLoss for training).
    """

    def __init__(self, input_dim: int, hidden_dims: List[int], dropout: float):
        super().__init__()
        layers: List[nn.Module] = []
        last_dim = input_dim
        for h in hidden_dims:
            layers.append(nn.Linear(last_dim, h))
            layers.append(nn.ReLU(inplace=True))
            if dropout and dropout > 0:
                layers.append(nn.Dropout(dropout))
            last_dim = h
        layers.append(nn.Linear(last_dim, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)

# TODO: delete
class TwoTowerMLP(nn.Module):
    """
    Simple feed-forward MLP for binary classification.

    Architecture: [Linear -> ReLU -> Dropout] x N  ->  Linear(last_dim, 1)
    Output: raw logits (use BCEWithLogitsLoss for training).
    """

    def __init__(self, input_dim: int, hidden_dims: List[int], dropout: float):
        super().__init__()
        layers: List[nn.Module] = []
        last_dim = input_dim
        for h in hidden_dims:
            layers.append(nn.Linear(last_dim, h))
            layers.append(nn.ReLU(inplace=True))
            if dropout and dropout > 0:
                layers.append(nn.Dropout(dropout))
            last_dim = h
        layers.append(nn.Linear(last_dim, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)
