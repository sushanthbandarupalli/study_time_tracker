from django.core.management.base import BaseCommand
from tracker.models import Subject


class Command(BaseCommand):
    help = "Create the eleven default StudyTrack subjects without duplicating them."
    colors = ["#3563e9", "#7c4dff", "#16a56b", "#e67e22", "#e55252", "#0f9ca6", "#a855f7", "#d97706", "#db2777", "#4f7dff", "#64748b"]

    def handle(self, *args, **options):
        for number, color in enumerate(self.colors, 1):
            Subject.objects.get_or_create(name=f"Subject {number}", defaults={"color": color})
        self.stdout.write(self.style.SUCCESS("StudyTrack subjects are ready."))
