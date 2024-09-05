from rest_framework import serializers
from .models import User, Profile, Doctor, Patient, Appointment

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

class AppointmentCreateSerializer(serializers.ModelSerializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.all())

    class Meta:
        model = Appointment
        fields = ['doctor', 'date', 'reason']

    def create(self, validated_data):
        # Automatically associate the logged-in user as the patient
        user = self.context['request'].user

        if not hasattr(user, 'profile') or user.profile.role != 'patient':
            raise serializers.ValidationError('Only patients can book appointments.')

        # Ensure the user has a related patient profile
        if not hasattr(user.profile, 'patient_profile'):
            raise serializers.ValidationError('User profile does not have an associated patient profile.')

        patient = user.profile.patient_profile
        appointment = Appointment.objects.create(patient=patient, **validated_data)
        return appointment

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
