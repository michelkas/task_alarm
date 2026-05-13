# TODO - Task Alarm (voix)

## Étape 1: Logs + diagnostic
- [ ] Ajouter des logs détaillés dans `task/scheduler.py` (thread vocal, init pyttsx3, fallback, succès/échec par tâche).
- [ ] Ajouter un diagnostic court optionnel via variable d’environnement (ex: `VOICE_DIAGNOSTIC=1`) qui tente de parler une phrase et log le résultat.

## Étape 2: Correctif potentiel
- [ ] Corriger `task/management/commands/run_alarm.py` si un import manquant (`datetime`) provoque une erreur sur la boucle alternative.

## Étape 3: Vérification
- [ ] Relancer le serveur / redémarrer le worker.
- [ ] Déclencher une tâche et vérifier dans les logs que le thread TTS s’exécute et que le fallback marche si pyttsx3 échoue.

