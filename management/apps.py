from django.apps import AppConfig


class ManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'management'
    verbose_name = 'System Management'
    
    def ready(self):
        # Import any signals or other initialization code here if needed
        pass
