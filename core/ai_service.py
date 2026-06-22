"""
AI Assistant service for ImtihanHub.

Providers (tried in order):
1. Groq API (fast, generous free tier: 1.5M tokens/day)
2. Kimi / Moonshot AI (OpenAI-compatible)
3. Google Gemini API (fallback)

Set GROQ_API_KEY, KIMI_API_KEY, or GEMINI_API_KEY in your .env file.
Multiple comma-separated keys supported per provider.
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
    "The AI assistant is currently busy. Please try again in a few minutes."
)

QUOTA_EXCEEDED_MSG = (
    "The AI assistant is currently busy. Please try again in a few minutes."
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

def _get_ai_response_gemini(messages: list[dict], system_instruction: str, api_key: str) -> str:
    """Call Google Gemini API."""
    import requests as http_requests

    model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-2.0-flash')

    contents = []
    for i, msg in enumerate(messages):
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        gemini_role = 'user' if role == 'user' else 'model'
        if i == 0 and gemini_role == 'user':
            content = f"{system_instruction}\n\nStudent: {content}"
        contents.append({'role': gemini_role, 'parts': [{'text': content}]})

    if not contents:
        return GENERIC_ERROR_MSG

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        'contents': contents,
        'generationConfig': {'temperature': 0.7, 'maxOutputTokens': 2048}
    }

    try:
        response = http_requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            candidates = data.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                finish_reason = candidates[0].get('finishReason', '')
                if parts:
                    text = parts[0].get('text', '').strip()
                    if finish_reason == 'MAX_TOKENS' and text:
                        text += "\n\n*(Response was cut short — ask me to continue if you need more.)*"
                    return text
            logger.warning(f"Gemini: 200 but no candidates. Response: {str(data)[:300]}")
            return GENERIC_ERROR_MSG
        elif response.status_code == 429:
            logger.error(f"Gemini quota error (429): {response.text[:300]}")
            return "__QUOTA__"
        elif response.status_code in (400, 401, 403):
            logger.error(f"Gemini auth error ({response.status_code}): {response.text[:300]}")
            return "__AUTH__"
        else:
            logger.error(f"Gemini HTTP {response.status_code}: {response.text[:300]}")
            return "__ERROR__"
    except Exception as e:
        logger.warning(f"Gemini connection error: {e}")
        return "__ERROR__"


def _get_ai_response_openai_compatible(
    messages: list[dict], system_instruction: str, api_key: str,
    base_url: str, model: str
) -> str:
    """Generic OpenAI-compatible API caller (Groq, Kimi, etc.)."""
    import requests as http_requests

    chat_messages = []
    if system_instruction:
        chat_messages.append({'role': 'system', 'content': system_instruction})
    for msg in messages:
        role = 'assistant' if msg.get('role') == 'model' else msg.get('role', 'user')
        chat_messages.append({'role': role, 'content': msg.get('content', '')})

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': model,
        'messages': chat_messages,
        'temperature': 0.7,
        'max_tokens': 2048,
    }

    try:
        response = http_requests.post(
            f'{base_url}/v1/chat/completions',
            headers=headers, json=payload, timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            choices = data.get('choices', [])
            if choices:
                text = choices[0].get('message', {}).get('content', '').strip()
                finish_reason = choices[0].get('finish_reason', '')
                if finish_reason == 'length' and text:
                    text += "\n\n*(Response was cut short — ask me to continue if you need more.)*"
                return text
            logger.warning(f"OpenAI-compat ({base_url}): 200 but no choices. Response: {str(data)[:300]}")
            return GENERIC_ERROR_MSG
        elif response.status_code == 429:
            logger.error(f"OpenAI-compat ({base_url}) quota error (429): {response.text[:300]}")
            return "__QUOTA__"
        elif response.status_code in (400, 401, 403):
            logger.error(f"OpenAI-compat ({base_url}) auth error ({response.status_code}): {response.text[:300]}")
            return "__AUTH__"
        else:
            logger.error(f"OpenAI-compat ({base_url}) HTTP {response.status_code}: {response.text[:300]}")
            return "__ERROR__"
    except Exception as e:
        logger.warning(f"OpenAI-compat ({base_url}) connection error: {e}")
        return "__ERROR__"


def _get_ai_response_groq(messages: list[dict], system_instruction: str, api_key: str) -> str:
    """Call Groq API (fast, generous free tier)."""
    model = getattr(settings, 'GROQ_MODEL', 'llama-3.1-8b-instant')
    return _get_ai_response_openai_compatible(messages, system_instruction, api_key, 'https://api.groq.com/openai', model)


def _get_ai_response_kimi(messages: list[dict], system_instruction: str, api_key: str) -> str:
    """Call Kimi / Moonshot AI API."""
    model = getattr(settings, 'KIMI_MODEL', 'moonshot-v1-8k')
    return _get_ai_response_openai_compatible(messages, system_instruction, api_key, 'https://api.moonshot.cn', model)


def _try_keys(func, messages, system_instruction, keys_raw: str) -> str:
    """Try multiple comma-separated API keys until one succeeds."""
    if not keys_raw:
        return "__NO_KEYS__"
    keys = [k.strip() for k in keys_raw.split(',') if k.strip()]
    any_quota = False
    any_auth = False
    last_error = "__ERROR__"
    for key in keys:
        result = func(messages, system_instruction, key)
        if result and not result.startswith("__"):
            return result
        if result == "__QUOTA__":
            any_quota = True
        elif result == "__AUTH__":
            any_auth = True
        elif result:
            last_error = result
    if any_quota:
        return "__QUOTA__"
    if any_auth:
        return "__AUTH__"
    return last_error


def get_ai_response(messages: list[dict], mcq=None, context_type: str = "general") -> str:
    """
    Generate AI response. Tries Groq → Kimi → Gemini.
    Supports multiple comma-separated keys per provider.
    """
    system_instruction = _get_system_prompt(mcq, context_type)

    # Log which keys are configured (without revealing the actual keys)
    groq_keys = getattr(settings, 'GROQ_API_KEY', '')
    kimi_keys = getattr(settings, 'KIMI_API_KEY', '')
    gemini_keys = getattr(settings, 'GEMINI_API_KEY', '')
    logger.info(
        f"AI request: context={context_type}, "
        f"Groq={'yes' if groq_keys else 'no'}, "
        f"Kimi={'yes' if kimi_keys else 'no'}, "
        f"Gemini={'yes' if gemini_keys else 'no'}"
    )

    # 1. Try Groq keys
    if groq_keys:
        result = _try_keys(_get_ai_response_groq, messages, system_instruction, groq_keys)
        if result and not result.startswith("__"):
            return result
        logger.warning(f"All Groq keys failed (result={result}), trying Kimi fallback.")

    # 2. Try Kimi keys
    if kimi_keys:
        result = _try_keys(_get_ai_response_kimi, messages, system_instruction, kimi_keys)
        if result and not result.startswith("__"):
            return result
        logger.warning(f"All Kimi keys failed (result={result}), trying Gemini fallback.")

    # 3. Fallback to Gemini keys
    if gemini_keys:
        result = _try_keys(_get_ai_response_gemini, messages, system_instruction, gemini_keys)
        if result and not result.startswith("__"):
            return result
        logger.error(f"All Gemini keys failed (result={result}). All providers exhausted.")
        if result == "__QUOTA__":
            return QUOTA_EXCEEDED_MSG
        if result == "__AUTH__":
            return API_KEY_MISSING
        return GENERIC_ERROR_MSG

    logger.error("No AI API keys configured (GROQ_API_KEY, KIMI_API_KEY, or GEMINI_API_KEY). All empty.")
    return API_KEY_MISSING