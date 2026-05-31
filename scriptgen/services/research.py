"""Tavily deep research — build a ResearchBrief for a story."""

import json
import logging
from django.conf import settings
from openai import OpenAI

from scriptgen.models import ResearchBrief

logger = logging.getLogger(__name__)


def deep_research(story):
    """Deep research a story via Tavily, then structure with OpenAI."""
    # Check if brief already exists
    try:
        return story.research
    except ResearchBrief.DoesNotExist:
        pass

    try:
        from tavily import TavilyClient
    except ImportError:
        logger.error("tavily-python not installed")
        return _create_fallback_brief(story)

    client = TavilyClient(api_key=settings.TAVILY_API_KEY)

    # Deep search with multiple angles
    all_content = list(story.raw_facts) if story.raw_facts else []

    search_queries = [
        story.title,
        f"{story.title} latest update details",
        f"{story.title} numbers statistics facts",
    ]

    for query in search_queries:
        try:
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=5,
                include_raw_content=True,
                include_answer=True,
            )
            if response.get("answer"):
                all_content.append(response["answer"])
            for r in response.get("results", []):
                content = r.get("raw_content", r.get("content", ""))
                if content:
                    all_content.append(content[:2000])
        except Exception as e:
            logger.warning("Deep research search failed for '%s': %s", query, e)

    # Use OpenAI to structure the research into a brief
    brief_data = _structure_with_openai(story.title, all_content)

    brief = ResearchBrief.objects.create(
        story=story,
        facts=brief_data.get("facts", []),
        numbers=brief_data.get("numbers", []),
        orgs=brief_data.get("orgs", []),
        hook_angles=brief_data.get("hook_angles", []),
        sources=brief_data.get("sources", []),
    )

    logger.info("Research brief created for: %s", story.title)
    return brief


def _structure_with_openai(title, raw_contents):
    """Use OpenAI to extract structured data from raw research content."""
    combined = "\n\n---\n\n".join(raw_contents[:10])[:8000]

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract structured research data from raw content for a short-form "
                    "video script. Return ONLY valid JSON with these keys:\n"
                    '- "facts": list of 8-15 verified, specific facts (no vague claims)\n'
                    '- "numbers": list of specific numbers/statistics mentioned\n'
                    '- "orgs": list of organizations and people involved\n'
                    '- "hook_angles": list of 3-5 possible hook angles (what makes this story insane/viral)\n'
                    '- "sources": list of source URLs or publication names\n'
                    "Focus on facts that are FILMABLE — concrete, specific, surprising. "
                    "Skip boring policy details. Prioritize what would make someone stop scrolling."
                ),
            },
            {
                "role": "user",
                "content": f"Story: {title}\n\nRaw research:\n{combined}",
            },
        ],
        temperature=0.2,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )

    try:
        return json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, IndexError):
        logger.warning("Failed to parse structured research")
        return {"facts": [], "numbers": [], "orgs": [], "hook_angles": [], "sources": []}


def _create_fallback_brief(story):
    """Create a minimal brief from existing story data when Tavily is unavailable."""
    return ResearchBrief.objects.create(
        story=story,
        facts=story.raw_facts or [story.summary],
        numbers=[],
        orgs=[],
        hook_angles=[story.title],
        sources=[story.source_url] if story.source_url else [],
    )
