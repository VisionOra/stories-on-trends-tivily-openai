#!/usr/bin/env python3
"""
Script verification tool for Nick Jackson's short-form video scripts.
Checks ALL rules from the skill file before upload.
Exit code 0 = pass, 1 = fail.
Prints JSON with results.
"""

import sys
import re
import json


def count_words(text: str) -> int:
    return len(text.split())


def split_sentences(text: str) -> list[str]:
    """Split on sentence-ending punctuation followed by whitespace or newline."""
    sentences = re.split(r'(?<=[.?!])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def check_contractions(text: str) -> list[str]:
    """Find uncontracted negatives that should be contracted."""
    bad = []
    patterns = [
        ("do not", "don't"), ("does not", "doesn't"), ("did not", "didn't"),
        ("cannot", "can't"), ("can not", "can't"),
        ("is not", "isn't"), ("are not", "aren't"), ("was not", "wasn't"),
        ("were not", "weren't"), ("has not", "hasn't"), ("have not", "haven't"),
        ("will not", "won't"), ("would not", "wouldn't"), ("could not", "couldn't"),
        ("should not", "shouldn't"),
    ]
    lower = text.lower()
    for uncontracted, contracted in patterns:
        if uncontracted in lower:
            bad.append(f"'{uncontracted}' → should be '{contracted}'")
    return bad


def verify(hook: str, text: str, body: str, outro: str, story_type: str = "daily") -> dict:
    errors = []
    warnings = []

    # --- HOOK ---
    hook_words = count_words(hook)
    if story_type == "daily":
        if hook_words > 15:
            errors.append(f"HOOK: {hook_words} words (max 15 for daily)")
        elif hook_words > 10:
            warnings.append(f"HOOK: {hook_words} words (under 10 is ideal for daily)")
    else:  # evergreen
        if hook_words > 25:
            errors.append(f"HOOK: {hook_words} words (max 25 for evergreen)")
        elif hook_words < 15:
            warnings.append(f"HOOK: {hook_words} words (evergreen hooks are usually 15-25)")

    if hook.endswith("!"):
        errors.append("HOOK: ends with exclamation mark (use period or ellipsis)")

    # --- TEXT ---
    if not text:
        errors.append("TEXT: missing")

    # --- BODY ---
    body_words = count_words(body)
    if body_words < 165:
        errors.append(f"BODY: {body_words} words (minimum 165)")
    elif body_words > 176:
        errors.append(f"BODY: {body_words} words (maximum 176)")

    sentences = split_sentences(body)
    for i, s in enumerate(sentences):
        s_words = count_words(s)
        if s_words > 25:
            errors.append(f"BODY S{i+1}: {s_words} words (max 25) — \"{s[:60]}...\"")

    contraction_issues = check_contractions(body)
    for issue in contraction_issues:
        errors.append(f"CONTRACTION: {issue}")

    # Check hook contractions too
    hook_contraction_issues = check_contractions(hook)
    for issue in hook_contraction_issues:
        errors.append(f"HOOK CONTRACTION: {issue}")

    # --- OUTRO ---
    if not outro:
        errors.append("OUTRO: missing")
    outro_words = count_words(outro)
    if outro_words > 20:
        warnings.append(f"OUTRO: {outro_words} words (keep it punchy)")

    # --- FIRST SENTENCE CHECK ---
    if sentences:
        first = sentences[0].lower()
        hook_lower = hook.lower()
        # Check if first sentence just repeats the hook
        if first.startswith(hook_lower[:30]):
            errors.append("BODY: first sentence repeats the hook (must be a NEW fact)")

    passed = len(errors) == 0

    return {
        "passed": passed,
        "body_words": body_words,
        "hook_words": hook_words,
        "sentence_count": len(sentences),
        "errors": errors,
        "warnings": warnings,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: verify-script.py '<json>'")
        print('  JSON: {"hook": "...", "text": "...", "body": "...", "outro": "...", "type": "daily|evergreen"}')
        sys.exit(1)

    data = json.loads(sys.argv[1])
    result = verify(
        hook=data.get("hook", ""),
        text=data.get("text", ""),
        body=data.get("body", ""),
        outro=data.get("outro", ""),
        story_type=data.get("type", "daily"),
    )

    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
