from django.apps import AppConfig


class TaskConfig(AppConfig):
    name = 'task'

    def ready(self):
        from .scheduler import start_scheduler
        start_scheduler()
