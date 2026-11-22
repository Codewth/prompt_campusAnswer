"""Run bounded Gemini diagnostics without printing credentials."""

import json
import os
import time

import httpx

from app.engine import (
    GeminiUnavailableError,
    GEMINI_HTTP_CLIENT,
    _gemini_json_response,
    _gemini_text_response,
    answer_question,
    gemini_runtime_status,
)


def _timed(name, operation, summarize):
    started = time.perf_counter()
    try:
        result = operation()
    except GeminiUnavailableError as error:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        print(f"{name}=error error_type={type(error).__name__} elapsed_ms={elapsed_ms} detail={error}")
        return
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    print(f"{name}=ok elapsed_ms={elapsed_ms} {summarize(result)}")


def _model_catalog_check(api_key: str, configured_model: str) -> None:
    started = time.perf_counter()
    try:
        response = GEMINI_HTTP_CLIENT.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"pageSize": 100},
            headers={"x-goog-api-key": api_key},
        )
    except httpx.RequestError as error:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        print(f"model_catalog=error error_type={type(error).__name__} elapsed_ms={elapsed_ms}")
        return

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    if response.status_code != 200:
        print(f"model_catalog=error http_status={response.status_code} elapsed_ms={elapsed_ms}")
        return
    try:
        models = response.json().get("models", [])
    except (ValueError, AttributeError):
        print(f"model_catalog=error invalid_response=true elapsed_ms={elapsed_ms}")
        return
    names = {
        str(item.get("name", "")).removeprefix("models/")
        for item in models
        if isinstance(item, dict)
    }
    print(
        f"model_catalog=ok configured_model={configured_model} "
        f"listed_for_key={configured_model in names} elapsed_ms={elapsed_ms}"
    )


def main() -> None:
    status = gemini_runtime_status()
    if not status["configured"]:
        print("diagnostics=blocked reason=GEMINI_API_KEY_not_configured")
        raise SystemExit(2)

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = str(status["model"])
    _model_catalog_check(api_key, model)

    _timed(
        "plain_no_schema",
        lambda: _gemini_text_response(
            "Reply with only the word OK.",
            [{"role": "user", "parts": [{"text": "OK"}]}],
        ),
        lambda result: f"output={result.strip()[:40]!r}",
    )

    _timed(
        "structured_no_rag",
        lambda: _gemini_json_response(
            'Return a JSON object with the single property "answer" set to "OK".',
            [{"role": "user", "parts": [{"text": "Return the requested JSON."}]}],
            {
                "type": "OBJECT",
                "properties": {"answer": {"type": "STRING"}},
                "required": ["answer"],
            },
        ),
        lambda result: f"answer={result.get('answer', '')!r}",
    )

    def run_rag():
        return answer_question(
            "How do students apply for re-evaluation of marks?",
            collection="official",
        )

    _timed(
        "official_rag",
        run_rag,
        lambda result: (
            f"status={result.status} response_type={result.response_type} "
            f"citations={json.dumps([{'document': item.source_document, 'page': item.page} for item in result.citations])}"
        ),
    )


if __name__ == "__main__":
    main()
