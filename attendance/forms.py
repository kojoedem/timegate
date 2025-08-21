from django import forms
from django.contrib.auth.models import User
from .models import Profile
from .utils import find_matching_face

class UserRegistrationForm(forms.Form):
    username = forms.CharField(max_length=150, help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.")
    password = forms.CharField(widget=forms.PasswordInput)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    phone_number = forms.CharField(max_length=15)
    reference_image = forms.ImageField()

    def __init__(self, *args, **kwargs):
        super(UserRegistrationForm, self).__init__(*args, **kwargs)
        # Add bootstrap classes to all fields
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})

    def clean(self):
        cleaned_data = super().clean()
        image = cleaned_data.get('reference_image')

        if image:
            # Check for duplicate face
            user_id, confidence, reason = find_matching_face(image)
            if user_id is not None:
                raise forms.ValidationError("This face appears to be already registered to another user.", code='duplicate_face')

        return cleaned_data

    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data['username'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name']
        )
        # Profile is created by signal
        user.profile.phone_number = data['phone_number']
        user.profile.reference_image = data['reference_image']
        user.profile.save()
        return user
