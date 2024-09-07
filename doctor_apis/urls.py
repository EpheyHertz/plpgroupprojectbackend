# doctor_apis/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DoctorViewSet, PatientViewSet, AppointmentViewSet, Transcribe_audio, UserLoginView,UserLogoutView,UserSignupView,UserUpdateView,UserDetailView, BookAppointmentView,UserAppointmentsView,CancelAppointmentView, TranscribeAudioView

router = DefaultRouter()
router.register(r'doctors', DoctorViewSet)
router.register(r'patients', PatientViewSet)
router.register(r'appointments', AppointmentViewSet, basename='appointment')


urlpatterns = [
    path('', include(router.urls)),
    path('transcribearea/', Transcribe_audio.as_view(), name='transcribe_audio'),
    # path('transcribe-diagnose/', RealTimeTranscriptionDiagnosisView.as_view(), name='transcribe-diagnose'),
    path('transcribe/', TranscribeAudioView.as_view(), name='transcribing'),
    path('login/',  UserLoginView.as_view(), name='user_login'),
    path('logout/', UserLogoutView.as_view(), name='user_logout'),
    path('signup/', UserSignupView.as_view(), name='user_signup'),
    path('update/', UserUpdateView.as_view(), name='user_update'),
    path('user/', UserDetailView.as_view(), name='user-detail'),
    path('book-appointment/', BookAppointmentView.as_view(), name='book-appointment'),
    path('my-appointments/', UserAppointmentsView.as_view(), name='user-appointments'),
    path('cancel-appointment/<int:appointment_id>/', CancelAppointmentView.as_view(), name='cancel_appointment'),
     
]
