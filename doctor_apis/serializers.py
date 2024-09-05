# api/serializers.py

from rest_framework import serializers
from .models import User,Profile, Doctor, Patient, Appointment

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

    class Meta:
        model = Appointment
        fields = ['id', 'doctor', 'patient', 'date', 'reason']

class ProfileSerializer(serializers.ModelSerializer):
    doctor_profile = DoctorSerializer()  # This will include the doctor profile if it exists
    patient_profile = PatientSerializer()  # This will include the patient profile if it exists

    class Meta:
        model = Profile
        fields = ['id', 'user', 'gender', 'role', 'phone_number', 'address', 'doctor_profile', 'patient_profile']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.role == 'doctor':
            representation['doctor_profile'] = DoctorSerializer(instance.doctor_profile).data
            representation['patient_profile'] = None
        elif instance.role == 'patient':
            representation['doctor_profile'] = None
            representation['patient_profile'] = PatientSerializer(instance.patient_profile).data
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
        # Get all appointments for this user
        appointments = Appointment.objects.filter(user=obj)
        # Serialize appointments
        serializer = AppointmentSerializer(appointments, many=True)
        return serializer.data