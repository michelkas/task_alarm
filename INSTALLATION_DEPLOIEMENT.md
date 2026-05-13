# Instructions d'Installation et Déploiement

## ⚡ Démarrage rapide

### 1. Installation des dépendances Python
```bash
cd /code/task_alarm/task
pip install -r requirements.txt
```

### 2. Installation des dépendances système

**Linux (Ubuntu/Debian)** :
```bash
sudo apt update
sudo apt install espeak-ng speech-dispatcher libspeechd-dev
```

**macOS** :
```bash
# Aucune installation supplémentaire, 'say' est natif
# Tester: say "Test de son"
```

**Windows** :
```
# SAPI5 via PowerShell est déjà inclus
# Aucune installation supplémentaire requise
```

### 3. Migrations Django
```bash
python manage.py migrate
```

### 4. Démarrage du serveur
```bash
# Terminal 1 : Django
python manage.py runserver

# Terminal 2 : Ou utiliser la commande management
# (Le scheduler démarre automatiquement au lancement de Django)
```

---

## 🧪 Tester immédiatement

```bash
python test_voice_alarm.py
```

Cela va :
1. ✅ Lister les voix pyttsx3 disponibles
2. ✅ Tester la lecture via pyttsx3
3. ✅ Tester le fallback système
4. ✅ Afficher la configuration vocale actuelle
5. ✅ Reproduire un message d'alarme complet

---

## 📱 Test via interface Web

1. Ouvrir `http://localhost:8000/`
2. Créer une tâche :
   - **Nom** : "Test d'alarme"
   - **Date** : Aujourd'hui
   - **Heure** : 2 minutes à partir de maintenant
3. Attendre que l'horloge du haut arrive à cette heure
4. **Résultat attendu** : 
   - Son vocal "Attention. C'est le moment de: Test d'alarme."
   - Tâche marquée comme complétée ✓

---

## ⚙️ Configuration vocale (optionnel)

1. Cliquer sur **"Configuration voix"** en haut
2. Ajuster les paramètres :
   - **Voix** : Sélectionner une voix française (auto-sélection par défaut)
   - **Vitesse** : 155 mpm (défaut professionnel)
   - **Volume** : 1.0 (maximum, audible)
   - **Tonalité** : 100 (neutre)
   - **Répétitions** : 1-5 (nombre de fois que l'alarme est lue)
   - **Pause** : 0-10 secondes entre deux lectures
   - **Texte pré-alarme** : "Attention" (avant le nom de la tâche)
   - **Fallback système** : ✓ (activé)
3. Cliquer **"Enregistrer"**
4. Créer une nouvelle tâche pour tester les nouveaux réglages

---

## 🔍 Diagnostic des problèmes

### Pas de son du tout

**Étape 1 : Vérifier le volume système**
```bash
# Linux
amixer get Master
# macOS
osascript -e 'output volume of (get volume settings)'
# Windows
# Contrôle du volume via barre de tâches
```

**Étape 2 : Tester pyttsx3 directement**
```bash
python manage.py shell
>>> from task.scheduler import speak_text
>>> speak_text("Test de son")
```
*(Devrait produire un son)*

**Étape 3 : Vérifier les logs**
```bash
# Dans un terminal à part, si DEBUG=True
tail -f /tmp/django.log
# Ou lancer Django avec :
python manage.py runserver --verbosity=2
```

**Étape 4 : Tester le fallback système**
```bash
# Linux
spd-say -l fr "Test de son"
espeak-ng -v fr "Test de son"

# macOS
say "Test de son"

# Windows (PowerShell)
Add-Type -AssemblyName System.Speech
(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("Test de son")
```

---

### Voix française non trouvée

**Windows** :
- Aller dans Paramètres > Confidentialité et sécurité > Paramètres de la parole
- Télécharger une voix française (ex: Hortense)
- Relancer Django

**Linux** :
```bash
# Installer le paquet français pour espeak-ng
sudo apt install espeak-ng-mbrola-fr1

# Tester
espeak-ng -v fr "Bonjour"
```

**macOS** :
- Préférences Système > Accessibilité > Parole > Sélectionner "Français"

---

### Les tâches ne se déclenchent pas

**Cause 1 : Fuseau horaire incorrect**
```bash
python manage.py shell
>>> from django.utils import timezone
>>> print(timezone.now())  # Vérifier l'heure affichée
```
Correction dans `config/settings.py` :
```python
TIME_ZONE = 'Europe/Paris'  # (ou votre fuseau)
USE_TZ = True
```

**Cause 2 : Tâche en passé**
- Créer une tâche à une heure future (au moins 1 minute)
- Vérifier que la date d'aujourd'hui est correcte

**Cause 3 : Scheduler non actif**
- Vérifier que Django a démarré (chercher "Scheduler started" dans les logs)
- Vérifier que `should_start_scheduler()` retourne True
- Vérifier que le processus n'est pas multi-process (runserver est ok)

---

### Les tâches se déclenchent mais sans son

**Vérifier les logs pyttsx3** :
```bash
python manage.py shell
>>> import logging
>>> logging.basicConfig(level=logging.DEBUG)
>>> from task.scheduler import speak_text
>>> speak_text("Test")  # Vérifier les logs
```

**Vérifier le moteur TTS choisi** :
```bash
python manage.py shell
>>> from task.voice import get_available_voices
>>> voices = get_available_voices()
>>> for v in voices:
...     print(f"{v['name']} - {v['languages']}")
```

---

## 🚀 Déploiement en production

### 1. Vérifier les dépendances systèmes
```bash
# Prod server (Linux)
sudo apt install espeak-ng speech-dispatcher
```

### 2. Configurer les logs
```python
# config/settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/django/alarm.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
        },
    },
    'loggers': {
        'task.scheduler': {'handlers': ['file'], 'level': 'INFO'},
        'task.voice': {'handlers': ['file'], 'level': 'INFO'},
    },
}
```

### 3. Vérifier que le scheduler démarre
```python
# config/settings.py, dans INSTALLED_APPS :
INSTALLED_APPS = [
    ...
    'task.apps.TaskConfig',  # Important: utiliser TaskConfig, pas 'task'
]
```

### 4. Utiliser Gunicorn/Uwsgi + systemd
```bash
# systemd service (/etc/systemd/system/task-alarm.service)
[Unit]
Description=Task Alarm Django App
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/path/to/task_alarm/task
ExecStart=/usr/bin/gunicorn config.wsgi:application --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 📊 Monitoring

### Vérifier les tâches expirées (API)
```bash
curl http://localhost:8000/api/due-tasks/
# Réponse: {"due_tasks": [{"id": 1, "name": "Réunion"}]}
```

### Logs du scheduler
```bash
# Afficher les 20 dernières lignes (temps réel)
tail -f /path/to/django/logs
```

### Nombre d'alarmes lues
```bash
grep "Alarme lue avec succes" /path/to/django/logs | wc -l
```

---

## ✅ Checklist de vérification

- [ ] `pip install -r requirements.txt` réussi
- [ ] Dépendances système installées (espeak-ng, speech-dispatcher sur Linux)
- [ ] Django démarre sans erreur
- [ ] `python test_voice_alarm.py` passe tous les tests
- [ ] Une tâche créée se déclenche avec son à l'heure prévue
- [ ] Configuration vocale est sauvegardée
- [ ] Fallback client (Web Speech API) fonctionne
- [ ] Les logs montrent "Alarme lue avec succes"

---

## 🎤 Pour supporter plus de langues

Modifier `voice.py` pour détecter d'autres langues :
```python
def _is_language_voice(voice, lang_code):
    text_parts = [voice.get('id', ''), voice.get('name', '')]
    # Ajouter support pour 'de', 'es', 'en', etc.
```

Puis adapter `scheduler.py` pour lire des alarmes multilingues.

---

## 📞 Support et Déboggage

**Activer le mode verbose** :
```bash
export DJANGO_LOG_LEVEL=DEBUG
python manage.py runserver --verbosity=3
```

**Redémarrer le scheduler** :
- Arrêter Django (`Ctrl+C`)
- Relancer (`python manage.py runserver`)

**Forcer une alarme pour test** :
```bash
python manage.py shell
>>> from task.scheduler import enqueue_alarm_speech
>>> enqueue_alarm_speech(task_id=999, task_name="Test immédiat")
# L'alarme se déclenchera dans les 2 secondes
```
