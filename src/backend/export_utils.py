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
    or display (\[...\] or $$...$$) math.
    """
    parts = []
    last = 0
    math_pat = re.compile(r'(\$\$.*?\$\$|\$.*?\$|\\\[.*?\\\]|\\\(.*?\\\))', re.DOTALL)
    for m in math_pat.finditer(text):
        non_math = text[last:m.start()]
        non_math = re.sub(r'(?<!\\)%','\\%', non_math)
        non_math = re.sub(r'(?<!\\)_','\\_', non_math)
        parts.append(non_math)
        parts.append(m.group(0))
        last = m.end()
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
        if len(lines) >= 2:
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
        t = "\n".join(lines).strip()

    # Lightly escape problem characters outside math
    t = _escape_percent_underscore_outside_math(t)

    # --- SANITIZE known-bad / uncommon packages that may not be installed ---
    # Remove the problematic 'thmstyle' package (observed from logs), and any exact matches
    t_before = t
    t = re.sub(r'\\usepackage(\[[^\]]*\])?\{thmstyle\}', r'% removed unsupported package: thmstyle', t, flags=re.IGNORECASE)

    # If the LLM inserted other nonstandard package lines that might break compilation,
    # we leave them alone except for a small whitelist approach can be added later if needed.
    if t != t_before:
        logger.info("Sanitized nonstandard package directives from LaTeX source (e.g., thmstyle).")

    # Detect if the document already has a \documentclass
    has_docclass = r"\documentclass" in t

    # Detect theorem-like environments used by the document
    theorem_envs = ["theorem", "lemma", "proposition", "corollary", "definition", "remark", "claim", "example"]
    begins = re.findall(r'\\begin\{([a-zA-Z*]+)\}', t)
    found_envs = set(e for e in begins if e in theorem_envs)

    # Helper: check whether a \newtheorem for env exists already in text
    def has_newtheorem(env_name: str, text: str) -> bool:
        pat = re.compile(r'\\newtheorem\s*\{\s*' + re.escape(env_name) + r'\s*\}', re.IGNORECASE)
        return bool(pat.search(text))

    missing_newtheorems = []
    for env in sorted(found_envs):
        if not has_newtheorem(env, t):
            display = env.capitalize()
            missing_newtheorems.append(r"\newtheorem{" + env + r"}{" + display + r"}")

    # If no \documentclass, create a minimal wrapper and include packages + newtheorems
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
        # If any theorem-like envs are present, append their \newtheorem definitions
        if missing_newtheorems:
            pre.extend(missing_newtheorems)

        pre.append(r"\begin{document}")
        doc = "\n".join(pre) + "\n\n" + t
        if r"\end{document}" not in doc:
            doc += "\n\n\\end{document}\n"
        return doc

    # If the doc already has \documentclass: attempt to inject missing packages/defs
    needed_inserts = []

    # Ensure amsthm if theorem-like envs were detected and amsthm isn't present
    if missing_newtheorems and "\\usepackage{amsthm}" not in t:
        needed_inserts.append(r"\usepackage{amsthm}")
    # Add any missing newtheorem definitions
    for nt in missing_newtheorems:
        if nt not in t:
            needed_inserts.append(nt)

    # Ensure enumitem if itemize/enumerate used
    if "\\begin{itemize}" in t and "\\usepackage{enumitem}" not in t:
        needed_inserts.append(r"\usepackage{enumitem}")

    # Common macros -> packages
    if "\\mathbb" in t and ("\\usepackage{amsfonts}" not in t and "\\usepackage{amssymb}" not in t):
        needed_inserts.append(r"\usepackage{amsfonts}")

    if needed_inserts:
        idx = t.find(r"\begin{document}")
        if idx != -1:
            insert_block = "\n".join(needed_inserts) + "\n"
            t = t[:idx] + insert_block + t[idx:]
        else:
            t = "\n".join(needed_inserts) + "\n" + t

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
            # move to final out_dir
            final_pdf = Path(out_dir) / f"{filename_prefix}.pdf"
            if final_pdf.exists():
                final_pdf = Path(out_dir) / f"{filename_prefix}_{int(time.time())}.pdf"
            shutil.move(str(pdf_tmp), str(final_pdf))
            return str(final_pdf)
    except Exception as e:
        logger.exception("LaTeX -> PDF conversion failed: %s", e)
        return ""
    