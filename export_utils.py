# export_utils.py
import os
from pathlib import Path
import logging
import subprocess
import re

logger = logging.getLogger(__name__)

def clean_latex(text: str) -> str:
    """
    Basic cleaning: ensure isolated math commands are wrapped, and escape stray characters if needed.
    This is conservative — the model should ideally produce valid LaTeX already.
    """
    # Wrap common single-token latex commands if not in math mode (best-effort)
    replacements = [
        r'\\epsilon',
        r'\\alpha',
        r'\\beta',
        r'\\gamma',
        r'\\delta',
        r'\\theta',
        r'\\lambda',
        r'\\mu',
        r'\\sigma',
        r'\\pi'
    ]
    for symbol in replacements:
        text = re.sub(rf'(?<!\$)({symbol})(?!\$)', r'$\1$', text)
    return text

def write_latex(latex_text: str, out_dir: str, filename_prefix: str) -> str:
    """
    Writes latex_text to out_dir/filename_prefix.tex and returns path.
    """
    os.makedirs(out_dir, exist_ok=True)
    tex_path = Path(out_dir) / f"{filename_prefix}.tex"
    tex_content = clean_latex(latex_text)
    tex_path.write_text(tex_content, encoding="utf-8")
    return str(tex_path)

def try_make_pdf_from_latex(tex_path: str) -> str:
    """
    Try pypandoc first, then try calling pdflatex (twice) as fallback.
    Return PDF path or empty string.
    """
    out_pdf = str(Path(tex_path).with_suffix(".pdf"))

    # 1) Try pypandoc (if available)
    try:
        import pypandoc
        logger.info("Converting LaTeX -> PDF with pypandoc")
        # pypandoc will call pdflatex under the hood, too; ensure pandoc & texlive present
        pypandoc.convert_file(tex_path, "pdf", outputfile=out_pdf, format="latex")
        if Path(out_pdf).exists():
            return out_pdf
    except Exception as e:
        logger.info("pypandoc conversion not available or failed: %s", e)

    # 2) Fallback: run pdflatex directly (recommended to run in a temporary dir)
    try:
        tex_file = Path(tex_path).resolve()
        workdir = tex_file.parent
        cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_file.name]
        # run twice to resolve refs
        subprocess.run(cmd, cwd=workdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(cmd, cwd=workdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        candidate = workdir / tex_file.with_suffix(".pdf").name
        if candidate.exists():
            return str(candidate)
    except Exception as e:
        logger.info("pdflatex fallback failed: %s", e)

    return ""
