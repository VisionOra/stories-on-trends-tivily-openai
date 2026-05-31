"""Tavily story discovery — find viral-worthy stories across Nick's lanes."""

import logging
from django.conf import settings
from django.utils import timezone

from scriptgen.models import Story, TrendSnapshot

logger = logging.getLogger(__name__)

SEARCH_QUERIES = [
    "breaking science discovery today",
    "NASA space news this week",
    "SpaceX launch update",
    "new virus outbreak 2024",
    "military news Pentagon",
    "FBI investigation breaking",
    "earthquake today major",
    "asteroid near Earth",
    "AI breakthrough news",
    "nuclear news today",
    "conspiracy theory confirmed",
    "government secret revealed",
    "mysterious disappearance scientist",
    "extreme weather event",
    "ocean discovery deep sea",
]


def discover_stories(max_stories=20):
    """Search Tavily for recent stories across Nick's content lanes."""
    try:
        from tavily import TavilyClient
    except ImportError:
        logger.error("tavily-python not installed")
        return []

    client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    candidates = []

    for query in SEARCH_QUERIES:
        try:
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=3,
                include_raw_content=False,
                include_answer=True,
            )

            for result in response.get("results", []):
                title = result.get("title", "")
                url = result.get("url", "")

                # Skip duplicates
                if Story.objects.filter(source_url=url).exists():
                    continue

                candidates.append({
                    "title": title,
                    "summary": result.get("content", "")[:500],
                    "source_url": url,
                    "topic": _classify_topic(query),
                    "raw_facts": [result.get("content", "")],
                    "query": query,
                })
        except Exception as e:
            logger.warning("Tavily search failed for '%s': %s", query, e)
            continue

    # Score candidates against trends
    trending_keywords = list(
        TrendSnapshot.objects.order_by("-score").values_list("keyword", flat=True)[:30]
    )
    scored = _score_candidates(candidates, trending_keywords)

    # Create Story objects for top candidates
    stories = []
    for c in scored[:max_stories]:
        story = Story.objects.create(
            title=c["title"],
            summary=c["summary"],
            source_url=c["source_url"],
            topic=c["topic"],
            trend_score=c["trend_score"],
            virality_notes=c.get("virality_notes", ""),
            raw_facts=c["raw_facts"],
            status="candidate",
        )
        stories.append(story)

    logger.info("Discovered %d candidate stories", len(stories))
    return stories


def _classify_topic(query):
    q = query.lower()
    if any(w in q for w in ["nasa", "space", "asteroid", "spacex"]):
        return "space"
    if any(w in q for w in ["science", "discovery", "ocean", "deep sea"]):
        return "science"
    if any(w in q for w in ["virus", "outbreak", "weather"]):
        return "health"
    return "news"


def _score_candidates(candidates, trending_keywords):
    """Score candidates by trend relevance and virality potential."""
    for c in candidates:
        score = 0
        text = (c["title"] + " " + c["summary"]).lower()

        # Trend keyword matches
        for kw in trending_keywords:
            if kw.lower() in text:
                score += 10

        # Virality signals
        virality_signals = []
        if any(w in text for w in ["first time", "never before", "unprecedented"]):
            virality_signals.append("novelty")
            score += 15
        if any(w in text for w in ["million", "billion", "trillion"]):
            virality_signals.append("big numbers")
            score += 10
        if any(w in text for w in ["fbi", "pentagon", "nasa", "cia", "government"]):
            virality_signals.append("authority name-drop")
            score += 12
        if any(w in text for w in ["secret", "classified", "hidden", "conspiracy"]):
            virality_signals.append("mystery/secret")
            score += 15
        if any(w in text for w in ["ban", "illegal", "warning", "emergency"]):
            virality_signals.append("urgency")
            score += 10

        c["trend_score"] = score
        c["virality_notes"] = ", ".join(virality_signals) if virality_signals else "general interest"

    return sorted(candidates, key=lambda x: x["trend_score"], reverse=True)


def select_top_stories(count=5):
    """Select top N candidate stories for script generation."""
    stories = Story.objects.filter(status="candidate").order_by("-trend_score")[:count]
    for story in stories:
        story.status = "selected"
        story.save()
    logger.info("Selected %d stories for generation", len(stories))
    return list(stories)
