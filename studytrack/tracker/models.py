from django.core.exceptions import ValidationError
from django.db import models


class Subject(models.Model):
    name = models.CharField(max_length=120, unique=True)
    color = models.CharField(max_length=7, default="#4f46e5")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class TimeEntry(models.Model):
    class Activity(models.TextChoices):
        CLASS = "class", "Class"
        NOTES = "notes", "Notes"
        FREE_TIME = "free", "Practice Time"
        OTHER = "other", "Other"

    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, null=True, blank=True, related_name="entries")
    activity = models.CharField(max_length=12, choices=Activity.choices)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_datetime"]

    @property
    def is_active(self):
        return self.end_datetime is None

    def clean(self):
        if self.activity in (self.Activity.CLASS, self.Activity.NOTES) and not self.subject:
            raise ValidationError({"subject": "A subject is required for Class and Notes sessions."})
        if self.end_datetime and self.end_datetime <= self.start_datetime:
            raise ValidationError({"end_datetime": "End time must be after start time."})

    def save(self, *args, **kwargs):
        if self.end_datetime:
            self.duration_seconds = max(0, int((self.end_datetime - self.start_datetime).total_seconds()))
        else:
            self.duration_seconds = 0
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_activity_display()} — {self.start_datetime:%d %b %Y}"
