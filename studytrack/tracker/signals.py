from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .defaults import create_default_subjects


@receiver(post_save, sender=get_user_model())
def create_subjects_for_new_user(sender, instance, created, **kwargs):
    if created:
        create_default_subjects(instance)
