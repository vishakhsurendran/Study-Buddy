"""
Production-quality academic summarizer
"""

from huggingface_hub import InferenceClient
from dotenv import load_dotenv
import os

load_dotenv()

def summarize(text: str) -> str:

    api_key = os.getenv("HF_TOKEN")

    if not api_key:
        raise RuntimeError("HF_TOKEN not set")


    client = InferenceClient(
        provider="featherless-ai",
        api_key=api_key,
    )


    system_prompt = """
You are an expert academic note-taking assistant.

Your job is to convert course material into clean, structured LaTeX notes.

STRICT RULES:

• Use \\section{}, \\subsection{}, \\subsubsection{}
• Use itemize for bullet points
• Bullet points MUST be concise
• Include equations in LaTeX math mode
• DO NOT invent information
• DO NOT repeat ideas
• DO NOT include exercises
• DO NOT include commentary
• Only output LaTeX notes
"""


    user_prompt = f"""
Convert the following text into structured LaTeX notes:

{text}
"""


    completion = client.chat.completions.create(

        model="meta-llama/Meta-Llama-3-8B-Instruct",

        messages=[

            {"role": "system", "content": system_prompt},

            {"role": "user", "content": user_prompt}

        ],

        temperature=0.2,

        max_tokens=1500,

    )


    return completion.choices[0].message.content
