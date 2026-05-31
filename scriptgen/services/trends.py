"""Trend discovery — Tavily primary, pytrends fallback. Cached to DB."""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from scriptgen.models import TrendSnapshot

logger = logging.getLogger(__name__)

SEED_TERMS = [
    "NASA", "SpaceX", "space", "science", "virus", "outbreak",
    "military", "Pentagon", "FBI", "earthquake", "asteroid",
    "AI artificial intelligence", "nuclear", "climate",
]

TAVILY_TREND_QUERIES = [
    "trending science news today",
    "trending space news today",
    "viral news stories right now",
    "breaking news today",
    "trending on social media today",
    "biggest story on the internet right now",
    "NASA SpaceX latest update",
    "military Pentagon breaking news",
    "FBI investigation breaking news",
    "virus outbreak health news today",
    "AI artificial intelligence news today",
    "climate earthquake natural disaster news",
    "conspiracy theory confirmed news",
    "government secret revealed today",
]

CACHE_HOURS = 24


def refresh_trends():
    """Fetch trends. Tavily first, pytrends fallback. Cached for 24h."""
    cutoff = timezone.now() - timedelta(hours=CACHE_HOURS)
    if TrendSnapshot.objects.filter(captured_at__gte=cutoff).exists():
        logger.info("Trends cached within %dh, skipping refresh", CACHE_HOURS)
        return list(TrendSnapshot.objects.filter(captured_at__gte=cutoff))

    # Try Tavily first
    snapshots = _fetch_tavily_trends()

    # Fall back to pytrends if Tavily got nothing
    if not snapshots:
        logger.info("Tavily trends empty, falling back to pytrends")
        snapshots = _fetch_pytrends()

    logger.info("Captured %d trend snapshots total", len(snapshots))
    return snapshots


def _fetch_tavily_trends():
    """Use Tavily to discover trending topics across Nick's lanes."""
    try:
        from tavily import TavilyClient
    except ImportError:
        logger.error("tavily-python not installed")
        return []

    client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    snapshots = []
    seen_keywords = set()

    for query in TAVILY_TREND_QUERIES:
        try:
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=5,
                include_answer=True,
            )

            for result in response.get("results", []):
                title = result.get("title", "")
                content = result.get("content", "")
                keywords = _extract_keywords(title, content)

                for kw, score in keywords:
                    kw_lower = kw.lower()
                    if kw_lower in seen_keywords:
                        continue
                    seen_keywords.add(kw_lower)

                    snap = TrendSnapshot.objects.create(
                        keyword=kw,
                        score=score,
                        source="tavily",
                    )
                    snapshots.append(snap)

            # Also capture the query-level answer as a trend signal
            answer = response.get("answer", "")
            if answer:
                answer_kws = _extract_keywords(answer, "")
                for kw, score in answer_kws[:2]:
                    kw_lower = kw.lower()
                    if kw_lower in seen_keywords:
                        continue
                    seen_keywords.add(kw_lower)
                    snap = TrendSnapshot.objects.create(
                        keyword=kw,
                        score=score,
                        source="tavily_answer",
                    )
                    snapshots.append(snap)

        except Exception as e:
            logger.warning("Tavily trend search failed for '%s': %s", query, e)
            continue

    logger.info("Tavily trends: captured %d snapshots", len(snapshots))
    return snapshots


def _extract_keywords(title, content):
    """Extract trending keywords from a title/content with a relevance score."""
    text = (title + " " + content).lower()
    keywords = []

    # Authority / institution matches (high value for Nick's content)
    authority_terms = {
        "FBI": 90, "Pentagon": 85, "NASA": 90, "CIA": 85,
        "White House": 80, "Congress": 75, "SpaceX": 85,
        "WHO": 80, "CDC": 75, "DOD": 70, "NSA": 75,
    }
    for term, base_score in authority_terms.items():
        if term.lower() in text:
            keywords.append((term, base_score))

    # Topic matches with scoring
    topic_signals = {
        "outbreak": 80, "pandemic": 85, "virus": 75,
        "earthquake": 70, "asteroid": 75, "meteor": 70,
        "military draft": 90, "nuclear": 80, "classified": 85,
        "missing": 70, "investigation": 65, "conspiracy": 75,
        "alien": 80, "ufo": 80, "deep sea": 65,
        "ai artificial intelligence": 70,
        "space station": 65, "rocket launch": 70,
        "government secret": 85, "surveillance": 70,
        "climate emergency": 65, "wildfire": 60,
    }
    for term, base_score in topic_signals.items():
        if term in text:
            keywords.append((term.title(), base_score))

    # Use the title itself if it's short and punchy (under 8 words)
    title_words = title.split()
    if 2 <= len(title_words) <= 8 and title not in [k for k, _ in keywords]:
        keywords.append((title, 50))

    # Boost if multiple signals appear together
    if len(keywords) > 2:
        keywords = [(kw, min(score + 10, 100)) for kw, score in keywords]

    return keywords


def _fetch_pytrends():
    """Fallback: fetch trending keywords from Google Trends via pytrends."""
    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.warning("pytrends not installed, skipping fallback")
        return []

    snapshots = []
    try:
        pytrends = TrendReq(hl="en-US", tz=300)

        for i in range(0, len(SEED_TERMS), 5):
            batch = SEED_TERMS[i : i + 5]
            try:
                pytrends.build_payload(batch, timeframe="now 7-d")
                interest = pytrends.interest_over_time()

                if not interest.empty:
                    for kw in batch:
                        if kw in interest.columns:
                            score = float(interest[kw].mean())
                            snap = TrendSnapshot.objects.create(
                                keyword=kw, score=score, source="pytrends"
                            )
                            snapshots.append(snap)

                related = pytrends.related_queries()
                for kw in batch:
                    if kw in related and related[kw]["rising"] is not None:
                        for _, row in related[kw]["rising"].head(3).iterrows():
                            snap = TrendSnapshot.objects.create(
                                keyword=row["query"],
                                score=float(row.get("value", 50)),
                                source="pytrends_related",
                            )
                            snapshots.append(snap)
            except Exception as e:
                logger.warning("pytrends batch failed for %s: %s", batch, e)
                continue

        logger.info("pytrends fallback: captured %d snapshots", len(snapshots))
    except Exception as e:
        logger.warning("pytrends failed entirely: %s", e)

    return snapshots


def get_trending_keywords():
    """Get current trending keywords from cache."""
    cutoff = timezone.now() - timedelta(hours=CACHE_HOURS)
    return list(
        TrendSnapshot.objects.filter(captured_at__gte=cutoff)
        .order_by("-score")
        .values_list("keyword", flat=True)[:20]
    )
