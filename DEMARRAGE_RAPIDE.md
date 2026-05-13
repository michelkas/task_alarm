# 🚀 GUIDE DE DÉMARRAGE RAPIDE

## En 10 minutes, démarrez avec des alarmes vocales françaises !

### ⏱️ Étape 1 : Installation (3 min)

```bash
# Naviguer dans le dossier projet
cd /code/task_alarm/task

# Installer les dépendances Python
pip install -r requirements.txt

# Linux uniquement : installer TTS système
sudo apt install espeak-ng speech-dispatcher libspeechd-dev

# Migrations Django
python manage.py migrate
```

### ⏱️ Étape 2 : Tester le diagnostic (2 min)

```bash
python test_voice_alarm.py
```

**Résultat attendu** :
```
✅ PASS - Voix disponibles
✅ PASS - Lecture pyttsx3
✅ PASS - Fallback système
✅ PASS - Configuration vocale
✅ PASS - Message d'alarme

🎉 Tous les tests sont passés!
```

### ⏱️ Étape 3 : Lancer le serveur (1 min)

```bash
python manage.py runserver
```

Ouvrir le navigateur : **http://localhost:8000/**

### ⏱️ Étape 4 : Créer et tester une tâche (4 min)

1. Dans l'interface, remplir :
   - **Nom** : "Test d'alarme"
   - **Date** : Aujourd'hui
   - **Heure** : Maintenant + 2 minutes

2. Cliquer **"Ajouter"**

3. **Attendre l'heure** → Écouter l'alarme vocale !

4. **Résultat attendu** :
   ```
   "Attention. C'est le moment de: Test d'alarme."
   ```

---

## 🎤 Configuration vocale (optionnel)

Cliquer sur **"Configuration voix"** pour :

- ✅ Sélectionner une voix française (auto par défaut)
- ✅ Ajuster vitesse, volume, tonalité
- ✅ Ajouter un texte pré-alarme custom ("Alerte", "Important", etc.)
- ✅ Configurer répétitions (1-5 fois)

---

## 🔧 Troubleshooting rapide

| Problème | Solution |
|----------|----------|
| **Pas de son ?** | Vérifier volume système + exécuter `python test_voice_alarm.py` |
| **Alarme ne déclenche pas ?** | Créer tâche à heure future + vérifier fuseau horaire |
| **Voix française absent ?** | Linux : `sudo apt install espeak-ng-mbrola-fr1` |
| **Thread crash ?** | Redémarrer Django (`Ctrl+C` puis relancer) |

Consulter [INSTALLATION_DEPLOIEMENT.md](INSTALLATION_DEPLOIEMENT.md) pour debug complet.

---

## 📚 Prochaines étapes

1. **Lire le guide complet** : [GUIDE_ALARMES_VOCALES.md](GUIDE_ALARMES_VOCALES.md)
2. **Explorer la configuration** : [AMELIORATIONS_TECHNIQUES.md](AMELIORATIONS_TECHNIQUES.md)
3. **Déployer en production** : [INSTALLATION_DEPLOIEMENT.md](INSTALLATION_DEPLOIEMENT.md)

---

## ✅ Vous êtes prêt !

Les alarmes vocales en français sont maintenant fonctionnelles. 🎉

- 🔊 **Son produit** : Clair et audible
- 🇫🇷 **Langue** : Français automatiquement détecté
- 🔄 **Fiable** : Fallback multi-étage
- 📱 **Multiplateforme** : Windows, Linux, macOS

**Profitez de votre planificateur vocal ! 🚀**
