# doctor_apis/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser, Permission, Group

class User(AbstractUser):
    # Custom fields for your user model
    role = models.CharField(max_length=10, choices=[('doctor', 'Doctor'), ('patient', 'Patient')])

    # Use inherited fields for groups and permissions
    # groups and user_permissions should not be redefined here

    def __str__(self):
        return self.username

class Profile(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]

    ROLE_CHOICES = [
        ('doctor', 'Doctor'),
        ('patient', 'Patient'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, null=True, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, null=True, blank=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.user.username} Profile'

class Doctor(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='doctor_profile',default=1)
    name = models.CharField(max_length=100)
    specialty = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Patient(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='patient_profile',default=1)
    name = models.CharField(max_length=100)
    age = models.IntegerField()
    medical_history = models.TextField()

    def __str__(self):
        return self.name

class Appointment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE) 
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE,default=None)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE,default=None)
    date = models.DateTimeField()
    reason = models.TextField()

    def __str__(self):
        return f"Appointment with {self.doctor} on {self.date}"