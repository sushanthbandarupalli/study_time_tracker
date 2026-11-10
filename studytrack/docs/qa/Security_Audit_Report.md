# StudyTrack Security Audit Report

## Scope

Reviewed Django settings, authentication and authorization behavior, user-scoped data access, timer handling, user-controlled chart labels, CSV export, subject settings, and migration behavior. Automated security-focused regressions ran as part of the 42-test suite. Production application records were not modified.

## Findings and disposition

| Finding | Risk | Disposition |
|---|---|---|
| User-controlled subject labels were serialized in inline chart JavaScript without escaping script-significant characters. | Stored script-context injection risk. | Fixed by escaping `<`, `>`, and `&`; regression test passes. |
| A data-ownership migration deleted existing pre-authentication subject/session data. | Potential irreversible data loss. | Fixed to halt if legacy rows are present; regression test confirms rows remain after the migration aborts. |
| Missing `DEBUG` and `SECRET_KEY` settings had unsafe fallback behavior. | Debug exposure or predictable signed values under misconfiguration. | Fixed: DEBUG defaults false and startup requires a configured secret. |
| Timer creation was not serialized when no active timer row existed. | Race condition could allow multiple active timers. | Fixed by locking the user/account row before checking for an active timer. Parallel-request stress testing remains outstanding. |
| CSV export accepted formula-like values as spreadsheet cells. | Spreadsheet formula execution risk for exported data. | Fixed by neutralizing formula-leading cells; regression test passes. |
| Subject settings did not strictly constrain name length and color format. | Invalid presentation data and malformed stored values. | Fixed with a 120-character cap and six-digit hexadecimal color validation. |
| Unknown email addresses received password-reset email. | Unsolicited email and account-state inference through delivery behavior. | Fixed with `ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False`; generic responses and enumeration prevention remain enabled. |

## Configuration and integration checks

- Django's production deployment check passed with `DEBUG=False` and a temporary strong key.
- The local ignored environment produced warning `security.W009` when checked as production. The configured local key is not reproduced here and was not changed. Confirm a unique, sufficiently strong production key and rotate if necessary.
- Authentication and per-user access tests passed, including denial of cross-user subject/entry access and required sign-in for private pages.
- Neon connectivity and migration state were checked. No production records were altered or restored.
- SMTP credentials authenticated successfully without sending mail. Google OAuth was disabled because client credentials were absent, so its live flow remains unverified.

## Residual risk and limitations

- The migration guard only protects databases where the migration has not already been applied. It cannot recover legacy rows removed by an earlier migration. Backups and explicit data assignment are required before applying it to any database containing legacy rows.
- The timer account-row lock was not validated with a simultaneous-request stress test.
- No load testing, external penetration test, or cross-browser security test was performed.
- Review was limited to the checked-out project and local configuration. No production data was inspected.

## Automated evidence

All 42 Django tests passed after remediation. Relevant cases include `test_chart_json_escapes_user_controlled_subject_names`, `test_legacy_data_migration_stops_without_deleting_existing_rows`, `test_csv_export_neutralizes_spreadsheet_formulas`, `test_user_cannot_access_another_users_subjects_or_entries`, and password-reset tests for both registered and unregistered addresses.
