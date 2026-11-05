from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Subject, TimeEntry


class StudyTrackTests(TestCase):
    def setUp(self):
        call_command("seed_data")
        self.subject = Subject.objects.first()

    def at(self, day, hour=9, minute=0):
        return timezone.make_aware(datetime.combine(day, time(hour, minute)))

    def entry(self, day, seconds, activity="class", subject=None):
        start = self.at(day)
        return TimeEntry.objects.create(
            subject=self.subject if subject is None and activity in {"class", "notes"} else subject,
            activity=activity, start_datetime=start, end_datetime=start + timedelta(seconds=seconds), notes="Test entry",
        )

    def test_seed_data_creates_exactly_eleven_subjects_idempotently(self):
        call_command("seed_data")
        self.assertEqual(Subject.objects.count(), 11)
        self.assertEqual(Subject.objects.get(pk=1).name, "Subject 1")

    def test_start_timer_creates_persistent_active_entry(self):
        start = self.at(date(2026, 9, 8))
        with patch("tracker.views.timezone.now", return_value=start):
            response = self.client.post(reverse("timer"), {"subject": self.subject.pk, "activity": "class"})
        self.assertRedirects(response, reverse("timer"))
        active = TimeEntry.objects.get(end_datetime__isnull=True)
        self.assertEqual(active.start_datetime, start)
        self.assertEqual(active.duration_seconds, 0)

    def test_stop_timer_calculates_server_duration(self):
        start, end = self.at(date(2026, 9, 8)), self.at(date(2026, 9, 8), 10, 35)
        with patch("tracker.views.timezone.now", return_value=start):
            self.client.post(reverse("timer"), {"subject": self.subject.pk, "activity": "class"})
        with patch("tracker.views.timezone.now", return_value=end):
            self.client.post(reverse("stop_timer"))
        entry = TimeEntry.objects.get()
        self.assertEqual(entry.duration_seconds, 5700)
        self.assertEqual(entry.end_datetime, end)

    def test_only_one_active_timer_is_allowed(self):
        self.client.post(reverse("timer"), {"subject": self.subject.pk, "activity": "class"})
        response = self.client.post(reverse("timer"), {"subject": self.subject.pk, "activity": "notes"}, follow=True)
        self.assertEqual(TimeEntry.objects.filter(end_datetime__isnull=True).count(), 1)
        self.assertContains(response, "A timer is already running")

    def test_active_timer_survives_refresh(self):
        active = TimeEntry.objects.create(subject=self.subject, activity="class", start_datetime=timezone.now() - timedelta(minutes=7))
        response = self.client.get(reverse("timer"))
        self.assertEqual(response.context["active"].pk, active.pk)
        self.assertGreater(response.context["elapsed_seconds"], 400)

    def test_class_and_notes_require_subject(self):
        for activity in ("class", "notes"):
            response = self.client.post(reverse("timer"), {"subject": "", "activity": activity})
            self.assertContains(response, "Choose a subject")
        self.assertEqual(TimeEntry.objects.count(), 0)

    def test_free_time_allows_blank_subject(self):
        response = self.client.post(reverse("timer"), {"subject": "", "activity": "free"})
        self.assertRedirects(response, reverse("timer"))
        self.assertIsNone(TimeEntry.objects.get().subject)

    def test_free_time_is_labeled_practice_time(self):
        response = self.client.get(reverse("timer"))
        activity_choices = dict(response.context["form"].fields["activity"].choices)
        self.assertEqual(activity_choices["free"], "Practice Time")
        self.assertEqual(TimeEntry.Activity.FREE_TIME.label, "Practice Time")

    def test_daily_totals_and_date_filtering(self):
        target, other = date(2026, 9, 8), date(2026, 9, 7)
        self.entry(target, 3600, "class")
        self.entry(target, 1200, "notes")
        self.entry(target, 600, "free", subject=None)
        self.entry(other, 7200, "class")
        response = self.client.get(reverse("dashboard"), {"date": target.isoformat()})
        metrics = response.context["metrics"]
        self.assertEqual((metrics["class"], metrics["notes"], metrics["free"], metrics["study"]), (3600, 1200, 600, 4800))
        self.assertEqual(len(response.context["entries"]), 3)

    def test_weekly_totals_and_matrix(self):
        monday = date(2026, 9, 7)
        self.entry(monday, 3600, "class")
        self.entry(monday + timedelta(days=2), 1800, "class")
        response = self.client.get(reverse("weekly"), {"week": monday.isoformat()})
        self.assertEqual(response.context["metrics"]["class"], 5400)
        self.assertEqual(response.context["rows"][0]["seconds"], 5400)

    def test_monthly_totals_and_subject_summary(self):
        self.entry(date(2026, 9, 2), 1800, "class")
        self.entry(date(2026, 9, 20), 900, "notes")
        self.entry(date(2026, 10, 1), 3600, "class")
        response = self.client.get(reverse("monthly"), {"month": "2026-09"})
        self.assertEqual(response.context["metrics"]["study"], 2700)
        self.assertEqual(response.context["summary"][0]["class_seconds"], 1800)

    def test_edit_recalculates_duration_and_delete_removes_entry(self):
        entry = self.entry(date(2026, 9, 8), 600)
        response = self.client.post(reverse("edit_entry", args=[entry.pk]), {
            "subject": self.subject.pk, "activity": "notes", "start_datetime": "2026-09-08T10:00",
            "end_datetime": "2026-09-08T11:30", "notes": "Updated",
        })
        self.assertRedirects(response, reverse("time_log"))
        entry.refresh_from_db()
        self.assertEqual(entry.duration_seconds, 5400)
        response = self.client.post(reverse("delete_entry", args=[entry.pk]))
        self.assertRedirects(response, reverse("time_log"))
        self.assertFalse(TimeEntry.objects.exists())

    def test_subject_renaming_updates_settings(self):
        payload = {}
        for subject in Subject.objects.all():
            payload[f"name_{subject.pk}"] = "Financial Accounting" if subject == self.subject else subject.name
            payload[f"color_{subject.pk}"] = subject.color
            payload[f"active_{subject.pk}"] = "on"
        response = self.client.post(reverse("settings"), payload)
        self.assertRedirects(response, reverse("settings"))
        self.subject.refresh_from_db()
        self.assertEqual(self.subject.name, "Financial Accounting")

    def test_settings_can_add_subject_with_custom_color(self):
        response = self.client.post(reverse("settings"), {
            "add_subject": "1", "name": "Mathematics", "color": "#123abc",
        })
        self.assertRedirects(response, reverse("settings"))
        added = Subject.objects.get(name="Mathematics")
        self.assertEqual(added.color, "#123abc")
        self.assertTrue(added.active)
        self.assertEqual(Subject.objects.count(), 12)
        timer_form = self.client.get(reverse("timer")).context["form"]
        self.assertTrue(timer_form.fields["subject"].queryset.filter(pk=added.pk).exists())

    def test_settings_rejects_blank_or_duplicate_subject_names(self):
        for name in ("", "subject 1"):
            with self.subTest(name=name):
                response = self.client.post(reverse("settings"), {"add_subject": "1", "name": name, "color": "#123abc"})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "This field is required." if not name else "A subject with this name already exists.")
                self.assertEqual(Subject.objects.count(), 11)

    def test_settings_can_delete_subject_without_sessions(self):
        response = self.client.post(reverse("delete_subject", args=[self.subject.pk]))
        self.assertRedirects(response, reverse("settings"))
        self.assertFalse(Subject.objects.filter(pk=self.subject.pk).exists())

    def test_settings_subject_delete_button_opens_confirmation_modal(self):
        response = self.client.get(reverse("settings"))
        self.assertContains(response, 'data-bs-target="#deleteSubjectModal"')
        self.assertContains(response, f'data-delete-url="{reverse("delete_subject", args=[self.subject.pk])}"')
        self.assertContains(response, f'name="active_{self.subject.pk}"')
        self.assertContains(response, "subject-options")
        self.assertContains(response, "Are you sure you want to delete")
        self.assertContains(response, ">Cancel</button>")
        self.assertContains(response, "> Delete</button>")

    def test_settings_cannot_delete_subject_with_saved_sessions(self):
        entry = self.entry(date(2026, 9, 8), 600)
        response = self.client.post(reverse("delete_subject", args=[self.subject.pk]), follow=True)
        self.assertContains(response, "has saved sessions and cannot be deleted")
        self.assertTrue(Subject.objects.filter(pk=self.subject.pk).exists())
        entry.refresh_from_db()
        self.assertEqual(entry.subject, self.subject)

    def test_subject_delete_requires_post(self):
        response = self.client.get(reverse("delete_subject", args=[self.subject.pk]))
        self.assertEqual(response.status_code, 405)

    def test_csv_export_contains_completed_entries(self):
        self.entry(date(2026, 9, 8), 3600, "class")
        response = self.client.get(reverse("export_time_log"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn(b"Date,Subject,Activity,Start,End,Duration,Notes", response.content)
        self.assertIn(b"Subject 1,Class", response.content)

    def test_health_check_returns_ok(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.content, b"OK")
