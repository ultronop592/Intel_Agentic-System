import difflib
import hashlib


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_diff(old_text: str, new_text: str) -> str:
    diff_lines = difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        lineterm="",
    )
    filtered = [line for line in diff_lines if line.startswith("+") or line.startswith("-")]
    if not filtered:
        return "No significant changes detected."
    return "\n".join(filtered)[:2000]
