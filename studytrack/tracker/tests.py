from datetime import date, datetime, time, timedelta
from importlib import import_module
from unittest.mock import Mock, patch

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Subject, TimeEntry
from .auth_utils import GOOGLE_AUTH_TIMESTAMP_SESSION_KEY, GOOGLE_AUTH_UID_SESSION_KEY
from .views import duration


class StudyTrackTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="studyuser",
            email="studyuser@example.com",
            password="SecureStudyPassword!2026",
        )
        self.google_account = SocialAccount.objects.create(
            user=self.user, provider="google", uid="google-studyuser"
        )
        self.client.force_login(self.user)
        call_command("seed_data")
        self.subject = Subject.objects.filter(user=self.user).first()

    def at(self, day, hour=9, minute=0):
        return timezone.make_aware(datetime.combine(day, time(hour, minute)))

    def test_duration_display_always_includes_hours_minutes_and_seconds(self):
        cases = {
            0: "0h 00m 00s",
            59: "0h 00m 59s",
            60: "0h 01m 00s",
            3599: "0h 59m 59s",
            3600: "1h 00m 00s",
            3661: "1h 01m 01s",
        }
        for seconds, expected in cases.items():
            with self.subTest(seconds=seconds):
                self.assertEqual(duration(seconds), expected)

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

    def test_pause_resume_excludes_paused_time_from_elapsed_and_saved_duration(self):
        start = self.at(date(2026, 9, 8))
        paused_at = start + timedelta(hours=1)
        resumed_at = start + timedelta(hours=1, minutes=30)
        with patch("tracker.views.timezone.now", return_value=start):
            self.client.post(reverse("timer"), {"subject": self.subject.pk, "activity": "class"})
        with patch("tracker.views.timezone.now", return_value=paused_at):
            self.client.post(reverse("pause_timer"))
        with patch("tracker.views.timezone.now", return_value=start + timedelta(hours=1, minutes=15)):
            response = self.client.get(reverse("timer"))
        self.assertEqual(response.context["elapsed_seconds"], 3600)
        self.assertContains(response, "Resume timer")
        self.assertContains(response, 'data-paused="true"')
        with patch("tracker.views.timezone.now", return_value=resumed_at):
            self.client.post(reverse("resume_timer"))
        with patch("tracker.views.timezone.now", return_value=start + timedelta(hours=2)):
            response = self.client.get(reverse("timer"))
        self.assertEqual(response.context["elapsed_seconds"], 5400)
        with patch("tracker.views.timezone.now", return_value=start + timedelta(hours=2, minutes=30)):
            self.client.post(reverse("stop_timer"))
        entry = TimeEntry.objects.get()
        self.assertEqual(entry.paused_duration, timedelta(minutes=30))
        self.assertEqual(entry.duration_seconds, 7200)
        self.assertIsNone(entry.paused_at)

    def test_stopping_while_paused_excludes_final_pause_interval(self):
        start = self.at(date(2026, 9, 8))
        paused_at = start + timedelta(minutes=10)
        stopped_at = start + timedelta(minutes=20)
        with patch("tracker.views.timezone.now", return_value=start):
            self.client.post(reverse("timer"), {"subject": self.subject.pk, "activity": "class"})
        with patch("tracker.views.timezone.now", return_value=paused_at):
            self.client.post(reverse("pause_timer"))
        with patch("tracker.views.timezone.now", return_value=stopped_at):
            self.client.post(reverse("stop_timer"))
        entry = TimeEntry.objects.get()
        self.assertEqual(entry.paused_duration, timedelta(minutes=10))
        self.assertEqual(entry.duration_seconds, 600)
        self.assertIsNone(entry.paused_at)

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

    def test_settings_rejects_invalid_subject_color_and_overlong_name(self):
        subjects = list(Subject.objects.filter(user=self.user))
        payload = {}
        for subject in subjects:
            payload[f"name_{subject.pk}"] = subject.name
            payload[f"color_{subject.pk}"] = subject.color
            payload[f"active_{subject.pk}"] = "on"

        payload[f"color_{self.subject.pk}"] = "#12zzzz"
        response = self.client.post(reverse("settings"), payload)
        self.assertRedirects(response, reverse("settings"))
        self.subject.refresh_from_db()
        self.assertEqual(self.subject.color, "#3563e9")

        payload[f"name_{self.subject.pk}"] = "x" * 121
        response = self.client.post(reverse("settings"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Subject names must be 120 characters or fewer.")
        self.subject.refresh_from_db()
        self.assertEqual(self.subject.name, "Subject 1")

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

    def test_sign_in_page_renders_username_login_and_signup_link(self):
        self.client.logout()
        response = self.client.get(reverse("account_login"))
        self.assertContains(response, "Sign in to access your private study data.")
        self.assertContains(response, "Username")
        self.assertContains(response, reverse("account_signup"))
        self.assertContains(response, reverse("account_password_recovery"))
        self.assertContains(response, 'class="auth-remember-toggle"')
        self.assertContains(response, 'class="auth-switch-track"')
        self.assertContains(response, 'id="id_remember"')
        self.assertContains(response, "Remember Me")

    @override_settings(ACCOUNT_RATE_LIMITS=False)
    def test_username_signup_creates_account_without_email_or_automatic_login(self):
        self.client.logout()
        response = self.client.post(reverse("account_signup"), {
            "username": "NewStudent",
            "password1": "A-secure-unique-password-47!",
            "password2": "A-secure-unique-password-47!",
        })
        self.assertRedirects(response, reverse("account_signup_success"))
        new_user = get_user_model().objects.get(username="newstudent")
        self.assertEqual(new_user.email, "")
        self.assertTrue(new_user.check_password("A-secure-unique-password-47!"))
        self.assertEqual(new_user.subjects.count(), 11)
        self.assertFalse(self.client.session.get("_auth_user_id"))
        success_response = self.client.get(reverse("account_signup_success"))
        self.assertContains(success_response, "Account created successfully")
        self.assertContains(success_response, reverse("account_login"))

    @override_settings(ACCOUNT_RATE_LIMITS=False)
    def test_signup_rejects_case_insensitive_duplicate_username(self):
        self.client.logout()
        response = self.client.post(reverse("account_signup"), {
            "username": "STUDYUSER",
            "password1": "A-secure-unique-password-47!",
            "password2": "A-secure-unique-password-47!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This username is already taken.")
        self.assertEqual(get_user_model().objects.filter(username__iexact="studyuser").count(), 1)

    def test_login_with_username_redirects_to_dashboard_when_recovery_is_linked(self):
        self.client.logout()
        response = self.client.post(reverse("account_login"), {
            "login": "studyuser",
            "password": "SecureStudyPassword!2026",
        })
        self.assertRedirects(response, reverse("dashboard"))

    @override_settings(ACCOUNT_RATE_LIMITS=False)
    def test_login_with_unlinked_username_is_sent_to_recovery_setup(self):
        unlinked_user = get_user_model().objects.create_user(
            username="unlinked", password="SecureStudyPassword!2026"
        )
        self.client.logout()
        response = self.client.post(reverse("account_login"), {
            "login": unlinked_user.username,
            "password": "SecureStudyPassword!2026",
        })
        self.assertRedirects(
            response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.get(response["Location"]),
            reverse("account_recovery_setup"),
        )

    @override_settings(
        GOOGLE_OAUTH_ENABLED=True,
        SOCIALACCOUNT_PROVIDERS={"google": {"APP": {"client_id": "test-client", "secret": "test-secret", "key": ""}}},
    )
    def test_google_signup_is_offered_when_oauth_is_configured(self):
        self.client.logout()
        response = self.client.get(reverse("account_signup"))
        self.assertContains(response, "Continue with Google")
        self.assertContains(response, f'action="{reverse("google_login")}?process=signup"')
        self.assertContains(response, 'method="post"')
        login_response = self.client.get(reverse("account_login"))
        self.assertContains(login_response, "Continue with Google")
        self.assertContains(login_response, f'action="{reverse("google_login")}?process=login"')

    def test_unlinked_user_is_required_to_link_google_before_tracker_access(self):
        self.client.logout()
        unlinked_user = get_user_model().objects.create_user(
            username="unlinked", password="SecureStudyPassword!2026"
        )
        self.client.force_login(unlinked_user)
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("account_recovery_setup"))
        setup_response = self.client.get(reverse("account_recovery_setup"))
        self.assertContains(setup_response, "Link a Google account")
        self.assertNotContains(setup_response, "Dashboard</a>")

        SocialAccount.objects.create(
            user=unlinked_user, provider="google", uid="google-unlinked"
        )
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_email_password_reset_route_is_disabled(self):
        self.client.logout()
        response = self.client.get("/accounts/password/reset/")
        self.assertRedirects(response, reverse("account_password_recovery"))
        recovery_response = self.client.get(reverse("account_password_recovery"))
        self.assertContains(recovery_response, "previously linked")

    def test_set_password_requires_a_recent_linked_google_authentication(self):
        response = self.client.get(reverse("account_set_password"))
        self.assertContains(response, "Confirm your identity with the linked Google account")
        self.assertContains(response, "Confirm with Google")

        self.client.post(reverse("account_set_password"), {
            "new_password1": "New-secure-password-58!",
            "new_password2": "New-secure-password-58!",
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("SecureStudyPassword!2026"))

    def test_google_authenticated_user_can_set_password(self):
        session = self.client.session
        session[GOOGLE_AUTH_TIMESTAMP_SESSION_KEY] = timezone.now().timestamp()
        session[GOOGLE_AUTH_UID_SESSION_KEY] = self.google_account.uid
        session.save()

        response = self.client.post(reverse("account_set_password"), {
            "new_password1": "New-secure-password-58!",
            "new_password2": "New-secure-password-58!",
        })
        self.assertRedirects(response, reverse("account_recovery_setup"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("New-secure-password-58!"))

    def test_linked_google_account_cannot_be_removed(self):
        from .auth_adapters import StudyTrackSocialAccountAdapter

        accounts = SocialAccount.objects.filter(user=self.user)
        with self.assertRaisesMessage(
            ValidationError, "A Google account must stay linked so you can recover your password."
        ):
            StudyTrackSocialAccountAdapter().validate_disconnect(
                self.google_account, accounts
            )

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

    def test_csv_export_neutralizes_spreadsheet_formulas(self):
        entry = self.entry(date(2026, 9, 8), 3600, "class")
        entry.notes = " =1+1"
        entry.save()
        response = self.client.get(reverse("export_time_log"))
        self.assertIn(b"' =1+1", response.content)

    def test_chart_json_escapes_user_controlled_subject_names(self):
        self.subject.name = "</script><script>qa()</script>"
        self.subject.save()
        self.entry(timezone.localdate(), 60, "class")
        for url in (reverse("dashboard"), reverse("weekly"), reverse("monthly")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "</script><script>qa()</script>")
                self.assertContains(response, r"\u003C/script\u003E\u003Cscript\u003Eqa()\u003C/script\u003E")

    def test_legacy_data_migration_stops_without_deleting_existing_rows(self):
        migration = import_module("tracker.migrations.0003_user_owned_data")
        historical_models = {name: Mock() for name in ("TimeEntry", "Subject")}
        for model in historical_models.values():
            model.objects.using.return_value.exists.return_value = True
        apps = Mock()
        apps.get_model.side_effect = lambda app_label, model_name: historical_models[model_name]
        schema_editor = Mock()
        schema_editor.connection.alias = "default"

        with self.assertRaisesMessage(RuntimeError, "stopped to prevent data loss"):
            migration.refuse_legacy_data_loss(apps, schema_editor)

        for model in historical_models.values():
            model.objects.using.return_value.delete.assert_not_called()

    def test_health_check_returns_ok(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.content, b"OK")
