# doctor_apis/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DoctorViewSet, PatientViewSet, AppointmentViewSet, transcribe_audio, UserLoginView,UserLogoutView,UserSignupView,UserUpdateView,UserDetailView, BookAppointmentView,UserAppointmentsView

router = DefaultRouter()
router.register(r'doctors', DoctorViewSet)
router.register(r'patients', PatientViewSet)
router.register(r'appointments', AppointmentViewSet, basename='appointment')


urlpatterns = [
    path('', include(router.urls)),
    path('transcribe/', transcribe_audio, name='transcribe_audio'),
    path('login/',  UserLoginView.as_view(), name='user_login'),
    path('logout/', UserLogoutView.as_view(), name='user_logout'),
    path('signup/', UserSignupView.as_view(), name='user_signup'),
    path('update/', UserUpdateView.as_view(), name='user_update'),
    path('user/', UserDetailView.as_view(), name='user-detail'),
    path('book-appointment/', BookAppointmentView.as_view(), name='book-appointment'),
    path('my-appointments/', UserAppointmentsView.as_view(), name='user-appointments'),
     
]
