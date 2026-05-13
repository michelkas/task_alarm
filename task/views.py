from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Task, VoiceConfig
from .forms import TaskForm, VoiceConfigForm
from .voice import get_available_voices, pick_french_voice_id, build_voice_choices, voice_id_is_french

def index(request):
    tasks = Task.objects.all()
    form = TaskForm()
    # Important: le déclenchement vocal doit se faire côté backend (scheduler).
    # On laisse le front uniquement pour afficher et/ou un bouton de lecture manuelle.
    return render(request, 'tasks/index.html', {'tasks': tasks, 'form': form})

def add_task(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Tâche ajoutée avec succès.")
        else:
            messages.error(request, "Impossible d'ajouter la tâche. Vérifiez les champs.")
    return redirect('index')


@require_POST
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    task_name = task.name
    task.delete()
    messages.success(request, f"Tâche supprimée: {task_name}")
    return redirect('index')


def due_tasks_api(request):
    """Retourne les tâches expirées en JSON pour le contrôle du front-end."""
    now = timezone.localtime()
    due_tasks = []
    # Aligné sur le scheduler : due_date__lte (pas due_date == aujourd'hui seul).
    for task in Task.objects.filter(
        is_active=True,
        due_date__lte=now.date(),
    ).order_by("due_date", "due_time"):
        if task.due_datetime_local <= now:
            due_tasks.append({"id": task.id, "name": task.name})
    return JsonResponse({"due_tasks": due_tasks})


def voice_config_view(request):
    config = VoiceConfig.get_solo()
    voice_list = get_available_voices()
    voice_choices = build_voice_choices(voice_list)
    french_voice_id = pick_french_voice_id(voice_list)

    # La planification reste cote web, mais la voix doit rester francaise cote systeme.
    if config.voice_id and not voice_id_is_french(voice_list, config.voice_id):
        if french_voice_id:
            config.voice_id = french_voice_id
            config.save()
            messages.warning(request, "La voix configurée n'était pas française; une voix française a été sélectionnée automatiquement.")
        else:
            config.voice_id = ""
            config.save()
            messages.warning(request, "Aucune voix française détectée. Activez le fallback système ou installez une voix FR.")
    elif not config.voice_id:
        if french_voice_id:
            config.voice_id = french_voice_id
            config.save()
        else:
            messages.warning(
                request,
                "Aucune voix française détectée. Activez le fallback système ou installez une voix FR."
            )

    if request.method == 'POST':
        form = VoiceConfigForm(request.POST, instance=config, voice_choices=voice_choices)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuration vocale enregistrée.")
            return redirect('voice_config')
        messages.error(request, "Configuration invalide. Vérifiez les valeurs.")
    else:
        form = VoiceConfigForm(instance=config, voice_choices=voice_choices)
    return render(request, 'tasks/voice_config.html', {
        'form': form,
        'voice_list': voice_list,
    })
