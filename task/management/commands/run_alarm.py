import signal
import sys

from django.core.management.base import BaseCommand

from task.scheduler import run_scheduler_forever, stop_scheduler


class Command(BaseCommand):
    help = "Surveille les taches et declenche les alarmes vocales a l'heure prevue."

    def handle(self, *args, **options):
        self.stdout.write("Demarrage du surveillant d'alarmes vocales...")

        def signal_handler(sig, frame):
            self.stdout.write("\nArret demande, liberation du moteur vocal...")
            stop_scheduler(wait=True)
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            run_scheduler_forever()
        except KeyboardInterrupt:
            signal_handler(signal.SIGINT, None)
