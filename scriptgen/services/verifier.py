"""Run Nick's verify-script.py via subprocess."""

import json
import logging
import subprocess
import sys
from pathlib import Path

from scriptgen.models import VerificationResult

logger = logging.getLogger(__name__)

VERIFY_SCRIPT = Path(__file__).resolve().parent.parent / "skill" / "verify.py"


def verify_script(script):
    """Run verification on a Script model instance. Returns VerificationResult."""
    script_json = json.dumps({
        "hook": script.hook,
        "text": script.text_line,
        "body": script.body,
        "outro": script.outro,
        "type": "daily",
    })

    try:
        result = subprocess.run(
            [sys.executable, str(VERIFY_SCRIPT), script_json],
            capture_output=True,
            text=True,
            timeout=30,
        )
        raw_output = result.stdout.strip()
        parsed = json.loads(raw_output) if raw_output else {}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        logger.error("Verification subprocess failed: %s", e)
        parsed = {
            "passed": False,
            "body_words": 0,
            "hook_words": 0,
            "sentence_count": 0,
            "errors": [f"Verification script error: {e}"],
            "warnings": [],
        }
        raw_output = str(e)

    vr, _ = VerificationResult.objects.update_or_create(
        script=script,
        defaults={
            "passed": parsed.get("passed", False),
            "body_words": parsed.get("body_words", 0),
            "hook_words": parsed.get("hook_words", 0),
            "sentence_count": parsed.get("sentence_count", 0),
            "errors": parsed.get("errors", []),
            "warnings": parsed.get("warnings", []),
            "raw_output": raw_output,
        },
    )

    logger.info(
        "Verification %s: %d body words, %d errors",
        "PASSED" if vr.passed else "FAILED",
        vr.body_words,
        len(vr.errors),
    )
    return vr
