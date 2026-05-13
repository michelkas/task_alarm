from django import forms
from .models import Task, VoiceConfig
from .voice import build_neural_voice_choices


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['name', 'due_date', 'due_time']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Appeler le client'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'due_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }


class VoiceConfigForm(forms.ModelForm):
    voice_id = forms.ChoiceField(
        label="Voix",
        required=False,
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    neural_voice_id = forms.ChoiceField(
        label="Voix neurale",
        required=False,
        choices=build_neural_voice_choices(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = VoiceConfig
        fields = [
            'tts_engine',
            'voice_id',
            'neural_voice_id',
            'rate',
            'volume',
            'audio_gain',
            'play_attention_sound',
            'pitch',
            'repeat_count',
            'repeat_interval_seconds',
            'pre_alarm_text',
            'use_system_fallback',
        ]
        widgets = {
            'tts_engine': forms.Select(attrs={'class': 'form-select'}),
            'rate': forms.NumberInput(attrs={'type': 'range', 'class': 'form-range', 'min': 135, 'max': 185, 'step': 5}),
            'volume': forms.NumberInput(attrs={'type': 'range', 'class': 'form-range', 'min': 0.2, 'max': 1, 'step': 0.05}),
            'audio_gain': forms.NumberInput(attrs={'type': 'range', 'class': 'form-range', 'min': 1, 'max': 3, 'step': 0.1}),
            'play_attention_sound': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'pitch': forms.NumberInput(attrs={'type': 'range', 'class': 'form-range', 'min': 80, 'max': 125, 'step': 5}),
            'repeat_count': forms.NumberInput(attrs={'type': 'range', 'class': 'form-range', 'min': 1, 'max': 5, 'step': 1}),
            'repeat_interval_seconds': forms.NumberInput(attrs={'type': 'range', 'class': 'form-range', 'min': 0, 'max': 10, 'step': 1}),
            'pre_alarm_text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Attention'}),
            'use_system_fallback': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, voice_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        base_choice = [('', 'Automatique (français recommandé)')]
        self.fields['voice_id'].choices = base_choice + (voice_choices or [])
