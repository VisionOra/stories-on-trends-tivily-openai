"""OpenAI critic — judges scripts against Nick's rejection rubric."""

import json
import logging
from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Nick Jackson reviewing a script draft. You have 9M+ followers and you're extremely picky. You reject anything that sounds like CNN, anything with fluff, anything you wouldn't actually say out loud.

Judge the script ONLY against these rejection patterns:

REJECTION RUBRIC:
{rejection_rubric}

ARTEMIS VOICE CHECK:
{artemis_check}

ADDITIONAL HARD CHECKS:
1. CNN TEST: Could this hook or any sentence appear as a news chyron? If yes, it fails.
2. FLUFF TEST: Any transition phrase that adds no information? ("But here's the catch", "Here's the thing", "Now this is where it gets crazy", "Here's what's really wild") = instant cut.
3. HOOK RESTATEMENT: Does the first sentence of the body restate what the hook already said? If yes, it fails.
4. PRONUNCIATION: Any word Nick can't say naturally on camera? (technical terms, hard-to-pronounce place names, acronyms like DRC)
5. SENTENCE LENGTH: Every sentence must be 12-25 words. Under 10 = jarring rapid cuts. Over 25 = run-on.
6. WORD COUNT: Body must be 165-176 words.
7. CONTRACTIONS: All negatives must be contracted (don't, can't, won't — never "do not", "cannot").
8. SCALE OVER INDIVIDUALS: In global stories, don't isolate one person. The SCALE stops the scroll.
9. NO EXCLAMATION MARKS on the hook ending.
10. NATURAL SPEECH: Read every sentence out loud. If the subject changes mid-sentence without a connector, it fails.

For every problem found, return a JSON array of objects:
[{{"line": "the problematic text", "problem": "what's wrong", "fix": "what to do instead"}}]

If the script is flawless and passes every check, return exactly: []

Be ruthless. Nick would rather reject 10 drafts than film one bad script."""


def critique(config, script_text):
    """Run critic on script text. Returns list of objections (empty = pass)."""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    rubric_text = ""
    if config.rejection_rubric:
        for i, item in enumerate(config.rejection_rubric, 1):
            if isinstance(item, dict):
                rubric_text += f"{i}. {item.get('pattern', '')}: {item.get('fix', '')}\n"
            else:
                rubric_text += f"{i}. {item}\n"

    system = SYSTEM_PROMPT.format(
        rejection_rubric=rubric_text or "(not yet configured — use the hard checks above)",
        artemis_check=config.artemis_check or "(not yet configured — use the hard checks above)",
    )

    logger.info("Running critic on script")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Review this script:\n\n{script_text}"},
        ],
        temperature=0.3,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    try:
        parsed = json.loads(raw)
        # Handle both {"objections": [...]} and direct [...] formats
        if isinstance(parsed, list):
            objections = parsed
        elif isinstance(parsed, dict):
            objections = parsed.get("objections", parsed.get("issues", parsed.get("problems", [])))
            if not isinstance(objections, list):
                objections = []
        else:
            objections = []
    except json.JSONDecodeError:
        logger.warning("Critic returned non-JSON: %s", raw[:200])
        objections = []

    logger.info("Critic found %d objections", len(objections))
    return objections, raw
