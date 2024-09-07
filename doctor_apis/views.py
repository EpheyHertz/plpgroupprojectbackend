# doctor_apis/views.py
# from django.contrib.auth.models import User
from .models import User
from rest_framework.permissions import IsAuthenticated
import assemblyai as aai
from django.contrib.auth import authenticate, login, logout
import os
import io
import requests
import asyncio
import websockets
import base64
import json
import pyaudio
from django.shortcuts import render
from django.core.files.uploadedfile import InMemoryUploadedFile
from rest_framework import generics
from django.contrib import messages
from rest_framework.views import APIView
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes,authentication_classes
from rest_framework.response import Response
from django.core.files.storage import default_storage
from .models import Profile, Doctor, Patient, Appointment
from .serializers import UserSerializer, ProfileSerializer,DoctorSerializer, PatientSerializer, AppointmentSerializer,AppointmentCreateSerializer
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
# from .forms import UserUpdateForm, ProfileUpdateForm
from rest_framework.authentication import TokenAuthentication
from django.conf import settings
from django.urls import reverse_lazy
from django.views.generic import View
import google.generativeai as genai
from rest_framework.exceptions import PermissionDenied

# Configure AssemblyAI API key
aai.settings.api_key = settings.AAI_APIKEY
print(aai.settings.api_key)
GEMINI_AI_API_KEY=settings.GEMINI_AI_API_KEY
genai.configure(api_key=GEMINI_AI_API_KEY)

class UserAppointmentsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AppointmentSerializer

    def get_queryset(self):
        user = self.request.user
        if user.profile.role == 'doctor':
            # Check if doctor_profile exists
            if hasattr(user.profile, 'doctor_profile'):
                return Appointment.objects.filter(doctor=user.profile.doctor_profile)
            return Appointment.objects.none()
        elif user.profile.role == 'patient':
            # Check if patient_profile exists
            if hasattr(user.profile, 'patient_profile'):
                return Appointment.objects.filter(patient=user.profile.patient_profile)
            return Appointment.objects.none()
        return Appointment.objects.none()
    

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

class BookAppointmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Ensure the user is a patient
        if not hasattr(request.user, 'profile') or request.user.profile.role != 'patient':
            return Response({'error': 'Only patients can book appointments.'}, status=status.HTTP_403_FORBIDDEN)

        # Handle the appointment creation
        serializer = AppointmentCreateSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class CancelAppointmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, appointment_id, *args, **kwargs):
        try:
            # Fetch the appointment
            appointment = Appointment.objects.get(id=appointment_id)
        except Appointment.DoesNotExist:
            return Response({'error': 'Appointment not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        role = user.profile.role

        # Check if the user is either the patient or the doctor of the appointment
        if role == 'patient' and appointment.patient != user.profile.patient_profile:
            return Response({'error': 'You are not authorized to cancel this appointment.'}, status=status.HTTP_403_FORBIDDEN)

        if role == 'doctor' and appointment.doctor != user.profile.doctor_profile:
            return Response({'error': 'You are not authorized to cancel this appointment.'}, status=status.HTTP_403_FORBIDDEN)

        # Mark the appointment as canceled
        canceled_by = "doctor" if role == 'doctor' else "patient"
        appointment.cancel(canceled_by_user=canceled_by)

        # Send email notifications based on who canceled the appointment
        doctor = appointment.doctor.profile.user
        patient = appointment.patient.profile.user
        if role == 'patient':
            self.notify_cancellation(doctor, patient, canceled_by="patient")
        elif role == 'doctor':
            self.notify_cancellation(doctor, patient, canceled_by="doctor")

        return Response({'message': 'Appointment successfully canceled.'}, status=status.HTTP_200_OK)

    def notify_cancellation(self, doctor, patient, canceled_by):
        if canceled_by == "patient":
            # Notify the doctor that the patient canceled the appointment
            send_mail(
                subject="Appointment Canceled by Patient",
                message=f"Dear Dr. {doctor.username},\n\n"
                        f"The appointment with {patient.username} has been canceled by the patient.\n\n"
                        f"Please reach out if you have any questions.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[doctor.email],
                fail_silently=False,
            )
            # Notify the patient that the appointment was successfully canceled
            send_mail(
                subject="Appointment Canceled",
                message=f"Dear {patient.username},\n\n"
                        f"Your appointment with Dr. {doctor.username} has been successfully canceled.\n\n"
                        f"If you have any questions, feel free to contact us.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[patient.email],
                fail_silently=False,
            )

        elif canceled_by == "doctor":
            # Notify the patient that the doctor canceled the appointment
            send_mail(
                subject="Appointment Canceled by Doctor",
                message=f"Dear {patient.username},\n\n"
                        f"Your appointment with Dr. {doctor.username} has been canceled by the doctor.\n\n"
                        f"Please reach out if you have any questions.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[patient.email],
                fail_silently=False,
            )
            # Notify the doctor that they successfully canceled the appointment
            send_mail(
                subject="Appointment Successfully Canceled",
                message=f"Dear Dr. {doctor.username},\n\n"
                        f"You have successfully canceled your appointment with {patient.username}.\n\n"
                        f"If you have any questions, feel free to contact us.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[doctor.email],
                fail_silently=False,
            )
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

class DoctorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for doctors allowing only GET requests.
    """
    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get']  # Only allow GET requests

class PatientViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for patients allowing only GET requests.
    """
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get']  # Only allow GET requests

class AppointmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for appointments allowing only GET requests for the authenticated user's appointments.
    """
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get']  # Only allow GET requests

    def get_queryset(self):
        user = self.request.user
        # Filter appointments based on the authenticated user
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
def get_assemblyai_client():
    client = aai.Client(api_key=settings.AAI_KEY)
    return client
# View for handling audio file uploads and real-time transcription
class Transcribe_audio(APIView):
    def get(self,request):
        return render(request,'./transcribe.html')


 
import threading

class TranscribeAudioView(APIView):
    permission_classes = [IsAuthenticated]
    aai.settings.api_key = settings.AAI_APIKEY

    def post(self, request, *args, **kwargs):
        """
        Handle real-time audio transcription and diagnosis using AssemblyAI for transcription 
        and Lemur for diagnosis based on symptoms.
        """
        transcription_result = []  # Store the transcription as an array of strings.
        stop_timer = None  # Initialize a timer for stopping the transcription.
        action = request.data.get('action', 'start')  # Get action from frontend ('start' or 'stop')

        prompt = """ 
        Patient Information:
        derive it from the real-time transcription.
        Age: [Patient's Age]
        Gender: [Patient's Gender]
        Medical History: [Relevant Medical History]
        Current Medications: [Current Medications]
        Known Allergies: [Known Allergies]
        
        Transcription of Patient's Symptoms: [Patient's Transcribed Symptoms]

        Task:
        1. Understand the Patient's Condition:
           - Analyze the provided transcription to understand the patient's symptoms and any mentioned concerns or conditions.
           - Consider the patient’s age, gender, medical history, current medications, and allergies.
        
        2. Measure and Assess the Symptoms:
           - Identify and list the symptoms described by the patient.
           - Determine potential diseases or conditions that align with the described symptoms.
        
        3. Evaluate the Criticality:
           - Assess the severity and criticality of the possible conditions based on the symptoms.
        
        4. Provide Recommendations:
           - Suggest general recommendations for the symptoms and conditions identified.
           - Offer advice on lifestyle changes, over-the-counter treatments, or preliminary self-care measures.

        5. Advice on Professional Medical Consultation:
           - Emphasize the importance of seeing a healthcare professional for a thorough examination and diagnosis.
           - Suggest that the patient schedule an appointment with a doctor or specialist based on the identified conditions.
        """

        def stop_transcription():
            """Function to stop the transcription session."""
            print("No speech detected. Stopping transcription...")
            # Call on_close to handle the transcription completion and send it to Gemini AI.
            on_close()

        def reset_timer():
            """Reset the stop timer to close the session after 5 seconds of silence."""
            nonlocal stop_timer
            if stop_timer:
                stop_timer.cancel()  # Cancel the previous timer.
            stop_timer = threading.Timer(15.0, stop_transcription)
            stop_timer.start()

        def on_open(session_opened: aai.RealtimeSessionOpened):
            print("Session ID:", session_opened.session_id)

        def on_data(transcript: aai.RealtimeTranscript):
            if not transcript.text:
                return
            if isinstance(transcript, aai.RealtimeFinalTranscript):
                # Final transcription received, append to the result array.
                transcription_result.append(transcript.text)
                print(f"Final Transcript: {transcript.text}", end="\r\n")
            else:
                # Interim results, print for real-time feedback.
                print(f"Interim Transcript: {transcript.text}", end="\r")

            # Reset the timer on receiving any transcript (interim or final)
            reset_timer()

        def on_error(error: aai.RealtimeError):
            print("An error occurred:", error)
            self.error_message = str(error)

        def on_close():
            print("Closing Session")
            # When the session closes, send transcription data to Lemur AI for diagnosis.
            full_transcription = ' '.join(transcription_result)  # Concatenate all results.
            if full_transcription:
                # Send the transcription and prompt to Lemur API.
                gemini_diagnosis = self.get_diagnosis_from_gemini(full_transcription, prompt)
                print(gemini_diagnosis)
                return Response({'transcription': full_transcription, 'diagnosis': gemini_diagnosis}, status=status.HTTP_200_OK)
            else:
                return Response({'message': 'No transcription available'}, status=status.HTTP_200_OK)

        # Check if the action is 'stop', and if so, call on_close() to finalize and return transcription.
        if action == 'stop':
            on_close()
            return Response({"message":"closed by the user"})

        # If the action is 'start', proceed with starting the transcription session.
        # Initialize AssemblyAI Transcriber.
        transcriber = aai.RealtimeTranscriber(
            sample_rate=16_000,
            on_data=on_data,
            on_error=on_error,
            on_open=on_open,
            on_close=on_close,
        )
        
        transcriber.connect()

        try:
            # Start streaming microphone input for transcription.
            microphone_stream = aai.extras.MicrophoneStream(sample_rate=16_000)
            transcriber.stream(microphone_stream)
            
            # If any error occurs during the session
            if self.error_message:
                return Response({'error': self.error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_diagnosis_from_gemini(self, transcription, prompt):
        """
        Send the transcription to Lemur AI with the provided prompt for medical diagnosis.
        """ 
        model = genai.GenerativeModel("gemini-1.5-flash")
        # Construct a request payload for Lemur AI based on the transcription and prompt.
        gemini_prompt = prompt.replace("[Patient's Transcribed Symptoms]", transcription)
        
        # Assuming the Lemur API endpoint is available and set up properly.
        gemini_response = model.generate_content(
            gemini_prompt,
            generation_config = genai.GenerationConfig(
                max_output_tokens=1000,
                temperature=0.1,
            )
        )
        
        # Process and return Lemur's response.
        diagnosis =gemini_response.text
        return diagnosis

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
    


# ASSEMBLYAI_API_KEY = settings.ASSEMBLYAI_API_KEY
# GEMINI_AI_API_KEY = settings.GEMINI_AI_API_KEY

# AssemblyAI WebSocket URL
