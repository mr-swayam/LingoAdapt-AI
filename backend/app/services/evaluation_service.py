import json
import logging

from pydantic import ValidationError

from app.ai.base import AIProvider, ChatMessage
from app.ai.exceptions import AIResponseValidationError
from app.schemas.evaluation import AIEvaluationResult, RawAIEvaluation

logger = logging.getLogger("app.ai")

SYSTEM_PROMPT = """You are a strict evaluation API for a language-learning app. \
Given a learner's free-form written answer, evaluate it and respond with ONLY a \
single JSON object (no markdown, no backticks, no text outside the JSON) matching \
exactly this shape:

{
  "is_correct": boolean,
  "score": number between 0 and 1,
  "errors": [
    {
      "type": "GRAMMAR" | "VOCABULARY" | "SPELLING" | "WORD_ORDER" | "OTHER",
      "skill": "short description of what's wrong",
      "severity": "LOW" | "MEDIUM" | "HIGH"
    }
  ],
  "explanation": "short, encouraging, beginner-friendly explanation of the result",
  "corrected_answer": "a corrected version of the learner's answer"
}

Minor stylistic variation that doesn't change correctness should not be marked wrong. \
Be encouraging and concise."""


def _build_user_message(*, prompt: str, model_answer: str, rubric: str, submitted_text: str) -> str:
    return (
        f"Exercise prompt: {prompt}\n"
        f"Example correct answer: {model_answer}\n"
        f"What to check for: {rubric}\n"
        f"Learner's answer: {submitted_text}"
    )


async def evaluate_free_response(
    provider: AIProvider,
    *,
    prompt: str,
    model_answer: str,
    rubric: str,
    submitted_text: str,
) -> AIEvaluationResult:
    response = await provider.chat(
        [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=_build_user_message(
                    prompt=prompt,
                    model_answer=model_answer,
                    rubric=rubric,
                    submitted_text=submitted_text,
                ),
            ),
        ],
        json_mode=True,
        max_tokens=800,
        temperature=0.2,
    )

    try:
        raw_data = json.loads(response.content)
        raw = RawAIEvaluation.model_validate(raw_data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("ai_evaluation_schema_invalid content=%r error=%s", response.content, exc)
        raise AIResponseValidationError(
            f"AI evaluation response failed schema validation: {exc}"
        ) from exc

    return AIEvaluationResult.from_raw(raw)
