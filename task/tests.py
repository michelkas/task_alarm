from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from task.models import Task, VoiceConfig
from task.scheduler import run_scheduler_iteration
from task.voice import pick_french_voice_id, resolve_french_voice_settings


class VoiceSelectionTests(TestCase):
    def test_pick_french_voice_prefers_fr_voice(self):
        voices = [
            {"id": "english", "name": "English US", "languages": ["en_US"]},
            {"id": "french", "name": "Microsoft Hortense", "languages": ["fr_FR"]},
        ]

        self.assertEqual(pick_french_voice_id(voices), "french")

    def test_resolve_settings_ignores_configured_non_french_voice(self):
        voices = [
            {"id": "english", "name": "English US", "languages": ["en_US"]},
            {"id": "french", "name": "French", "languages": ["fr_FR"]},
        ]
        config = VoiceConfig(voice_id="english", rate=150, volume=0.4)

        settings = resolve_french_voice_settings(config, voices=voices)

        self.assertEqual(settings["voice_id"], "french")
        self.assertTrue(settings["french_available"])
        self.assertEqual(settings["rate"], 155)
        self.assertEqual(settings["volume"], 0.4)


class SchedulerDetectionTests(TestCase):
    def test_iteration_enqueues_all_due_tasks(self):
        now = timezone.localtime()
        due_time = (now - timedelta(seconds=5)).time().replace(microsecond=0)
        future_time = (now + timedelta(minutes=10)).time().replace(microsecond=0)
        task_a = Task.objects.create(name="Premiere alarme", due_date=now.date(), due_time=due_time)
        task_b = Task.objects.create(name="Deuxieme alarme", due_date=now.date(), due_time=due_time)
        Task.objects.create(name="Future alarme", due_date=now.date(), due_time=future_time)

        with patch("task.scheduler._ensure_speaker_thread"), patch("task.scheduler.enqueue_alarm_speech") as enqueue:
            due_tasks = run_scheduler_iteration(now=now)

        self.assertEqual([task.id for task in due_tasks], [task_a.id, task_b.id])
        self.assertEqual(enqueue.call_count, 2)
        enqueue.assert_any_call(task_a.id, task_a.name)
        enqueue.assert_any_call(task_b.id, task_b.name)
