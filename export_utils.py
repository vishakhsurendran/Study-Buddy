# export_utils.py
import os
import re
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# regexes (raw strings to avoid SyntaxWarning)
_CODEBLOCK_RE = re.compile(r"```(?:latex)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s*(.+)$", re.MULTILINE)
_MATH_INSIDE_PARENS_DOLLAR_LEFT = re.compile(r"\\\(\s*\$\s*")   # \( $  -> \(
_MATH_INSIDE_PARENS_DOLLAR_RIGHT = re.compile(r"\s*\$\s*\\\)")  # $ \)  -> \)
_SUBSCRIPT_DOLLAR = re.compile(r"_(?:\$\s*([\\]?[A-Za-z]+)\s*\$)")  # _$\epsilon$ -> _{\epsilon}
_INLINE_DOLLAR_AROUND_CMD = re.compile(r"\$\s*([\\][A-Za-z]+)\s*\$")  # $\epsilon$ -> \epsilon

# common unicode -> latex replacements (extend as needed)
UNICODE_MAP = {
    "ℓ": r"\ell",
    "∞": r"\infty",
    "≤": r"\leq",
    "≥": r"\geq",
    "×": r"\times",
    "−": "-",    # minus sign
    "·": r"\cdot",
    "π": r"\pi",
    "ε": r"\epsilon",
    "–": "-",  # ndash
    "—": "--", # mdash
}

def _extract_codeblock_if_present(text: str) -> Optional[str]:
    m = _CODEBLOCK_RE.search(text)
    if m:
        return m.group(1).strip()
    return None

def _convert_markdown_headings_to_latex(md: str) -> str:
    def _repl(m):
        level = len(m.group(1))
        title = m.group(2).strip()
        if level == 1:
            return r"\section{" + title + "}"
        if level == 2:
            return r"\subsection{" + title + "}"
        if level == 3:
            return r"\subsubsection{" + title + "}"
        return r"\paragraph{" + title + "}"
    return _MARKDOWN_HEADING_RE.sub(_repl, md)

def _fix_common_stray_dollars(text: str) -> str:
    # fix \$ inside \( \) and \[ \]
    text = _MATH_INSIDE_PARENS_DOLLAR_LEFT.sub(r"\\(", text)
    text = _MATH_INSIDE_PARENS_DOLLAR_RIGHT.sub(r"\\)", text)
    # subscripts like _$\epsilon$ -> _{\epsilon}
    text = _SUBSCRIPT_DOLLAR.sub(r"_{{\1}}", text)
    # inline commands like $\epsilon$ -> \epsilon
    text = _INLINE_DOLLAR_AROUND_CMD.sub(r"\1", text)
    # best-effort: remove stray single $ that are isolated (avoid touching legitimate math)
    text = re.sub(r"\$\s+", "", text)
    text = re.sub(r"\s+\$", "", text)
    return text

def _replace_unicode_math(text: str) -> str:
    for k, v in UNICODE_MAP.items():
        text = text.replace(k, v)
    return text

def _is_likely_latex(text: str) -> bool:
    return bool(re.search(r"\\(section|subsection|begin\{|\$\\\[|\\\(|\$\$|\\\])", text))

def _strip_preface_before_first_latex(text: str) -> str:
    """
    If text contains a LaTeX command somewhere, drop everything before the first
    clear LaTeX token (\section, \begin{, \[, \(, $$). This removes English prefaces
    that break compilation.
    """
    m = re.search(r"(\\begin\{document\}|\\section\b|\\subsection\b|\\subsubsection\b|\\begin\{|\\\[|\\\(|\$\$)", text)
    if m:
        return text[m.start():]
    # no obvious latex start -> return unchanged
    return text

def sanitize_model_output(raw: str) -> str:
    """
    Turn raw model output into a clean LaTeX fragment (best-effort).
    """
    if not raw:
        return ""

    # 1) prefer fenced latex block content if present
    code = _extract_codeblock_if_present(raw)
    if code:
        candidate = code
    else:
        candidate = raw

    # 2) If there is some LaTeX in the string, drop any preface before it
    if re.search(r"\\(section|begin\{|\\\[|\\\()", candidate) or "```latex" in raw.lower():
        candidate = _strip_preface_before_first_latex(candidate)

    # 3) Convert Markdown headings to LaTeX if present
    if "#" in candidate and re.search(r"^#{1,6}\s+", candidate, re.MULTILINE):
        candidate = _convert_markdown_headings_to_latex(candidate)

    # 4) Remove backticks / fences
    candidate = candidate.replace("```", "")
    candidate = candidate.replace("`", "")

    # 5) fix stray dollars and inline command dollars
    candidate = _fix_common_stray_dollars(candidate)

    # 6) replace common unicode math glyphs
    candidate = _replace_unicode_math(candidate)

    # 7) escape stray percent signs that are not intended as LaTeX comments (best-effort)
    # but keep existing percent comment lines intact (lines starting with %).
    lines = []
    for line in candidate.splitlines():
        if line.strip().startswith("%"):
            lines.append(line)
        else:
            lines.append(line.replace("%", r"\%"))
    candidate = "\n".join(lines)

    # 8) final trim & collapse excessive newlines
    candidate = re.sub(r"\n{3,}", "\n\n", candidate).strip()

    # 9) If candidate doesn't look like LaTeX, wrap into a section or itemize
    if not _is_likely_latex(candidate):
        para_chunks = [p.strip() for p in re.split(r"\n\s*\n", candidate) if p.strip()]
        if len(para_chunks) <= 3:
            wrapped = []
            for p in para_chunks:
                wrapped.append(p.replace("%", r"\%"))
            candidate = r"\section{Summary}" + "\n\n" + "\n\n".join(wrapped)
        else:
            items = ["\\item " + p.replace("%", r"\%") for p in para_chunks[:50]]
            candidate = r"\section{Summary}" + "\n\n\\begin{itemize}\n" + "\n".join(items) + "\n\\end{itemize}"

    return candidate

LATEX_PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb,amsthm}
\usepackage{hyperref}
\usepackage{geometry}
\geometry{margin=1in}
\setlength{\parskip}{6pt}
\setlength{\parindent}{0pt}
\begin{document}
"""

LATEX_END = r"""
\end{document}
"""

def write_latex(latex_text: str, out_dir: str, filename_prefix: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    tex_path = Path(out_dir) / f"{filename_prefix}.tex"

    clean_fragment = sanitize_model_output(latex_text)

    # If fragment already contains full document, keep as-is, otherwise wrap in preamble
    if re.search(r"\\begin\{document\}", clean_fragment):
        final = clean_fragment
    else:
        final = LATEX_PREAMBLE + "\n" + clean_fragment + "\n" + LATEX_END

    tex_path.write_text(final, encoding="utf-8")
    logger.info("Wrote TeX: %s", tex_path)
    return str(tex_path)

def try_make_pdf_from_latex(tex_path: str) -> str:
    tex_file = Path(tex_path)
    out_pdf = str(tex_file.with_suffix(".pdf"))

    # 1) pypandoc
    try:
        import pypandoc
        logger.info("Converting LaTeX -> PDF with pypandoc")
        pypandoc.convert_file(str(tex_file), "pdf", outputfile=out_pdf, format="latex")
        if Path(out_pdf).exists():
            return out_pdf
    except Exception as e:
        logger.info("pypandoc conversion not available or failed: %s", e)

    # helper runner
    def _run_cmd(cmd, cwd):
        try:
            subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True, None
        except subprocess.CalledProcessError as e:
            return False, (e.returncode, e.stdout.decode(errors="ignore"), e.stderr.decode(errors="ignore"))
        except Exception as e:
            return False, str(e)

    # 2) pdflatex (preferred)
    try:
        workdir = tex_file.parent
        cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_file.name]
        logger.info("Running pdflatex...")
        ok, info = _run_cmd(cmd, workdir)
        if ok:
            ok2, info2 = _run_cmd(cmd, workdir)
            if ok2 and Path(out_pdf).exists():
                return out_pdf
            else:
                logger.info("pdflatex second run info: %s", info2)
        else:
            logger.info("pdflatex first run info: %s", info)
    except Exception as e:
        logger.info("pdflatex fallback exception: %s", e)

    # 3) xelatex (better unicode support)
    try:
        workdir = tex_file.parent
        cmd = ["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex_file.name]
        logger.info("Running xelatex as fallback...")
        ok, info = _run_cmd(cmd, workdir)
        if ok:
            ok2, info2 = _run_cmd(cmd, workdir)
            if ok2 and Path(out_pdf).exists():
                return out_pdf
            else:
                logger.info("xelatex second run info: %s", info2)
        else:
            logger.info("xelatex first run info: %s", info)
    except Exception as e:
        logger.info("xelatex fallback exception: %s", e)

    logger.warning("All PDF conversion attempts failed for %s", tex_file)
    return ""
