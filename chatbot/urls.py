from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    path('process/', views.process_query, name='process_query'),
]
