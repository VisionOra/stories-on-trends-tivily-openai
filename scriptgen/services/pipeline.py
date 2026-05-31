"""Full pipeline orchestrator — runs the complete morning generation."""

import logging
from datetime import date

from django.utils import timezone

from scriptgen.models import GenerationRun
from scriptgen.services.trends import refresh_trends
from scriptgen.services.discovery import discover_stories, select_top_stories
from scriptgen.services.research import deep_research
from scriptgen.services.loop import run_loop

logger = logging.getLogger(__name__)


def run(count=5):
    """Execute the full pipeline: trends → discovery → research → write → verify."""
    today = date.today()

    gen_run = GenerationRun.objects.create(
        run_date=today,
        status="running",
        num_requested=count,
    )
    gen_run.append_log(f"Starting generation run for {today}, requesting {count} scripts")

    try:
        # Step 1: Refresh trends
        gen_run.append_log("Step 1: Refreshing trends...")
        trends = refresh_trends()
        gen_run.append_log(f"  Got {len(trends)} trend snapshots")

        # Step 2: Discover stories
        gen_run.append_log("Step 2: Discovering stories...")
        candidates = discover_stories(max_stories=count * 3)
        gen_run.append_log(f"  Found {len(candidates)} candidate stories")

        # Step 3: Select top stories
        gen_run.append_log("Step 3: Selecting top stories...")
        selected = select_top_stories(count=count)
        gen_run.append_log(f"  Selected {len(selected)} stories")

        if not selected:
            gen_run.append_log("ERROR: No stories selected, aborting")
            gen_run.status = "failed"
            gen_run.finished_at = timezone.now()
            gen_run.save()
            return gen_run

        # Step 4: For each story: research → write → verify
        num_passed = 0
        for i, story in enumerate(selected, 1):
            gen_run.append_log(f"\nStory {i}/{len(selected)}: {story.title}")

            try:
                # Deep research
                gen_run.append_log("  Researching...")
                brief = deep_research(story)
                gen_run.append_log(f"  Research complete: {len(brief.facts)} facts")

                # Writer → Critic → Verifier loop
                gen_run.append_log("  Running writer/critic/verifier loop...")
                script, verification = run_loop(story, brief, run=gen_run)

                gen_run.scripts.add(script)

                if verification.passed:
                    num_passed += 1
                    story.status = "used"
                    story.save()
                    gen_run.append_log(f"  DONE — script PASSED verification")
                else:
                    gen_run.append_log(f"  DONE — script FAILED verification")

            except Exception as e:
                logger.exception("Failed to process story: %s", story.title)
                gen_run.append_log(f"  ERROR: {e}")

        # Finalize
        gen_run.num_passed = num_passed
        gen_run.status = "completed"
        gen_run.finished_at = timezone.now()
        gen_run.save()
        gen_run.append_log(
            f"\nRun complete: {num_passed}/{count} scripts passed verification"
        )

    except Exception as e:
        logger.exception("Pipeline failed")
        gen_run.append_log(f"\nFATAL ERROR: {e}")
        gen_run.status = "failed"
        gen_run.finished_at = timezone.now()
        gen_run.save()

    return gen_run
