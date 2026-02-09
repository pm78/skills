from __future__ import annotations

import subprocess
from pathlib import Path


def test_cli_shows_clean_validation_error(tmp_path: Path) -> None:
    bad_config = tmp_path / "bad.json"
    bad_config.write_text('{"presentation": {"slides": "oops"}}', encoding="utf-8")

    script = Path(__file__).resolve().parents[1] / "scripts" / "generate_pptx.py"
    output = tmp_path / "out.pptx"

    result = subprocess.run(
        [
            "python3",
            str(script),
            "--config",
            str(bad_config),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Configuration validation failed" in result.stderr
    assert "Traceback" not in result.stderr
