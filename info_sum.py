# info_sum.py
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    logger.warning("HF_TOKEN not set - summarization will fail until you set HF_TOKEN in env or .env")

DEFAULT_MODEL = os.getenv("SUMMARIZER_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B")
DEFAULT_PROVIDER = os.getenv("HF_PROVIDER", None)


def _make_client():
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN not set. Please set HF_TOKEN in your environment or .env")
    if DEFAULT_PROVIDER:
        return InferenceClient(provider=DEFAULT_PROVIDER, api_key=HF_TOKEN)
    return InferenceClient(api_key=HF_TOKEN)


def summarize_text(
    text: str,
    *,
    output_format: str = "latex",
    max_tokens: int = 2000,
    temperature: float = 0.2,
    target_words: int = None,
) -> str:
    """
    Summarize `text` and return a string in the requested format.
    - output_format: 'latex' or 'markdown'
    - max_tokens: token budget for the model call
    - target_words: optional target word count guidance for the model (the prompt instructs the model)
    """

    client = _make_client()
    output_format = output_format.lower()
    if output_format not in ("markdown", "latex"):
        raise ValueError("output_format must be 'markdown' or 'latex'")

    if output_format == "latex":
        system_prompt = (
            "You are an expert academic assistant. Produce high-quality LaTeX lecture/notes.\n"
            "STRICT RULES:\n"
            "- Output only valid LaTeX (use \\section{}, \\subsection{}, \\subsubsection{}, itemize, math mode $...$ or $$...$$).\n"
            "- Keep bullet points concise and numbered/segmented where appropriate.\n"
            "- When referencing a provenance header (SOURCE: filename | page: N | chunk: K) include a short comment like % (filename, p.N).\n"
            "- Do NOT invent facts. If unsure, skip or mark it as uncertain in a short comment.\n"
        )
    else:
        system_prompt = (
            "You are an expert academic assistant. Produce concise Markdown notes.\n"
            "STRICT RULES:\n"
            "- Use headings #, ##, ### and itemize for bullets.\n"
            "- Include LaTeX math using $...$ or $$...$$ when needed.\n"
            "- After points referencing provenance, add a short parenthetical like (filename, p.N).\n"
            "- Do NOT invent facts."
        )

    # Provide optional target size guidance to the model
    size_guidance = ""
    if target_words:
        # guidance asks model to aim for target words (±20%) and to proportion output by important sections
        size_guidance = (
            f"\nGoal: produce approximately {target_words} words of {output_format.upper()} notes (±20%). "
            "Distribute length proportionally across the source material: more important/longer sections get more coverage. "
            "Do not add unrelated content."
        )

    user_prompt = (
        "Below are labeled chunks. Each chunk begins with a provenance header:\n"
        "  SOURCE: <filename> | page: <N> | chunk: <K>\n\n"
        "Follow the system instructions. Produce the final notes in the requested format.\n\n"
        f"{size_guidance}\n\n"
        "Text:\n\n"
        + text
    )

    try:
        completion = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        out = completion.choices[0].message.content
        if isinstance(out, bytes):
            out = out.decode("utf-8", errors="replace")
        return str(out)

    except Exception as e:
        logger.exception("LLM call failed: %s", e)
        raise
    