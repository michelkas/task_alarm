# Guide Complet : Alarmes Vocales en Français avec Task Alarm

## 🎯 Vue d'ensemble

Ce projet intègre un système robuste d'alarmes vocales en français utilisant :
- **pyttsx3** : synthèse vocale Python (moteur primaire)
- **fallback système** : spd-say/espeak-ng/espeak sur Linux, `say` sur macOS, PowerShell sur Windows
- **Web Speech API** : lecture côté client si le serveur est muet

## ⚙️ Architecture vocale

### 1. **voice.py** - Gestion des voix disponibles
- **`get_available_voices()`** : liste les voix pyttsx3 avec détection du driver adapté à la plateforme
- **`pick_french_voice_id()`** : sélectionne la meilleure voix française (Hortense, Audrey, Amélie sur Windows)
- **`resolve_french_voice_settings()`** : prépare réglages professionnels (vitesse=155 mpm, volume=1.0, pitch=100)

### 2. **scheduler.py** - Thread de synthèse vocale
#### Flux :
1. **`_run_loop()`** (main loop) : scanne les tâches expirées chaque seconde
2. **`enqueue_alarm_speech()`** : enfile l'alarme dans une queue thread-safe
3. **`_speaker_loop()`** (worker thread) : lit les alarmes une par une
   - Maintient un **moteur pyttsx3 unique** (pas d'initialisation/destruction répétées)
   - Fallback via **`_system_tts_fallback()`** si pyttsx3 échoue
4. **`speak_text()`** : réconcilie pyttsx3 et fallback système

#### Gestion des erreurs :
- ✅ Thread-safe avec `threading.Lock()`
- ✅ Pas de blocage : moteur réutilisé entre alarmes
- ✅ Fallback multiplateforme en cas de silence

### 3. **views.py & index.html** - Fallback client (Web Speech API)
- Endpoint `/api/due-tasks/` retourne les tâches expirées en JSON
- Script JS vérifie toutes les 5 secondes + lit via `SpeechSynthesisUtterance`
- Langue forcée à "fr-FR" et volume à 100%

---

## 🚀 Installation

### Prérequis
- Python 3.8+
- Django 3.2+
- Linux/macOS/Windows

### Étape 1 : Installer pyttsx3
```bash
pip install -r requirements.txt
```

### Étape 2 : Installer les dépendances système

#### **Linux (Ubuntu/Debian)**
```bash
sudo apt update
sudo apt install espeak-ng speech-dispatcher
```
Pour tester localement :
```bash
espeak-ng -v fr "Bonjour"
spd-say -l fr "Ceci est un test"
```

#### **macOS**
```bash
# La commande 'say' est incluse nativement
say "Bonjour"  # Doit fonctionner immédiatement
```

#### **Windows**
- SAPI5 est inclus nativement (PowerShell)
- Pas d'installation supplémentaire requise

### Étape 3 : Configuration Django
```bash
python manage.py migrate
```

---

## 🧪 Tests d'alarme vocale

### Test 1 : Vérifier les voix disponibles (CLI)
```bash
python manage.py shell
>>> from task.voice import get_available_voices, pick_french_voice_id
>>> voices = get_available_voices()
>>> for v in voices:
...     print(f"{v['name']} (ID: {v['id']})")
>>> french_id = pick_french_voice_id(voices)
>>> print(f"Voix française sélectionnée: {french_id}")
```

### Test 2 : Synthèse vocale simple (CLI)
```bash
python manage.py shell
>>> from task.scheduler import speak_text
>>> speak_text("C'est le moment de: Réunion important.")
```
**Attendu** : son produit en français clair

### Test 3 : Crédulité d'alarme via l'interface
1. Aller sur `http://localhost:8000/`
2. Créer une tâche avec :
   - Nom : "Appel client"
   - Date : Aujourd'hui
   - Heure : 1 minute à partir de maintenant
3. Attendre que l'heure se déclenche
4. **Résultat attendu** : 
   - Alarme vocale "Attention. C'est le moment de: Appel client."
   - Tâche marquée comme inactive

### Test 4 : Configuration vocale
1. Cliquer sur "Configuration voix"
2. Tester les curseurs :
   - **Vitesse** : 155 mpm (défaut français)
   - **Volume** : 1.0 (audible)
   - **Tonalité** : 100 (neutre)
   - **Répétitions** : 1-5 lectures successives
   - **Pause entre répétitions** : 0-10 secondes
3. Enregistrer et créer une nouvelle tâche pour vérifier

---

## 📋 Troubleshooting

### ❌ Pas de son du tout

**Diagnostic** :
1. Vérifier le volume système
2. Tester manuellement en CLI :
   ```bash
   python manage.py shell
   >>> from task.scheduler import _system_tts_fallback
   >>> _system_tts_fallback("Test de son")
   ```
3. Vérifier les logs Django :
   ```bash
   # Dans settings.py, activer DEBUG et voir les logs console/fichier
   LOGGING = {'loggers': {'task.scheduler': {'level': 'DEBUG'}}}
   ```

### ❌ Voix française non détectée
**Solution** :
1. **Windows** : Installer une voix française SAPI5
   - Panneau de configuration > Paramètres régionaux
   - Ou télécharger Hortense via Microsoft Store

2. **Linux** : Installer espeak-ng avec voix française
   ```bash
   sudo apt install espeak-ng-mbrola-fr1
   ```

3. **macOS** : Ajouter voix française
   - Préférences Système > Accessibilité > Parole > Sélectionner "Français"

### ❌ Thread speaker crash (logs rouges)
**Cause** : Généralement erreur DB ou pyttsx3
**Solution** : 
- Thread redémarre automatiquement via `_ensure_speaker_thread()`
- Vérifier les logs pour l'erreur sous-jacente

### ⚠️ Alarmes décalées ou manquées
**Cause** : Fuseau horaire
**Solution** :
- Vérifier `settings.py` : `TIME_ZONE = 'Europe/Paris'` (etc.)
- Tâche utilise `timezone.localtime()` pour comparaison

---

## 🔧 Architecture technique détaillée

### Thread-safety
```python
# Chaque alarme a son ID unique en pending_task_ids
# Deux threads ne peuvent jamais traiter la même tâche
_pending_lock = threading.Lock()
_pending_task_ids = set()  # Évite doublons
```

### Moteur pyttsx3 réutilisé (performance)
```python
def _speaker_loop():
    engine = None  # Initialisé une seule fois par worker
    while True:
        # ... traiter alarmes
        # Si engine = None, on le réinit (crash détecté)
        if engine is None:
            engine = _create_pyttsx3_engine()
```

### Fallback en cascade
1. pyttsx3 (moteur primaire)
2. spd-say (Linux - souvent plus audible)
3. espeak-ng (Linux alternative)
4. espeak (Linux legacy)
5. PowerShell SAPI (Windows)
6. say (macOS)
7. Web Speech API client (fallback ultime)

---

## 📝 Fichiers modifiés

| Fichier | Rôle |
|---------|------|
| `voice.py` | Gestion des voix + détection driver pyttsx3 |
| `scheduler.py` | Thread de synthèse vocale + fallback système |
| `views.py` | API JSON pour tâches expirées (client JS) |
| `urls.py` | Route `/api/due-tasks/` |
| `templates/tasks/index.html` | Fallback Web Speech API + polling 5s |
| `requirements.txt` | dépendances Python (inchangé mais documenté) |

---

## 🎤 Multiplateforme confirmé

| Plateforme | Moteur primaire | Fallback | Testé ✅ |
|-----------|-----------------|----------|---------|
| Windows | SAPI5 (pyttsx3) | PowerShell SAPI | ✅ |
| Linux | espeak-ng (pyttsx3) | spd-say/espeak-ng | ✅ |
| macOS | nsss (pyttsx3) | say | ✅ |

---

## 🔐 Sécurité

- ✅ Pas d'injection: texte échappé avant PowerShell
- ✅ Timeout 120s sur chaque commande TTS
- ✅ Subprocess.DEVNULL pour éviter les fuites
- ✅ Thread-safe: locks sur structures partagées

---

## 📞 Support

Pour les questions :
1. Activer DEBUG et vérifier logs (ex: `/api/due-tasks/` returns `[]` → pas de tâche expirée)
2. Tester la voix directement : `speak_text("Test")` en Python shell
3. Vérifier les voix disponibles : `get_available_voices()`
