# doctor_apis/views.py
from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated
import assemblyai as aai
from django.contrib.auth import authenticate, login, logout
import os
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes,authentication_classes
from rest_framework.response import Response
from django.core.files.storage import default_storage
from .models import Doctor, Patient, Appointment
from .serializers import DoctorSerializer, PatientSerializer, AppointmentSerializer
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from rest_framework.authentication import TokenAuthentication
from django.conf import settings

# Configure AssemblyAI API key
aai.settings.api_key = os.getenv('AAI_API_KEY')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def protected_view(request):
    """
    A view that requires the user to be authenticated.
    """
    return Response({'message': 'You have access to this view!'})

# ViewSets for the Doctor, Patient, and Appointment models
class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer
    permission_classes = [IsAuthenticated]

class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]

class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]

# View for handling audio file uploads and real-time transcription
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def transcribe_audio(request):
    """
    Handle audio file uploads and perform real-time transcription using AssemblyAI.
    """
    if 'file' not in request.FILES:
        return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

    audio_file = request.FILES['file']
    file_path = default_storage.save(audio_file.name, audio_file)
    full_path = default_storage.path(file_path)

    def on_open(session_opened: aai.RealtimeSessionOpened):
        """
        Callback function when the real-time transcription session is opened.
        """
        print("Session ID:", session_opened.session_id)

    def on_data(transcript: aai.RealtimeTranscript):
        """
        Callback function to handle real-time transcription data.
        """
        if not transcript.text:
            return
        if isinstance(transcript, aai.RealtimeFinalTranscript):
            return transcript.text
        return None

    def on_error(error: aai.RealtimeError):
        """
        Callback function to handle errors during transcription.
        """
        print("An error occurred:", error)
        return str(error)

    def on_close():
        """
        Callback function when the real-time transcription session is closed.
        """
        print("Closing Session")

    transcriber = aai.RealtimeTranscriber(
        sample_rate=16_000,
        on_data=on_data,
        on_error=on_error,
        on_open=on_open,
        on_close=on_close,
    )

    try:
        transcriber.connect()
        microphone_stream = aai.extras.MicrophoneStream(sample_rate=16_000)
        transcriber.stream(microphone_stream)
        
        # Process the audio file and get transcription
        transcription_result = None
        with open(full_path, 'rb') as f:
            transcription_result = transcriber.transcribe(f)
        
        transcriber.close()
        return Response({'transcription': transcription_result}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def user_signup(request):
    """
    Handle user registration.
    """
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')

    if not username or not email or not password:
        return Response({'error': 'Username, email, and password are required'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(email=email).exists():
        return Response({'error': 'Email is already registered'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Create the user
        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()
        
        # Send a welcome email
        send_mail(
            'Welcome to Our Platform',
            'Thank you for registering with us!',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        
        return Response({'message': 'User registered successfully'}, status=status.HTTP_201_CREATED)
    except ValidationError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def user_login(request):
    """
    Handle user login with email and password.
    """
    email = request.data.get('email')
    password = request.data.get('password')

    if not email or not password:
        return Response({'error': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)

    # Authenticate user (using username field for email)
    user = User.objects.filter(email=email).first()
    if user is not None:
        user = authenticate(request, username=user.username, password=password)
        if user is not None:
            login(request, user)
            return Response({'message': 'Login successful'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid email or password'}, status=status.HTTP_401_UNAUTHORIZED)
    else:
        return Response({'error': 'Invalid email or password'}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def user_logout(request):
    """
    Handle user logout.
    """
    logout(request)
    return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)
