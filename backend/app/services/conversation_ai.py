import json
import logging

from pydantic import ValidationError

from app.ai.base import AIProvider, ChatMessage
from app.ai.exceptions import AIResponseValidationError
from app.models.conversation import ConversationMessage, ConversationScenario, MessageRole
from app.schemas.conversation import AIConversationTurn, RawAIConversationTurn
from app.services.learner_context import LearnerContext

logger = logging.getLogger("app.ai")

# Encodes rules.md §6's 8 conversation rules directly into the system
# prompt, plus the JSON output contract (rules.md: prefer structured AI
# output over free-form).
SYSTEM_PROMPT_TEMPLATE = """You are a friendly, patient AI conversation tutor for a \
language-learning app. The learner is practicing English in this scenario: {scenario}.

Learner context (use this to calibrate your language, do not restate it to the learner):
{context_json}

Follow these rules:
1. Maintain the context of this conversation - refer back to what was said earlier when \
relevant.
2. Speak at the learner's approximate level ({level}) - do not use vocabulary or grammar \
far above it.
3. Encourage the learner to produce language - ask questions, don't just make statements.
4. Do not take over the conversation - keep your replies short (1-3 sentences).
5. Correct important errors without interrupting every sentence - only flag mistakes that \
matter for communication or learning, not every minor slip.
6. Distinguish real grammar mistakes from acceptable natural variation - do not correct \
stylistic choices that are still correct English.
7. Adapt your vocabulary and sentence complexity to the learner's level.
8. Stay in character for the scenario and keep the conversation moving naturally.

Respond with ONLY a single JSON object (no markdown, no backticks, no text outside the JSON) \
matching exactly this shape:

{{
  "reply": "your in-character reply to the learner, continuing the conversation",
  "corrections": [
    {{
      "original": "the exact phrase the learner wrote that had a mistake",
      "corrected": "the corrected version of that phrase",
      "explanation": "short, encouraging, beginner-friendly explanation of the fix",
      "skill": "PAST_TENSE" | "PREPOSITIONS" | "ARTICLES" | "SUBJECT_VERB_AGREEMENT" | \
"PLURALS" | "WORD_CHOICE" | "GENERAL"
    }}
  ]
}}

"corrections" should usually be empty or contain at most 1-2 entries - only include a \
correction for something genuinely worth teaching (rule 5). Never leave "reply" empty.

IMPORTANT: only include a correction for a mistake in the learner's LATEST message below \
(the final user turn). Never re-report a mistake from an earlier message in this \
conversation, even if you mentioned it before - each mistake should be corrected once."""

_ROLE_MAP = {MessageRole.LEARNER: "user", MessageRole.TUTOR: "assistant"}


def _build_system_prompt(*, scenario: ConversationScenario, context: LearnerContext) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        scenario=scenario.value.replace("_", " ").title(),
        context_json=json.dumps(context.to_prompt_dict()),
        level=context.estimated_level,
    )


async def generate_turn(
    provider: AIProvider,
    *,
    scenario: ConversationScenario,
    context: LearnerContext,
    history: list[ConversationMessage],
    learner_message: str,
) -> AIConversationTurn:
    messages = [
        ChatMessage(role="system", content=_build_system_prompt(scenario=scenario, context=context))
    ]
    for msg in history:
        messages.append(ChatMessage(role=_ROLE_MAP[msg.role], content=msg.content))
    messages.append(ChatMessage(role="user", content=learner_message))

    response = await provider.chat(messages, json_mode=True, max_tokens=600, temperature=0.4)

    try:
        raw_data = json.loads(response.content)
        raw = RawAIConversationTurn.model_validate(raw_data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("ai_conversation_schema_invalid content=%r error=%s", response.content, exc)
        raise AIResponseValidationError(
            f"AI conversation response failed schema validation: {exc}"
        ) from exc

    return AIConversationTurn.from_raw(raw)
