import os
from pathlib import Path
import logging

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
