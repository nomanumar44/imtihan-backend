"""
AI Assistant service for ImtihanHub.

Uses Google's Gemini API to provide exam tutoring via multi-turn chat sessions.
Set GEMINI_API_KEY in your .env file to enable real responses.
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# ── System Prompts ──

MCQ_SYSTEM_PROMPT = (
    "You are an expert Pakistani competitive exam tutor for ImtihanHub. "
    "The student is asking about this MCQ:\n\n"
    "{question_text}\n\n"
    "Options:\n{options}\n\n"
    "Correct Answer: {correct_option}\n\n"
    "Explain: why the correct answer is right, why other options are wrong, "
    "background knowledge about this topic, and exam tips for PPSC/FPSC/CSS context. "
    "Be concise but complete."
)

GENERAL_SYSTEM_PROMPT = (
    "You are an expert Pakistani competitive exam tutor for ImtihanHub. "
    "Help students preparing for PPSC, FPSC, CSS, NTS exams. "
    "Answer questions about exam topics, preparation strategy, syllabus, and general knowledge. "
    "Be concise and exam focused."
)

EXAM_BOARD_PROMPT = (
    "You are an expert Pakistani competitive exam tutor for ImtihanHub. "
    "The student is asking about a specific Pakistani exam board. "
    "Provide detailed, accurate information about: eligibility, exam pattern, "
    "important subjects, preparation strategy, and recent syllabus changes. "
    "Be factual and up-to-date."
)

PAST_PAPERS_PROMPT = (
    "You are an expert Pakistani competitive exam tutor for ImtihanHub. "
    "The student is asking about past papers. Help with: question patterns, "
    "repeated topics, paper analysis, and time management tips."
)

BLOG_NEWS_PROMPT = (
    "You are an expert Pakistani competitive exam tutor for ImtihanHub. "
    "The student is reading an article and wants exam-focused insights. "
    "Summarize the content, connect it to exam relevance, suggest possible MCQs, "
    "and mention which boards test this area."
)

# ── Error Messages ──

API_KEY_MISSING = (
    "I'm here to help with your exam preparation!\n\n"
    "Currently, the AI assistant is being configured. Please try again in a moment."
)

QUOTA_EXCEEDED_MSG = (
    "Daily AI limit reached on our end. Please try again later."
)

NETWORK_ERROR_MSG = (
    "Connection error. Please try again."
)

INVALID_REQUEST_MSG = (
    "Could not process your request. Please rephrase."
)

GENERIC_ERROR_MSG = (
    "Something went wrong. Please try again in a moment."
)


# ── Helpers ──

def _get_system_prompt(mcq, context_type: str) -> str:
    """Return the appropriate system prompt for the context."""
    if mcq and context_type in ("mcq", "mcq-practice"):
        options = []
        if mcq.option_a: options.append(f"A. {mcq.option_a}")
        if mcq.option_b: options.append(f"B. {mcq.option_b}")
        if mcq.option_c: options.append(f"C. {mcq.option_c}")
        if mcq.option_d: options.append(f"D. {mcq.option_d}")
        return MCQ_SYSTEM_PROMPT.format(
            question_text=mcq.question_text,
            options="\n".join(options),
            correct_option=mcq.correct_option,
        )
    if context_type == "exam-board":
        return EXAM_BOARD_PROMPT
    if context_type == "past-papers":
        return PAST_PAPERS_PROMPT
    if context_type in ("blog", "news"):
        return BLOG_NEWS_PROMPT
    return GENERAL_SYSTEM_PROMPT


def _to_gemini_history(messages: list[dict]) -> list[dict]:
    """
    Convert Django message format to Gemini chat history format.

    Django:  [{role: "user", content: "..."}, {role: "assistant", content: "..."}]
    Gemini:  [{role: "user", parts: ["..."]}, {role: "model", parts: ["..."]}]
    """
    result = []
    for msg in messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        gemini_role = 'user' if role == 'user' else 'model'
        result.append({'role': gemini_role, 'parts': [content]})
    return result


def _classify_error(error) -> str:
    """Map Gemini exceptions to friendly user-facing messages."""
    msg = str(error).lower()
    # Quota / rate limit errors
    if any(k in msg for k in ['quota', 'rate limit', 'resource exhausted', '429']):
        return QUOTA_EXCEEDED_MSG
    # Network / connection errors
    if any(k in msg for k in ['network', 'connection', 'timeout', 'unreachable', 'dns']):
        return NETWORK_ERROR_MSG
    # Invalid request / bad content
    if any(k in msg for k in ['invalid', 'bad request', 'blocked', 'safety', '400']):
        return INVALID_REQUEST_MSG
    return GENERIC_ERROR_MSG


# ── Main Entry Point ──

def get_ai_response(messages: list[dict], mcq=None, context_type: str = "general") -> str:
    """
    Generate AI response using Google Gemini multi-turn chat.

    Args:
        messages: Django-format history [{role, content}, ...].
        mcq: Optional MCQ instance for MCQ-specific tutoring.
        context_type: Page context from frontend.

    Returns:
        Response text string.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        logger.warning("GEMINI_API_KEY is not set. AI responses are disabled.")
        return API_KEY_MISSING

    try:
        import google.generativeai as genai
    except ImportError:
        logger.error("google-generativeai package is not installed.")
        return API_KEY_MISSING

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(getattr(settings, 'GEMINI_MODEL', 'gemini-1.5-flash'))
    except Exception as e:
        logger.error(f"Failed to initialize Gemini model: {e}")
        return GENERIC_ERROR_MSG

    # Build system instruction
    system_instruction = _get_system_prompt(mcq, context_type)

    # Convert message history to Gemini format
    gemini_history = _to_gemini_history(messages)

    # Prepend system instruction to the first user message so Gemini respects it
    if gemini_history:
        for i, msg in enumerate(gemini_history):
            if msg['role'] == 'user':
                gemini_history[i]['parts'][0] = (
                    f"{system_instruction}\n\n"
                    f"Student: {msg['parts'][0]}"
                )
                break

    # Separate history from the latest user message
    if len(gemini_history) >= 2:
        chat_history = gemini_history[:-1]
        latest_message = gemini_history[-1]['parts'][0]
    else:
        chat_history = []
        latest_message = gemini_history[0]['parts'][0] if gemini_history else ""

    try:
        # Start multi-turn chat session
        chat = model.start_chat(history=chat_history)

        # Send the latest message
        response = chat.send_message(latest_message)

        if response and response.text:
            return response.text.strip()
        return GENERIC_ERROR_MSG

    except Exception as e:
        friendly_msg = _classify_error(e)
        logger.error(f"Gemini API error ({type(e).__name__}): {e}")
        return friendly_msg
