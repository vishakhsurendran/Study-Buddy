# info_sum.py
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
import os
import logging
from typing import Any

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

HF_TOKEN = os.getenv("HF_TOKEN")

DEFAULT_MODEL = os.getenv(
    "SUMMARIZER_MODEL",
    "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
)

FALLBACK_MODEL = os.getenv(
    "SUMMARIZER_MODEL_FALLBACK",
    "mistralai/Mistral-7B-Instruct-v0.3"
)

DEFAULT_PROVIDER = os.getenv("HF_PROVIDER", None)


# ---------------------------
# CLIENT
# ---------------------------

def _make_client():
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN not set.")
    if DEFAULT_PROVIDER:
        return InferenceClient(provider=DEFAULT_PROVIDER, api_key=HF_TOKEN)
    return InferenceClient(api_key=HF_TOKEN)


# ---------------------------
# EXTRACTION
# ---------------------------

def _extract_text_from_completion(completion: Any) -> str:

    try:
        if hasattr(completion, "choices"):
            choices = completion.choices
            if choices and hasattr(choices[0], "message"):
                return str(choices[0].message.content)
            if choices and hasattr(choices[0], "text"):
                return str(choices[0].text)
    except Exception:
        pass

    try:
        if isinstance(completion, dict):
            return str(completion["choices"][0]["message"]["content"])
    except Exception:
        pass

    try:
        if hasattr(completion, "generated_text"):
            return str(completion.generated_text)
    except Exception:
        pass

    return ""


# ---------------------------
# LATEX CLEANER
# ---------------------------

def clean_latex(text: str) -> str:

    if not text.strip():
        return ""

    # remove markdown fences
    text = text.replace("```latex", "")
    text = text.replace("```", "")

    # ensure valid document structure
    if "\\begin{document}" not in text:

        text = (
            "\\documentclass{article}\n"
            "\\usepackage{amsmath}\n"
            "\\usepackage{amssymb}\n"
            "\\usepackage{graphicx}\n"
            "\\usepackage{hyperref}\n\n"
            "\\begin{document}\n\n"
            + text +
            "\n\n\\end{document}"
        )

    return text


# ---------------------------
# MODEL CALL
# ---------------------------

def _call_model(
    client,
    model,
    system_prompt,
    user_prompt,
    temperature,
    max_tokens,
):

    try:

        completion = client.chat.completions.create(

            model=model,

            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],

            temperature=temperature,
            max_tokens=max_tokens,
        )

        text = _extract_text_from_completion(completion)

        return text.strip()

    except Exception as e:

        logger.exception("Model failed: %s", e)

        return ""


# ---------------------------
# MAIN SUMMARIZER
# ---------------------------

def summarize_text(

    text: str,

    output_format="latex",

    max_tokens=4000,

    temperature=0.1,

):

    client = _make_client()

    if not text.strip():

        return "% No input text"


    if output_format == "latex":

        system_prompt = """

You are a professional academic LaTeX writer.

CRITICAL REQUIREMENTS:

Output ONLY valid LaTeX.

DO NOT output markdown.

DO NOT output explanation.

DO NOT output code fences.

USE:

\\section{}
\\subsection{}
\\begin{itemize}

Include math using $ $

Write lecture-style notes.

Never say "no content".

Always produce output.

"""
    else:
        system_prompt = """
Produce structured markdown notes.
Use headings and bullet points.

"""
    user_prompt = f"""
Summarize the following CONTENT blocks into structured notes.
{text}
"""

    # PRIMARY
    result = _call_model(
        client,
        DEFAULT_MODEL,
        system_prompt,
        user_prompt,
        temperature,
        max_tokens,
    )

    if result:
        return clean_latex(result) if output_format == "latex" else result

    # FALLBACK
    logger.warning("Primary failed. Using fallback model.")

    result = _call_model(
        client,
        FALLBACK_MODEL,
        system_prompt,
        user_prompt,
        temperature=0,
        max_tokens=max_tokens,
    )

    if result:
        return clean_latex(result) if output_format == "latex" else result

    # FINAL HARD FALLBACK
    logger.error("All models failed.")
    return clean_latex("""
\\section{Summary}
No content could be generated automatically.
""")
