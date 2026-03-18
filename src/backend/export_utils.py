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
    This is intentionally conservative and lightweight.
    """
    parts = []
    last = 0
    math_pat = re.compile(r'(\$\$.*?\$\$|\$.*?\$|\\\[.*?\\\]|\\\(.*?\\\))', re.DOTALL)

    for m in math_pat.finditer(text):
        non_math = text[last:m.start()]
        non_math = re.sub(r'(?<!\\)%', r'\\%', non_math)
        non_math = re.sub(r'(?<!\\)_', r'\\_', non_math)
        parts.append(non_math)
        parts.append(m.group(0))
        last = m.end()

    tail = text[last:]
    tail = re.sub(r'(?<!\\)%', r'\\%', tail)
    tail = re.sub(r'(?<!\\)_', r'\\_', tail)
    parts.append(tail)
    return "".join(parts)


def _ensure_full_document(lt_text: str) -> str:
    """
    Ensures the LaTeX is a compilable document.
    Removes unsupported package directives and injects theorem definitions when needed.
    """
    t = (lt_text or "").strip()

    if t.startswith("```"):
        lines = t.splitlines()
        if len(lines) >= 2:
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
        t = "\n".join(lines).strip()

    t = _escape_percent_underscore_outside_math(t)

    # Remove unsupported package if the model adds it
    t = re.sub(r'\\usepackage(\[[^\]]*\])?\{thmstyle\}', r'% removed unsupported package: thmstyle', t)

    theorem_envs = [
        "theorem",
        "lemma",
        "proposition",
        "corollary",
        "definition",
        "remark",
        "claim",
        "example",
        "exercise"
    ]

    found_envs = set(re.findall(r'\\begin\{([a-zA-Z*]+)\}', t))
    missing_newtheorems = []
    for env in theorem_envs:
        if env in found_envs and re.search(r'\\newtheorem\s*\{' + re.escape(env) + r'\}', t) is None:
            missing_newtheorems.append(r"\newtheorem{" + env + r"}{" + env.capitalize() + r"}")

    has_docclass = r"\documentclass" in t

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
        ]
        pre.extend(missing_newtheorems)
        pre.append(r"\begin{document}")
        doc = "\n".join(pre) + "\n\n" + t
        if r"\end{document}" not in doc:
            doc += "\n\n\\end{document}\n"
        return doc

    inserts = []

    if "\\usepackage{amsthm}" not in t and missing_newtheorems:
        inserts.append(r"\usepackage{amsthm}")

    for nt in missing_newtheorems:
        if nt not in t:
            inserts.append(nt)

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
                subprocess.run(cmd, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(cmd, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                stdout = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
                stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
                logger.info("xelatex failed: stdout:\n%s\nstderr:\n%s", stdout[:4000], stderr[:4000])

                cmd2 = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name]
                try:
                    subprocess.run(cmd2, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    subprocess.run(cmd2, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except subprocess.CalledProcessError as e2:
                    stdout2 = e2.stdout.decode("utf-8", errors="replace") if e2.stdout else ""
                    stderr2 = e2.stderr.decode("utf-8", errors="replace") if e2.stderr else ""
                    logger.error("pdflatex also failed: stdout:\n%s\nstderr:\n%s", stdout2[:4000], stderr2[:4000])

                    try:
                        debug_folder = Path(out_dir) / f"{filename_prefix}-latex-debug"
                        if debug_folder.exists():
                            shutil.rmtree(debug_folder)
                        shutil.copytree(tmpdir, str(debug_folder))
                        logger.info("Saved latex debug folder to %s", debug_folder)
                    except Exception:
                        logger.exception("Failed to save latex debug artifacts")

                    return ""

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
    