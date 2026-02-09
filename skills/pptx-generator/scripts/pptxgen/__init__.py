"""Internal helpers for the PPTX generator skill."""

from .api import generate_pptx_from_config, write_config
from .cli import run_cli
from .errors import ConfigValidationError
from .legacy_adapter import adapt_legacy_pptx_spec, normalize_legacy_layout
from .qa_pipeline import export_snapshots, run_qa_pipeline
from .validation import validate_config, validate_config_file

__all__ = [
    "ConfigValidationError",
    "adapt_legacy_pptx_spec",
    "export_snapshots",
    "generate_pptx_from_config",
    "normalize_legacy_layout",
    "run_cli",
    "run_qa_pipeline",
    "validate_config",
    "validate_config_file",
    "write_config",
]
