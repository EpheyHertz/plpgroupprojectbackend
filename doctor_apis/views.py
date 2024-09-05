# doctor_apis/views.py
# from django.contrib.auth.models import User
from .models import User
from rest_framework.permissions import IsAuthenticated
import assemblyai as aai
from django.contrib.auth import authenticate, login, logout
import os
from django.contrib import messages
from rest_framework.views import APIView
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes,authentication_classes
from rest_framework.response import Response
from django.core.files.storage import default_storage
from .models import Profile, Doctor, Patient, Appointment
from .serializers import UserSerializer, ProfileSerializer,DoctorSerializer, PatientSerializer, AppointmentSerializer
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
# from .forms import UserUpdateForm, ProfileUpdateForm
from rest_framework.authentication import TokenAuthentication
from django.conf import settings
from django.urls import reverse_lazy
from django.views.generic import View
from rest_framework.exceptions import PermissionDenied

# Configure AssemblyAI API key
aai.settings.api_key = os.getenv('AAI_API_KEY')



class UserDetailView(APIView):
    def get(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated:
            try:
                # Serialize the user with related profile and appointments
                serializer = UserSerializer(user)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'error': 'User not authenticated'}, status=status.HTTP_401_UNAUTHORIZED)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def protected_view(request):
    """
    A view that requires the user to be authenticated.
    """
    return Response({'message': 'You have access to this view!'})

class UserUpdateView(APIView):
    def get(self, request, *args, **kwargs):
        # Get the user instance
        user = request.user

        # Check if the user has a profile
        try:
            profile = user.profile
            profile_data = {
                'gender': profile.gender,
                'role': profile.role,
                'phone_number': profile.phone_number,
                'address': profile.address,
            }
            
            # Include role-specific details
            if profile.role == 'doctor':
                doctor = Doctor.objects.filter(profile=profile).first()
                doctor_data = DoctorSerializer(doctor).data if doctor else {}
                profile_data.update({'doctor_details': doctor_data})
            elif profile.role == 'patient':
                patient = Patient.objects.filter(profile=profile).first()
                patient_data = PatientSerializer(patient).data if patient else {}
                profile_data.update({'patient_details': patient_data})

        except Profile.DoesNotExist:
            profile_data = {
                'gender': None,
                'role': None,
                'phone_number': None,
                'address': None,
            }

        # Return user data along with profile data
        return Response({
            'user': {
                'username': user.username,
                'email': user.email,
                'role': getattr(user, 'role', None),
            },
            'profile': profile_data
        }, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        user = request.user
        profile = getattr(user, 'profile', None)

        # Serialize user data
        user_serializer = UserSerializer(user, data=request.data, partial=True)

        # Serialize profile data if it exists
        profile_serializer = ProfileSerializer(profile, data=request.data, partial=True) if profile else None

        # Validate and save user data
        if user_serializer.is_valid():
            user_serializer.save()
        else:
            return Response({
                'user_errors': user_serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle role-specific data
        role = user.role
        if profile_serializer:
            if profile_serializer.is_valid():
                profile_serializer.save()
                # Save role-specific data
                if role == 'doctor':
                    doctor_data = request.data.get('doctor_details', {})
                    doctor, created = Doctor.objects.get_or_create(profile=profile)
                    doctor_serializer = DoctorSerializer(doctor, data=doctor_data, partial=True)
                    if doctor_serializer.is_valid():
                        doctor_serializer.save()
                    else:
                        return Response({
                            'doctor_errors': doctor_serializer.errors,
                        }, status=status.HTTP_400_BAD_REQUEST)
                elif role == 'patient':
                    patient_data = request.data.get('patient_details', {})
                    patient, created = Patient.objects.get_or_create(profile=profile)
                    patient_serializer = PatientSerializer(patient, data=patient_data, partial=True)
                    if patient_serializer.is_valid():
                        patient_serializer.save()
                    else:
                        return Response({
                            'patient_errors': patient_serializer.errors,
                        }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'profile_errors': profile_serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Create a new profile if it does not exist
            profile_serializer = ProfileSerializer(data=request.data, partial=True)
            if profile_serializer.is_valid():
                profile = profile_serializer.save(user=user)  # Ensure the profile is associated with the user
                
                # Save role-specific data
                if role == 'doctor':
                    doctor_data = request.data.get('doctor_details', {})
                    doctor_serializer = DoctorSerializer(data=doctor_data)
                    if doctor_serializer.is_valid():
                        doctor = doctor_serializer.save(profile=profile)
                    else:
                        return Response({
                            'doctor_errors': doctor_serializer.errors,
                        }, status=status.HTTP_400_BAD_REQUEST)
                elif role == 'patient':
                    patient_data = request.data.get('patient_details', {})
                    patient_serializer = PatientSerializer(data=patient_data)
                    if patient_serializer.is_valid():
                        patient = patient_serializer.save(profile=profile)
                    else:
                        return Response({
                            'patient_errors': patient_serializer.errors,
                        }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'profile_errors': profile_serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'message': 'Your profile has been updated!',
            'user': user_serializer.data,
            'profile': profile_serializer.data if profile_serializer else None
        }, status=status.HTTP_200_OK)
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
    queryset = Patient.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        user = self.request.user
        # Filter appointments based on the user
        return Appointment.objects.filter(user=user)


    def get_queryset(self):
        """
        Override the default queryset to return only the appointments 
        for the currently authenticated user.
        """
        return Appointment.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """
        Override this method to ensure the appointment is created 
        for the currently authenticated user.
        """
        serializer.save(user=self.request.user)

    def update(self, request, *args, **kwargs):
        """
        Override this method to allow users to update only their own appointments.
        """
        appointment = self.get_object()

        # Check if the appointment belongs to the logged-in user
        if appointment.user != request.user:
            raise PermissionDenied("You do not have permission to edit this appointment.")

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Override this method to allow users to delete only their own appointments.
        """
        appointment = self.get_object()

        # Check if the appointment belongs to the logged-in user
        if appointment.user != request.user:
            raise PermissionDenied("You do not have permission to delete this appointment.")

        return super().destroy(request, *args, **kwargs)

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

class UserSignupView(APIView):
    """
    Handle user registration as a doctor or a patient.
    """

    def post(self, request):
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        role = request.data.get('role')  # Accept role (doctor or patient)

        # Check for required fields
        if not username or not email or not password or not role:
            return Response({'error': 'Username, email, password, and role are required'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate role
        if role not in ['doctor', 'patient']:
            return Response({'error': 'Role must be either doctor or patient'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if email is already registered
        if User.objects.filter(email=email).exists():
            return Response({'error': 'Email is already registered'}, status=status.HTTP_400_BAD_REQUEST)

        # Create the user object but do not save it yet
        user = User(username=username, email=email, role=role)
        user.set_password(password)

        try:
            # Try to send the welcome email first
            try:
                send_mail(
                    'Welcome to Our Platform',
                    f'Thank you for registering as a {role}!',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
            except Exception as e:
                return Response({'error': f'Failed to send welcome email.Please make sure you provide a Working Email: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # If email was sent successfully, save the user
            user.save()

            # Create or update the profile with the role from the user
            profile, created = Profile.objects.get_or_create(user=user)
            profile.role = role
            profile.save()

            # Create Doctor or Patient instance based on role
            if role == 'doctor':
                Doctor.objects.get_or_create(profile=profile, defaults={'name': username, 'specialty': 'General'})
            elif role == 'patient':
                Patient.objects.get_or_create(profile=profile, defaults={'name': username, 'age': 0, 'medical_history': ''})

            return Response({'message': f'User registered successfully as {role}'}, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
class UserLoginView(APIView):
    """
    Handle user login with email and password, and authenticate based on the role (doctor/patient).
    """

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        role = request.data.get('role')  # Accept role (doctor or patient)

        if not email or not password or not role:
            return Response({'error': 'Email, password, and role are required'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email=email, role=role).first()  # Filter by email and role

        if user is not None:
            user = authenticate(request, username=user.username, password=password)
            if user is not None:
                login(request, user)
                return Response({'message': 'Login successful as {}'.format(role)}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Invalid email or password'}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            return Response({'error': 'Invalid email, password, or role'}, status=status.HTTP_401_UNAUTHORIZED)

    def get(self, request):
        """
        Check if the user is logged in.
        """
        if request.user.is_authenticated:
            return Response({'message': 'User is authenticated'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'User is not authenticated'}, status=status.HTTP_401_UNAUTHORIZED)
class UserLogoutView(APIView):
    """
    Handle user logout.
    """
    def get(self, request):
        # Log out the user
        logout(request)
        return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)