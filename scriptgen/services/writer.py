"""OpenAI script writer — generates scripts in Nick Jackson's voice."""

import logging
from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You write short-form video scripts for Nick Jackson, a creator with 9M+ followers who posts science/space/news videos on TikTok. He films word-for-word off a teleprompter. Your script must sound like a guy telling his friend something insane on FaceTime — NEVER like a news anchor or CNN report.

HARD RULES — zero deviation:
{rules_text}

WORD COUNT: The script BODY must be EXACTLY {min_words}–{max_words} words. NOT the hook, NOT the outro — ONLY the BODY paragraph(s). Count carefully. Aim for 170 words. This is a HARD requirement — scripts outside this range are rejected automatically.
SENTENCES: Every sentence in the body must be {min_sentence}–{max_sentence} words. Every period = a camera cut.
CONTRACTIONS: Always use contractions (don't, can't, won't — never "do not", "cannot", "will not").

BANNED WORDS — never use any of these:
{banned_words}

STRUCTURE — output EXACTLY this format:
HOOK: [the scroll-stopping opening — 10-15 words for daily, 15-25 for evergreen]
TEXT: [2-4 words + emoji for on-screen text]
BODY: [the script body, {min_words}-{max_words} words]
OUTRO: [punchy closer or CTA, under 20 words]

HOOK RULES:
- Must sound like something Nick would actually say out loud to a friend
- No CNN headlines, no news anchor energy
- No exclamation marks at the end
- Name-drops must be universally recognized (FBI, NASA, Pentagon = good; MIT, DARPA = bad)
- Never claim "nobody is talking about this" if it's a big story
- Must roll off the tongue naturally — read it out loud

BODY RULES:
- First sentence must be NEW information — never restate the hook
- No fluff transitions: "But here's the catch", "Here's the thing", "Now this is where it gets crazy" — go straight to the fact
- Don't isolate individuals in global stories — scale is what stops the scroll
- No unpronounceable words (Bundibugyo, Johannesburg, Tenerife = bad; Congo, Spain = good)
- Don't bring up facts you immediately undercut ("there's a $250K fine... but nobody's ever been charged")
- Connect stories to trending events when possible — the connection is the engagement multiplier
- Brand integrations (Kalshi etc.) must read as data points, not ad breaks

OUTRO RULES:
- Factually defensible, not sarcastic
- CTA to follow/add preferred over dramatic closers

REACTION VOCABULARY (use sparingly, naturally):
HELLO? / OKAYYY / SO THAT'S INSANE? / DUDE

{few_shot_section}

Write a script for this story using ONLY these verified facts:
{research_brief}

Output the script ONLY in the exact format above. Nothing else."""

REWRITE_PROMPT = """The critic found these problems with your script:

{objections}

Fix EVERY objection while keeping all rules intact. Output the corrected script in the exact same format:
HOOK: ...
TEXT: ...
BODY: ...
OUTRO: ...

Output the script ONLY. Nothing else."""

VERIFY_FIX_PROMPT = """The verification script found these errors:

{errors}

The current body has {current_word_count} words. The REQUIRED range is 165-176 words.
{word_count_instruction}

Fix EVERY error while keeping all rules intact. Output the corrected script in the exact same format:
HOOK: ...
TEXT: ...
BODY: ...
OUTRO: ...

Output the script ONLY. Nothing else."""


def _get_client():
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _build_system_prompt(config, research_brief_text):
    few_shot = ""
    if config.few_shot_scripts.strip():
        few_shot = (
            "REFERENCE SCRIPTS — match this voice exactly:\n"
            + config.few_shot_scripts
        )

    return SYSTEM_PROMPT.format(
        rules_text=config.rules_text,
        min_words=config.min_words,
        max_words=config.max_words,
        min_sentence=config.min_sentence_words,
        max_sentence=config.max_sentence_words,
        banned_words=", ".join(config.banned_words) if config.banned_words else "(none configured)",
        few_shot_section=few_shot,
        research_brief=research_brief_text,
    )


def _format_research_brief(brief):
    parts = [f"STORY: {brief.story.title}", f"SUMMARY: {brief.story.summary}"]
    if brief.facts:
        parts.append("FACTS:\n" + "\n".join(f"- {f}" for f in brief.facts))
    if brief.numbers:
        parts.append("KEY NUMBERS:\n" + "\n".join(f"- {n}" for n in brief.numbers))
    if brief.orgs:
        parts.append("ORGS/PEOPLE:\n" + "\n".join(f"- {o}" for o in brief.orgs))
    if brief.hook_angles:
        parts.append("HOOK ANGLES:\n" + "\n".join(f"- {a}" for a in brief.hook_angles))
    if brief.sources:
        parts.append("SOURCES:\n" + "\n".join(f"- {s}" for s in brief.sources))
    return "\n\n".join(parts)


def parse_script_output(text):
    """Parse HOOK/TEXT/BODY/OUTRO from model output."""
    result = {"hook": "", "text_line": "", "body": "", "outro": ""}
    lines = text.strip().split("\n")
    current_key = None
    current_lines = []

    key_map = {
        "HOOK:": "hook",
        "TEXT:": "text_line",
        "BODY:": "body",
        "OUTRO:": "outro",
    }

    for line in lines:
        stripped = line.strip()
        matched = False
        for prefix, key in key_map.items():
            if stripped.upper().startswith(prefix):
                if current_key is not None:
                    result[current_key] = "\n".join(current_lines).strip()
                current_key = key
                current_lines = [stripped[len(prefix):].strip()]
                matched = True
                break
        if not matched and current_key is not None:
            current_lines.append(line)

    if current_key is not None:
        result[current_key] = "\n".join(current_lines).strip()

    return result


def generate_draft(config, research_brief):
    """Generate initial script draft from research brief."""
    client = _get_client()
    brief_text = _format_research_brief(research_brief)
    system = _build_system_prompt(config, brief_text)

    logger.info("Generating draft for: %s", research_brief.story.title)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Write the script for: {research_brief.story.title}"},
        ],
        temperature=0.7,
        max_tokens=1000,
    )

    raw = response.choices[0].message.content
    parsed = parse_script_output(raw)
    logger.info("Draft generated, body word count: %d", len(parsed["body"].split()))
    return parsed, raw


def rewrite_from_critique(config, research_brief, current_script_text, objections_text):
    """Rewrite script based on critic objections."""
    client = _get_client()
    brief_text = _format_research_brief(research_brief)
    system = _build_system_prompt(config, brief_text)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Here is the current script:\n\n{current_script_text}"},
            {"role": "assistant", "content": current_script_text},
            {"role": "user", "content": REWRITE_PROMPT.format(objections=objections_text)},
        ],
        temperature=0.6,
        max_tokens=1000,
    )

    raw = response.choices[0].message.content
    return parse_script_output(raw), raw


def rewrite_from_verification(config, research_brief, current_script_text, errors_text):
    """Rewrite script to fix verification errors."""
    client = _get_client()
    brief_text = _format_research_brief(research_brief)
    system = _build_system_prompt(config, brief_text)

    # Calculate current body word count for the prompt
    parsed = parse_script_output(current_script_text)
    current_wc = len(parsed["body"].split()) if parsed["body"] else 0
    words_needed = max(0, config.min_words - current_wc)
    if current_wc < config.min_words:
        wc_instruction = f"You need to ADD at least {words_needed} more words to the body. Expand facts, add details, add another sentence."
    elif current_wc > config.max_words:
        wc_instruction = f"You need to CUT {current_wc - config.max_words} words from the body. Tighten sentences, remove redundancy."
    else:
        wc_instruction = "Word count is in range. Keep it there."

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Here is the current script:\n\n{current_script_text}"},
            {"role": "assistant", "content": current_script_text},
            {"role": "user", "content": VERIFY_FIX_PROMPT.format(
                errors=errors_text,
                current_word_count=current_wc,
                word_count_instruction=wc_instruction,
            )},
        ],
        temperature=0.5,
        max_tokens=1000,
    )

    raw = response.choices[0].message.content
    return parse_script_output(raw), raw
