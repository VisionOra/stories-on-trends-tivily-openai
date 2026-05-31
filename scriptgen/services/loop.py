"""Writer-critic-verifier orchestration loop."""

import json
import logging

from scriptgen.models import Script, RevisionCycle, SkillConfig
from scriptgen.services.writer import (
    generate_draft, parse_script_output,
    rewrite_from_critique, rewrite_from_verification,
)
from scriptgen.services.critic import critique
from scriptgen.services.verifier import verify_script

logger = logging.getLogger(__name__)

MAX_CRITIC_CYCLES = 5
MAX_VERIFY_RETRIES = 5


def _format_script_text(parsed):
    return (
        f"HOOK: {parsed['hook']}\n"
        f"TEXT: {parsed['text_line']}\n"
        f"BODY: {parsed['body']}\n"
        f"OUTRO: {parsed['outro']}"
    )


def _save_script(script, parsed, status="draft"):
    script.hook = parsed["hook"]
    script.text_line = parsed["text_line"]
    script.body = parsed["body"]
    script.outro = parsed["outro"]
    script.content = _format_script_text(parsed)
    script.word_count = len(parsed["body"].split())
    script.status = status
    script.save()


def run_loop(story, research_brief, run=None):
    """Run the full writer→critic→verify loop. Returns (script, verification)."""
    config = SkillConfig.load()

    # Generate initial draft
    if run:
        run.append_log(f"Generating draft for: {story.title}")

    parsed, raw = generate_draft(config, research_brief)
    script = Script.objects.create(
        story=story,
        hook=parsed["hook"],
        text_line=parsed["text_line"],
        body=parsed["body"],
        outro=parsed["outro"],
        content=_format_script_text(parsed),
        word_count=len(parsed["body"].split()),
        status="draft",
    )

    # Writer ↔ Critic loop
    for cycle_no in range(1, MAX_CRITIC_CYCLES + 1):
        if run:
            run.append_log(f"  Critic cycle {cycle_no}/{MAX_CRITIC_CYCLES}")

        script_text = _format_script_text(parsed)
        objections, critic_raw = critique(config, script_text)

        RevisionCycle.objects.create(
            script=script,
            cycle_no=cycle_no,
            critique=objections,
            changelog=f"Cycle {cycle_no}: {len(objections)} objections found",
        )

        if not objections:
            logger.info("Critic passed on cycle %d", cycle_no)
            if run:
                run.append_log(f"  Critic passed on cycle {cycle_no}")
            break

        logger.info("Cycle %d: %d objections, rewriting", cycle_no, len(objections))
        objections_text = json.dumps(objections, indent=2)
        parsed, raw = rewrite_from_critique(
            config, research_brief, script_text, objections_text
        )
        _save_script(script, parsed, status="revision")

    # Verification loop
    for attempt in range(1, MAX_VERIFY_RETRIES + 1):
        if run:
            run.append_log(f"  Verification attempt {attempt}/{MAX_VERIFY_RETRIES}")

        vr = verify_script(script)

        if vr.passed:
            logger.info("Verification passed on attempt %d", attempt)
            script.status = "final"
            script.is_final = True
            script.save()
            if run:
                run.append_log(f"  Verification PASSED ({vr.body_words} body words)")
            return script, vr

        if attempt < MAX_VERIFY_RETRIES:
            logger.info("Verification failed, fixing: %s", vr.errors)
            errors_text = "\n".join(vr.errors)
            script_text = _format_script_text(parsed)
            parsed, raw = rewrite_from_verification(
                config, research_brief, script_text, errors_text
            )
            _save_script(script, parsed, status="revision")

    # Failed all verification attempts
    logger.warning("Script failed verification after %d attempts", MAX_VERIFY_RETRIES)
    if run:
        run.append_log(f"  Verification FAILED after {MAX_VERIFY_RETRIES} attempts")
    script.status = "draft"
    script.save()
    return script, vr
