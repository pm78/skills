"""Export PPTX slides to images (PNG/JPG), optimized for WSL + Windows PowerPoint.

This script exists because python-pptx cannot render slides. In WSL environments,
we can call Windows PowerPoint via `powershell.exe` COM automation to export each
slide as an image, enabling a visual review loop.
"""

from __future__ import annotations

import argparse
import base64
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _is_wsl() -> bool:
    return bool(
        # Present on most WSL setups
        "WSL_INTEROP" in os.environ
        or "WSL_DISTRO_NAME" in os.environ
    )


def _wsl_to_windows_path(path: Path) -> str:
    wslpath = _which("wslpath")
    if not wslpath:
        raise RuntimeError("wslpath not found; cannot convert Linux path to Windows path for PowerPoint export.")
    result = subprocess.run([wslpath, "-w", str(path)], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _ps_single_quote(value: str) -> str:
    # PowerShell single-quoted strings escape single quotes by doubling them.
    return "'" + value.replace("'", "''") + "'"


def export_with_powerpoint(
    pptx_path: Path,
    outdir: Path,
    img_format: str,
    *,
    width: Optional[int],
    height: Optional[int],
) -> None:
    if not _which("powershell.exe"):
        raise RuntimeError("powershell.exe not found; cannot use Windows PowerPoint export method.")

    if _is_wsl():
        pptx_win = _wsl_to_windows_path(pptx_path)
        outdir_win = _wsl_to_windows_path(outdir)
    else:
        pptx_win = str(pptx_path)
        outdir_win = str(outdir)

    fmt = img_format.lower()
    if fmt in {"jpg", "jpeg"}:
        filter_name = "JPG"
    elif fmt == "png":
        filter_name = "PNG"
    else:
        raise ValueError(f"Unsupported format: {img_format}")

    width_expr = str(int(width)) if width else "$null"
    height_expr = str(int(height)) if height else "$null"

    ps_script = f"""
$ErrorActionPreference = 'Stop'

$pptxPath = {_ps_single_quote(pptx_win)}
$outDir = {_ps_single_quote(outdir_win)}
$filterName = {_ps_single_quote(filter_name)}
$scaleWidth = {width_expr}
$scaleHeight = {height_expr}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$ppt = New-Object -ComObject PowerPoint.Application
try {{
  # Some PowerPoint environments disallow hiding the window (Visible=0). Prefer
  # hidden when supported, but fall back to visible to avoid failing export.
  $ppt.Visible = 0
}} catch {{
  try {{ $ppt.Visible = 1 }} catch {{ }}
}}

try {{
  $presentation = $ppt.Presentations.Open($pptxPath, $true, $false, $false)
  try {{
    if ($scaleWidth -and $scaleHeight) {{
      $presentation.Export($outDir, $filterName, $scaleWidth, $scaleHeight)
    }} else {{
      $presentation.Export($outDir, $filterName)
    }}
  }} finally {{
    $presentation.Close()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($presentation) | Out-Null
  }}
}} finally {{
  $ppt.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}}
"""

    encoded = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
        check=True,
        capture_output=True,
        text=True,
    )


def export_with_libreoffice(pptx_path: Path, outdir: Path, img_format: str) -> None:
    soffice = _which("soffice") or _which("libreoffice")
    if not soffice:
        raise RuntimeError("LibreOffice not found (soffice/libreoffice); cannot use libreoffice export method.")

    fmt = img_format.lower()
    if fmt == "jpeg":
        fmt = "jpg"
    if fmt not in {"png", "jpg"}:
        raise ValueError(f"Unsupported format for LibreOffice: {img_format}")

    subprocess.run(
        [
            soffice,
            "--headless",
            "--nologo",
            "--nolockcheck",
            "--norestore",
            "--convert-to",
            fmt,
            "--outdir",
            str(outdir),
            str(pptx_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _slide_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"(\d+)", path.stem)
    return (int(match.group(1)) if match else 10**9, path.name.lower())


def write_gallery(outdir: Path, images: list[Path]) -> Path:
    gallery_path = outdir / "index.html"
    rows = "\n".join(
        [
            f'<div class="slide"><div class="label">{img.name}</div><img src="{img.name}" /></div>'
            for img in images
        ]
    )
    gallery_path.write_text(
        f"""<!doctype html>
<meta charset="utf-8" />
<title>Slide Snapshots</title>
<style>
  body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 18px; }}
  .slide {{ border: 1px solid #ddd; border-radius: 10px; padding: 12px; background: #fff; }}
  .label {{ font-size: 12px; color: #444; margin-bottom: 8px; }}
  img {{ width: 100%; height: auto; border-radius: 6px; }}
</style>
<h1>Slide Snapshots</h1>
<div class="grid">
{rows}
</div>
""",
        encoding="utf-8",
    )
    return gallery_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export PPTX slides to PNG/JPG images")
    parser.add_argument("--pptx", required=True, help="Path to PPTX file")
    parser.add_argument("--outdir", required=True, help="Output directory for images")
    parser.add_argument("--format", default="png", choices=["png", "jpg", "jpeg"], help="Image format")
    parser.add_argument(
        "--method",
        default="auto",
        choices=["auto", "powerpoint", "libreoffice"],
        help="Export method (default: auto)",
    )
    parser.add_argument("--width", type=int, default=1920, help="Image width in pixels (PowerPoint only)")
    parser.add_argument("--height", type=int, default=1080, help="Image height in pixels (PowerPoint only)")
    parser.add_argument("--gallery", action="store_true", help="Write an index.html gallery next to images")

    args = parser.parse_args()

    pptx_path = Path(args.pptx).resolve()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    if not pptx_path.exists():
        raise SystemExit(f"PPTX not found: {pptx_path}")

    try:
        if args.method == "libreoffice":
            export_with_libreoffice(pptx_path, outdir, args.format)
        elif args.method == "powerpoint":
            export_with_powerpoint(
                pptx_path,
                outdir,
                args.format,
                width=args.width,
                height=args.height,
            )
        else:
            soffice = _which("soffice") or _which("libreoffice")
            if soffice:
                export_with_libreoffice(pptx_path, outdir, args.format)
            else:
                export_with_powerpoint(
                    pptx_path,
                    outdir,
                    args.format,
                    width=args.width,
                    height=args.height,
                )
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        hint = (
            "If you are on WSL: either install LibreOffice in WSL (soffice), "
            "or ensure Windows interop + PowerPoint are available."
        )
        raise SystemExit(f"Slide export failed.\n{stderr}\n{hint}") from e
    except RuntimeError as e:
        raise SystemExit(str(e)) from e

    fmt = args.format.lower()
    if fmt == "jpeg":
        fmt = "jpg"
    images = sorted(outdir.glob(f"*.{fmt}"), key=_slide_sort_key)
    if not images:
        images = sorted(outdir.glob(f"*.{fmt.upper()}"), key=_slide_sort_key) + images

    if not images:
        raise SystemExit(f"No images were produced in {outdir}.")

    for img in images:
        print(img)

    if args.gallery:
        gallery_path = write_gallery(outdir, images)
        print(gallery_path)


if __name__ == "__main__":
    main()
