from rest_framework import serializers
from .models import User, Profile, Doctor, Patient, Appointment, Chat, ChatMessage
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from django.utils.timezone import localtime
import pytz


class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ['id', 'name', 'specialty']


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ['id', 'name', 'age', 'medical_history']


class AppointmentSerializer(serializers.ModelSerializer):
    doctor = DoctorSerializer()
    patient = PatientSerializer()
    
    # Include status, canceled_by, and cancellation_date in the serializer
    status = serializers.SerializerMethodField()
    canceled_by = serializers.CharField(allow_null=True, required=False)
    cancellation_date = serializers.DateTimeField(allow_null=True, required=False)

    class Meta:
        model = Appointment
        fields = ['id', 'doctor', 'patient', 'date', 'reason', 'status', 'canceled_by', 'cancellation_date']

    def get_status(self, obj):
        # Call the check_status method to get the current status of the appointment
        return obj.check_status()


class AppointmentCreateSerializer(serializers.ModelSerializer):
    doctor_username = serializers.CharField(write_only=True)  # Field to accept doctor's username

    class Meta:
        model = Appointment
        fields = ['doctor_username', 'date', 'reason']

    def create(self, validated_data):
        user = self.context['request'].user

        # Ensure the user is a patient
        if not getattr(user, 'profile', None) or user.profile.role != 'patient':
            raise serializers.ValidationError('Only patients can book appointments.')

        # Get doctor using the provided username through profile__user
        doctor_username = validated_data.pop('doctor_username')
        try:
            doctor = Doctor.objects.get(profile__user__username=doctor_username)
        except Doctor.DoesNotExist:
            raise serializers.ValidationError({'doctor_username': f'Doctor with username {doctor_username} does not exist.'})

        # Get patient profile
        patient = getattr(user.profile, 'patient_profile', None)
        if not patient:
            raise serializers.ValidationError('The patient profile could not be found.')

        # Create the appointment, assigning the user who booked it
        appointment = Appointment.objects.create(
            doctor=doctor,
            patient=patient,
            user=user,  # Ensure the user is set here
            **validated_data
        )

        # Send email notifications (ensure this method exists)
        if hasattr(self, 'send_email_notifications'):
            self.send_email_notifications(appointment, user, doctor)

        return appointment

    def send_email_notifications(self, appointment, patient_user, doctor):
        # Capture the user's time zone (if sent in the request, otherwise use UTC)
        user_time_zone = self.context['request'].data.get('time_zone', 'UTC')
        time_zone = pytz.timezone(user_time_zone)
        
        # Convert appointment date to local time of the user
        local_appointment_time = appointment.date.astimezone(time_zone)

        # Format the appointment time in a professional way
        formatted_time = local_appointment_time.strftime('%Y-%m-%d %I:%M %p %Z')

        # Generate cancel URL
        cancel_url = self.get_cancel_url(appointment)

        # Send email to the doctor
        doctor_email = doctor.profile.user.email
        send_mail(
            subject="New Appointment Booked",
            message=f"Dear Dr. {doctor.profile.user.username},\n\n"
                    f"You have a new appointment scheduled with {patient_user.username}.\n"
                    f"Date & Time: {formatted_time}\n\n (localtime)"
                    f"Reason: {appointment.reason}\n\n"
                    f"Please ensure to prepare accordingly.\n\n"
                    f"Best regards,\n"
                    f"Doctor AI Medical Team",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[doctor_email],
            fail_silently=False,
        )

        # Send email to the patient
        patient_email = patient_user.email
        send_mail(
            subject="Appointment Confirmation",
            message=f"Dear {patient_user.username},\n\n"
                    f"Your appointment with Dr. {doctor.profile.user.username} has been successfully booked.\n"
                    f"Date & Time: {formatted_time}\n\n (localtime)"
                    f"If you wish to cancel the appointment, you can do so by clicking the link below:\n"
                    f"{cancel_url}\n\n"
                    f"Reason: {appointment.reason}\n\n"
                    f"Best regards,\n"
                    f"Doctor AI Medical Team",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[patient_email],
            fail_silently=False,
        )

    def get_cancel_url(self, appointment):
        # Generates the URL for canceling the appointment
        cancel_path = reverse('cancel_appointment', args=[appointment.id])
        return f"{settings.FRONTEND_URL}{cancel_path}"

class ProfileSerializer(serializers.ModelSerializer):
    doctor_profile = DoctorSerializer(read_only=True)
    patient_profile = PatientSerializer(read_only=True)

    class Meta:
        model = Profile
        fields = ['id', 'user', 'gender', 'role', 'phone_number', 'address', 'doctor_profile', 'patient_profile']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.role == 'doctor':
            representation['doctor_profile'] = DoctorSerializer(instance.doctor_profile).data if instance.doctor_profile else None
            representation['patient_profile'] = None
        elif instance.role == 'patient':
            representation['doctor_profile'] = None
            representation['patient_profile'] = PatientSerializer(instance.patient_profile).data if instance.patient_profile else None
        else:
            representation['doctor_profile'] = None
            representation['patient_profile'] = None
        return representation


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()
    appointments = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'profile', 'appointments']

    def get_appointments(self, obj):
        profile = getattr(obj, 'profile', None)
        if not profile:
            return []

        if profile.role == 'doctor':
            doctor_profile = getattr(profile, 'doctor_profile', None)
            if doctor_profile:
                appointments = Appointment.objects.filter(doctor=doctor_profile)
            else:
                appointments = Appointment.objects.none()
        elif profile.role == 'patient':
            patient_profile = getattr(profile, 'patient_profile', None)
            if patient_profile:
                appointments = Appointment.objects.filter(patient=patient_profile)
            else:
                appointments = Appointment.objects.none()
        else:
            appointments = Appointment.objects.none()

        serializer = AppointmentSerializer(appointments, many=True)
        return serializer.data

    def update(self, instance, validated_data):
        # Update user fields
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.role = validated_data.get('role', instance.role)
        instance.save()

        # Handle nested profile data
        profile_data = validated_data.pop('profile', None)
        if profile_data:
            profile_serializer = ProfileSerializer(instance.profile, data=profile_data, partial=True)
            if profile_serializer.is_valid():
                profile_serializer.save()

        return instance


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'chat', 'sender', 'message', 'timestamp']
        read_only_fields = ['id', 'chat', 'timestamp']

class ChatSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()  # Displays the user's username
    doctor = serializers.StringRelatedField()  # Displays the doctor's name (optional)
    messages = ChatMessageSerializer(many=True, read_only=True, source='chatmessage_set')  # Nested chat messages

    class Meta:
        model = Chat
        fields = ['id', 'user', 'doctor', 'started_at', 'updated_at', 'messages']
        read_only_fields = ['id', 'started_at', 'updated_at']