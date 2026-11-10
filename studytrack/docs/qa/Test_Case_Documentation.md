# StudyTrack Test Case Documentation

The 42 automated cases are implemented in `tracker/tests.py`. The table groups the coverage by user-visible behavior and records the post-fix result.

| Area | Automated cases | Expected behavior | Result |
|---|---|---|---|
| Subject setup | `test_seed_data_creates_exactly_eleven_subjects_idempotently`, `test_new_user_gets_private_default_subjects` | New accounts receive their own 11 default subjects; reseeding does not duplicate them. | Pass |
| Subject management | `test_subject_renaming_updates_settings`, `test_settings_can_add_subject_with_custom_color`, `test_settings_rejects_blank_or_duplicate_subject_names`, `test_settings_rejects_invalid_subject_color_and_overlong_name`, `test_settings_can_delete_subject_without_sessions`, `test_settings_subject_delete_button_opens_confirmation_modal`, `test_settings_cannot_delete_subject_with_saved_sessions`, `test_subject_delete_requires_post`, `test_manage_dropdown_contains_subject_and_password_links` | Names/colors are validated; add, rename, and safe deletion work; deletion is confirmed and uses POST; subjects with history are protected. | Pass |
| Timer lifecycle | `test_start_timer_creates_persistent_active_entry`, `test_stop_timer_calculates_server_duration`, `test_only_one_active_timer_is_allowed`, `test_active_timer_survives_refresh`, `test_class_and_notes_require_subject`, `test_free_time_allows_blank_subject`, `test_free_time_is_labeled_practice_time`, `test_active_timer_is_isolated_per_user` | Timer state persists, server time determines duration, invalid subject choices are rejected, free/practice time may be unassigned, and users do not share active timers. | Pass |
| Reports and history | `test_daily_totals_and_date_filtering`, `test_weekly_totals_and_matrix`, `test_monthly_totals_and_subject_summary`, `test_edit_recalculates_duration_and_delete_removes_entry` | Date filters, summaries, history edits, and deletes produce consistent totals. | Pass |
| Authentication and authorization | `test_anonymous_visitors_must_sign_in_for_tracker_pages`, `test_health_check_remains_public`, `test_user_cannot_access_another_users_subjects_or_entries`, `test_sign_in_page_renders_email_login_and_signup_link`, `test_email_registration_requires_verification`, `test_signup_with_registered_email_offers_login_without_sending_code`, `test_google_signup_is_offered_when_oauth_is_configured`, `test_password_change_requires_current_password_and_matching_new_password` | Private pages require authentication; user data remains isolated; signup verification, duplicate handling, OAuth availability, and password-change validation follow configured behavior. | Pass |
| Password reset and verification UI | `test_password_reset_does_not_send_email_for_unregistered_address`, `test_password_reset_sends_email_for_registered_address`, `test_password_reset_form_uses_studytrack_styles`, `test_email_verification_page_uses_studytrack_styles` | Unknown addresses receive no email while the generic response is retained; registered addresses can request reset; auth pages retain the application styling. | Pass |
| Email delivery failure handling | `test_signup_email_delivery_failure_shows_error_and_rolls_back_account`, `test_failed_otp_resend_shows_error_on_verification_card` | Delivery failures are surfaced, and failed signup delivery does not leave an incomplete account. | Pass |
| Export and security regressions | `test_csv_export_contains_completed_entries`, `test_csv_export_neutralizes_spreadsheet_formulas`, `test_chart_json_escapes_user_controlled_subject_names`, `test_legacy_data_migration_stops_without_deleting_existing_rows` | CSV output is useful but formula-safe; chart labels cannot escape script context; the migration stops before deleting legacy records. | Pass |
| Health endpoint | `test_health_check_returns_ok` | The public health route returns the expected healthy response. | Pass |

## Browser and responsive cases

Authenticated routes checked at each of 1920x1080, 1366x768, 768x1024, 390x844, and 360x800:

- Dashboard (`/`)
- Timer (`/timer/`)
- Time log (`/log/`)
- Weekly report (`/weekly/`)
- Monthly report (`/monthly/`)
- Subject settings (`/settings/`)

All returned HTTP 200 and had no document-width overflow. The sign-in and password-reset pages were also checked at all five exact viewport pairs. Login switch geometry confirmed the track precedes the label text with a horizontal gap and a vertical-center difference below 0.01 CSS pixels. The password-reset page returned HTTP 200 at all five sizes.

Additional browser checks confirmed rendered charts, timer display updates, Manage menu behavior, the delete confirmation modal, and no JavaScript page errors in the 45-navigation sweep. That sweep ran with an authenticated context; requests for sign-in and signup redirected to the dashboard and are therefore not counted as anonymous page-render tests.

## Limitations

- Signup's anonymous responsive check passed in an earlier width-based sweep, but the exact five width/height pairs were not re-run without an authenticated browser session.
- The browser automation could measure Remember Me layout but could not reliably synthesize pointer clicks on the opacity-hidden checkbox in the resumed session. The checkbox is wrapped by its label; the prior task recorded successful click behavior.
- No load, concurrency stress, or separate Chrome/Firefox validation was run. Timer locking is regression-tested by code inspection and functional tests, not by a simultaneous-request stress case.
