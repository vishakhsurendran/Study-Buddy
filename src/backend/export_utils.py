# export_utils.py
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def write_markdown(md_text: str, out_dir: str, filename_prefix: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    md_path = Path(out_dir) / f"{filename_prefix}.md"
    md_path.write_text(md_text, encoding="utf-8")
    return str(md_path)


def write_latex(latex_text: str, out_dir: str, filename_prefix: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    tex_path = Path(out_dir) / f"{filename_prefix}.tex"
    tex_path.write_text(latex_text, encoding="utf-8")
    return str(tex_path)


def _escape_percent_underscore_outside_math(text: str) -> str:
    """
    Escapes % and _ outside simple math regions.
    """
    parts = []
    last = 0
    math_pat = re.compile(r"(\$\$.*?\$\$|\$.*?\$|\\\[.*?\\\]|\\\(.*?\\\))", re.DOTALL)

    for m in math_pat.finditer(text):
        non_math = text[last:m.start()]
        non_math = re.sub(r"(?<!\\)%", r"\\%", non_math)
        non_math = re.sub(r"(?<!\\)_", r"\\_", non_math)
        parts.append(non_math)
        parts.append(m.group(0))
        last = m.end()

    tail = text[last:]
    tail = re.sub(r"(?<!\\)%", r"\\%", tail)
    tail = re.sub(r"(?<!\\)_", r"\\_", tail)
    parts.append(tail)
    return "".join(parts)


def _replace_env_with_heading(text: str, env: str, title: str) -> str:
    """
    Replace \\begin{env}...\\end{env} with a safe subsection heading.
    """
    pat = re.compile(rf"\\begin\{{{re.escape(env)}\}}(.*?)\\end\{{{re.escape(env)}\}}", re.DOTALL)

    def repl(match: re.Match) -> str:
        body = match.group(1).strip()
        if body:
            return f"\\subsection*{{{title}}}\n{body}\n"
        return f"\\subsection*{{{title}}}\n"

    return pat.sub(repl, text)


def _sanitize_latex_body(t: str) -> str:
    """
    Make model output safer before wrapping/compiling.
    """
    t = t.strip()

    # Strip code fences if the model wrapped the answer.
    if t.startswith("```"):
        lines = t.splitlines()
        if len(lines) >= 2:
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
        t = "\n".join(lines).strip()

    # Remove unsupported package directives that the model might inject.
    t = re.sub(r"\\usepackage(\[[^\]]*\])?\{thmstyle\}\s*", "", t)

    # Remove explicit theorem declarations if the model adds them.
    t = re.sub(r"\\newtheorem\{[^}]+\}\{[^}]*\}(?:\[[^\]]*\])?\s*", "", t)

    # Convert risky or non-standard environments into plain subsection headings.
    env_map = {
        "theorem": "Theorem",
        "lemma": "Lemma",
        "proposition": "Proposition",
        "corollary": "Corollary",
        "definition": "Definition",
        "remark": "Remark",
        "claim": "Claim",
        "example": "Example",
        "exercise": "Exercise",
        "solution": "Solution",
        "neighborhood": "Neighborhood",
    }
    for env, title in env_map.items():
        t = _replace_env_with_heading(t, env, title)

    # If any stray begin/end tags remain for those environments, remove them.
    for env in env_map:
        t = re.sub(rf"\\begin\{{{re.escape(env)}\}}", "", t)
        t = re.sub(rf"\\end\{{{re.escape(env)}\}}", "", t)

    # Normalize a couple of common display-math forms.
    t = t.replace(r"\begin{equation*}", r"\[")
    t = t.replace(r"\end{equation*}", r"\]")
    t = t.replace(r"\begin{equation}", r"\[")
    t = t.replace(r"\end{equation}", r"\]")

    # Escape obvious text-only characters outside simple math.
    t = _escape_percent_underscore_outside_math(t)

    return t.strip()


def _ensure_full_document(lt_text: str) -> str:
    """
    Ensures the LaTeX is a compilable document.
    """
    t = _sanitize_latex_body(lt_text)

    has_docclass = r"\documentclass" in t

    if not has_docclass:
        pre = [
            r"\documentclass[11pt]{article}",
            r"\usepackage{amsmath}",
            r"\usepackage{amssymb}",
            r"\usepackage{amsfonts}",
            r"\usepackage{geometry}",
            r"\usepackage{iftex}",
            r"\geometry{margin=1in}",
            r"\ifXeTeX",
            r"    \usepackage{fontspec}",
            r"    \setmainfont{Latin Modern Roman}",
            r"\else",
            r"    \usepackage[T1]{fontenc}",
            r"    \usepackage{lmodern}",
            r"\fi",
            r"\begin{document}",
        ]
        doc = "\n".join(pre) + "\n\n" + t
        if r"\end{document}" not in doc:
            doc += "\n\n\\end{document}\n"
        return doc

    # If the model already emitted a full document, inject only minimal missing packages.
    inserts = []

    if "\\begin{itemize}" in t and "\\usepackage{enumitem}" not in t:
        inserts.append(r"\usepackage{enumitem}")

    if "\\mathbb" in t and "\\usepackage{amsfonts}" not in t and "\\usepackage{amssymb}" not in t:
        inserts.append(r"\usepackage{amsfonts}")

    if inserts:
        idx = t.find(r"\begin{document}")
        if idx != -1:
            t = t[:idx] + "\n".join(inserts) + "\n" + t[idx:]
        else:
            t = "\n".join(inserts) + "\n" + t

    if r"\end{document}" not in t:
        t += "\n\n\\end{document}\n"

    return t


def try_make_pdf_from_latex(lt_text: str, out_dir: str, filename_prefix: str) -> str:
    """
    Compiles LaTeX to PDF locally.
    Returns the local PDF path on success, or an empty string on failure.
    """
    try:
        full_doc = _ensure_full_document(lt_text)

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
                subprocess.run(
                    cmd,
                    cwd=tmpdir,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                subprocess.run(
                    cmd,
                    cwd=tmpdir,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as e:
                stdout = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
                stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
                logger.error("xelatex failed: stdout:\n%s\nstderr:\n%s", stdout[:4000], stderr[:4000])

                # Important: xelatex can still emit doc.pdf before returning nonzero.
                pdf_tmp = Path(tmpdir) / "doc.pdf"
                if not pdf_tmp.exists():
                    try:
                        debug_folder = Path(out_dir) / f"{filename_prefix}-latex-debug"
                        if debug_folder.exists():
                            shutil.rmtree(debug_folder)
                        shutil.copytree(tmpdir, str(debug_folder))
                        logger.info("Saved latex debug folder to %s", debug_folder)
                    except Exception:
                        logger.exception("Failed to save latex debug artifacts")
                    return ""

                logger.warning("xelatex returned nonzero, but doc.pdf exists. Keeping the PDF.")
            pdf_tmp = Path(tmpdir) / "doc.pdf"
            if not pdf_tmp.exists():
                logger.error("PDF not created at expected path %s", pdf_tmp)
                return ""

            final_pdf = Path(out_dir) / f"{filename_prefix}.pdf"
            if final_pdf.exists():
                final_pdf = Path(out_dir) / f"{filename_prefix}_{int(time.time())}.pdf"

            shutil.move(str(pdf_tmp), str(final_pdf))
            return str(final_pdf)

    except Exception as e:
        logger.exception("LaTeX -> PDF conversion failed: %s", e)
        return ""
    