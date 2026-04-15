from __future__ import annotations

import instructor
import openai

from app.core.config import settings
from app.models.schemas import TranscriptExtractionSchema

def _get_client():
    if not settings.dashscope_api_key:
        raise ValueError("Please set DASHSCOPE_API_KEY in your .env file before running extraction.")
    openai_client = openai.OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )
    return instructor.from_openai(openai_client, mode=instructor.Mode.JSON)


def extract_structured_transcript(text_content: str, model_name: str | None = None) -> TranscriptExtractionSchema:
    client = _get_client()
    messages = [
        {
            "role": "system",
            "content": (
                "You are a senior university registrar and transcript auditor. "
                "Extract only explicitly stated student information and course records from the document. "
                "Do not invent missing values, do not calculate GPA, and do not include explanations."
            ),
        },
        {
            "role": "user",
            "content": (
                "Return only the fields required by the schema.\n"
                "Rules:\n"
                "1. If a field is missing, return null.\n"
                "2. Preserve the original grade text.\n"
                "3. Ignore repeated headers, page numbers, explanatory notes, and summary prose that is not part of the transcript.\n"
                "4. Extract one course object per module.\n"
                "5. The transcript may place two course entries on the same line; capture all modules you can identify.\n\n"
                f"--- BEGIN DOCUMENT TEXT ---\n{text_content}\n--- END DOCUMENT TEXT ---"
            ),
        },
    ]

    return client.chat.completions.create(
        model=model_name or settings.llm_model,
        temperature=0,
        max_retries=3,
        response_model=TranscriptExtractionSchema,
        messages=messages,
    )
