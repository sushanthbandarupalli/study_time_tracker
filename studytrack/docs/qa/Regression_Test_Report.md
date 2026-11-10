# StudyTrack Regression Test Report

## Outcome

| Run | Result | Duration |
|---|---|---:|
| Baseline, before the QA fixes | 38 passed | 631.776 seconds |
| Post-fix full suite | 42 passed | 687.991 seconds |

The regression suite ran with `manage.py test --keepdb` against the isolated Neon test database. No tests failed.

## New regression coverage

Four tests were added for risks found during the audit:

1. `test_settings_rejects_invalid_subject_color_and_overlong_name` verifies input constraints.
2. `test_csv_export_neutralizes_spreadsheet_formulas` verifies spreadsheet-safe export behavior.
3. `test_chart_json_escapes_user_controlled_subject_names` verifies chart data cannot break out of its script context.
4. `test_legacy_data_migration_stops_without_deleting_existing_rows` verifies a migration abort leaves legacy rows intact.

The suite also covers timer start/stop and ownership, reports, subject operations, authentication and authorization, password reset and change, email delivery failures, exports, and the health endpoint. See [`Test_Case_Documentation.md`](./Test_Case_Documentation.md) for the grouped case inventory.

## Additional checks

- Django system checks passed.
- `makemigrations --check` passed with no model changes pending migration.
- Python compilation passed.
- Production deployment checks passed with production-style settings and a temporary strong key.
- Read-only Neon connection check passed.
- Browser responsive checks found no horizontal overflow on tested authenticated pages, login, and password-reset pages at the exact viewport pairs listed in [`QA_Testing_Report.md`](./QA_Testing_Report.md).

## Boundaries

- No stress or load benchmark was run. In particular, timer row-lock behavior lacks a simultaneous-start test.
- Google OAuth was not exercised because credentials were unavailable. SMTP authentication was tested without delivering a message.
- Signup exact-height viewport coverage was not re-run anonymously in the final browser pass; its earlier width-based check passed.
- The application/test database used for the browser fixture was `test_neondb`. The temporary account and all owned test rows were removed and verified absent. No production data was changed.
