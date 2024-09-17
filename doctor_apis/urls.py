# doctor_apis/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DoctorViewSet, PatientViewSet, AppointmentViewSet, Transcribe_audio, UserLoginView,UserLogoutView,UserSignupView,UserUpdateView,UserDetailView, BookAppointmentView,UserAppointmentsView,CancelAppointmentView, TranscribeAudioView,MyTokenObtainPairView, DoctorChatbotView,ChatMessagesAPIView,UserChatListView,PasswordResetRequestView, PasswordResetConfirmView
from rest_framework_simplejwt.views import (
    
    TokenRefreshView,
)

router = DefaultRouter()
router.register(r'doctors', DoctorViewSet)
router.register(r'patients', PatientViewSet)
router.register(r'appointments', AppointmentViewSet, basename='appointment')


urlpatterns = [
    path('', include(router.urls)),
    path('transcribearea/', Transcribe_audio.as_view(), name='transcribe_audio'),
     path('token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # path('transcribe-diagnose/', RealTimeTranscriptionDiagnosisView.as_view(), name='transcribe-diagnose'),
    path('transcribe/', TranscribeAudioView.as_view(), name='transcribing'),
    path('user/chats/', UserChatListView.as_view(), name='user-chats'),
    path('chatbotdiagnosis/',  DoctorChatbotView.as_view(), name='chatbot'),
    path('login/',  UserLoginView.as_view(), name='user_login'),
    path('logout/', UserLogoutView.as_view(), name='user_logout'),
    path('signup/', UserSignupView.as_view(), name='user_signup'),
    path('update/', UserUpdateView.as_view(), name='user_update'),
    path('user/', UserDetailView.as_view(), name='user-detail'),
    path('user/chats/<int:chat_id>/', ChatMessagesAPIView.as_view(), name='chat_messages'),
    path('book-appointment/', BookAppointmentView.as_view(), name='book-appointment'),
    path('my-appointments/', UserAppointmentsView.as_view(), name='user-appointments'),
    path('cancel-appointment/<int:appointment_id>/', CancelAppointmentView.as_view(), name='cancel_appointment'),
    path('password-reset-request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    
    # Endpoint for confirming and resetting the password using the token
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    # path('auth/', include('dj_rest_auth.urls')),  # Includes login, logout, password reset, etc.
    # path('auth/registration/', include('dj_rest_auth.registration.urls')),  # Includes social login
    # path('accounts/', include('allauth.urls')),
    # path('auth/google/', GoogleLogin.as_view(), name='google_login'),

]
