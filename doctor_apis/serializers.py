from rest_framework import serializers
from .models import User, Profile, Doctor, Patient, Appointment
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings

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
    canceled_by = serializers.CharField( allow_null=True, required=False)
    cancellation_date = serializers.DateTimeField( allow_null=True, required=False)

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
        if not hasattr(user, 'profile') or user.profile.role != 'patient':
            raise serializers.ValidationError('Only patients can book appointments.')

        # Get doctor using the provided username through profile__user
        doctor_username = validated_data.pop('doctor_username')
        try:
            doctor = Doctor.objects.get(profile__user__username=doctor_username)
        except Doctor.DoesNotExist:
            raise serializers.ValidationError(f'Doctor with username {doctor_username} does not exist.')

        # Get patient profile
        patient = user.profile.patient_profile

        # Create the appointment, assigning the user who booked it
        appointment = Appointment.objects.create(
            doctor=doctor,
            patient=patient,
            user=user,  # Ensure the user is set here
            **validated_data
        )

        # Send email notifications
        self.send_email_notifications(appointment, user, doctor)

        return appointment

    def send_email_notifications(self, appointment, patient_user, doctor):
        # Patient cancellation link
        cancel_url = self.get_cancel_url(appointment)
        
        # Send email to the doctor
        doctor_email = doctor.profile.user.email
        send_mail(
            subject="New Appointment Booked",
            message=f"Dear Dr. {doctor.profile.user.username},\n\n"
                    f"You have a new appointment scheduled with {patient_user.username} on {appointment.date}.\n\n"
                    f"Reason: {appointment.reason}\n",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[doctor_email],
            fail_silently=False,
        )

        # Send email to the patient
        patient_email = patient_user.email
        send_mail(
            subject="Appointment Confirmation",
            message=f"Dear {patient_user.username},\n\n"
                    f"Your appointment with Dr. {doctor.profile.user.username} has been successfully booked for {appointment.date}.\n\n"
                    f"If you wish to cancel the appointment, you can do so by clicking the link below:\n"
                    f"{cancel_url}\n\n"
                    f"Reason: {appointment.reason}\n",
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
        if not hasattr(obj, 'profile'):
            return []

        if obj.profile.role == 'doctor':
            if hasattr(obj.profile, 'doctor_profile'):
                appointments = Appointment.objects.filter(doctor=obj.profile.doctor_profile)
            else:
                appointments = Appointment.objects.none()
        elif obj.profile.role == 'patient':
            if hasattr(obj.profile, 'patient_profile'):
                appointments = Appointment.objects.filter(patient=obj.profile.patient_profile)
            else:
                appointments = Appointment.objects.none()
        else:
            appointments = Appointment.objects.none()

        serializer = AppointmentSerializer(appointments, many=True)
        return serializer.data
