from django.contrib import admin
from .models import Task, VoiceConfig

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("name", "due_date", "due_time", "is_active", "created_at")
    list_filter = ("is_active", "due_date")
    search_fields = ("name",)


@admin.register(VoiceConfig)
class VoiceConfigAdmin(admin.ModelAdmin):
    list_display = (
        "tts_engine",
        "neural_voice_id",
        "voice_id",
        "rate",
        "volume",
        "audio_gain",
        "pitch",
        "play_attention_sound",
        "repeat_count",
        "repeat_interval_seconds",
        "use_system_fallback",
    )
