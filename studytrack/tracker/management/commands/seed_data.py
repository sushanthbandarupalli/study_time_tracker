from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from tracker.defaults import create_default_subjects


class Command(BaseCommand):
    help = "Ensure each registered user has the eleven default StudyTrack subjects."

    def handle(self, *args, **options):
        users = get_user_model().objects.all()
        for user in users.iterator():
            create_default_subjects(user)
        self.stdout.write(self.style.SUCCESS(f"Default subjects are ready for {users.count()} users."))
