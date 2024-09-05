from django.contrib import admin
from .models import User,Profile, Doctor, Patient, Appointment
# from django.contrib.auth.admin import UserAdmin
# from .models import User
# admin.site.register(User, UserAdmin)
admin.site.register(User)
admin.site.register(Profile)
admin.site.register(Doctor)
admin.site.register(Patient)
admin.site.register(Appointment)