from datetime import date, datetime, time, timedelta
import smtplib
import re
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Subject, TimeEntry


class StudyTrackTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="studyuser",
            email="studyuser@example.com",
            password="SecureStudyPassword!2026",
        )
        self.client.force_login(self.user)
        call_command("seed_data")
        self.subject = Subject.objects.filter(user=self.user).first()

    def at(self, day, hour=9, minute=0):
        return timezone.make_aware(datetime.combine(day, time(hour, minute)))

    def entry(self, day, seconds, activity="class", subject=None):
        start = self.at(day)
        return TimeEntry.objects.create(
            user=self.user, subject=self.subject if subject is None and activity in {"class", "notes"} else subject,
            activity=activity, start_datetime=start, end_datetime=start + timedelta(seconds=seconds), notes="Test entry",
        )

    def test_seed_data_creates_exactly_eleven_subjects_idempotently(self):
        call_command("seed_data")
        self.assertEqual(Subject.objects.filter(user=self.user).count(), 11)
        self.assertTrue(Subject.objects.filter(user=self.user, name="Subject 1").exists())

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
        active = TimeEntry.objects.create(user=self.user, subject=self.subject, activity="class", start_datetime=timezone.now() - timedelta(minutes=7))
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
        self.assertEqual(Subject.objects.filter(user=self.user).count(), 12)
        timer_form = self.client.get(reverse("timer")).context["form"]
        self.assertTrue(timer_form.fields["subject"].queryset.filter(pk=added.pk).exists())

    def test_settings_rejects_blank_or_duplicate_subject_names(self):
        for name in ("", "subject 1"):
            with self.subTest(name=name):
                response = self.client.post(reverse("settings"), {"add_subject": "1", "name": name, "color": "#123abc"})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "This field is required." if not name else "A subject with this name already exists.")
                self.assertEqual(Subject.objects.filter(user=self.user).count(), 11)

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

    def test_manage_dropdown_contains_subject_and_password_links(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "/static/tracker/navigation.css")
        self.assertContains(response, "Manage")
        self.assertContains(response, "Manage subjects")
        self.assertContains(response, "Reset Password")
        self.assertContains(response, 'data-bs-toggle="dropdown"')

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

    def test_new_user_gets_private_default_subjects(self):
        other = get_user_model().objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="SecureOtherPassword!2026",
        )
        self.assertEqual(other.subjects.count(), 11)
        self.assertEqual(
            set(other.subjects.values_list("name", flat=True)),
            set(self.user.subjects.values_list("name", flat=True)),
        )
        self.assertNotEqual(other.subjects.first().user_id, self.user.id)
        self.assertEqual(Subject.objects.filter(user=self.user).count(), 11)

    def test_anonymous_visitors_must_sign_in_for_tracker_pages(self):
        self.client.logout()
        for path in (reverse("dashboard"), reverse("timer"), reverse("settings"), reverse("time_log")):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith(reverse("account_login")))

    def test_health_check_remains_public(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("health")).status_code, 200)

    def test_user_cannot_access_another_users_subjects_or_entries(self):
        other = get_user_model().objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="SecureOtherPassword!2026",
        )
        other_subject = other.subjects.first()
        other_entry = TimeEntry.objects.create(
            user=other,
            subject=other_subject,
            activity="class",
            start_datetime=self.at(date(2026, 9, 8)),
            end_datetime=self.at(date(2026, 9, 8), 10),
            notes="Private notes",
        )

        self.assertEqual(self.client.get(reverse("edit_entry", args=[other_entry.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("delete_entry", args=[other_entry.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("delete_subject", args=[other_subject.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("time_log")), "Private notes")
        self.assertNotIn(b"Private notes", self.client.get(reverse("export_time_log")).content)

        response = self.client.post(reverse("timer"), {"subject": other_subject.pk, "activity": "class"})
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(TimeEntry.objects.filter(user=self.user, end_datetime__isnull=True).exists())
        with self.assertRaisesMessage(ValidationError, "Choose one of your own subjects."):
            TimeEntry.objects.create(
                user=self.user, subject=other_subject, activity="class",
                start_datetime=self.at(date(2026, 9, 8)),
            )
        dashboard = self.client.get(reverse("dashboard"))
        self.assertEqual(len(dashboard.context["subjects"]), 11)
        self.assertEqual(dashboard.context["entries"], [])

    def test_sign_in_page_renders_email_login_and_signup_link(self):
        self.client.logout()
        response = self.client.get(reverse("account_login"))
        self.assertContains(response, "Sign in to access your private study data.")
        self.assertContains(response, reverse("account_signup"))
        self.assertContains(response, 'class="auth-remember-toggle"')
        self.assertContains(response, 'class="auth-switch-track"')
        self.assertContains(response, 'id="id_remember"')
        self.assertContains(response, "Remember Me")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_does_not_send_email_for_unregistered_address(self):
        self.client.logout()
        response = self.client.post(reverse("account_reset_password"), {
            "email": "not-registered@example.com",
        })
        self.assertRedirects(response, reverse("account_reset_password_done"))
        self.assertEqual(len(mail.outbox), 0)
        done_response = self.client.get(reverse("account_reset_password_done"))
        self.assertContains(done_response, "/static/tracker/style.css")
        self.assertContains(done_response, "/static/tracker/auth.css")
        self.assertContains(done_response, "If an account exists for that email")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_sends_email_for_registered_address(self):
        self.client.logout()
        EmailAddress.objects.create(
            user=self.user,
            email=self.user.email,
            primary=True,
            verified=True,
        )
        response = self.client.post(reverse("account_reset_password"), {
            "email": self.user.email,
        })
        self.assertRedirects(response, reverse("account_reset_password_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)

    def test_password_reset_form_uses_studytrack_styles(self):
        self.client.logout()
        response = self.client.get(reverse("account_reset_password"))
        self.assertContains(response, "/static/tracker/style.css")
        self.assertContains(response, "/static/tracker/auth.css")
        self.assertContains(response, "app-card form-card auth-card")
        self.assertContains(response, "Reset password")

    def test_email_verification_page_uses_studytrack_styles(self):
        self.client.logout()
        self.client.post(reverse("account_signup"), {
            "email": "verification-screen@example.com",
            "password1": "A-secure-unique-password-47!",
            "password2": "A-secure-unique-password-47!",
        })
        response = self.client.get(reverse("account_email_verification_sent"))
        self.assertContains(response, "/static/tracker/style.css")
        self.assertContains(response, "/static/tracker/auth.css")
        self.assertContains(response, "auth-screen")
        self.assertContains(response, "app-card form-card auth-card")
        self.assertContains(response, "Verify your email")
        self.assertContains(response, "The code expires shortly.")
        self.assertContains(response, "Confirm email")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_signup_with_registered_email_offers_login_without_sending_code(self):
        self.client.logout()
        response = self.client.post(reverse("account_signup"), {
            "email": self.user.email.upper(),
            "password1": "A-secure-unique-password-47!",
            "password2": "A-secure-unique-password-47!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This email is already registered")
        self.assertContains(response, "Try signing in")
        self.assertContains(response, reverse("account_login"))
        self.assertNotContains(response, "Enter the six-digit code")
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(get_user_model().objects.filter(email__iexact=self.user.email).count(), 1)

    @override_settings(
        GOOGLE_OAUTH_ENABLED=True,
        SOCIALACCOUNT_PROVIDERS={"google": {"APP": {"client_id": "test-client", "secret": "test-secret", "key": ""}}},
    )
    def test_google_signup_is_offered_when_oauth_is_configured(self):
        self.client.logout()
        response = self.client.get(reverse("account_signup"))
        self.assertContains(response, "Sign up with Google")
        self.assertContains(response, f'action="{reverse("google_login")}?process=signup"')
        self.assertContains(response, 'method="post"')
        login_response = self.client.get(reverse("account_login"))
        self.assertContains(login_response, "Continue with Google")
        self.assertContains(login_response, f'action="{reverse("google_login")}?process=login"')

    def test_active_timer_is_isolated_per_user(self):
        other = get_user_model().objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="SecureOtherPassword!2026",
        )
        TimeEntry.objects.create(
            user=other, subject=other.subjects.first(), activity="class",
            start_datetime=timezone.now() - timedelta(minutes=5),
        )
        response = self.client.post(reverse("timer"), {"subject": self.subject.pk, "activity": "class"})
        self.assertRedirects(response, reverse("timer"))
        self.assertEqual(TimeEntry.objects.filter(end_datetime__isnull=True).count(), 2)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_registration_requires_verification(self):
        self.client.logout()
        response = self.client.post(reverse("account_signup"), {
            "email": "newuser@example.com",
            "password1": "A-secure-unique-password-47!",
            "password2": "A-secure-unique-password-47!",
        })
        self.assertEqual(response.status_code, 302)
        new_user = get_user_model().objects.get(email="newuser@example.com")
        self.assertFalse(self.client.session.get("_auth_user_id"))
        self.assertTrue(new_user.check_password("A-secure-unique-password-47!"))
        self.assertNotEqual(new_user.password, "A-secure-unique-password-47!")
        self.assertEqual(new_user.subjects.count(), 11)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("newuser@example.com", mail.outbox[0].to)
        self.assertIn("Your email verification code is listed below.", mail.outbox[0].body)
        login_response = self.client.post(reverse("account_login"), {
            "login": "newuser@example.com",
            "password": "A-secure-unique-password-47!",
        })
        self.assertEqual(login_response.status_code, 302)
        self.assertFalse(self.client.session.get("_auth_user_id"))

        code = next(line.strip() for line in mail.outbox[0].body.splitlines() if re.fullmatch(r"\d{6}", line.strip()))
        verification_response = self.client.post(
            reverse("account_email_verification_sent"),
            {"code": code},
        )
        self.assertEqual(verification_response.status_code, 302)
        self.assertTrue(
            EmailAddress.objects.filter(user=new_user, email="newuser@example.com", verified=True).exists()
        )
        verified_login = self.client.post(reverse("account_login"), {
            "login": "newuser@example.com",
            "password": "A-secure-unique-password-47!",
        })
        self.assertEqual(verified_login.status_code, 302)
        self.assertEqual(str(self.client.session["_auth_user_id"]), str(new_user.pk))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    @patch(
        "allauth.account.adapter.DefaultAccountAdapter.send_confirmation_mail",
        side_effect=smtplib.SMTPException("mail service unavailable"),
    )
    def test_signup_email_delivery_failure_shows_error_and_rolls_back_account(self, send_confirmation_mail):
        self.client.logout()
        response = self.client.post(reverse("account_signup"), {
            "email": "delivery-failure@example.com",
            "password1": "A-secure-unique-password-47!",
            "password2": "A-secure-unique-password-47!",
        })
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "Unable to send the OTP", status_code=503)
        self.assertFalse(get_user_model().objects.filter(email="delivery-failure@example.com").exists())

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        ACCOUNT_RATE_LIMITS=False,
    )
    def test_failed_otp_resend_shows_error_on_verification_card(self):
        self.client.logout()
        signup_response = self.client.post(reverse("account_signup"), {
            "email": "resend-failure@example.com",
            "password1": "A-secure-unique-password-47!",
            "password2": "A-secure-unique-password-47!",
        })
        self.assertEqual(signup_response.status_code, 302)

        with patch(
            "allauth.account.adapter.DefaultAccountAdapter.send_confirmation_mail",
            side_effect=smtplib.SMTPException("mail service unavailable"),
        ):
            resend_response = self.client.post(
                reverse("account_email_verification_sent"),
                {"action": "resend"},
                follow=True,
            )
        self.assertContains(resend_response, "Unable to send the OTP")
        self.assertContains(resend_response, "alert-danger")
        self.assertContains(resend_response, "Verify your email")

    def test_password_change_requires_current_password_and_matching_new_password(self):
        self.user.set_password("Existing-password-47!")
        self.user.save(update_fields=["password"])
        self.client.force_login(self.user)
        change_url = reverse("account_change_password")

        page_response = self.client.get(change_url)
        self.assertContains(page_response, "/static/tracker/style.css")
        self.assertContains(page_response, "/static/tracker/auth.css")
        self.assertContains(page_response, "app-card form-card auth-card")
        self.assertContains(page_response, f'href="{change_url}"')

        invalid_response = self.client.post(change_url, {
            "oldpassword": "Incorrect-password-47!",
            "password1": "New-secure-password-58!",
            "password2": "New-secure-password-58!",
        })
        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, "Please type your current password.")
        self.assertTrue(self.user.check_password("Existing-password-47!"))

        mismatch_response = self.client.post(change_url, {
            "oldpassword": "Existing-password-47!",
            "password1": "New-secure-password-58!",
            "password2": "Different-password-69!",
        })
        self.assertEqual(mismatch_response.status_code, 200)
        self.assertContains(mismatch_response, "You must type the same password each time.")
        self.assertTrue(self.user.check_password("Existing-password-47!"))

        success_response = self.client.post(change_url, {
            "oldpassword": "Existing-password-47!",
            "password1": "New-secure-password-58!",
            "password2": "New-secure-password-58!",
        })
        self.assertRedirects(success_response, change_url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("New-secure-password-58!"))

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
