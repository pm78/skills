"""Custom exceptions for PPTX generator config/runtime errors."""

from __future__ import annotations


class ConfigValidationError(ValueError):
    """Raised when input JSON config is invalid for deck generation."""

    def __init__(self, issues: list[str]):
        self.issues = [str(i).strip() for i in issues if str(i).strip()]
        if not self.issues:
            self.issues = ["Invalid configuration"]
        super().__init__(self._format())

    def _format(self) -> str:
        lines = ["Configuration validation failed:"]
        for issue in self.issues:
            lines.append(f"- {issue}")
        return "\n".join(lines)
