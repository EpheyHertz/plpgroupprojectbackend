"""
ASGI config for doctor_ai project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path
from doctor_apis.consumers import TranscriptionConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doctor_ai.settings')

# ASGI application for HTTP requests
django_asgi_app = get_asgi_application()

# ASGI routing for HTTP and WebSocket
application = ProtocolTypeRouter({
    "http": django_asgi_app,  # Handles HTTP requests
    "websocket": AuthMiddlewareStack(
        URLRouter([
            path("ws/transcribe/", TranscriptionConsumer.as_asgi()),  # WebSocket route
        ])
    ),
})
