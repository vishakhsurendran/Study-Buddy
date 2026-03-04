import os
from pathlib import Path
import logging
import subprocess
import tempfile

logger = logging.getLogger(__name__)

def write_markdown(md_text: str, out_dir: str, filename_prefix: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    md_path = Path(out_dir) / f"{filename_prefix}.md"
    md_path.write_text(md_text, encoding="utf-8")
    return str(md_path)

def try_make_pdf_from_markdown(md_path: str) -> str:
    out_pdf = str(Path(md_path).with_suffix(".pdf"))
    # Try pypandoc
    try:
        import pypandoc
        logger.info("Converting with pypandoc")
        pypandoc.convert_file(md_path, "pdf", outputfile=out_pdf)
        return out_pdf
    except Exception as e:
        logger.info("pypandoc not available or failed: %s", e)

    # Fallback: markdown -> html -> weasyprint
    try:
        import markdown
        from weasyprint import HTML
        logger.info("Converting with markdown + weasyprint")
        html = markdown.markdown(Path(md_path).read_text(encoding="utf-8"), extensions=["fenced_code", "tables"])
        HTML(string=html).write_pdf(out_pdf)
        return out_pdf
    except Exception as e:
        logger.info("weasyprint fallback failed: %s", e)

    # If both fail, return empty string
    return ""

def try_make_pdf_from_latex(lt_text: str, out_dir: str, filename_prefix: str) -> None:
    # first, clean up latex
    lt_text = clean_latex(lt_text)
    # then try and create pdf from latex
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "doc.tex")

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(lt_text)

        result = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error", "doc.tex"],
            cwd=tmpdir,
            check=True
        )

        # print("STDOUT:\n", result.stdout)
        # print("STDERR:\n", result.stderr)

        if result.returncode != 0:
            raise RuntimeError("LaTeX compilation failed")

        pdf_path = os.path.join(tmpdir, "doc.pdf")
        os.makedirs(out_dir, exist_ok=True)
        final_pdf_path = Path(out_dir) / f"{filename_prefix}.pdf"
        os.rename(pdf_path, final_pdf_path)

def clean_latex(lt_text: str) -> str:
    lt_text = lt_text.strip()
    idx = lt_text.find("```")
    if idx == -1:
        pass
    else:
        lt_text = lt_text[idx:]
    if lt_text.startswith("```"):
        lt_text = lt_text.split("\n", 1)[1]
    if lt_text.endswith("```"):
        lt_text = lt_text.rsplit("\n", 1)[0]
    if r"\usepackage{amssymb}" not in lt_text:
        lt_text = lt_text.replace(
            r"\usepackage{amsmath}",
            r"\usepackage{amsmath}" + "\n" + r"\usepackage{amssymb}"
        )
    if r'\usepackage{fontspec}' not in lt_text:
        lt_text = lt_text.replace(
            r"\usepackage{amsmath}", 
            r"\usepackage{amsmath}" + "\n" + r'\usepackage{fontspec}'
        )
    if r'\end{document}' not in lt_text:
        lt_text += '\n' + r'\end{document}'
    return lt_text.strip()
