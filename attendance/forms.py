from django import forms
from django.contrib.auth.models import User, Group
from .models import Profile, GroupTimePolicy, Logo
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
        if self.instance and self.instance.pk:
             self.fields['group'].disabled = True
        else:
            self.fields['group'].queryset = Group.objects.filter(time_policy__isnull=True)

class CreateGroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'New Group Name'})
        }

class UserEditForm(forms.ModelForm):
    phone_number = forms.CharField(max_length=20, required=False)
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'groups']

    def __init__(self, *args, **kwargs):
        user_groups = kwargs.pop('user_groups', None)
        super().__init__(*args, **kwargs)
        if self.instance:
            self.fields['phone_number'].initial = self.instance.profile.phone_number
            if self.instance.pk:
                self.fields['groups'].initial = self.instance.groups.all()
        if user_groups:
            self.fields['groups'].queryset = user_groups

    def save(self, *args, **kwargs):
        user = super().save(*args, **kwargs)
        user.profile.phone_number = self.cleaned_data['phone_number']
        user.profile.save()
        return user

class LogoUploadForm(forms.ModelForm):
    class Meta:
        model = Logo
        fields = ['name', 'image']

class GroupEditForm(forms.Form):
    name = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    logo = forms.ModelChoiceField(
        queryset=Logo.objects.all(),
        required=False,
        help_text="Select a logo for this group.",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        supervisor_logos = kwargs.pop('supervisor_logos', None)
        super().__init__(*args, **kwargs)
        if supervisor_logos is not None:
            self.fields['logo'].queryset = supervisor_logos
