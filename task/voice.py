import logging
import sys

import pyttsx3

FRENCH_PRO_RATE = 155
FRENCH_PRO_VOLUME = 1.0
FRENCH_ESPEAK_AMPLITUDE = 200
NEURAL_FRENCH_VOICE_CHOICES = [
    ("fr-FR-DeniseNeural", "Denise - francais France, naturel"),
    ("fr-FR-HenriNeural", "Henri - francais France, naturel"),
    ("fr-CA-SylvieNeural", "Sylvie - francais Canada, naturel"),
    ("fr-CA-AntoineNeural", "Antoine - francais Canada, naturel"),
    ("fr-BE-CharlineNeural", "Charline - francais Belgique, naturel"),
    ("fr-CH-ArianeNeural", "Ariane - francais Suisse, naturel"),
]
DEFAULT_NEURAL_FRENCH_VOICE = NEURAL_FRENCH_VOICE_CHOICES[0][0]
logger = logging.getLogger(__name__)


def pyttsx3_driver_candidates():
    """Retourne uniquement les drivers pyttsx3 capables de produire du son."""
    if sys.platform.startswith("win"):
        return ["sapi5"]
    if sys.platform == "darwin":
        return ["nsss", "espeak"]
    # pyttsx3 expose le driver "espeak"; espeak-ng est utilise en fallback CLI.
    return ["espeak"]


def init_pyttsx3_engine(driver_name=None):
    """Initialise pyttsx3 avec un driver adapte a la plateforme."""
    last_exception = None
    candidates = [driver_name] if driver_name else [*pyttsx3_driver_candidates(), None]
    tried = set()

    for driver in candidates:
        key = driver or "__default__"
        if key in tried:
            continue
        tried.add(key)
        try:
            if driver:
                engine = pyttsx3.init(driverName=driver)
                logger.info("Initialisation de pyttsx3 via driver %s", driver)
            else:
                engine = pyttsx3.init()
                logger.info("Initialisation de pyttsx3 via le driver par defaut")
            return engine
        except Exception as exc:
            driver_label = driver or "defaut"
            logger.warning("Impossible d'initialiser pyttsx3 driver %s: %s", driver_label, exc)
            last_exception = exc

    logger.error("Impossible d'initialiser pyttsx3 avec les drivers disponibles.")
    raise last_exception or RuntimeError("Aucun driver pyttsx3 disponible")


def _voice_to_dict(voice):
    languages = []
    for item in getattr(voice, 'languages', []) or []:
        if isinstance(item, bytes):
            languages.append(item.decode(errors='ignore'))
        else:
            languages.append(str(item))
    return {
        'id': str(getattr(voice, 'id', '') or ''),
        'name': str(getattr(voice, 'name', '') or ''),
        'languages': languages,
    }


def get_engine_voices(engine):
    """Liste les voix depuis un moteur deja initialise, sans creer un second moteur."""
    try:
        return [_voice_to_dict(voice) for voice in (engine.getProperty('voices') or [])]
    except Exception as exc:
        logger.warning("Impossible de lire les voix depuis le moteur pyttsx3: %s", exc)
        return []


def get_available_voices():
    """Retourne les voix disponibles avec informations utiles."""
    engine = None
    try:
        engine = init_pyttsx3_engine()
        return get_engine_voices(engine)
    except Exception as exc:
        logger.warning("Impossible de lister les voix pyttsx3: %s", exc)
        return []
    finally:
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass


def _looks_french(text):
    normalized = (text or "").lower().replace("_", "-")
    markers = (
        "fr-fr",
        "fr-ca",
        "fr-be",
        "fr-ch",
        "france",
        "french",
        "francais",
        "français",
        "hortense",
        "audrey",
        "amelie",
        "amélie",
        "thomas",
        "denise",
        "henri",
        "lucie",
    )
    if any(marker in normalized for marker in markers):
        return True
    tokens = normalized.replace("/", " ").replace("\\", " ").replace(".", " ").split()
    return any(token == "fr" or token.startswith("fr-") for token in tokens)


def is_french_voice(voice):
    text_parts = [voice.get('id', ''), voice.get('name', '')]
    languages = voice.get('languages', [])
    for item in languages:
        text_parts.append(str(item))
    return _looks_french(" ".join(text_parts))


def voice_id_is_french(voices, voice_id):
    if not voice_id:
        return False
    for voice in voices:
        if voice.get('id') == voice_id:
            return is_french_voice(voice)
    return _looks_french(voice_id)


def pick_french_voice_id(voices):
    """Prend la meilleure voix française disponible, sinon None."""
    french_voices = [v for v in voices if is_french_voice(v)]
    if not french_voices:
        return None

    preferred_markers = (
        "fr-fr", "hortense", "audrey", "amelie", "amélie",
        "thomas", "denise", "henri", "lucie", "french", "france"
    )

    def _score(voice):
        normalized = (
            f"{voice.get('id', '')} {voice.get('name', '')} "
            f"{' '.join(str(x) for x in voice.get('languages', []))}"
        ).lower()
        return sum(1 for marker in preferred_markers if marker in normalized)

    ranked = sorted(french_voices, key=_score, reverse=True)
    return ranked[0]['id']


def build_voice_choices(voices):
    """Transforme les voix en choices Django."""
    choices = []
    for v in voices:
        name = v.get('name') or v.get('id') or 'Voix sans nom'
        choices.append((v.get('id', ''), name))
    return choices


def build_neural_voice_choices():
    """Voix francaises premium compatibles avec edge-tts."""
    return NEURAL_FRENCH_VOICE_CHOICES


def build_alarm_message(task_name):
    """Construit un message d'alarme clair et naturel en français."""
    clean_name = (task_name or "").strip()
    if not clean_name:
        return "Attention. Une alarme vient de se declencher."
    return f"C'est le moment de, {clean_name}."


def _edge_rate_from_wpm(rate):
    percent = round(((int(rate) - FRENCH_PRO_RATE) / FRENCH_PRO_RATE) * 100)
    percent = max(-35, min(35, percent))
    return f"{percent:+d}%"


def _edge_pitch_from_pyttsx3_pitch(pitch):
    hz = round((int(pitch) - 100) * 1.5)
    hz = max(-60, min(60, hz))
    return f"{hz:+d}Hz"


def _edge_volume_from_volume(volume):
    percent = round(((float(volume) - 1.0) * 100) + 20)
    percent = max(-50, min(30, percent))
    return f"{percent:+d}%"


def normalize_neural_voice_id(voice_id):
    available_ids = {voice_id for voice_id, _label in NEURAL_FRENCH_VOICE_CHOICES}
    if voice_id in available_ids:
        return voice_id
    return DEFAULT_NEURAL_FRENCH_VOICE


def build_neural_voice_settings(rate, volume, pitch):
    """Convertit les reglages locaux vers le format Edge TTS."""
    return {
        "rate": _edge_rate_from_wpm(rate),
        "volume": _edge_volume_from_volume(volume),
        "pitch": _edge_pitch_from_pyttsx3_pitch(pitch),
    }


def normalize_tts_engine(engine):
    allowed = {"auto", "neural", "pyttsx3", "system"}
    return engine if engine in allowed else "auto"


def resolve_french_voice_settings(config, voices=None):
    """
    Détermine des réglages vocaux professionnels en français.
    - Voix: utilise une voix francaise configuree ou detectee automatiquement.
    - Vitesse: défaut naturel FR si non défini.
    - Volume: niveau fort et clair pour une alarme.
    """
    voices = list(get_available_voices() if voices is None else voices)
    french_voice_id = pick_french_voice_id(voices)
    configured_voice_id = (getattr(config, "voice_id", "") or "").strip()
    configured_is_french = voice_id_is_french(voices, configured_voice_id)

    if configured_voice_id and configured_is_french:
        selected_voice_id = configured_voice_id
    else:
        selected_voice_id = french_voice_id or ""
    french_available = bool(selected_voice_id and voice_id_is_french(voices, selected_voice_id))
    configured_voice_ignored = bool(configured_voice_id and configured_voice_id != selected_voice_id)

    # Harmonise les anciennes configs (150) vers un rendu FR plus naturel.
    if not config.rate or config.rate == 150:
        rate = FRENCH_PRO_RATE
    else:
        rate = config.rate
    # Bornes de qualite: trop lent ou trop aigu/grave devient vite peu intelligible.
    rate = max(135, min(185, int(rate)))
    raw_volume = config.volume if config.volume is not None else FRENCH_PRO_VOLUME
    volume = max(0.2, min(1.0, float(raw_volume)))
    pitch = max(80, min(125, int(getattr(config, "pitch", 100))))
    tts_engine = normalize_tts_engine(getattr(config, "tts_engine", "auto"))
    neural_voice_id = normalize_neural_voice_id(getattr(config, "neural_voice_id", DEFAULT_NEURAL_FRENCH_VOICE))
    neural_settings = build_neural_voice_settings(rate, volume, pitch)
    audio_gain = max(1.0, min(3.0, float(getattr(config, "audio_gain", 1.2) or 1.2)))
    play_attention_sound = bool(getattr(config, "play_attention_sound", True))
    repeat_count = max(1, min(5, int(getattr(config, "repeat_count", 1))))
    repeat_interval_seconds = max(0, min(10, int(getattr(config, "repeat_interval_seconds", 1))))
    pre_alarm_text = (getattr(config, "pre_alarm_text", "") or "").strip()
    use_system_fallback = bool(getattr(config, "use_system_fallback", True))

    return {
        "voice_id": selected_voice_id,
        "french_available": french_available,
        "configured_voice_ignored": configured_voice_ignored,
        "rate": rate,
        "volume": volume,
        "pitch": pitch,
        "tts_engine": tts_engine,
        "neural_voice_id": neural_voice_id,
        "neural_rate": neural_settings["rate"],
        "neural_volume": neural_settings["volume"],
        "neural_pitch": neural_settings["pitch"],
        "audio_gain": audio_gain,
        "play_attention_sound": play_attention_sound,
        "repeat_count": repeat_count,
        "repeat_interval_seconds": repeat_interval_seconds,
        "pre_alarm_text": pre_alarm_text,
        "use_system_fallback": use_system_fallback,
    }


def configure_engine_for_french(engine, config, voices=None):
    """
    Applique les reglages audibles au moteur pyttsx3.
    Le moteur est deja cree dans le thread vocal: on ne cree pas de second moteur ici.
    """
    engine_voices = get_engine_voices(engine) if voices is None else list(voices)
    settings = resolve_french_voice_settings(config, voices=engine_voices)

    if settings["configured_voice_ignored"]:
        logger.warning(
            "La voix configuree n'est pas francaise ou indisponible; selection auto: %r",
            settings["voice_id"] or "voix systeme",
        )

    if settings["voice_id"]:
        try:
            engine.setProperty("voice", settings["voice_id"])
        except Exception as exc:
            logger.warning("Impossible d'appliquer la voix francaise %r: %s", settings["voice_id"], exc)
            settings["voice_id"] = ""
            settings["french_available"] = False

    try:
        engine.setProperty("rate", settings["rate"])
        engine.setProperty("volume", settings["volume"])
    except Exception as exc:
        logger.warning("Parametres pyttsx3 invalides (rate/volume): %s", exc)

    # Tous les drivers ne gerent pas pitch; l'echec n'empeche pas l'alarme.
    try:
        engine.setProperty("pitch", settings["pitch"])
    except Exception:
        pass

    if not settings["french_available"]:
        logger.error(
            "Aucune voix francaise pyttsx3 detectee. Installez une voix FR "
            "ou laissez le fallback systeme actif (Linux: espeak-ng/speech-dispatcher, Windows: voix FR SAPI5)."
        )

    return settings
