from django.db import models


class SkillConfig(models.Model):
    """Singleton config: Nick's rules, banned words, rubric. Edit via admin."""

    rules_text = models.TextField(
        help_text="Full rules extracted from skill file"
    )
    banned_words = models.JSONField(
        default=list, help_text="JSON list of banned words"
    )
    rejection_rubric = models.JSONField(
        default=list,
        help_text="JSON list of rejection patterns from revision examples",
    )
    min_words = models.IntegerField(default=165)
    max_words = models.IntegerField(default=176)
    min_sentence_words = models.IntegerField(default=12)
    max_sentence_words = models.IntegerField(default=25)
    few_shot_scripts = models.TextField(
        blank=True,
        help_text="Paste 3-5 of Nick's best scripts for few-shot prompting",
    )
    artemis_check = models.TextField(
        blank=True,
        help_text="The 7-point Artemis voice check criteria",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Skill Config"
        verbose_name_plural = "Skill Config"

    def __str__(self):
        return "SkillConfig (singleton)"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class TrendSnapshot(models.Model):
    keyword = models.CharField(max_length=255)
    score = models.FloatField(default=0)
    source = models.CharField(
        max_length=50, default="pytrends", help_text="pytrends or reddit"
    )
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-score"]

    def __str__(self):
        return f"{self.keyword} ({self.score})"


class Story(models.Model):
    class Status(models.TextChoices):
        CANDIDATE = "candidate", "Candidate"
        SELECTED = "selected", "Selected"
        USED = "used", "Used"
        SKIPPED = "skipped", "Skipped"

    title = models.CharField(max_length=500)
    summary = models.TextField(blank=True)
    source_url = models.URLField(max_length=1000, blank=True)
    topic = models.CharField(
        max_length=50, blank=True, help_text="science, space, news, etc."
    )
    trend_score = models.FloatField(default=0)
    virality_notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CANDIDATE
    )
    raw_facts = models.JSONField(
        default=list, help_text="Facts from Tavily search"
    )
    discovered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-trend_score", "-discovered_at"]
        verbose_name_plural = "Stories"

    def __str__(self):
        return self.title


class ResearchBrief(models.Model):
    story = models.OneToOneField(
        Story, on_delete=models.CASCADE, related_name="research"
    )
    facts = models.JSONField(default=list)
    numbers = models.JSONField(default=list)
    orgs = models.JSONField(default=list)
    hook_angles = models.JSONField(default=list)
    sources = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Research: {self.story.title[:60]}"


class Script(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVISION = "revision", "In Revision"
        FINAL = "final", "Final"

    story = models.ForeignKey(
        Story, on_delete=models.CASCADE, related_name="scripts"
    )
    content = models.TextField(help_text="Full script text")
    hook = models.TextField(blank=True)
    text_line = models.CharField(
        max_length=100, blank=True, help_text="On-screen text (2-4 words + emoji)"
    )
    body = models.TextField(blank=True)
    outro = models.TextField(blank=True)
    word_count = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    is_final = models.BooleanField(default=False)
    nick_notes = models.TextField(
        blank=True, help_text="Nick's feedback/edits for rubric tuning"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Script [{self.status}]: {self.story.title[:50]}"


class RevisionCycle(models.Model):
    script = models.ForeignKey(
        Script, on_delete=models.CASCADE, related_name="revisions"
    )
    cycle_no = models.IntegerField()
    critique = models.JSONField(
        default=list, help_text="JSON list of objections"
    )
    changelog = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["cycle_no"]

    def __str__(self):
        return f"Cycle {self.cycle_no} for Script #{self.script_id}"


class VerificationResult(models.Model):
    script = models.OneToOneField(
        Script, on_delete=models.CASCADE, related_name="verification"
    )
    passed = models.BooleanField(default=False)
    body_words = models.IntegerField(default=0)
    hook_words = models.IntegerField(default=0)
    sentence_count = models.IntegerField(default=0)
    errors = models.JSONField(default=list)
    warnings = models.JSONField(default=list)
    raw_output = models.TextField(blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"Verify [{status}]: Script #{self.script_id}"


class GenerationRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    run_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.RUNNING
    )
    num_requested = models.IntegerField(default=5)
    num_passed = models.IntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    log = models.TextField(blank=True)
    scripts = models.ManyToManyField(Script, blank=True, related_name="runs")

    class Meta:
        ordering = ["-run_date"]

    def __str__(self):
        return f"Run {self.run_date} [{self.status}]"

    def append_log(self, message):
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log += f"[{ts}] {message}\n"
        self.save(update_fields=["log"])
