import os
import asyncio
import logging
import subprocess
import sys
import tempfile
import threading
from queue import Empty, Queue
from datetime import datetime
from pathlib import Path

from django.db import close_old_connections
from django.utils import timezone

from task.models import Task, VoiceConfig
from task.voice import (
    FRENCH_ESPEAK_AMPLITUDE,
    FRENCH_PRO_RATE,
    build_alarm_message,
    configure_engine_for_french,
    init_pyttsx3_engine,
    resolve_french_voice_settings,
)

_worker_thread = None
_worker_lock = threading.Lock()
_speaker_thread = None
_speaker_lock = threading.Lock()
_speech_queue = Queue()
_pending_task_ids = set()
_pending_lock = threading.Lock()
_stop_event = threading.Event()
ATTENTION_SOUND_MAX_SECONDS = 2
logger = logging.getLogger(__name__)


def _configure_engine(engine):
    config = VoiceConfig.get_solo()
    return configure_engine_for_french(engine, config)


def _create_pyttsx3_engine():
    """Initialise un moteur pyttsx3 unique pour le thread vocal."""
    try:
        return init_pyttsx3_engine()
    except Exception as exc:
        logger.error("Aucun moteur pyttsx3 disponible: %s", exc)
        return None


def _shutdown_pyttsx3_engine(engine):
    if engine is None:
        return
    try:
        engine.stop()
    except Exception:
        pass


def _speak_with_engine(engine, text):
    try:
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception as exc:
        logger.exception("Erreur pyttsx3 pendant le speak: %s", exc)
        return False


def _run_command(command, timeout=120, timeout_is_success=False):
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return True
        output = (result.stderr or result.stdout or b"").decode(errors="ignore")
        logger.warning("Commande audio echouee (%s): %s", command[0], output)
    except FileNotFoundError:
        return False
    except subprocess.TimeoutExpired:
        if timeout_is_success:
            logger.info("Commande audio arretee apres %ss (%s)", timeout, command[0])
            return True
        logger.warning("Timeout commande audio (%s)", command[0])
    except Exception as exc:
        logger.warning("Erreur commande audio (%s): %s", command[0], exc)
    return False


def _ring_attention_bell():
    """Petit ding terminal apres la sonnerie principale, quand le terminal le permet."""
    try:
        print("\a", end="", flush=True)
        return True
    except Exception:
        return False


def _play_attention_tone():
    """Joue un court signal avant la voix quand la plateforme le permet."""
    try:
        if sys.platform.startswith("win"):
            import winsound

            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            _ring_attention_bell()
            return True
        if sys.platform == "darwin":
            if _run_command(
                ["afplay", "/System/Library/Sounds/Glass.aiff"],
                timeout=ATTENTION_SOUND_MAX_SECONDS,
                timeout_is_success=True,
            ):
                _ring_attention_bell()
                return True

        linux_sounds = [
            "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
            "/usr/share/sounds/freedesktop/stereo/complete.oga",
            "/usr/share/sounds/Yaru/stereo/complete.oga",
        ]
        for sound_path in linux_sounds:
            if Path(sound_path).exists() and _run_command(
                ["paplay", sound_path],
                timeout=ATTENTION_SOUND_MAX_SECONDS,
                timeout_is_success=True,
            ):
                _ring_attention_bell()
                return True
        if _run_command(
            ["canberra-gtk-play", "-i", "alarm-clock-elapsed"],
            timeout=ATTENTION_SOUND_MAX_SECONDS,
            timeout_is_success=True,
        ):
            _ring_attention_bell()
            return True
    except Exception as exc:
        logger.debug("Signal d'attention indisponible: %s", exc)

    # Dernier recours: bell terminal. N'est pas garanti, mais ne bloque jamais.
    return _ring_attention_bell()


def _with_pre_alarm_text(pre_alarm_text, alarm_text):
    pre_alarm_text = (pre_alarm_text or "").strip()
    if not pre_alarm_text:
        return alarm_text
    return f"{pre_alarm_text.rstrip('.!?')}. {alarm_text}"


def _play_audio_file(audio_path, audio_gain=1.0):
    """Lit un fichier audio genere par une voix premium."""
    normalized_gain = max(1.0, min(3.0, float(audio_gain or 1.0)))

    try:
        import pygame

        pygame.mixer.init()
        pygame.mixer.music.set_volume(min(1.0, normalized_gain))
        pygame.mixer.music.load(str(audio_path))
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if _stop_event.wait(0.02):
                pygame.mixer.music.stop()
                break
        pygame.mixer.quit()
        return True
    except ImportError:
        logger.info("pygame non installe; tentative lecteurs systeme pour la voix premium.")
    except Exception as exc:
        logger.warning("Lecture pygame impossible: %s", exc)
        try:
            pygame.mixer.quit()
        except Exception:
            pass

    if sys.platform.startswith("win"):
        ps_path = str(audio_path).replace("'", "''")
        ps = (
            "Add-Type -AssemblyName presentationCore; "
            "$player = New-Object System.Windows.Media.MediaPlayer; "
            f"$player.Open([uri]'{ps_path}'); "
            "$player.Volume = 1.0; $player.Play(); "
            "Start-Sleep -Milliseconds 250; "
            "while ($player.NaturalDuration.HasTimeSpan -and "
            "$player.Position -lt $player.NaturalDuration.TimeSpan) { Start-Sleep -Milliseconds 100 }; "
            "$player.Close();"
        )
        return _run_command(["powershell", "-NoProfile", "-Command", ps], timeout=120)

    if sys.platform == "darwin" and _run_command(["afplay", str(audio_path)], timeout=120):
        return True

    volume = str(int(min(100, 80 * normalized_gain)))
    commands = [
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-volume", volume, str(audio_path)],
        ["mpg123", "-q", "-f", str(int(32768 * normalized_gain)), str(audio_path)],
        ["mpv", "--no-video", "--really-quiet", f"--volume={volume}", str(audio_path)],
        ["cvlc", "--play-and-exit", "--quiet", "--gain", str(normalized_gain), str(audio_path)],
    ]
    for command in commands:
        if _run_command(command, timeout=120):
            return True
    return False


async def _save_edge_tts_audio(text, settings, audio_path):
    import edge_tts

    communicate = edge_tts.Communicate(
        text=text,
        voice=settings["neural_voice_id"],
        rate=settings["neural_rate"],
        volume=settings["neural_volume"],
        pitch=settings["neural_pitch"],
    )
    await communicate.save(str(audio_path))


def _speak_with_neural_voice(text, settings):
    """
    Voix francaise premium via edge-tts.
    Cette couche est optionnelle: si edge-tts, internet ou lecteur MP3 manque, on laisse le fallback parler.
    """
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        logger.info("edge-tts non installe; voix neurale premium ignoree.")
        return False

    audio_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="task_alarm_", suffix=".mp3", delete=False) as tmp:
            audio_path = Path(tmp.name)

        asyncio.run(asyncio.wait_for(_save_edge_tts_audio(text, settings, audio_path), timeout=30))
        if audio_path.exists() and audio_path.stat().st_size > 0:
            if _play_audio_file(audio_path, settings["audio_gain"]):
                logger.info("Lecture voix neurale reussie avec %s.", settings["neural_voice_id"])
                return True
        logger.warning("Audio neural genere mais non lu: %s", audio_path)
    except Exception as exc:
        logger.warning("Voix neurale indisponible: %s", exc)
    finally:
        if audio_path:
            try:
                audio_path.unlink(missing_ok=True)
            except Exception:
                pass
    return False


def _speak_best_effort(text, settings, engine, use_engine, use_fallback):
    """
    Lit le texte avec le meilleur moteur disponible.
    Retourne (spoken, engine, use_engine), car pyttsx3 doit etre recrée apres certaines erreurs.
    """
    mode = settings["tts_engine"]
    spoken = False

    if mode in {"auto", "neural"}:
        spoken = _speak_with_neural_voice(text, settings)
        if spoken:
            return True, engine, use_engine

    if mode in {"auto", "pyttsx3"} and use_engine:
        spoken = _speak_with_engine(engine, text)
        if spoken:
            return True, engine, use_engine

        _shutdown_pyttsx3_engine(engine)
        engine = None
        use_engine = False

    if use_fallback:
        spoken = _system_tts_fallback(text)

    return spoken, engine, use_engine


def _windows_powershell_tts(text):
    """Fallback Windows sans dependance supplementaire (SAPI via PowerShell)."""
    safe = text.replace("'", "''")
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.Rate = 0; $s.Volume = 100; "
        "$fr = $s.GetInstalledVoices() | "
        "Where-Object { $_.VoiceInfo.Culture.Name -like 'fr*' } | "
        "Select-Object -First 1; "
        "if ($fr) { $s.SelectVoice($fr.VoiceInfo.Name) } "
        "else { Write-Warning 'Aucune voix francaise SAPI5 installee; voix systeme utilisee.' }; "
        f"$s.Speak('{safe}')"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            check=False,
            capture_output=True,
            timeout=120,
        )
        if result.returncode == 0:
            logger.info("Lecture fallback Windows (PowerShell SAPI) reussie.")
            return True
        logger.warning(
            "PowerShell TTS echoue: %s",
            (result.stderr or result.stdout or b"").decode(errors="ignore"),
        )
    except FileNotFoundError:
        logger.warning("powershell introuvable pour le fallback TTS Windows.")
    except Exception as exc:
        logger.warning("Erreur PowerShell TTS: %s", exc)
    return False


def _system_tts_fallback(text):
    # Fallback hors pyttsx3 (souvent plus fiable sur Linux / CI sans audio espeak pipe).
    if sys.platform.startswith("win"):
        return _windows_powershell_tts(text)
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["say", text],
                check=False,
                capture_output=True,
                timeout=120,
                stdin=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                logger.info("Lecture fallback macOS (say) reussie.")
                return True
            logger.warning("say (macOS) echoue: %s", result.stderr.decode(errors="ignore"))
        except FileNotFoundError:
            logger.warning("Commande say introuvable sur macOS.")
        except Exception as exc:
            logger.warning("Erreur say macOS: %s", exc)
    commands = [
        ["spd-say", "-w", "-l", "fr", text],
        ["espeak-ng", "-v", "fr", "-s", str(FRENCH_PRO_RATE), "-a", str(FRENCH_ESPEAK_AMPLITUDE), text],
        ["espeak", "-v", "fr", "-s", str(FRENCH_PRO_RATE), "-a", str(FRENCH_ESPEAK_AMPLITUDE), text],
    ]
    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                timeout=120,
                stdin=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                logger.info("Lecture fallback reussie via %s", cmd[0])
                return True
            logger.warning("Commande fallback echouee (%s): %s", cmd[0], result.stderr.decode(errors="ignore"))
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            logger.warning("Timeout fallback TTS (%s)", cmd[0])
            continue
        except Exception as exc:
            logger.warning("Erreur fallback TTS (%s): %s", cmd[0], exc)
            continue
    logger.error("Aucun moteur TTS fallback disponible (installez speech-dispatcher ou espeak-ng).")
    return False


def speak_text(text, use_system_fallback=True):
    logger.debug("speak_text() appel: texte=%r fallback=%s", text, use_system_fallback)

    """Lit un texte avec pyttsx3 et bascule vers le fallback si nécessaire."""
    engine = None
    try:
        config = VoiceConfig.get_solo()
        settings = resolve_french_voice_settings(config)
        if use_system_fallback and settings["tts_engine"] in {"auto", "neural"}:
            if _speak_with_neural_voice(text, settings):
                return True
        if settings["tts_engine"] == "system":
            return _system_tts_fallback(text) if use_system_fallback else False

        engine = _create_pyttsx3_engine()
        if engine is not None:
            settings = _configure_engine(engine)
            if settings["french_available"] or not use_system_fallback:
                engine.say(text)
                engine.runAndWait()
                logger.info("pyttsx3: lecture terminee (verifiez le volume systeme si aucun son).")
                return True
            logger.warning("pyttsx3: aucune voix francaise, tentative fallback systeme en francais.")
        logger.warning("pyttsx3: aucun moteur disponible, tentative fallback systeme.")
    except Exception as exc:
        logger.exception("Erreur pyttsx3 pendant la lecture: %s", exc)
    finally:
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass

    if use_system_fallback:
        return _system_tts_fallback(text)
    return False


def enqueue_alarm_speech(task_id, task_name):
    """Ajoute une alarme a lire de maniere thread-safe."""
    with _pending_lock:
        pending_size = len(_pending_task_ids)
    logger.info(
        "enqueue_alarm_speech(): speaker_alive=%s pending_size=%s",
        (_speaker_thread is not None and _speaker_thread.is_alive()),
        pending_size,
    )

    with _pending_lock:
        if task_id in _pending_task_ids:
            logger.debug("Tache id=%s deja en attente vocale, ignoree.", task_id)
            return
        _pending_task_ids.add(task_id)
    logger.info("Alarme en file vocale: tache id=%s nom=%r", task_id, task_name)
    _speech_queue.put((task_id, build_alarm_message(task_name)))


def _speaker_loop():
    """
    Thread dedie au TTS.
    Un seul moteur pyttsx3 est actif a la fois pour eviter les conflits.
    """
    engine = None
    logger.info("_speaker_loop(): thread demarre (id=%s)", id(threading.current_thread()))

    # Diagnostic optionnel (permet de voir si la parole fonctionne reellement sur la machine).
    if os.environ.get("VOICE_DIAGNOSTIC", "").strip() == "1":
        try:
            diag_text = "Diagnostic audio: test alarme."
            logger.info("VOICE_DIAGNOSTIC=1 -> tentative speak_text(%r)", diag_text)
            ok = speak_text(diag_text, use_system_fallback=True)
            logger.info("VOICE_DIAGNOSTIC result: ok=%s", ok)
        except Exception:
            logger.exception("VOICE_DIAGNOSTIC exception")

    while not _stop_event.is_set():
        item = None
        task_id = None

        try:
            item = _speech_queue.get(timeout=0.5)
            if item is None:
                logger.info("_speaker_loop: signal d'arret recu.")
                _speech_queue.task_done()
                break
            task_id, text = item
        except Empty:
            continue

        try:
            close_old_connections()
            config = VoiceConfig.get_solo()
            requested_engine = getattr(config, "tts_engine", "auto")
            needs_pyttsx3 = requested_engine in {"auto", "pyttsx3"}

            if engine is None and needs_pyttsx3:
                logger.info("_speaker_loop: initialisation moteur pyttsx3...")
                engine = _create_pyttsx3_engine()
                logger.info("_speaker_loop: moteur pyttsx3=%s", bool(engine))

            if engine is not None and needs_pyttsx3:
                settings = _configure_engine(engine)
            else:
                settings = resolve_french_voice_settings(config, voices=[])

            use_engine = bool(engine is not None and needs_pyttsx3 and settings["french_available"])
            use_fallback = bool(settings["use_system_fallback"])
            task_spoken = False

            logger.info(
                "_speaker_loop: debut tache id=%s mode=%s french_available=%s voice_id=%r neural_voice=%s repeat=%s/%ss pre_alarm=%r fallback=%s",
                task_id,
                settings.get("tts_engine"),
                settings.get("french_available"),
                settings.get("voice_id"),
                settings.get("neural_voice_id"),
                settings.get("repeat_count"),
                settings.get("repeat_interval_seconds"),
                settings.get("pre_alarm_text"),
                use_fallback,
            )

            if settings["play_attention_sound"]:
                _play_attention_tone()

            if settings["tts_engine"] != "neural" and not use_engine and not use_fallback:
                logger.error(
                    "Aucune voix francaise pyttsx3 disponible et fallback systeme desactive; "
                    "la tache id=%s sera retentee.",
                    task_id,
                )

            repeats = max(1, int(settings["repeat_count"]))
            pause = max(0, int(settings["repeat_interval_seconds"]))
            first_alarm_text = _with_pre_alarm_text(settings["pre_alarm_text"], text)
            for i in range(repeats):
                speech_text = first_alarm_text if i == 0 else text
                spoken_this_round, engine, use_engine = _speak_best_effort(
                    speech_text,
                    settings,
                    engine,
                    use_engine,
                    use_fallback,
                )

                task_spoken = task_spoken or spoken_this_round

                if i < repeats - 1 and pause > 0:
                    if _stop_event.wait(pause):
                        break

            if task_spoken:
                Task.objects.filter(id=task_id, is_active=True).update(is_active=False)
                logger.info("Alarme lue avec succes pour la tache id=%s", task_id)
            else:
                logger.error(
                    "Alerte non lue, nouvelle tentative ulterieure pour id=%s text=%r",
                    task_id,
                    text,
                )

        except Exception:
            logger.exception("Erreur dans le thread vocal (tache id=%s)", task_id)
            if engine is not None:
                _shutdown_pyttsx3_engine(engine)
                engine = None
        finally:
            if task_id is not None:
                with _pending_lock:
                    _pending_task_ids.discard(task_id)
            if item is not None:
                _speech_queue.task_done()

    _shutdown_pyttsx3_engine(engine)
    logger.info("_speaker_loop(): thread arrete.")


def _ensure_speaker_thread():
    """Demarre ou redemarre le thread vocal s'il est mort (erreur non geree auparavant)."""
    global _speaker_thread
    with _speaker_lock:
        if _speaker_thread is not None and _speaker_thread.is_alive():
            return
        if _speaker_thread is not None:
            logger.warning(
                "Thread vocal inactif: redemarrage (id=%s).",
                id(_speaker_thread),
            )
        logger.info("Demarrage thread vocal (task-alarm-speaker)...")
        _stop_event.clear()
        _speaker_thread = threading.Thread(target=_speaker_loop, name="task-alarm-speaker", daemon=True)
        _speaker_thread.start()
        logger.info("Thread vocal demarre: alive=%s id=%s", _speaker_thread.is_alive(), id(_speaker_thread))



def _task_due_datetime(task, current_tz):
    naive_dt = datetime.combine(task.due_date, task.due_time)
    if timezone.is_naive(naive_dt):
        return timezone.make_aware(naive_dt, current_tz)
    return timezone.localtime(naive_dt, current_tz)


def get_due_tasks(now=None):
    """Retourne toutes les taches actives dont l'echeance date+heure est atteinte."""
    now = now or timezone.localtime()
    current_tz = timezone.get_current_timezone()
    candidates = Task.objects.filter(
        is_active=True,
        due_date__lte=now.date(),
    ).order_by("due_date", "due_time", "id")

    due_tasks = []
    for task in candidates:
        due_dt = _task_due_datetime(task, current_tz)
        if due_dt <= now:
            due_tasks.append(task)
    return due_tasks


def run_scheduler_iteration(now=None, ensure_speaker=True):
    """
    Execute un cycle de detection.
    Les taches dues sont toutes mises en file; le thread vocal les lit ensuite une par une.
    """
    if ensure_speaker:
        _ensure_speaker_thread()
    close_old_connections()
    due_tasks = get_due_tasks(now=now)
    for task in due_tasks:
        enqueue_alarm_speech(task.id, task.name)
    return due_tasks


def _run_loop():
    while not _stop_event.is_set():
        try:
            run_scheduler_iteration()
        except Exception as exc:
            # On garde le worker vivant même si une itération échoue.
            logger.exception("Erreur dans la boucle scheduler: %s", exc)
        _stop_event.wait(1)


def should_start_scheduler():
    # En dev, Django lance deux processus avec autoreload.
    if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
        return False

    # Ne pas démarrer sur commandes one-shot qui n'ont pas besoin du worker.
    blocked_commands = {
        "makemigrations",
        "migrate",
        "collectstatic",
        "shell",
        "dbshell",
        "test",
        "check",
        "run_alarm",
    }
    return not any(cmd in sys.argv for cmd in blocked_commands)


def start_scheduler():
    global _worker_thread
    if not should_start_scheduler():
        return
    _stop_event.clear()
    _ensure_speaker_thread()
    with _worker_lock:
        if _worker_thread and _worker_thread.is_alive():
            return
        _worker_thread = threading.Thread(target=_run_loop, name="task-alarm-scheduler", daemon=True)
        _worker_thread.start()


def stop_scheduler(wait=False):
    """Demande l'arret propre des threads et libere le moteur vocal."""
    _stop_event.set()
    if _speaker_thread and _speaker_thread.is_alive():
        _speech_queue.put(None)
    if wait:
        if _worker_thread and _worker_thread.is_alive():
            _worker_thread.join(timeout=5)
        if _speaker_thread and _speaker_thread.is_alive():
            _speaker_thread.join(timeout=10)


def run_scheduler_forever():
    """Boucle bloquante utilisee par la commande Django run_alarm."""
    _stop_event.clear()
    logger.info("Boucle d'alarmes vocale demarree en mode commande.")
    while not _stop_event.is_set():
        try:
            due_tasks = run_scheduler_iteration()
            if due_tasks:
                logger.info("%s tache(s) due(s) envoyee(s) au thread vocal.", len(due_tasks))
        except Exception as exc:
            logger.exception("Erreur dans la commande scheduler: %s", exc)
        _stop_event.wait(1)
