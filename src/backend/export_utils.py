# export_utils.py
import os
from pathlib import Path
import logging
import subprocess
import tempfile
import time

logger = logging.getLogger(__name__)


def write_latex(latex_text: str, out_dir: str, filename_prefix: str) -> str:
    """
    Writes latex_text to out_dir/filename_prefix.tex and returns path.
    """
    os.makedirs(out_dir, exist_ok=True)
    tex_path = Path(out_dir) / f"{filename_prefix}.tex"
    tex_path.write_text(latex_text, encoding="utf-8")
    return str(tex_path)


def _ensure_full_document(lt_text: str) -> str:
    """
    If the model output is a fragment (no \documentclass), wrap it with a minimal preamble.
    If it already contains \documentclass, leave as-is but ensure \end{document} present.
    """
    t = lt_text.strip()

    # If it's a fenced code block, strip triple backticks
    if t.startswith("```"):
        # remove the first fence and optional language tag
        lines = t.splitlines()
        # drop leading fence
        lines = lines[1:]
        # drop trailing fence if present
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()

    # Ensure we have \end{document}
    if r"\documentclass" not in t:
        pre = [
            r"\documentclass[11pt]{article}",
            r"\usepackage{amsmath}",
            r"\usepackage{amssymb}",
            r"\usepackage{geometry}",
            r"\usepackage{fontspec}",  # works with xelatex/lualatex
            r"\geometry{margin=1in}",
            r"\setmainfont{Latin Modern Roman}",  # safe default on many TeX installs
            r"\begin{document}",
        ]
        doc = "\n".join(pre) + "\n\n" + t
        if r"\end{document}" not in doc:
            doc += "\n\n\\end{document}\n"
        return doc
    else:
        # has \documentclass — ensure end document
        if r"\end{document}" not in t:
            t = t + "\n\n\\end{document}\n"
        return t


def try_make_pdf_from_latex(lt_text: str, out_dir: str, filename_prefix: str) -> str:
    """
    Create a PDF from the LaTeX source `lt_text`.
    Returns the absolute path to created PDF, or empty string on failure.
    """
    try:
        full_doc = _ensure_full_document(lt_text)

        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = Path(tmpdir) / "doc.tex"
            tex_path.write_text(full_doc, encoding="utf-8")

            # Prefer xelatex (better unicode / fontspec support). Run twice for refs.
            cmd = ["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name]
            logger.info("Running xelatex in %s", tmpdir)
            try:
                subprocess.run(cmd, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(cmd, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                logger.info("xelatex failed, attempting pdflatex fallback: %s", e)
                # fallback to pdflatex without fontspec (still may fail on unicode)
                cmd2 = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name]
                subprocess.run(cmd2, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(cmd2, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            pdf_tmp = Path(tmpdir) / "doc.pdf"
            if not pdf_tmp.exists():
                logger.error("PDF not created at expected path %s", pdf_tmp)
                return ""
            os.makedirs(out_dir, exist_ok=True)
            final_pdf = Path(out_dir) / f"{filename_prefix}.pdf"
            # if file exists append timestamp to avoid clobbering
            if final_pdf.exists():
                final_pdf = Path(out_dir) / f"{filename_prefix}_{int(time.time())}.pdf"
            pdf_tmp.replace(final_pdf)
            return str(final_pdf)
    except Exception as e:
        logger.exception("LaTeX -> PDF conversion failed: %s", e)
        return ""
    