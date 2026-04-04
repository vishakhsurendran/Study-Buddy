'''
Function that takes in text and returns summarized notes, with bulletpoints and appropriate title and sections
'''

from huggingface_hub import InferenceClient
from dotenv import load_dotenv
import os
import logging
import time
import httpx

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
            """You are an AI assistant that converts educational text into clean, structured LaTeX lecture notes.
Output only valid LaTeX content for the body of the document.
Do NOT include \\documentclass, \\usepackage, \\begin{document}, or \\end{document}.
Do NOT include explanations or commentary outside of LaTeX.

Rules:
1. Organize content using \\section, \\subsection, and \\subsubsection as appropriate.
2. Use \\begin{itemize}...\\end{itemize} or \\begin{enumerate}...\\end{enumerate} for lists.
3. Format mathematics only with standard LaTeX math delimiters such as $...$ or \\[...\\].
4. Do not use custom environments like exercise, solution, neighborhood, remark, claim, theorem, proposition, lemma, corollary, definition, or example.
   Use headings instead, such as \\subsection*{Exercise}, \\subsection*{Definition}, or \\subsection*{Example}.
5. Do not emit \\begin{equation}, \\begin{equation*}, \\end{equation}, or \\end{equation*}.
6. Keep LaTeX syntax correct; do not invent commands.
7. Break content into logical sections and subsections based on the input text."""
        )

    user_prompt = (
        f"""
Here is the text from my course material:

{text}

Convert this text into structured LaTeX lecture notes:
- Organize topics using sections and subsections.
- Use itemize or enumerate for lists.
- Format all definitions, examples, and equations properly in LaTeX.
- Do NOT include the LaTeX preamble (\\documentclass, \\usepackage) or \\begin{{document}}/\\end{{document}}.
- For non-math content, focus on clear structure and lists; skip math formatting if not present.
- Do not use custom environments like exercise, solution, neighborhood, remark, claim, theorem, proposition, lemma, corollary, definition, or example.
- Use \\subsection* for exercises, solutions, remarks, and similar sections instead.
"""
    )

    last_err = None
    for attempt in range(3):
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

        except httpx.RemoteProtocolError as e:
            last_err = e
            logger.warning("HF RemoteProtocolError on attempt %d/3: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
            else:
                logger.exception("LLM call failed after retries: %s", e)
        except Exception as e:
            logger.exception("LLM call failed: %s", e)
            raise

    raise last_err
