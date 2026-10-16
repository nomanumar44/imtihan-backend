from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        import core.signals  # noqa: F401
        import core.quality  # noqa: F401  (MCQ change-history signals)
