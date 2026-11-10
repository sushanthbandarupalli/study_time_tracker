# StudyTrack Bug and Fix Report

This report records confirmed findings from the QA pass and the remediations made in the current worktree. The complete automated suite passed after the fixes.

| Finding | Impact | Fix | Verification |
|---|---|---|---|
| Subject names were inserted into inline chart JavaScript without script-context escaping. | A crafted user-controlled label could break out of a script data context. | Escape `<`, `>`, and `&` in chart JSON serialization. | `test_chart_json_escapes_user_controlled_subject_names` passed; charts rendered in browser checks. |
| The account-ownership migration could delete pre-authentication subjects and sessions. | Existing study history could be irreversibly lost on a database where the migration had not yet run. | Migration now aborts when legacy rows exist, requiring backup and explicit assignment instead of deletion. | `test_legacy_data_migration_stops_without_deleting_existing_rows` passed. |
| Missing `DEBUG` defaulted to enabled and a missing secret key had a known fallback. | Unsafe defaults could expose debug details or enable predictable signing tokens in a misconfigured deployment. | `DEBUG` now defaults to false and startup fails if `SECRET_KEY` is absent. | Django checks passed; production deployment check passed with a temporary strong key. |
| Two simultaneous timer-start requests could both observe no active timer. | Concurrent requests could create multiple active timers for one account. | Lock the account row before checking and creating the active timer. | Timer lifecycle tests passed; no parallel-request stress test was run. |
| CSV subject/note values could be interpreted as spreadsheet formulas. | Exported files could execute formulas when opened in spreadsheet software. | Neutralize formula-like exported cells. | `test_csv_export_neutralizes_spreadsheet_formulas` and CSV export test passed. |
| Subject settings accepted overlong names and arbitrary color strings. | Invalid or unsafe values could be stored and disrupt presentation. | Enforce a 120-character name limit and six-digit hex colors. | `test_settings_rejects_invalid_subject_color_and_overlong_name` passed. |
| Password reset sent mail to unknown addresses. | Unregistered recipients received unsolicited reset mail and could use delivery behavior to probe the reset flow. | Set `ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False` while retaining the generic response and enumeration prevention. | Unknown/registered reset tests passed: no mail for unknown address; mail is still queued for a registered account. |
| Remember Me switch and label had been overlapping. | Login control was difficult to read and operate, especially on mobile. | Use the existing toggle, switch-track, and wrapper classes as a flex label with consistent gap and alignment. | Exact viewport geometry and screenshots show side-by-side alignment with no horizontal overflow. Prior browser verification recorded click behavior; the resumed hidden-checkbox pointer automation was inconclusive. |

## Remaining observations

- A production-style check against the local ignored environment produced Django warning `security.W009` for the locally configured key. The key was not displayed, changed, or copied into this report. Use a unique strong `SECRET_KEY` in production and rotate it if a weak key has ever been deployed.
- The migration safeguard prevents future deletion when migration 0003 has not yet been applied. It cannot restore rows deleted by an already-applied migration. No production rows were inspected or modified as part of this QA run.
- SMTP authentication was checked without sending email. Google OAuth could not be exercised because credentials are not configured.
