# doctor_apis/views.py
# from django.contrib.auth.models import User
# from .models import User,Chat, ChatMessage
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
import requests
from django.shortcuts import render
from django.core.files.uploadedfile import InMemoryUploadedFile
from rest_framework import generics
from django.contrib import messages
from rest_framework.views import APIView
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes,authentication_classes
from rest_framework.response import Response
from django.core.files.storage import default_storage
from .models import Profile, Doctor, Patient, Appointment,Chat,User, ChatMessage
from .serializers import UserSerializer, ProfileSerializer,DoctorSerializer, PatientSerializer, AppointmentSerializer,AppointmentCreateSerializer,ChatSerializer,ChatMessageSerializer
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils import timezone
# from .forms import UserUpdateForm, ProfileUpdateForm
from rest_framework.authentication import TokenAuthentication
from django.conf import settings
# from django.urls import reverse_lazy
from django.views.generic import View
import google.generativeai as genai
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from django.db import IntegrityError
import logging

logger = logging.getLogger(__name__)
# ?\from dj_rest_auth.registration.views import SocialLoginView
# from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
# Configure AssemblyAI API key
aai.settings.api_key = settings.AAI_APIKEY
print(aai.settings.api_key)
GEMINI_AI_API_KEY=settings.GEMINI_AI_API_KEY
genai.configure(api_key=GEMINI_AI_API_KEY)
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
# from google.oauth2 import id_token
# import requests as req
# from google.auth.transport import requests
# class GoogleLogin(APIView):
#     permission_classes = [AllowAny]

#     def post(self, request, *args, **kwargs):
#         print(request.data)
#         access_token = request.data.get('access_token')
#         id_token = request.data.get('id_token')
#         code = request.data.get('code')

#         if not access_token or not id_token or not code:
#             return Response({"status": "error", "message": "Missing tokens"}, status=400)

#         # Verify ID token
#         client_id = settings.OAUTH_CLIENT_ID  # Replace with your client ID
#         idinfo = self.verify_id_token(id_token, client_id)
#         if not idinfo:
#             return Response({"status": "error", "message": "Invalid ID token"}, status=400)

#         # Verify Access token (Optional)
#         token_info = self.verify_access_token(access_token)
#         if not token_info:
#             return Response({"status": "error", "message": "Invalid access token"}, status=400)

#         # Process the tokens
#         # For example, you might want to associate the user with your application

#         return Response({"status": "success", "message": "Tokens received"}, status=200)

#     def verify_id_token(self, id_token, client_id):
#         try:
#             idinfo = id_token.verify_oauth2_token(id_token, requests.Request(), client_id)
#             return idinfo
#         except ValueError:
#             return None

#     def verify_access_token(self, access_token):
#         try:
#             response = req.get('https://www.googleapis.com/oauth2/v1/tokeninfo', params={'access_token': access_token})
#             if response.status_code == 200:
#                 return response.json()
#             else:
#                 return None
#         except req.RequestException:
#             return None
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def validate(cls, attrs):
        email = attrs.get('username')
        password = attrs.get('password')

        # Retrieve user by email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid email or password')

        # Authenticate the user using username and password
        user = authenticate(username=user.username, password=password)

        if user is None:
            raise serializers.ValidationError('Invalid email or password')

        # Get the token using the parent class method
        token = cls.get_token(user)

        # Return token data
        return {
            'refresh': str(token),
            'access': str(token.access_token),
        }

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token['username'] = user.username
        token['email'] = user.email
        token['role'] = user.role

        return token

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
    
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
        # print(request.user)
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
@ permission_classes([IsAuthenticated])
class BookAppointmentView(APIView):
    # permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Ensure the user is a patient
        if not hasattr(request.user, 'profile') or request.user.profile.role != 'patient':
            return Response({'error': 'Only patients can book appointments.'}, status=status.HTTP_403_FORBIDDEN)
        print(request.data)
        # Handle the appointment creation
        serializer = AppointmentCreateSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
@ permission_classes([IsAuthenticated])
class CancelAppointmentView(APIView):
   

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
@ permission_classes([IsAuthenticated])
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
        response ={
            'user': {
                'username': user.username,
                'email': user.email,
                'role': getattr(user, 'role', None),
            },
            'profile': profile_data
        }
        # print(response)
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
        data = request.data

        # Debugging output
        # print("Received data:", data)
        # print("User instance:", user)

        profile = getattr(user, 'profile', None)

        # Serialize user data
        user_serializer = UserSerializer(user, data=data, partial=True)
        if user_serializer.is_valid():
            user_serializer.save()
        else:
            return Response({
                'user_errors': user_serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)

        # Serialize profile data
        profile_serializer = ProfileSerializer(profile, data=data, partial=True) if profile else None
        if profile_serializer:
            if profile_serializer.is_valid():
                profile_serializer.save()
                profile = profile_serializer.instance
            else:
                return Response({
                    'profile_errors': profile_serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Create new profile if not exists
            profile_serializer = ProfileSerializer(data=data, partial=True)
            if profile_serializer.is_valid():
                profile = profile_serializer.save(user=user)  # Associate profile with user
            else:
                return Response({
                    'profile_errors': profile_serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

        # Handle role-specific data
        role = profile.role if profile else user.role
        if role == 'doctor':
            doctor_data = data.get('doctor_details', {})
            doctor, created = Doctor.objects.get_or_create(profile=profile)
            doctor_serializer = DoctorSerializer(doctor, data=doctor_data, partial=True)
            if doctor_serializer.is_valid():
                doctor_serializer.save()
            else:
                return Response({
                    'doctor_errors': doctor_serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        elif role == 'patient':
            patient_data = data.get('patient_details', {})
            patient, created = Patient.objects.get_or_create(profile=profile)
            patient_serializer = PatientSerializer(patient, data=patient_data, partial=True)
            if patient_serializer.is_valid():
                patient_serializer.save()
            else:
                return Response({
                    'patient_errors': patient_serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': 'Your profile has been updated!',
            'user': user_serializer.data,
            'profile': profile_serializer.data if profile_serializer else None
        }, status=status.HTTP_200_OK)
# ViewSets for the Doctor, Patient, and Appointment models
@ permission_classes([IsAuthenticated])
class DoctorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for doctors allowing only GET requests.
    """
    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get']  # Only allow GET requests
@ permission_classes([IsAuthenticated])
class PatientViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for patients allowing only GET requests.
    """
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get']  # Only allow GET requests
@ permission_classes([IsAuthenticated])
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
    permission_classes = [AllowAny]
    def get(self,request):
        return render(request,'./transcribe.html')


generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    system_instruction=(
        "Gemini Medical Chatbot AI Prompt:\n\n"
        "Welcome to Doctor AI, your health assistant powered by Gemini. "
        "Also you are restricted to only health related issues and questions and if a user provides anything out of the health scope you should explain to them that you are a health AI"
        "I am here to assist you with minor health concerns and provide information based on your symptoms. "
        "Before ask for the details please try to look at the chat history passed to you, and see if you can get the user information.If you dont get any then go forward asking them the details.To ensure I can offer you the most accurate guidance, I will first need a few basic details:\n\n"
        "* **Full Name:**\n"
        "* **Email Address:**\n"
        "* **Age:**\n"
        "* **Symptoms:**\n\n"
        "Once I have this information, I will perform a thorough investigation of your symptoms using the following trusted medical resources:\nAlso you can go on and ask the user more questions in order for you to have concrete information before giving recomendation.Try to be more interactive and engage the user \n"
        "1. [MedlinePlus](https://medlineplus.gov) – Comprehensive health information from the U.S. National Library of Medicine.\n"
        "2. [Healthily](https://www.livehealthily.com) – A health library and symptom checker offering advice on wellness and minor health concerns.\n"
        "3. [PEPID](https://www.pepid.com) – A professional medical reference tool with support for diagnostics and treatment.\n"
        "4. [UpToDate](https://www.wolterskluwer.com/en/solutions/uptodate) – Evidence-based medical knowledge used by healthcare professionals worldwide.\n"
        "5. [Buoy Health](https://www.buoyhealth.com) – An AI-driven symptom checker designed to offer potential diagnoses based on user-reported symptoms.\n\n"
        "Disclaimer: While I strive to provide helpful and accurate information based on your symptoms and the latest medical resources, "
        "I am an AI model and not a licensed healthcare professional. My responses are intended to offer general advice and support. trying keeping the data throughout the conversation"
        "For a comprehensive diagnosis and personalized medical advice, please consult with a licensed healthcare provider or medical professional.\n\n"
        "Let's begin by collecting your details. Afterward, I will investigate your symptoms and offer guidance or next steps based on the information from these reputable sources.\n\n"
    ),
)
class ChatMessagesAPIView(APIView):
    def get(self, request, chat_id, *args, **kwargs):
        try:
            chat = Chat.objects.get(id=chat_id, user=request.user)
        except Chat.DoesNotExist:
            return Response({'error': 'Chat not found or you do not have permission to access this chat.'}, status=status.HTTP_404_NOT_FOUND)

        messages = ChatMessage.objects.filter(chat=chat).order_by('timestamp')
        serializer = ChatMessageSerializer(messages, many=True)
        # print(serializer.data)

        return Response({'messages': serializer.data})

class UserChatListView(generics.ListAPIView):
    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated]  # Ensure user is logged in

    def get_queryset(self):
        # Return all chats where the user is the participant
        user = self.request.user
        return Chat.objects.filter(user=user).order_by('-updated_at')  # Ordering by most recent chats

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # Check if no chats are found for the user
        if not queryset.exists():
            return Response({"detail": "No chats found for the user."}, status=status.HTTP_404_NOT_FOUND)
        
        # Serialize the chat data
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import status
# from .models import Chat, ChatMessage, User
# from rest_framework.permissions import AllowAny

# class DoctorChatbotView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, *args, **kwargs):
#         """
#         Handle user interactions with the doctor AI chatbot using Gemini AI.
#         Persist chat history and associate each chat with a user.
#         """
#         user_message = request.data.get('message', '')
#         chat_id = request.data.get('chat_id')
#         user = request.user  # Get the authenticated user

#         if not user_message:
#             return Response({'error': 'No message provided'}, status=status.HTTP_400_BAD_REQUEST)

#         try:
#             # Retrieve or create a new chat for this user
#             chat = self.get_or_create_chat(user, chat_id)

#             # Save the user message to the chat
#             ChatMessage.objects.create(chat=chat, sender='user', message=user_message)

#             # Retrieve chat history (pass entire chat history for context)
#             chat_history = self.get_chat_history(chat)

#             # Get the chatbot response from Gemini AI with full chat history
#             chatbot_response = self.get_chatbot_response(user_message, chat_history)

#             # Save the chatbot response to the chat
#             ChatMessage.objects.create(chat=chat, sender='bot', message=chatbot_response)

#             # Return the response along with the chat ID for future messages
#             return Response({
#                 'response': chatbot_response,
#                 'chat_id': chat.id  # Send the chat ID back to the frontend
#             }, status=status.HTTP_200_OK)

#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def get_or_create_chat(self, user, chat_id):
#         """
#         Retrieve an existing chat or create a new one if no chat ID is provided.
#         """
#         if chat_id:
#             try:
#                 # Attempt to retrieve the chat based on the provided chat ID and user
#                 chat = Chat.objects.get(id=chat_id, user=user)
#             except Chat.DoesNotExist:
#                 raise ValidationError({'error': 'Chat not found or you do not have permission to access it.'})
#         else:
#             # Create a new chat if no chat ID is provided
#             chat = Chat.objects.create(user=user)
        
#         return chat

#     def get_chat_history(self, chat):
#         """
#         Retrieve and format the entire chat history for the given chat instance.
#         """
#         messages = ChatMessage.objects.filter(chat=chat).order_by('timestamp')
#         history = []
#         for message in messages:
#             role = 'user' if message.sender == 'user' else 'model'
#             history.append({
#                 "role": role,
#                 "parts": [message.message],
#             })
#         return history

#     def get_chatbot_response(self, user_message, history):
#         """
#         Send the user's message and chat history to Gemini AI to get a response from the doctor chatbot.
#         """
#         try:
#             # Replace with actual communication with Gemini AI or other chatbot models
#             chat = model.start_chat(history=history)  # Start chat with full history

#             # Send the user's message to the chatbot and get a response
#             response = chat.send_message(user_message)

#             return response.text  # Return the chatbot's textual response
#         except Exception as e:
#             print(f"Error getting chatbot response: {e}")
#             return "Sorry, I couldn't process your request."
class DoctorChatbotView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        Handle user interactions with the doctor AI chatbot using Gemini AI.
        Persist chat history and associate each chat with a user.
        """
        user_message = request.data.get('message', '')
        chat_id = request.data.get('chat_id')
        user = request.user  # Get the authenticated user

        if not user_message:
            return Response({'error': 'No message provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Retrieve or create a new chat for this user
            chat = self.get_or_create_chat(user, chat_id)

            # Save the user message to the chat
            ChatMessage.objects.create(chat=chat, sender='user', message=user_message)

            # Retrieve chat history (optimize by limiting message count)
            chat_history = self.get_chat_history(chat)

            # Get the chatbot response from Gemini AI
            chatbot_response = self.get_chatbot_response(user_message, chat_history)

            # Save the chatbot response to the chat
            ChatMessage.objects.create(chat=chat, sender='bot', message=chatbot_response)

            # Return the response along with the chat ID for future messages
            return Response({
                'response': chatbot_response,
                'chat_id': chat.id  # Send the chat ID back to the frontend
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error in chatbot interaction: {e}")
            return Response({'error': 'Something went wrong while processing your request.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_or_create_chat(self, user, chat_id):
        """
        Retrieve an existing chat or create a new one if no chat ID is provided.
        """
        if chat_id:
            try:
                chat = Chat.objects.get(id=chat_id, user=user)
            except Chat.DoesNotExist:
                raise ValidationError('Chat not found or you do not have permission to access it.')
        else:
            chat = Chat.objects.create(user=user)  # Create a new chat for the user
        return chat

    def get_chat_history(self, chat, limit=20):
        """
        Retrieve and format the chat history, limit to last N messages for efficiency.
        """
        messages = ChatMessage.objects.filter(chat=chat).order_by('-timestamp')[:limit]
        messages = reversed(messages)  # Reverse to keep the order as oldest-to-newest
        history = []
        for message in messages:
            role = 'user' if message.sender == 'user' else 'model'
            history.append({
                "role": role,
                "parts": [message.message],
            })
        # print(history)
        return history

    def get_chatbot_response(self, user_message, history):
        """
        Send the user's message and chat history to Gemini AI to get a response.
        """
        try:
            chat = model.start_chat(history=history)  # Replace with Gemini AI interaction
            response = chat.send_message(user_message)
            return response.text  # Return the chatbot's textual response
        except Exception as e:
            logger.error(f"Error getting chatbot response from Gemini AI: {e}")
            return "Sorry, I couldn't process your request at this time."

import threading

class TranscribeAudioView(APIView):
    permission_classes = [AllowAny]
    # permission_classes = [IsAuthenticated]
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
            """Reset the stop timer to close the session after 15 seconds of silence."""
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
    permission_classes = [AllowAny]

    def post(self, request):
        # print(request.data)
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

        # Check if username is already taken
        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username is already taken'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if email is already registered
        if User.objects.filter(email=email).exists():
            return Response({'error': 'Email is already registered'}, status=status.HTTP_400_BAD_REQUEST)

        # Create the user and save the role in User model
        user = User(username=username, email=email, role=role)
        user.set_password(password)

        try:
            # Send the welcome email before saving the user
            try:
                send_mail(
                    'Welcome to Doctor AI - Your Healthcare Companion',
                    f'''
                    Dear {username},

                    We are thrilled to welcome you to Doctor AI! You have successfully registered as a {role}, and we are excited to have you on board.

                    As a {role}, you now have access to a range of tools designed to enhance your healthcare experience. Whether you are seeking personalized medical advice or looking to provide top-notch care, Doctor AI is here to support you every step of the way.

                    If you are a doctor, you can start engaging with patients and providing them with expert guidance. If you are a patient, feel free to ask our AI-powered system any medical-related questions or seek advice on common health issues.

                    We're committed to providing you with the best experience possible. If you have any questions or need assistance, don't hesitate to reach out to our support team at epheynyaga@gmail.com.

                    Welcome once again, and we look forward to assisting you on your healthcare journey.

                    Best regards,
                    The Doctor AI Team
                    ''',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
            except Exception as e:
                return Response({'error': f'Failed to send welcome email: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Save the user after sending email
            user.save()

            # Create or update the profile with the role from the user
            profile, created = Profile.objects.get_or_create(user=user)
            profile.role = role  # Save role in Profile
            profile.save()

            # Create Doctor or Patient instance based on role
            if role == 'doctor':
                Doctor.objects.get_or_create(profile=profile, defaults={'name': username, 'specialty': 'General'})
            elif role == 'patient':
                Patient.objects.get_or_create(profile=profile, defaults={'name': username, 'age': 0, 'medical_history': ''})

            return Response({'message': f'User registered successfully as {role}'}, status=status.HTTP_201_CREATED)

        except IntegrityError:
            return Response({'error': 'An error occurred while creating the user. Please try again.'}, status=status.HTTP_400_BAD_REQUEST)

        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            # Handle unexpected exceptions
            return Response({'error': f'An unexpected error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class UserLoginView(APIView):
    """
    Handle user login with email, password, and role (doctor/patient).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        role = request.data.get('role')  # Accept role (doctor or patient)

        if not email or not password or not role:
            return Response({'error': 'Email, password, and role are required'}, status=status.HTTP_400_BAD_REQUEST)

        # First, check if the user exists with the provided email and role
        try:
            user = User.objects.get(email=email, role=role)
        except User.DoesNotExist:
            return Response({'error': 'Invalid email or role'}, status=status.HTTP_401_UNAUTHORIZED)

        # Now authenticate the user (this checks the password)
        authenticated_user = authenticate(request, username=user.username, password=password)
        if authenticated_user is None:
            return Response({'error': 'Invalid password'}, status=status.HTTP_401_UNAUTHORIZED)

        # If authenticated, log the user in
        login(request, authenticated_user)
        return Response({'message': f'Login successful as {role}'}, status=status.HTTP_200_OK)
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
    permission_classes = [IsAuthenticated]
    def post(self, request):
        # Log out the user
        logout(request)
        return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)
    


# ASSEMBLYAI_API_KEY = settings.ASSEMBLYAI_API_KEY
# GEMINI_AI_API_KEY = settings.GEMINI_AI_API_KEY

# AssemblyAI WebSocket URL
