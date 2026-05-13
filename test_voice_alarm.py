#!/usr/bin/env python
"""
Script de diagnostic et test des alarmes vocales.
Usage: python test_voice_alarm.py
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from task.voice import get_available_voices, pick_french_voice_id, resolve_french_voice_settings
from task.scheduler import speak_text, _system_tts_fallback
from task.models import VoiceConfig

def test_voice_availability():
    print("\n" + "=" * 60)
    print("TEST 1: Voix disponibles")
    print("=" * 60)
    voices = get_available_voices()
    if not voices:
        print("❌ Aucune voix pyttsx3 détectée.")
        return False
    
    print(f"✅ {len(voices)} voix(es) trouvée(s):")
    for v in voices:
        print(f"   - {v['name']} (ID: {v['id']})")
    
    french_id = pick_french_voice_id(voices)
    if french_id:
        print(f"✅ Voix française sélectionnée: {french_id}")
    else:
        print("⚠️  Aucune voix française détectée (fallback système sera utilisé).")
    
    return True

def test_pyttsx3_speech():
    print("\n" + "=" * 60)
    print("TEST 2: Lecture pyttsx3 simple")
    print("=" * 60)
    test_text = "Ceci est un test de synthèse vocale en français."
    print(f"Texte: '{test_text}'")
    print("Tentative de lecture...")
    
    success = speak_text(test_text, use_system_fallback=False)
    if success:
        print("✅ Lecture pyttsx3 réussie (écoutez le son).")
    else:
        print("❌ Lecture pyttsx3 échouée.")
    return success

def test_system_fallback():
    print("\n" + "=" * 60)
    print("TEST 3: Fallback système")
    print("=" * 60)
    test_text = "Ceci est un test du fallback système."
    print(f"Texte: '{test_text}'")
    print("Tentative de lecture via fallback système...")
    
    success = _system_tts_fallback(test_text)
    if success:
        print("✅ Fallback système réussi (écoutez le son).")
    else:
        print("⚠️  Fallback système échoué (dépendances système manquantes?).")
    return success

def test_voice_config():
    print("\n" + "=" * 60)
    print("TEST 4: Configuration vocale")
    print("=" * 60)
    config = VoiceConfig.get_solo()
    settings = resolve_french_voice_settings(config)
    
    print(f"Voice ID: {settings['voice_id']}")
    print(f"Moteur vocal: {settings['tts_engine']}")
    print(f"Voix premium: {settings['neural_voice_id']}")
    print(f"Gain audio: {settings['audio_gain']}")
    print(f"Rate (mpm): {settings['rate']}")
    print(f"Volume: {settings['volume']}")
    print(f"Pitch: {settings['pitch']}")
    print(f"Repeat count: {settings['repeat_count']}")
    print(f"Repeat interval (s): {settings['repeat_interval_seconds']}")
    print(f"Pre-alarm text: '{settings['pre_alarm_text']}'")
    print(f"French available: {settings['french_available']}")
    print(f"Use system fallback: {settings['use_system_fallback']}")
    
    if settings['voice_id']:
        print("✅ Voix configurée.")
    else:
        print("⚠️  Aucune voix configurée (défaut système).")
    
    return True

def test_alarm_message():
    print("\n" + "=" * 60)
    print("TEST 5: Message d'alarme avec configuration")
    print("=" * 60)
    config = VoiceConfig.get_solo()
    settings = resolve_french_voice_settings(config)
    
    alarm_text = f"{settings['pre_alarm_text']}. C'est le moment de: Réunion importante."
    print(f"Message d'alarme: '{alarm_text}'")
    print("Tentative de lecture...")
    
    success = speak_text(alarm_text)
    if success:
        print("✅ Alarme lue avec succès (écoutez le son).")
    else:
        print("❌ Alarme non lue.")
    
    return success

def run_all_tests():
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  TEST DE SYNTHÈSE VOCALE - TASK ALARM                      ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    results = {
        "Voix disponibles": test_voice_availability(),
        "Lecture pyttsx3": test_pyttsx3_speech(),
        "Fallback système": test_system_fallback(),
        "Configuration vocale": test_voice_config(),
        "Message d'alarme": test_alarm_message(),
    }
    
    print("\n" + "=" * 60)
    print("RÉSUMÉ DES TESTS")
    print("=" * 60)
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_pass = all(results.values())
    if all_pass:
        print("\n🎉 Tous les tests sont passés! Les alarmes vocales doivent fonctionner.")
    else:
        print("\n⚠️  Certains tests ont échoué. Consultez le guide de troubleshooting.")
    
    return all_pass

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
