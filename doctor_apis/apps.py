from django.apps import AppConfig


class DoctorApisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'doctor_apis'

    def ready(self):
        import doctor_apis.signals
