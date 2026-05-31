from django.contrib import admin
from .models import (
    SkillConfig, TrendSnapshot, Story, ResearchBrief,
    Script, RevisionCycle, VerificationResult, GenerationRun,
)


@admin.register(SkillConfig)
class SkillConfigAdmin(admin.ModelAdmin):
    list_display = ["__str__", "min_words", "max_words", "updated_at"]

    def has_add_permission(self, request):
        return not SkillConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TrendSnapshot)
class TrendSnapshotAdmin(admin.ModelAdmin):
    list_display = ["keyword", "score", "source", "captured_at"]
    list_filter = ["source"]


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ["title", "topic", "trend_score", "status", "discovered_at"]
    list_filter = ["status", "topic"]
    search_fields = ["title", "summary"]


@admin.register(ResearchBrief)
class ResearchBriefAdmin(admin.ModelAdmin):
    list_display = ["story", "created_at"]


@admin.register(Script)
class ScriptAdmin(admin.ModelAdmin):
    list_display = ["story", "status", "word_count", "is_final", "created_at"]
    list_filter = ["status", "is_final"]


@admin.register(RevisionCycle)
class RevisionCycleAdmin(admin.ModelAdmin):
    list_display = ["script", "cycle_no", "created_at"]


@admin.register(VerificationResult)
class VerificationResultAdmin(admin.ModelAdmin):
    list_display = ["script", "passed", "body_words", "hook_words", "checked_at"]
    list_filter = ["passed"]


@admin.register(GenerationRun)
class GenerationRunAdmin(admin.ModelAdmin):
    list_display = ["run_date", "status", "num_requested", "num_passed", "started_at"]
    list_filter = ["status"]
