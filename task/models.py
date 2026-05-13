from datetime import datetime

from django.db import models
from django.utils import timezone


class Task(models.Model):
    name = models.CharField("Nom de la tâche", max_length=200)
    due_date = models.DateField("Date")
    due_time = models.TimeField("Heure")
    is_active = models.BooleanField("Active", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['due_date', 'due_time']

    def __str__(self):
        return f"{self.name} ({self.due_date} {self.due_time})"

    @property
    def due_datetime_local(self):
        """Echeance en fuseau horaire courant (aligne avec le scheduler)."""
        naive = datetime.combine(self.due_date, self.due_time)
        return timezone.make_aware(naive, timezone.get_current_timezone())


class VoiceConfig(models.Model):
    """
    Configuration unique de la voix.
    On utilise un singleton : une seule ligne en base.
    """
    TTS_ENGINE_AUTO = "auto"
    TTS_ENGINE_NEURAL = "neural"
    TTS_ENGINE_PYTTSX3 = "pyttsx3"
    TTS_ENGINE_SYSTEM = "system"
    TTS_ENGINE_CHOICES = [
        (TTS_ENGINE_AUTO, "Automatique: voix premium puis fallback"),
        (TTS_ENGINE_NEURAL, "Voix neurale premium"),
        (TTS_ENGINE_PYTTSX3, "pyttsx3 hors ligne"),
        (TTS_ENGINE_SYSTEM, "Moteur systeme"),
    ]

    tts_engine = models.CharField(
        "Moteur vocal",
        max_length=20,
        choices=TTS_ENGINE_CHOICES,
        default=TTS_ENGINE_AUTO,
        help_text="Automatique utilise d'abord une voix neurale francaise si disponible."
    )
    voice_id = models.CharField(
        "ID de la voix",
        max_length=500,
        blank=True,
        help_text="Laissez vide pour utiliser la voix par défaut du système."
    )
    rate = models.IntegerField("Vitesse", default=150, help_text="Mots par minute (défaut: 150)")
    volume = models.FloatField("Volume", default=1.0, help_text="Entre 0.0 et 1.0")
    neural_voice_id = models.CharField(
        "Voix neurale francaise",
        max_length=100,
        default="fr-FR-DeniseNeural",
        help_text="Voix Microsoft Edge TTS utilisee quand edge-tts est installe."
    )
    audio_gain = models.FloatField(
        "Gain audio",
        default=1.2,
        help_text="Amplification du lecteur audio premium (1.0 a 3.0)."
    )
    play_attention_sound = models.BooleanField(
        "Son d'attention",
        default=True,
        help_text="Joue un court signal avant la lecture vocale lorsque le systeme le permet."
    )
    pitch = models.IntegerField(
        "Tonalite",
        default=100,
        help_text="Tonalite de la voix (80-125, profil naturel)."
    )
    repeat_count = models.PositiveSmallIntegerField(
        "Nombre de repetitions",
        default=1,
        help_text="Nombre de lectures de la tache (1-5)."
    )
    repeat_interval_seconds = models.PositiveSmallIntegerField(
        "Pause entre repetitions",
        default=1,
        help_text="Pause en secondes entre deux lectures (0-10)."
    )
    pre_alarm_text = models.CharField(
        "Texte pre-alarme",
        max_length=200,
        blank=True,
        default="Attention",
        help_text="Texte lu avant le nom de la tache."
    )
    use_system_fallback = models.BooleanField(
        "Activer fallback systeme",
        default=True,
        help_text="Utilise spd-say/espeak si pyttsx3 echoue."
    )

    class Meta:
        verbose_name = "Configuration vocale"
        verbose_name_plural = "Configuration vocale"

    def save(self, *args, **kwargs):
        # S'assure qu'il n'y a qu'une seule instance
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        """Retourne l'unique instance ou la crée."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
