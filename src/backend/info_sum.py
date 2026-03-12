'''
Function that takes in text and returns summarized notes, with bulletpoints and appropriate title and sections
'''

from huggingface_hub import InferenceClient
from huggingface_hub import login
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    logger.warning("HF_TOKEN not set - summarization will fail until you set HF_TOKEN in env or .env")

DEFAULT_MODEL = os.getenv(
    "SUMMARIZER_MODEL",
    "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
)

DEFAULT_PROVIDER = os.getenv("HF_PROVIDER", None)


def _make_client():

    if not HF_TOKEN:
        raise RuntimeError(
            "HF_TOKEN not set. Please set HF_TOKEN in your environment or .env"
        )

    if DEFAULT_PROVIDER:
        return InferenceClient(
            provider=DEFAULT_PROVIDER,
            api_key=HF_TOKEN
        )

    return InferenceClient(
        api_key=HF_TOKEN
    )

def summarize_text(
    text: str,
    *,
    output_format: str = "markdown",
    max_tokens: int = 2000,
    temperature: float = 0.2
) -> str:

    client = _make_client()
    output_format = output_format.lower()

    if output_format not in ("markdown", "latex"):
        raise ValueError("output_format must be markdown or latex")

    if output_format == "markdown":
        system_prompt = (
            "You are an expert academic assistant producing concise Markdown notes.\n"
            "- Use headings\n"
            "- Use bullet points\n"
            "- Include citations from provenance\n"
            "- Output only Markdown"
        )
    else:
        system_prompt = (
            "You are an expert academic assistant producing concise LaTeX notes.\n"
            "- Use sections\n"
            "- Use itemize\n"
            "- Include provenance comments\n"
            "- Output only LaTeX code\n"
            "- Do not include Mardown code, or code of any other format\n"
            "- Use vocabulary that matches the level of the provided chuncks\n"
        )

    user_prompt = (
        "Summarize the following chunks:\n\n"
        + text
    )

    try:
        completion = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                },
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
    