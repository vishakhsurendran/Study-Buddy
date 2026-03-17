# export_utils.py (supabase upload aware)
import os
import re
import subprocess
import tempfile
import time
import logging
import shutil
from pathlib import Path

from supabase_client import supabase
from file_storage import StorageManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

storage = StorageManager()  # uses default buckets

def write_latex(latex_text: str, out_dir: str, filename_prefix: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    tex_path = Path(out_dir) / f"{filename_prefix}.tex"
    tex_path.write_text(latex_text, encoding="utf-8")
    return str(tex_path)

def _escape_percent_underscore_outside_math(text: str) -> str:
    """
    Naive escape: escapes '%' and '_' that are not already escaped and are outside inline ($...$)
    or display (\[...\] or $$...$$) math. This is not perfect, but helps avoid many LLM-produced
    stray characters that break compilation.
    """
    # We'll split the document into math and non-math parts using a simple delimiter approach.
    # Patterns: $...$, $$...$$, \[...\], \(...\) — naive, but good enough for most outputs.
    parts = []
    last = 0
    # regex finds math starts and ends (keeps delimiters)
    math_pat = re.compile(r'(\$\$.*?\$\$|\$.*?\$|\\\[.*?\\\]|\\\(.*?\\\))', re.DOTALL)
    for m in math_pat.finditer(text):
        # non-math part
        non_math = text[last:m.start()]
        # escape unescaped % and _
        non_math = re.sub(r'(?<!\\)%','\\%', non_math)
        non_math = re.sub(r'(?<!\\)_','\\_', non_math)
        parts.append(non_math)
        parts.append(m.group(0))  # math part unchanged
        last = m.end()
    # tail
    tail = text[last:]
    tail = re.sub(r'(?<!\\)%','\\%', tail)
    tail = re.sub(r'(?<!\\)_','\\_', tail)
    parts.append(tail)
    return "".join(parts)


def _ensure_full_document(lt_text: str) -> str:
    """
    Ensure the LaTeX text is a full document, inject commonly-needed packages and
    theorem/env definitions if the generated tex uses them. Also lightly sanitize.
    Returns modified LaTeX source.
    """
    t = lt_text or ""
    t = t.strip()

    # Remove triple-backtick fences from LLM output if present
    if t.startswith("```"):
        lines = t.splitlines()
        # remove first fence line and drop last fence if present
        if len(lines) >= 2:
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
        t = "\n".join(lines).strip()

    # Lightly escape problem characters outside math
    t = _escape_percent_underscore_outside_math(t)

    has_docclass = r"\documentclass" in t

    # If no \documentclass, create a minimal wrapper with useful packages
    if not has_docclass:
        pre = [
            r"\documentclass[11pt]{article}",
            r"\usepackage{amsmath}",
            r"\usepackage{amssymb}",
            r"\usepackage{amsfonts}",
            r"\usepackage{amsthm}",
            r"\usepackage{enumitem}",
            r"\usepackage{geometry}",
            r"\usepackage{fontspec}",
            r"\geometry{margin=1in}",
            r"\setmainfont{Latin Modern Roman}",
            r"\begin{document}",
        ]
        doc = "\n".join(pre) + "\n\n" + t
        if r"\end{document}" not in doc:
            doc += "\n\n\\end{document}\n"
        # ensure a basic theorem environment exists if text mentions theorem
        if re.search(r'\\begin\{theorem\}', doc) and r'\newtheorem{theorem}' not in doc:
            doc = doc.replace(r"\begin{document}", r"\newtheorem{theorem}{Theorem}" + "\n\n" + r"\begin{document}")
        return doc

    # If the doc already has \documentclass: attempt to inject missing packages/defs
    # We will insert packages before \begin{document}
    needed_pkgs = []
    body = t

    # Common macros -> packages
    if re.search(r'\\mathbb\b', t) and ("\\usepackage{amsfonts}" not in t and "\\usepackage{amssymb}" not in t):
        needed_pkgs.append(r"\usepackage{amsfonts}")
    if re.search(r'\\mathscr\b', t) and "\\usepackage{mathrsfs}" not in t:
        needed_pkgs.append(r"\usepackage{mathrsfs}")
    if re.search(r'\\mathcal\b', t) and "\\usepackage{mathrsfs}" not in t:
        # mathcal usually builtin, but keep it safe
        pass
    if re.search(r'\\begin\{theorem\}', t) or re.search(r'\\begin\{lemma\}', t) or re.search(r'\\begin\{proposition\}', t):
        if "\\usepackage{amsthm}" not in t:
            needed_pkgs.append(r"\usepackage{amsthm}")
        # add defaults for theorem-like envs if not defined
        if r'\newtheorem{theorem}' not in t:
            # we'll add one default theorem environment
            needed_pkgs.append(r"\newtheorem{theorem}{Theorem}")
    # Ensure enumitem if itemize/enumerate used
    if "\\begin{itemize}" in t and "\\usepackage{enumitem}" not in t:
        needed_pkgs.append(r"\usepackage{enumitem}")

    if needed_pkgs:
        idx = t.find(r"\begin{document}")
        if idx != -1:
            insert_block = "\n".join(needed_pkgs) + "\n"
            t = t[:idx] + insert_block + t[idx:]
        else:
            t = "\n".join(needed_pkgs) + "\n" + t

    # Ensure \end{document} present
    if r"\end{document}" not in t:
        t = t + "\n\n\\end{document}\n"

    return t

def try_make_pdf_from_latex(lt_text: str, out_dir: str, filename_prefix: str) -> str:
    """
    Create a PDF from the LaTeX source `lt_text`.
    Returns path or URL (depending on your upload helper) or empty string on failure.
    """
    try:
        full_doc = _ensure_full_document(lt_text)

        # Save the .tex to the out_dir for persistent debugging (useful in container mount)
        os.makedirs(out_dir, exist_ok=True)
        debug_tex_path = Path(out_dir) / f"{filename_prefix}.tex"
        debug_tex_path.write_text(full_doc, encoding="utf-8")
        logger.info("Wrote debug .tex to %s", debug_tex_path)

        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = Path(tmpdir) / "doc.tex"
            tex_path.write_text(full_doc, encoding="utf-8")

            cmd = ["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name]
            logger.info("Running xelatex in %s", tmpdir)

            try:
                subprocess.run(cmd, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(cmd, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                # capture output and log it for debugging
                stdout = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
                stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
                logger.info("xelatex failed: stdout:\n%s\nstderr:\n%s", stdout[:4000], stderr[:4000])
                # fallback to pdflatex
                cmd2 = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name]
                try:
                    subprocess.run(cmd2, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    subprocess.run(cmd2, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except subprocess.CalledProcessError as e2:
                    stdout2 = e2.stdout.decode("utf-8", errors="replace") if e2.stdout else ""
                    stderr2 = e2.stderr.decode("utf-8", errors="replace") if e2.stderr else ""
                    logger.error("pdflatex also failed: stdout:\n%s\nstderr:\n%s", stdout2[:4000], stderr2[:4000])
                    # copy the generated doc.tex to out_dir for manual inspection
                    try:
                        shutil.copy(tex_path, debug_tex_path)
                        # optionally copy the full tmpdir to out_dir/<prefix>-debug for deeper inspection
                        debug_folder = Path(out_dir) / f"{filename_prefix}-latex-debug"
                        if not debug_folder.exists():
                            shutil.copytree(tmpdir, str(debug_folder))
                            logger.info("Saved latex debug folder to %s", debug_folder)
                    except Exception:
                        logger.exception("Failed to save latex debug artifacts")
                    return ""

            pdf_tmp = Path(tmpdir) / "doc.pdf"
            if not pdf_tmp.exists():
                logger.error("PDF not created at expected path %s", pdf_tmp)
                return ""
            # move to final out_dir
            final_pdf = Path(out_dir) / f"{filename_prefix}.pdf"
            if final_pdf.exists():
                final_pdf = Path(out_dir) / f"{filename_prefix}_{int(time.time())}.pdf"
            pdf_tmp.replace(final_pdf)
            return str(final_pdf)
    except Exception as e:
        logger.exception("LaTeX -> PDF conversion failed: %s", e)
        return ""
    