from django import forms
from django.contrib.auth.models import User
from .models import Profile

class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    phone_number = forms.CharField(max_length=15, required=True)
    reference_image = forms.ImageField(required=True)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'password']

    def __init__(self, *args, **kwargs):
        super(UserRegistrationForm, self).__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

    def save(self, commit=True):
        user = super(UserRegistrationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            # The profile is already created by the post_save signal
            user.profile.phone_number = self.cleaned_data['phone_number']
            user.profile.reference_image = self.cleaned_data['reference_image']
            user.profile.save()
        return user
