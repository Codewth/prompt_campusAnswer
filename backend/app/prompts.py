from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def get_prompt(version: str) -> str:
    path = PROMPT_DIR / version / "prompt.txt"
    if not path.exists():
        path = PROMPT_DIR / "final" / "prompt.txt"
    return path.read_text(encoding="utf-8")
