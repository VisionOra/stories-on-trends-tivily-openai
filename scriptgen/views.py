from datetime import date, timedelta

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import GenerationRun, Script, Story, TrendSnapshot


def dashboard(request):
    today = date.today()
    run = GenerationRun.objects.filter(run_date=today).order_by("-started_at").first()
    scripts = []
    if run:
        scripts = run.scripts.filter(is_final=True).select_related(
            "story", "verification"
        )
    recent_runs = GenerationRun.objects.all()[:7]
    return render(
        request,
        "scriptgen/dashboard.html",
        {"run": run, "scripts": scripts, "recent_runs": recent_runs, "today": today},
    )


def script_detail(request, pk):
    script = get_object_or_404(
        Script.objects.select_related("story", "verification"), pk=pk
    )
    revisions = script.revisions.all()
    research = getattr(script.story, "research", None)
    return render(
        request,
        "scriptgen/script_detail.html",
        {"script": script, "revisions": revisions, "research": research},
    )


def stories(request):
    story_list = Story.objects.all()[:50]
    return render(request, "scriptgen/stories.html", {"stories": story_list})


def story_detail_json(request, pk):
    story = get_object_or_404(Story, pk=pk)
    research = None
    try:
        brief = story.research
        research = {
            "facts": brief.facts,
            "numbers": brief.numbers,
            "orgs": brief.orgs,
            "hook_angles": brief.hook_angles,
            "sources": brief.sources,
        }
    except Exception:
        pass

    scripts_data = []
    for s in story.scripts.all().order_by("-created_at"):
        scripts_data.append({
            "id": s.pk,
            "status": s.get_status_display(),
            "is_final": s.is_final,
            "word_count": s.word_count,
        })

    return JsonResponse({
        "id": story.pk,
        "title": story.title,
        "summary": story.summary,
        "source_url": story.source_url,
        "topic": story.topic,
        "trend_score": story.trend_score,
        "virality_notes": story.virality_notes,
        "status": story.get_status_display(),
        "raw_facts": story.raw_facts,
        "discovered_at": story.discovered_at.strftime("%b %d, %Y %H:%M"),
        "research": research,
        "scripts": scripts_data,
    })


@require_POST
def save_note(request, pk):
    script = get_object_or_404(Script, pk=pk)
    script.nick_notes = request.POST.get("nick_notes", "")
    script.save(update_fields=["nick_notes"])
    return redirect("script_detail", pk=pk)


@require_POST
def regenerate(request, pk):
    script = get_object_or_404(Script.objects.select_related("story"), pk=pk)
    story = script.story

    try:
        from .services.research import deep_research
        from .services.loop import run_loop

        brief = deep_research(story)
        new_script, vr = run_loop(story, brief)
        return redirect("script_detail", pk=new_script.pk)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@ensure_csrf_cookie
def trends(request):
    cutoff = timezone.now() - timedelta(hours=24)
    current_trends = TrendSnapshot.objects.filter(captured_at__gte=cutoff).order_by("-score")
    stale_trends = TrendSnapshot.objects.filter(captured_at__lt=cutoff).order_by("-score")[:30]

    last_fetch = TrendSnapshot.objects.order_by("-captured_at").first()
    last_fetch_at = last_fetch.captured_at if last_fetch else None
    is_stale = last_fetch_at is None or last_fetch_at < cutoff

    # Group: main trends (tavily or pytrends seed) vs related/secondary
    main_sources = ["tavily", "pytrends"]
    secondary_sources = ["tavily_answer", "pytrends_related"]
    main_trends = current_trends.filter(source__in=main_sources)
    related_trends = current_trends.filter(source__in=secondary_sources)

    # Find the max score for relative bar widths
    max_score = main_trends.first().score if main_trends.exists() else 1

    # Detect which provider was used
    sources_used = set(current_trends.values_list("source", flat=True).distinct())
    provider = "Tavily" if any(s.startswith("tavily") for s in sources_used) else "pytrends" if sources_used else "none"

    return render(
        request,
        "scriptgen/trends.html",
        {
            "main_trends": main_trends,
            "related_trends": related_trends,
            "stale_trends": stale_trends,
            "last_fetch_at": last_fetch_at,
            "is_stale": is_stale,
            "total_count": current_trends.count(),
            "max_score": max_score,
            "provider": provider,
        },
    )


@require_POST
def refresh_trends_view(request):
    from .services.trends import refresh_trends

    # Clear old trends before refreshing
    cutoff = timezone.now() - timedelta(hours=24)
    TrendSnapshot.objects.filter(captured_at__lt=cutoff).delete()

    trends = refresh_trends()
    return JsonResponse({
        "ok": True,
        "count": len(trends),
    })


@require_POST
def generate_from_trend(request, pk):
    """Take a trend keyword and discover + generate a story from it."""
    trend = get_object_or_404(TrendSnapshot, pk=pk)

    try:
        from .services.discovery import discover_stories, _classify_topic, _score_candidates
        from .services.research import deep_research
        from .services.loop import run_loop
        from django.conf import settings
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        response = client.search(
            query=f"{trend.keyword} latest news",
            search_depth="basic",
            max_results=5,
            include_answer=True,
        )

        # Pick the best result
        results = response.get("results", [])
        if not results:
            return JsonResponse({"error": "No stories found for this trend"}, status=404)

        best = results[0]
        story = Story.objects.create(
            title=best.get("title", trend.keyword),
            summary=best.get("content", "")[:500],
            source_url=best.get("url", ""),
            topic=_classify_topic(trend.keyword),
            trend_score=trend.score,
            virality_notes=f"Generated from trend: {trend.keyword}",
            raw_facts=[r.get("content", "") for r in results],
            status="selected",
        )

        brief = deep_research(story)
        script, vr = run_loop(story, brief)

        story.status = "used" if vr.passed else "selected"
        story.save()

        return JsonResponse({
            "ok": True,
            "story_id": story.pk,
            "script_id": script.pk,
            "passed": vr.passed,
            "redirect": f"/script/{script.pk}/",
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
