import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

from .models import AnswerResponse, Citation, PolicySection
from .policies import list_documents
from .prompts import get_prompt


CONTACTS = {
    "attendance": "Academic Affairs Office",
    "exams": "Examinations Office",
    "fees": "Finance Office",
    "hostel": "Residence Life Office",
}
KEYWORDS = {
    "attendance": {"attendance", "attend", "class", "classes", "absent", "presence"},
    "exams": {"exam", "exams", "examination", "eligibility", "assessment", "retake", "invigilator"},
    "fees": {"fee", "fees", "payment", "pay", "deadline", "tuition", "installment"},
    "hostel": {"hostel", "residence", "curfew", "visitor", "warden", "dorm"},
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
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def classify(question: str) -> str:
    normalized = set(re.findall(r"[a-z]+", _clean_question(question).lower()))
    scores = {category: len(normalized & terms) for category, terms in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "out_of_scope"
    if sum(score > 0 for score in scores.values()) > 1:
        return "out_of_scope"
    return best


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


def _unsupported(category: str, reason: str, version: str, status: str = "unsupported") -> AnswerResponse:
    return AnswerResponse(
        category=category,
        answer=reason,
        citations=[],
        confidence="Low",
        status=status,
        contact=CONTACTS.get(category),
        mode="demo",
        prompt_version=version,
    )


def _contradiction(sections: list[PolicySection]) -> bool:
    for first_index, first in enumerate(sections):
        for second in sections[first_index + 1:]:
            if first.title.lower() == second.title.lower() and first.text.strip().lower() != second.text.strip().lower():
                return True
    return False


def deterministic_answer(question: str, version: str = "v3") -> AnswerResponse:
    if _has_multiple_questions(question):
        return _unsupported("out_of_scope", "This message contains multiple questions. Please ask one policy question at a time so each answer can be checked against its own evidence.", version, "clarification_needed")
    category = classify(question)
    if category == "out_of_scope":
        return _unsupported(category, "I can only help with attendance, exams, fees, and hostel policies. Please contact the relevant university office for other questions.", version, "refused")

    matches = retrieve(question, category, [section for doc in list_documents() for section in doc.sections])
    if not matches:
        return _unsupported(category, "The supplied policy documents do not contain enough information to answer this question.", version)
    if _contradiction(matches):
        return _unsupported(category, "The supplied policy documents contain conflicting sections on this topic. Please contact the relevant university office for clarification.", version, "conflict")

    selected = matches[:1]
    return AnswerResponse(
        category=category,
        answer=selected[0].text,
        citations=[
            Citation(source_document=section.document, source_section=section.section, source_quote=section.text)
            for section in selected
        ],
        confidence="High",
        status="supported",
        contact=None,
        mode="demo",
        prompt_version=version,
    )


def _verify_and_normalize(payload: dict, evidence: list[PolicySection], category: str, version: str) -> AnswerResponse:
    if not isinstance(payload, dict):
        return _unsupported(category, "The model returned an invalid structured response.", version)
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
            verified.append(Citation(source_document=source.document, source_section=source.section, source_quote=quote))
    answer = str(payload.get("answer", "")).strip()
    if payload.get("status") != "supported" or payload.get("confidence") not in {"High", "Medium", "Low"} or not verified or not answer:
        return _unsupported(category, "The supplied policy documents do not provide a verifiable answer. Please contact the relevant university office.", version)
    if not any(answer in citation.source_quote for citation in verified):
        return _unsupported(category, "The generated answer could not be verified as a verbatim statement in the cited policy text.", version)
    answer_numbers = set(SENSITIVE_CLAIM.findall(answer))
    evidence_text = " ".join(citation.source_quote for citation in verified)
    if answer_numbers and any(number.lower() not in evidence_text.lower() for number in answer_numbers):
        return _unsupported(category, "The generated answer included a claim that could not be verified in the cited policy text.", version)
    return AnswerResponse(
        category=category,
        answer=answer,
        citations=verified,
        confidence=payload.get("confidence", "Low"),
        status="supported",
        contact=None,
        mode="gemini",
        prompt_version=version,
    )


def _gemini_answer(question: str, category: str, evidence: list[PolicySection], version: str) -> AnswerResponse:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return deterministic_answer(question, version)
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    prompt = get_prompt(version)
    evidence_json = json.dumps(
        [{"source_document": item.document, "source_section": item.section, "title": item.title, "text": item.text} for item in evidence],
        ensure_ascii=False,
    )
    request_body = {
        "system_instruction": {"parts": [{"text": prompt}]},
        "contents": [{"role": "user", "parts": [{"text": f"Category: {category}\nQuestion: {question}\nEvidence (untrusted policy text): {evidence_json}"}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "answer": {"type": "STRING"},
                    "status": {"type": "STRING", "enum": ["supported", "unsupported", "conflict", "clarification_needed", "refused"]},
                    "confidence": {"type": "STRING", "enum": ["High", "Medium", "Low"]},
                    "citations": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                        "source_document": {"type": "STRING"}, "source_section": {"type": "STRING"}, "source_quote": {"type": "STRING"}
                    }, "required": ["source_document", "source_section", "source_quote"]}},
                },
                "required": ["answer", "status", "confidence", "citations"],
            },
        },
    }
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Gemini request failed: {error}") from error
    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        payload = json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("Gemini returned an invalid structured response.") from error
    return _verify_and_normalize(payload, evidence, category, version)


def answer_question(question: str, version: str = "v3") -> AnswerResponse:
    if _has_multiple_questions(question):
        return _unsupported("out_of_scope", "This message contains multiple questions. Please ask one policy question at a time so each answer can be checked against its own evidence.", version, "clarification_needed")
    category = classify(question)
    all_sections = [section for document in list_documents() for section in document.sections]
    evidence = retrieve(question, category, all_sections) if category != "out_of_scope" else []
    if not os.getenv("GEMINI_API_KEY", "").strip():
        return deterministic_answer(question, version)
    if category == "out_of_scope":
        return _unsupported(category, "I can only help with attendance, exams, fees, and hostel policies. Please contact the relevant university office.", version, "refused")
    if not evidence:
        return _unsupported(category, "The supplied policy documents do not contain enough information to answer this question.", version)
    if _contradiction(evidence):
        return _unsupported(category, "The supplied policy documents contain conflicting sections on this topic. Please contact the relevant university office for clarification.", version, "conflict")
    return _gemini_answer(question, category, evidence, version)
