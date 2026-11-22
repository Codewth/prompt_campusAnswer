import json
import logging
import os
import re
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from .models import AnswerResponse, AnswerSegment, Citation, ConversationMessage, PolicySection
from .official_index import search_official
from .policies import list_documents
from .prompts import get_prompt


CONTACTS = {
    "attendance": "Academic Affairs Office",
    "exams": "Examinations Office",
    "fees": "Finance Office",
    "hostel": "Residence Life Office",
    "scholarships": "Scholarship Office",
    "campus": "Campus Administration Office",
}
KEYWORDS = {
    "attendance": {"attendance", "attend", "absent", "presence"},
    "exams": {"exam", "exams", "examination", "eligibility", "assessment", "retake", "invigilator"},
    "fees": {"fee", "fees", "payment", "pay", "deadline", "tuition", "installment"},
    "hostel": {"hostel", "residence", "curfew", "visitor", "warden", "dorm"},
    "scholarships": {"scholarship", "scholarships", "grant", "grants", "stipend"},
    "campus": {"campus", "library", "parking", "security", "transport"},
}
STOP_WORDS = {
    "what", "when", "where", "which", "who", "how", "does", "do", "is", "are", "can",
    "could", "would", "should", "the", "a", "an", "to", "of", "for", "in", "on", "and",
    "or", "my", "me", "i", "please", "tell", "about", "policy", "rule", "rules", "at",
    "university", "unrelated", "this", "that", "it", "your", "ignore", "previous",
}
SYNONYMS = {
    "hostel": "residence",
    "dorm": "residence",
    "curfew": "entry",
    "timings": "time",
    "timing": "time",
    "exam": "examination",
    "exams": "examination",
    "fees": "fee",
    "pay": "payment",
}
GENERIC_TERMS = {"attendance", "examination", "fee", "residence", "policy"}
SENSITIVE_CLAIM = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent|am|pm|hours?|days?|weeks?|months?|₹|rupees?)\b", re.I)
CURRENT_POLICY_QUERY = re.compile(r"\b(?:current|currently|latest|most recent|as of now|this academic year)\b", re.I)
CLOCK_TIME_QUERY = re.compile(r"\b(?:what time|at what time|curfew|hostel timings?|exact time)\b", re.I)
CLOCK_TIME_VALUE = re.compile(r"\b(?:[01]?\d|2[0-3])(?:(?::|\.)[0-5]\d)?\s*(?:a\.?m\.?|p\.?m\.?)\b", re.I)
ATTENDANCE_PERCENTAGE = re.compile(
    r"\b(?:minimum attendance(?: of)?|attendance requirement(?: of)?)\D{0,60}(\d+(?:\.\d+)?\s*%)",
    re.I,
)
FOLLOW_UP = re.compile(
    r"\b(?:explain|elaborate|clarify|expand)\b.*\b(?:previous|last|above|that|it|answer|response)\b"
    r"|\b(?:why|how so|what does that mean|tell me more)\b",
    re.I,
)
MIXED_SPLIT = re.compile(
    r"(?<=[?;])\s*|\s+(?:and also|also|and)\s+(?=(?:what|when|where|who|why|how|explain|define|tell)\b)",
    re.I,
)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logger = logging.getLogger(__name__)
GEMINI_MODEL_DEFAULT = "gemini-3.8-flash"
GEMINI_CONNECT_TIMEOUT_SECONDS = 5
GEMINI_READ_TIMEOUT_SECONDS = 45
GEMINI_MAX_RETRIES = 1
GEMINI_RETRY_BACKOFF_SECONDS = 0.5
MAX_POLICY_EVIDENCE_CHUNKS = 5
MAX_POLICY_EVIDENCE_CHARS = 12_000
MAX_HISTORY_MESSAGES = 8
MAX_HISTORY_MESSAGE_CHARS = 1_200
GEMINI_HTTP_CLIENT = httpx.Client(
    timeout=httpx.Timeout(
        connect=GEMINI_CONNECT_TIMEOUT_SECONDS,
        read=GEMINI_READ_TIMEOUT_SECONDS,
        write=10,
        pool=5,
    )
)


class GeminiUnavailableError(RuntimeError):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


class GeminiRateLimitError(GeminiUnavailableError):
    def __init__(self):
        super().__init__("Gemini rate limit reached. Wait a little, then retry.", status_code=429)


class GeminiServiceUnavailableError(GeminiUnavailableError):
    def __init__(self):
        super().__init__("Gemini is temporarily unavailable. Please retry shortly.", status_code=503)


class GeminiTimeoutError(GeminiUnavailableError):
    def __init__(self):
        super().__init__("Gemini took too long to respond. Please retry.", status_code=504)


def gemini_runtime_status() -> dict[str, str | bool]:
    return {
        "configured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "model": os.getenv("GEMINI_MODEL", GEMINI_MODEL_DEFAULT).strip() or GEMINI_MODEL_DEFAULT,
    }


def classify(question: str) -> str:
    categories = _matched_policy_categories(question)
    return categories[0] if len(categories) == 1 else "out_of_scope"


def _matched_policy_categories(question: str) -> list[str]:
    normalized = set(re.findall(r"[a-z]+", _clean_question(question).lower()))
    if "financial" in normalized and "aid" in normalized:
        normalized.add("scholarship")
    scores = {category: len(normalized & terms) for category, terms in KEYWORDS.items()}
    return [category for category, score in scores.items() if score > 0]


def _conversation_response(question: str, version: str, collection: str) -> AnswerResponse | None:
    normalized = re.sub(r"[^a-z0-9' ]", "", question.lower()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if re.fullmatch(r"(?:hi|hello|hey|hiya|good morning|good afternoon|good evening)", normalized):
        answer = "Hello! I'm CampusAnswer. I can chat, answer general questions, or look up university policies in the supplied documents."
    elif re.fullmatch(r"(?:how are you|how's it going|how are you doing)", normalized):
        answer = "I'm doing well, thanks! I can help with general questions or find evidence in the supplied university policies."
    elif re.fullmatch(r"(?:thanks|thank you|thanks a lot|thank you so much)", normalized):
        answer = "You're welcome! Feel free to ask me another question."
    elif re.fullmatch(r"(?:who are you|what is your name|introduce yourself|tell me about yourself)", normalized):
        answer = "I'm CampusAnswer, an assistant for general questions and document-grounded university policy help."
    else:
        return None
    return AnswerResponse(
        category="out_of_scope",
        answer=answer,
        citations=[],
        confidence=None,
        status="supported",
        contact=None,
        mode="predefined",
        prompt_version=version,
        collection=collection,
        response_type="general_conversation",
        response_label="General conversation",
    )


def _clean_question(question: str) -> str:
    return re.sub(
        r"\b(?:ignore|disregard|forget)\b.*?(?=\b(?:what|when|where|which|who|how|can|could|does|do|is|are)\b)",
        "",
        question,
        flags=re.IGNORECASE,
    )


def _has_multiple_questions(question: str) -> bool:
    if len(re.findall(r"\?", question)) > 1 or re.search(r"\b(and also|additionally|secondly)\b", question, re.I):
        return True
    words = set(re.findall(r"[a-z]+", _clean_question(question).lower()))
    mentioned_categories = sum(bool(words & keywords) for keywords in KEYWORDS.values())
    return mentioned_categories > 1


def _last_history_message(
    history: list[ConversationMessage],
    role: str,
) -> ConversationMessage | None:
    return next((message for message in reversed(history) if message.role == role), None)


def _follow_up_context(
    question: str,
    history: list[ConversationMessage],
) -> tuple[str, str, str] | None:
    if not FOLLOW_UP.search(question):
        return None
    previous_user = _last_history_message(history, "user")
    previous_assistant = _last_history_message(history, "assistant")
    prior_question = previous_user.content if previous_user else ""
    response_type = previous_assistant.response_type if previous_assistant else None
    category = previous_assistant.category if previous_assistant else None
    latest_user_index = max(
        (index for index, message in enumerate(history) if message.role == "user"),
        default=-1,
    )
    latest_assistant_index = max(
        (index for index, message in enumerate(history) if message.role == "assistant"),
        default=-1,
    )
    if latest_user_index > latest_assistant_index:
        response_type = None
        category = classify(prior_question)
    if response_type in {"verified_policy", "policy_unavailable", "demo_policy"}:
        category = category or classify(prior_question)
        if category != "out_of_scope":
            return "policy", category, f"{prior_question}\n{question}".strip()
    if response_type in {"general_conversation", "general_knowledge"}:
        return "general_knowledge", "out_of_scope", question
    if prior_question and classify(prior_question) != "out_of_scope":
        return "policy", classify(prior_question), f"{prior_question}\n{question}".strip()
    return "general_knowledge", "out_of_scope", question


def _mixed_question_parts(question: str) -> list[tuple[str, str]] | None:
    parts = [part.strip(" ,.") for part in MIXED_SPLIT.split(question) if part.strip(" ,.?;")]
    if len(parts) < 2:
        return None
    routed = [(part, classify(part)) for part in parts]
    has_policy = any(category != "out_of_scope" for _, category in routed)
    has_general = any(category == "out_of_scope" for _, category in routed)
    return routed if has_policy and has_general else None


def retrieve(question: str, category: str, sections: list[PolicySection]) -> list[PolicySection]:
    terms = {
        SYNONYMS.get(term, term)
        for term in re.findall(r"[a-z0-9]+", _clean_question(question).lower())
        if term not in STOP_WORDS and term not in GENERIC_TERMS
    }
    if not terms:
        return []
    candidates: list[tuple[int, PolicySection]] = []
    document_markers = {
        "attendance": ("attendance",),
        "exams": ("examination", "exam"),
        "fees": ("fee", "tuition"),
        "hostel": ("hostel", "residence"),
    }
    for section in sections:
        title = section.document.lower()
        known_domain = next(
            (domain for domain, markers in document_markers.items() if any(marker in title for marker in markers)),
            None,
        )
        if known_domain and known_domain != category:
            continue
        searchable = f"{section.title} {section.text}".lower()
        score = sum(1 for term in terms if term in searchable)
        if score:
            candidates.append((score, section))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [section for score, section in candidates[:5] if score > 0]


def _bounded_evidence(evidence: list[PolicySection]) -> list[PolicySection]:
    bounded = []
    total_chars = 0
    for section in evidence:
        if len(bounded) >= MAX_POLICY_EVIDENCE_CHUNKS:
            break
        if total_chars + len(section.text) > MAX_POLICY_EVIDENCE_CHARS:
            continue
        bounded.append(section)
        total_chars += len(section.text)
    return bounded


def _unsupported(
    category: str,
    reason: str,
    version: str,
    status: str = "unsupported",
    collection: str = "demo",
) -> AnswerResponse:
    return AnswerResponse(
        category=category,
        answer=reason,
        citations=[],
        confidence="Low",
        status=status,
        contact=CONTACTS.get(category),
        mode="demo",
        prompt_version=version,
        collection=collection,
        response_type="policy_unavailable",
        response_label="Policy information unavailable",
    )


def _contradiction(sections: list[PolicySection]) -> bool:
    for first_index, first in enumerate(sections):
        for second in sections[first_index + 1:]:
            if first.title.lower() == second.title.lower() and first.text.strip().lower() != second.text.strip().lower():
                return True
    return False


def _official_attendance_conflict_sections(sections: list[PolicySection]) -> list[PolicySection]:
    sections_by_claim: dict[str, PolicySection] = {}
    for section in sections:
        if not re.search(r"\battendance\b", section.text, re.I):
            continue
        claims = ATTENDANCE_PERCENTAGE.findall(section.text)
        for claim in claims:
            normalized = re.sub(r"\s+", "", claim).lower()
            sections_by_claim.setdefault(normalized, section)
    if len(sections_by_claim) < 2:
        return []
    return list(sections_by_claim.values())


def _official_attendance_conflict_response(
    sections: list[PolicySection],
    version: str,
) -> AnswerResponse:
    return AnswerResponse(
        category="attendance",
        answer=(
            "The retrieved official sources state different minimum attendance percentages. "
            "Their available metadata does not establish which requirement currently applies. "
            "Please contact the Academic Affairs Office to confirm."
        ),
        citations=[
            Citation(
                source_document=section.document,
                source_section=section.section,
                source_quote=section.text,
                collection=section.collection,
                academic_year=section.academic_year,
                source_url=section.source_url,
                page=section.page,
                extraction_method=section.extraction_method,
            )
            for section in sections
        ],
        confidence="Low",
        status="conflict",
        contact=CONTACTS["attendance"],
        mode="demo",
        prompt_version=version,
        collection="official",
        response_type="policy_unavailable",
        response_label="Policy information unavailable",
    )


def _official_query_requires_unknown_current_policy(question: str, collection: str) -> bool:
    return collection == "official" and bool(CURRENT_POLICY_QUERY.search(question))


def _requested_detail_missing(question: str, evidence: list[PolicySection]) -> bool:
    evidence_text = " ".join(section.text for section in evidence)
    if CLOCK_TIME_QUERY.search(question):
        if not CLOCK_TIME_VALUE.search(evidence_text):
            return True
        if re.search(r"\bcurfew\b", question, re.I):
            curfew_time = re.compile(
                rf"\bcurfew\b[^.!?\n]{{0,100}}{CLOCK_TIME_VALUE.pattern}|"
                rf"{CLOCK_TIME_VALUE.pattern}[^.!?\n]{{0,100}}\bcurfew\b",
                re.I,
            )
            if not curfew_time.search(evidence_text):
                return True
        if re.search(r"\bhostel timings?\b", question, re.I):
            hostel_time = re.compile(
                rf"\bhostel timings?\b[^.!?\n]{{0,100}}{CLOCK_TIME_VALUE.pattern}|"
                rf"{CLOCK_TIME_VALUE.pattern}[^.!?\n]{{0,100}}\bhostel timings?\b",
                re.I,
            )
            if not hostel_time.search(evidence_text):
                return True
    if re.search(r"\b(?:percentage|percent|%|rate)\b", question, re.I) and not re.search(r"\d+(?:\.\d+)?\s*%", evidence_text):
        return True
    return False


def _answer_policy(
    question: str,
    retrieval_question: str,
    category: str,
    version: str,
    collection: str,
    history: list[ConversationMessage],
) -> AnswerResponse:
    if _official_query_requires_unknown_current_policy(question, collection):
        return _unsupported(
            category,
            "The available official sources do not establish which policy is currently in force. Please confirm the current rule with the relevant university office.",
            version,
            collection=collection,
        )
    retrieval_started = time.perf_counter()
    if collection == "official":
        retrieval_limit = 10 if category == "attendance" else MAX_POLICY_EVIDENCE_CHUNKS
        retrieved_evidence = search_official(retrieval_question, category, limit=retrieval_limit)
    else:
        retrieved_evidence = retrieve(
            retrieval_question,
            category,
            [section for doc in list_documents() for section in doc.sections],
        )
    evidence = _bounded_evidence(retrieved_evidence)
    logger.info(
        "Policy retrieval completed collection=%s category=%s chunks=%d context_chars=%d elapsed_ms=%d",
        collection,
        category,
        len(evidence),
        sum(len(section.text) for section in evidence),
        round((time.perf_counter() - retrieval_started) * 1000),
    )
    if not evidence:
        return _unsupported(
            category,
            "The selected policy documents do not contain enough information to verify this answer. Please contact the relevant university office.",
            version,
            collection=collection,
        )
    attendance_conflicts = (
        _official_attendance_conflict_sections(retrieved_evidence)
        if collection == "official" and category == "attendance"
        else []
    )
    if attendance_conflicts:
        return _official_attendance_conflict_response(attendance_conflicts, version)
    if _requested_detail_missing(question, evidence):
        return _unsupported(
            category,
            "The retrieved policy text does not establish the specific detail requested. Please confirm it with the relevant university office.",
            version,
            collection=collection,
        )
    if _contradiction(retrieved_evidence):
        return _unsupported(
            category,
            "The selected policy documents contain conflicting sections on this topic. Please contact the relevant university office for clarification.",
            version,
            "conflict",
            collection,
        )
    return _gemini_answer(question, category, evidence, version, collection, history)


def _verify_and_normalize(
    payload: dict,
    evidence: list[PolicySection],
    category: str,
    version: str,
    collection: str = "demo",
) -> AnswerResponse:
    if not isinstance(payload, dict):
        return _unsupported(category, "The model returned an invalid structured response.", version, collection=collection)
    evidence_lookup = {(item.document, item.section): item for item in evidence}
    citations = payload.get("citations", [])
    if not isinstance(citations, list):
        citations = []
    verified = []
    for item in citations:
        if not isinstance(item, dict):
            continue
        document_name = item.get("source_document")
        section_number = item.get("source_section")
        quote = item.get("source_quote", "")
        if not isinstance(document_name, str) or not isinstance(section_number, str) or not isinstance(quote, str):
            continue
        source = evidence_lookup.get((document_name, section_number))
        if source and quote and quote in source.text:
            verified.append(
                Citation(
                    source_document=source.document,
                    source_section=source.section,
                    source_quote=quote,
                    collection=source.collection,
                    academic_year=source.academic_year,
                    source_url=source.source_url,
                    page=source.page,
                    extraction_method=source.extraction_method,
                )
            )
    answer = str(payload.get("answer", "")).strip()
    if payload.get("status") != "supported" or payload.get("confidence") not in {"High", "Medium", "Low"} or not verified or not answer:
        return _unsupported(category, "The selected source collection does not provide a verifiable answer. Please contact the relevant university office.", version, collection=collection)
    if not any(answer in citation.source_quote for citation in verified):
        return _unsupported(category, "The generated answer could not be verified as a verbatim statement in the cited policy text.", version, collection=collection)
    answer_numbers = set(SENSITIVE_CLAIM.findall(answer))
    evidence_text = " ".join(citation.source_quote for citation in verified)
    if answer_numbers and any(number.lower() not in evidence_text.lower() for number in answer_numbers):
        return _unsupported(category, "The generated answer included a claim that could not be verified in the cited policy text.", version, collection=collection)
    return AnswerResponse(
        category=category,
        answer=answer,
        citations=verified,
        confidence=payload.get("confidence", "Low"),
        status="supported",
        contact=None,
        mode="gemini",
        prompt_version=version,
        collection=collection,
        response_type="verified_policy" if collection == "official" else "demo_policy",
        response_label="Verified university policy" if collection == "official" else "Fictional policy demonstration",
    )


def _gemini_generate_text(
    system_prompt: str,
    contents: list[dict],
    generation_config: dict | None = None,
) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiUnavailableError(
            "Gemini is not configured on this backend. Ask an administrator to set GEMINI_API_KEY."
        )
    model = os.getenv("GEMINI_MODEL", GEMINI_MODEL_DEFAULT).strip() or GEMINI_MODEL_DEFAULT
    request_body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
    }
    if generation_config is not None:
        request_body["generationConfig"] = generation_config
    started = time.perf_counter()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    response = None
    for attempt in range(GEMINI_MAX_RETRIES + 1):
        try:
            response = GEMINI_HTTP_CLIENT.post(
                url,
                json=request_body,
                headers={"x-goog-api-key": api_key},
            )
        except (httpx.ConnectTimeout, httpx.ConnectError) as error:
            retrying = attempt < GEMINI_MAX_RETRIES
            logger.warning(
                "Gemini connection failure model=%s phase=%s attempt=%d elapsed_ms=%d retry=%s",
                model,
                type(error).__name__,
                attempt + 1,
                round((time.perf_counter() - started) * 1000),
                retrying,
            )
            if retrying:
                time.sleep(GEMINI_RETRY_BACKOFF_SECONDS)
                continue
            if isinstance(error, httpx.ConnectTimeout):
                raise GeminiTimeoutError() from error
            raise GeminiUnavailableError(
                "Could not connect to Gemini. Check the backend network and try again.",
                status_code=502,
            ) from error
        except httpx.ReadTimeout as error:
            logger.warning(
                "Gemini network timeout model=%s phase=ReadTimeout attempt=%d elapsed_ms=%d retry=false reason=avoid_duplicate_generation",
                model,
                attempt + 1,
                round((time.perf_counter() - started) * 1000),
            )
            raise GeminiTimeoutError() from error
        except httpx.TimeoutException as error:
            logger.warning(
                "Gemini network timeout model=%s phase=%s attempt=%d elapsed_ms=%d retry=false",
                model,
                type(error).__name__,
                attempt + 1,
                round((time.perf_counter() - started) * 1000),
            )
            raise GeminiTimeoutError() from error
        except httpx.RequestError as error:
            logger.warning(
                "Gemini network request failed model=%s error_type=%s attempt=%d elapsed_ms=%d",
                model,
                type(error).__name__,
                attempt + 1,
                round((time.perf_counter() - started) * 1000),
            )
            raise GeminiUnavailableError(
                "Could not reach Gemini. Check the backend network and try again.",
                status_code=502,
            ) from error

        if response.status_code == 503 and attempt < GEMINI_MAX_RETRIES:
            logger.warning(
                "Gemini transient upstream error model=%s http_status=503 attempt=%d retry=true elapsed_ms=%d",
                model,
                attempt + 1,
                round((time.perf_counter() - started) * 1000),
            )
            time.sleep(GEMINI_RETRY_BACKOFF_SECONDS)
            continue
        break

    assert response is not None
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    if response.status_code >= 400:
        try:
            provider_error = response.json().get("error", {})
        except (ValueError, AttributeError):
            provider_error = {}
        if not isinstance(provider_error, dict):
            provider_error = {}
        provider_status = str(provider_error.get("status", "UNKNOWN"))
        provider_message = str(provider_error.get("message", ""))
        if api_key:
            provider_message = provider_message.replace(api_key, "[REDACTED]")
        logger.warning(
            "Gemini upstream error model=%s http_status=%d provider_status=%s elapsed_ms=%d message=%s",
            model,
            response.status_code,
            provider_status,
            elapsed_ms,
            provider_message[:300],
        )
        if response.status_code == 429:
            raise GeminiRateLimitError()
        if response.status_code == 503 or response.status_code >= 500:
            raise GeminiServiceUnavailableError()
        if response.status_code == 404:
            raise GeminiUnavailableError(
                f"Gemini model '{model}' was not found. Check GEMINI_MODEL in the backend settings.",
                status_code=502,
            )
        if response.status_code in {401, 403}:
            raise GeminiUnavailableError(
                "Gemini rejected the API key or model access. Check the key and model permissions in backend settings.",
                status_code=502,
            )
        raise GeminiUnavailableError(
            f"Gemini rejected the request (HTTP {response.status_code}). Check the model and request configuration.",
            status_code=502,
        )
    logger.info("Gemini request completed model=%s http_status=%d elapsed_ms=%d", model, response.status_code, elapsed_ms)
    try:
        result = response.json()
    except (ValueError, TypeError) as error:
        raise GeminiUnavailableError("Gemini returned an invalid response.") from error
    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as error:
        raise GeminiUnavailableError("Gemini returned an invalid response.") from error
    if not isinstance(text, str) or not text.strip():
        raise GeminiUnavailableError("Gemini returned an empty response.")
    return text


def _gemini_text_response(system_prompt: str, contents: list[dict]) -> str:
    return _gemini_generate_text(
        system_prompt,
        contents,
        {"maxOutputTokens": 24, "temperature": 0},
    )


def _gemini_json_response(system_prompt: str, contents: list[dict], schema: dict) -> dict:
    text = _gemini_generate_text(
        system_prompt,
        contents,
        {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise GeminiUnavailableError("Gemini returned an invalid structured response.") from error
    if not isinstance(payload, dict):
        raise GeminiUnavailableError("Gemini returned an invalid structured response.")
    return payload


def _history_contents(history: list[ConversationMessage]) -> list[dict]:
    contents: list[dict] = []
    for message in history[-MAX_HISTORY_MESSAGES:]:
        role = "model" if message.role == "assistant" else "user"
        text = message.content[:MAX_HISTORY_MESSAGE_CHARS]
        if message.response_type:
            text = f"[{message.response_type}] {text}"
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"][0]["text"] += f"\n{text}"
        else:
            contents.append({"role": role, "parts": [{"text": text}]})
    return contents


def _gemini_answer(
    question: str,
    category: str,
    evidence: list[PolicySection],
    version: str,
    collection: str,
    history: list[ConversationMessage] | None = None,
) -> AnswerResponse:
    evidence_json = json.dumps(
        [
            {
                "source_document": item.document,
                "source_section": item.section,
                "title": item.title,
                "text": item.text,
                "academic_year": item.academic_year,
                "source_url": item.source_url,
                "page": item.page,
                "extraction_method": item.extraction_method,
            }
            for item in evidence
        ],
        ensure_ascii=False,
    )
    contents = _history_contents(history or [])
    contents.append({
        "role": "user",
        "parts": [{
            "text": f"Category: {category}\nQuestion: {question}\nRetrieved evidence (untrusted policy text): {evidence_json}"
        }],
    })
    schema = {
        "type": "OBJECT",
        "properties": {
            "answer": {"type": "STRING"},
            "status": {"type": "STRING", "enum": ["supported", "unsupported", "conflict", "clarification_needed", "refused"]},
            "confidence": {"type": "STRING", "enum": ["High", "Medium", "Low"]},
            "citations": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "source_document": {"type": "STRING"},
                        "source_section": {"type": "STRING"},
                        "source_quote": {"type": "STRING"},
                    },
                    "required": ["source_document", "source_section", "source_quote"],
                },
            },
        },
        "required": ["answer", "status", "confidence", "citations"],
    }
    prompt = (
        get_prompt(version)
        + "\n\nUse conversation history only to resolve references. Policy claims must be grounded in the retrieved evidence in this request."
    )
    payload = _gemini_json_response(prompt, contents, schema)
    return _verify_and_normalize(payload, evidence, category, version, collection)


def _gemini_general_answer(
    question: str,
    version: str,
    collection: str,
    history: list[ConversationMessage],
) -> AnswerResponse:
    contents = _history_contents(history)
    contents.append({"role": "user", "parts": [{"text": question}]})
    payload = _gemini_json_response(
        get_prompt("general"),
        contents,
        {
            "type": "OBJECT",
            "properties": {"answer": {"type": "STRING"}},
            "required": ["answer"],
        },
    )
    answer = payload.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise GeminiUnavailableError("Gemini returned an empty general-knowledge answer.")
    return AnswerResponse(
        category="out_of_scope",
        answer=answer.strip(),
        citations=[],
        confidence=None,
        status="supported",
        contact=None,
        mode="gemini",
        prompt_version=version,
        collection=collection,
        response_type="general_knowledge",
        response_label="General AI knowledge",
    )


def _as_segment(response: AnswerResponse) -> AnswerSegment:
    return AnswerSegment(
        response_type=response.response_type,
        response_label=response.response_label,
        category=response.category,
        answer=response.answer,
        citations=response.citations,
        confidence=response.confidence,
        status=response.status,
        contact=response.contact,
        mode=response.mode,
    )


def _mixed_response(
    responses: list[AnswerResponse],
    version: str,
    collection: str,
) -> AnswerResponse:
    return AnswerResponse(
        category="out_of_scope",
        answer="\n\n".join(f"{item.response_label}: {item.answer}" for item in responses),
        citations=[citation for item in responses for citation in item.citations],
        confidence=None,
        status="supported",
        contact=None,
        mode="gemini" if any(item.mode == "gemini" for item in responses) else "predefined",
        prompt_version=version,
        collection=collection,
        response_type="mixed",
        response_label="Mixed response",
        segments=[_as_segment(item) for item in responses],
    )


def answer_question(
    question: str,
    version: str = "v3",
    collection: str = "demo",
    history: list[ConversationMessage] | None = None,
) -> AnswerResponse:
    if collection not in {"official", "demo"}:
        raise ValueError("Collection must be 'official' or 'demo'.")
    conversation = history or []
    simple_response = _conversation_response(question, version, collection)
    if simple_response:
        return simple_response

    follow_up = _follow_up_context(question, conversation)
    if follow_up:
        route, category, retrieval_question = follow_up
        if route == "policy":
            return _answer_policy(question, retrieval_question, category, version, collection, conversation)
        return _gemini_general_answer(question, version, collection, conversation)

    mixed_parts = _mixed_question_parts(question)
    if mixed_parts:
        responses = []
        for part, category in mixed_parts:
            if category == "out_of_scope":
                response = _conversation_response(part, version, collection)
                if response is None:
                    response = _gemini_general_answer(part, version, collection, conversation)
            else:
                response = _answer_policy(part, part, category, version, collection, conversation)
            responses.append(response)
        return _mixed_response(responses, version, collection)

    policy_categories = _matched_policy_categories(question)
    if len(policy_categories) > 1:
        return _unsupported(
            "out_of_scope",
            "Please ask about one university policy category at a time so each answer can be checked against its own evidence.",
            version,
            "clarification_needed",
            collection,
        )
    category = classify(question)
    if category != "out_of_scope":
        if _has_multiple_questions(question):
            return _unsupported(
                category,
                "Please ask one university-policy question at a time so I can retrieve and verify the evidence for each answer.",
                version,
                "clarification_needed",
                collection,
            )
        return _answer_policy(question, question, category, version, collection, conversation)
    return _gemini_general_answer(question, version, collection, conversation)
