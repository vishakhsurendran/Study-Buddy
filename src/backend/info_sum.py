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
            """You are an AI assistant that converts educational text into clean, structured LaTeX lecture notes.
Output **only valid LaTeX code**. Do NOT include \\documentclass, \\usepackage, \\begin{document}, or \\end{document}.
Do NOT include explanations or commentary outside of LaTeX.

Rules:
1. Organize content using \\section, \\subsection, \\subsubsection as appropriate.
2. Use \\begin{itemize}...\\end{itemize} or \\begin{enumerate}...\\end{enumerate} for lists.
3. Format all equations in LaTeX math mode. Ensure all mathematical symbols are valid in LaTeX and wrap all math in $...$ or \[...\] as appropriate. If there is no math, skip math formatting.
4. For definitions, examples, theorems, and propositions, use the standard amsthm environments **only if appropriate**:
   - \\begin{definition} ... \\end{definition}
   - \\begin{theorem} ... \\end{theorem}
   - \\begin{proposition} ... \\end{proposition}
   - \\begin{example} ... \\end{example}
5. Replace any non-standard environments (e.g., exercise, solution, remark) with standard LaTeX structures:
   - Use \\subsection*{Exercise} for exercises
   - Use \\subsection*{Solution} for solutions
   - Use \\subsection*{Remark} for remarks
6. Keep LaTeX syntax correct; do not invent commands. Use only standard LaTeX and amsmath/amsfonts/amscls commands.
7. Break content into logical sections and subsections based on the input text."""
        )

    user_prompt = (
        f'''
        Here is the text from my course material:

{text}

Convert this text into structured LaTeX lecture notes:
- Organize topics using sections and subsections.
- Use itemize or enumerate for lists.
- Format all definitions, theorems, examples, and equations properly in LaTeX.
- Do NOT include the LaTeX preamble (\\documentclass, \\usepackage) or \\begin{{document}}/\\end{{document}}.
- For non-math content, focus on clear structure and lists; skip math formatting if not present.
- Use \\subsection* for exercises, solutions, and remarks instead of any custom environments.
'''
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
    