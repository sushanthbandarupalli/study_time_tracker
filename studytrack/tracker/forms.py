from django import forms
from django.utils import timezone
from .models import Subject, TimeEntry


class SubjectForm(forms.ModelForm):
    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    class Meta:
        model = Subject
        fields = ["name", "color"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "maxlength": 120, "placeholder": "e.g. Mathematics"}),
            "color": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
        }

    def clean_name(self):
        name = self.cleaned_data["name"]
        if Subject.objects.filter(user=self.user, name__iexact=name).exists():
            raise forms.ValidationError("A subject with this name already exists.")
        return name

    def save(self, commit=True):
        subject = super().save(commit=False)
        subject.user = self.user
        if commit:
            subject.save()
        return subject


class TimerStartForm(forms.Form):
    subject = forms.ModelChoiceField(queryset=Subject.objects.none(), required=False, empty_label="No subject")
    activity = forms.ChoiceField(choices=TimeEntry.Activity.choices)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subject"].queryset = Subject.objects.filter(user=user, active=True)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("activity") in (TimeEntry.Activity.CLASS, TimeEntry.Activity.NOTES) and not cleaned.get("subject"):
            self.add_error("subject", "Choose a subject for Class or Notes.")
        return cleaned


class TimeEntryForm(forms.ModelForm):
    start_datetime = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"), input_formats=["%Y-%m-%dT%H:%M"])
    end_datetime = forms.DateTimeField(required=True, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"), input_formats=["%Y-%m-%dT%H:%M"])

    class Meta:
        model = TimeEntry
        fields = ["subject", "activity", "start_datetime", "end_datetime", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional note about this session"})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subject"].queryset = Subject.objects.filter(user=user)
        if self.instance and self.instance.pk:
            for field in ("start_datetime", "end_datetime"):
                value = getattr(self.instance, field)
                if value:
                    self.initial[field] = timezone.localtime(value).strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned = super().clean()
        activity = cleaned.get("activity")
        subject = cleaned.get("subject")
        start, end = cleaned.get("start_datetime"), cleaned.get("end_datetime")
        if activity in (TimeEntry.Activity.CLASS, TimeEntry.Activity.NOTES) and not subject:
            self.add_error("subject", "A subject is required for Class and Notes sessions.")
        if start and end and end <= start:
            self.add_error("end_datetime", "End time must be after start time.")
        return cleaned
