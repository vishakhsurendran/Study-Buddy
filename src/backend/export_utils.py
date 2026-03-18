# export_utils.py (supabase upload aware)
import os
import re
import subprocess
import tempfile
import time
import re

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
    If the model output is a fragment (no \\documentclass), wrap it with a minimal preamble.
    If it already contains \\documentclass, leave as-is but ensure \\end{document} present.
    """
    t = lt_text or ""
    t = t.strip()

    t = re.sub(r'\\chapter(\s*\{)', r'\\section\1', t)

    # If it's a fenced code block, strip triple backticks
    if t.startswith("```"):
        lines = t.splitlines()
        if len(lines) >= 2:
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
        t = "\n".join(lines).strip()

    # remove \document class if it already exists
    t = re.sub(r'\\documentclass(\[[^\]]*\])?\{[^}]*\}\s*', '', t)
    t = re.sub(r'\\begin\{document\}', '', t)
    t = re.sub(r'\\usepackage(\[[^\]]*\])?\{[^}]*\}\s*', '', t)
    # Ensure we have \end{document}
    if r"\documentclass" not in t:
        pre = [
            r"\documentclass[11pt]{article}",
            r"\usepackage{amsmath}",
            r"\usepackage{amssymb}",
            r"\usepackage{amsfonts}",
            r"\usepackage{amsthm}",
            r"\usepackage{enumitem}",
            r"\usepackage{geometry}",
            r"\usepackage{amsfonts}",
            r"\usepackage{fontspec}",  # works with xelatex/lualatex
            r"\usepackage{amsthm}",
            r"\newtheorem{theorem}{Theorem}",
            r"\newtheorem{definition}{Definition}",
            r"\newtheorem{proposition}{Proposition}",
            r"\newtheorem{lemma}{Lemma}",
            r"\newtheorem{example}{Example}",
            r"\geometry{margin=1in}",
            r"\usepackage{iftex}",
            r"\ifXeTeX",
            r"    \usepackage{fontspec}",
            r"    \setmainfont{Latin Modern Roman}",
            r"\else",
            r"    \usepackage[T1]{fontenc}",
            r"    \usepackage{lmodern}",
            r"\fi",
            r"\setmainfont{Latin Modern Roman}",  # safe default on many TeX installs
            r"\begin{document}",
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
        # print(full_doc)

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
                # subprocess.run(cmd, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            except subprocess.CalledProcessError as e:
                # logger.info("xelatex failed, attempting pdflatex fallback: %s", e)
                # logger.info("xelatex failed, attempting pdflatex fallback")
                logger.info("xelatex failed")
                print("STDOUT:\n", e.stdout)
                print("STDERR:\n", e.stderr)
                return ''
                # fallback to pdflatex without fontspec (still may fail on unicode)
                cmd2 = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name]
                try:
                    subprocess.run(cmd2, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    # subprocess.run(cmd2, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except subprocess.CalledProcessError as e:
                    logger.info("pdflatex failed")
                    print("STDOUT:\n", e.stdout)
                    print("STDERR:\n", e.stderr)
                    return ''
                

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
    