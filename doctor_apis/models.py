from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    # Custom fields for user roles (doctor or patient)
    role = models.CharField(max_length=10, choices=[('doctor', 'Doctor'), ('patient', 'Patient')])

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
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='doctor_profile', null=True, blank=True)
    name = models.CharField(max_length=100)
    specialty = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Patient(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='patient_profile', null=True, blank=True)
    name = models.CharField(max_length=100)
    age = models.IntegerField()
    medical_history = models.TextField()

    def __str__(self):
        return self.name

# New Chat model to store conversations
class Chat(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chats')  # Reference the user
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True)  # Optional doctor reference
    started_at = models.DateTimeField(auto_now_add=True)  # When the chat started
    updated_at = models.DateTimeField(auto_now=True)  # Last time the chat was updated

    def __str__(self):
        return f'Chat {self.id} with {self.user.username}'

class ChatMessage(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='messages')  # Reference the Chat
    sender = models.CharField(max_length=10, choices=[('user', 'User'), ('doctor', 'Doctor'), ('bot', 'Bot')])  # Sender can be the user, doctor, or bot
    message = models.TextField()  # The message content
    timestamp = models.DateTimeField(auto_now_add=True)  # Timestamp for when the message was sent

    def __str__(self):
        return f'Message from {self.sender} at {self.timestamp}'

class Appointment(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE,null=True,blank=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, null=True, blank=True)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateTimeField()
    reason = models.TextField()

    canceled_by = models.CharField(max_length=50, null=True, blank=True)  # 'doctor' or 'patient'
    cancellation_date = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='scheduled')

    def cancel(self, canceled_by_user):
        """
        Mark the appointment as canceled and track who canceled it.
        """
        self.canceled_by = canceled_by_user
        self.cancellation_date = timezone.now()
        self.status = 'cancelled'
        self.save()

    def check_status(self):
        """
        Check if the appointment is expired or still scheduled.
        """
        if self.status != 'cancelled' and self.date < timezone.now():
            self.status = 'expired'
            self.save()
        return self.status

    def __str__(self):
        return f"Appointment with {self.doctor} on {self.date} ({self.get_status_display()})"
