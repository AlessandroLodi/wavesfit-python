"""Spectroscopy models, bounded fitting, and file-stream acquisition."""

from .backgrounds import background
from .fitting import FitResult, fit
from .models import (
    Component,
    Model,
    Parameter,
    default_model,
    doniach_sunjic,
    nexafs,
    voigt,
)

__version__ = "0.1.0"
__all__ = [
    "Component",
    "FitResult",
    "Model",
    "Parameter",
    "background",
    "default_model",
    "doniach_sunjic",
    "fit",
    "nexafs",
    "voigt",
]
