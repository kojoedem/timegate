from django import forms
from django.contrib.auth.models import User, Group
from .models import Profile, GroupTimePolicy
from .utils import is_face_already_registered

class UserRegistrationForm(forms.ModelForm):
    phone_number = forms.CharField(max_length=20, required=False)
    reference_image = forms.ImageField(required=True, help_text="A clear, forward-facing photo for facial recognition.")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def clean_reference_image(self):
        image = self.cleaned_data.get('reference_image')
        if image:
            is_duplicate, reason = is_face_already_registered(image)
            if is_duplicate:
                raise forms.ValidationError(f"This face seems to be already registered. Reason: {reason}")
        return image

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(User.objects.make_random_password())
        if commit:
            user.save()
            profile, created = Profile.objects.get_or_create(user=user)
            profile.phone_number = self.cleaned_data.get('phone_number')
            profile.reference_image = self.cleaned_data.get('reference_image')
            profile.save()
        return user

class SingleUserCreationForm(forms.ModelForm):
    phone_number = forms.CharField(max_length=20, required=False)
    reference_image = forms.ImageField(required=True, help_text="A clear, forward-facing photo for the user.")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

class GroupTimePolicyForm(forms.ModelForm):
    class Meta:
        model = GroupTimePolicy
        fields = ['group', 'start_time', 'end_time']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If editing an existing policy, don't limit the group queryset
        if self.instance and self.instance.pk:
             self.fields['group'].queryset = Group.objects.all()
        else:
            # For new policies, only show groups that don't have one yet
            self.fields['group'].queryset = Group.objects.filter(time_policy__isnull=True)
