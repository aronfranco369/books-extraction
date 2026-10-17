"""Compile editable Chemfig fragments to external SVG assets (never through KaTeX).

Requires PyMuPDF and Tectonic; set TECTONIC or put tectonic on PATH.
On Linux run setup.sh (installs tectonic to ~/.local/bin). On Windows, tools/tectonic/tectonic.exe is used if present.
"""
import hashlib
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile

import pymupdf

ASSETS = Path(__file__).resolve().parents[1] / "assets"
PREAMBLE = r"""\documentclass[12pt,border=4pt]{standalone}
\usepackage{chemfig}
\usepackage[version=4]{mhchem}
\setchemfig{atom sep=2em,bond style={line width=0.5pt}}
\begin{document}
"""


def render(source, asset_dir="chemical_structures"):
    if not isinstance(source, str) or not source.strip() or r"\chemfig" not in source:
        raise ValueError("Chemfig source must contain a non-empty drawing")
    if any(x in source for x in (r"\documentclass", r"\begin{document}", r"\end{document}")):
        raise ValueError("Chemfig source must be a fragment, not a LaTeX document")
    folder = (ASSETS / asset_dir).resolve()
    if not folder.is_relative_to(ASSETS.resolve()):
        raise ValueError("Asset directory must be inside assets")
    document = PREAMBLE + source + "\n\\end{document}\n"
    key = hashlib.sha256(("svg-physical-units-v1\n" + document).encode()).hexdigest()[:24]
    target = folder / ("chemfig_" + key + ".svg")
    if not target.is_file():
        engine = os.environ.get("TECTONIC") or shutil.which("tectonic")
        if not engine:
            local = Path(__file__).parent / "tectonic" / "tectonic.exe"
            engine = str(local) if local.is_file() else None
        if not engine:
            raise RuntimeError("Chemfig rendering requires Tectonic; install it or set TECTONIC")
        with tempfile.TemporaryDirectory(prefix="chemfig-") as temp:
            tex = Path(temp) / "structure.tex"
            tex.write_text(document, encoding="utf-8")
            result = subprocess.run(
                [engine, "--untrusted", "--keep-logs", "--reruns", "1", str(tex)],
                cwd=temp, capture_output=True, text=True, timeout=240,
            )
            pdf = tex.with_suffix(".pdf")
            if result.returncode or not pdf.is_file():
                raise RuntimeError("Chemfig compilation failed:\n" + (result.stdout + result.stderr)[-6000:])
            with pymupdf.open(pdf) as doc:
                if len(doc) != 1:
                    raise ValueError("A chemical_structure must render to exactly one page")
                svg = doc[0].get_svg_image(text_as_path=True)
                # MuPDF emits PDF point dimensions as unitless SVG pixels. Keep
                # their physical size so 12pt atoms match the viewer's 12pt text.
                svg = re.sub(r'\b(width|height)="([0-9.]+)"', r'\1="\2pt"', svg, count=2)
            folder.mkdir(parents=True, exist_ok=True)
            target.write_text(svg, encoding="utf-8")
    return target.relative_to(ASSETS).as_posix()


def block(source, asset_dir="chemical_structures"):
    return {"type": "chemical_structure", "format": "chemfig", "source": source,
            "rendered_asset": render(source, asset_dir)}
