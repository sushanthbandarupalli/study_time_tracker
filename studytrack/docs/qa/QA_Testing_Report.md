# StudyTrack QA Testing Report

## Summary

The post-fix Django suite passed all 42 tests. Django configuration and migration checks passed, and the production deployment check was clean when run with `DEBUG=False` and a temporary strong key. Responsive checks found no horizontal overflow on the authenticated routes and public sign-in/reset pages tested at the specified viewports.

The audit made targeted fixes for chart-script escaping, legacy-data migration safety, secret/debug defaults, concurrent timer starts, CSV formula injection, and subject input validation. The configured Neon test database was used for test and browser fixtures; production application records were not modified.

## Scope and environment

- Django 5.2.6, django-allauth 65.21.1, Python 3.12, PostgreSQL on Neon.
- Functional baseline and post-fix tests ran with `manage.py test --keepdb` against the isolated test database.
- Read-only database connectivity was confirmed with `SELECT 1`; configured migrations were applied.
- Browser UI checks ran against local StudyTrack at port 8001 and used only a temporary account in `test_neondb`.
- The isolated QA user, its 11 subjects, and 2 entries were removed after testing. The test database was verified to have zero users, subjects, and entries. The QA server was stopped. The normal local server on port 8000 was left running.

## Results

| Area | Result |
|---|---|
| Baseline regression suite | 38 passed in 631.776 seconds |
| Post-fix regression suite | 42 passed in 687.991 seconds |
| Django checks | Passed |
| Migration consistency (`makemigrations --check`) | Passed |
| Python compilation | Passed |
| Production deployment check | Passed with `DEBUG=False` and a temporary strong key |
| Neon connectivity | Read-only connection check passed |
| Responsive authenticated UI | Dashboard, timer, time log, weekly, monthly, and subject settings: HTTP 200 and no horizontal overflow at all five exact viewports |
| Responsive sign-in UI | HTTP 200 and no horizontal overflow at all five exact viewports; switch and label were side-by-side and vertically aligned |
| Responsive password-reset request UI | HTTP 200 and no horizontal overflow at all five exact viewports |
| Browser JavaScript errors | None in the 45-navigation sweep |
| Gmail SMTP | Authentication succeeded; no email was sent |
| Google OAuth | Not end-to-end tested; credentials are not configured and OAuth is disabled |

Exact viewports: 1920x1080, 1366x768, 768x1024, 390x844, and 360x800. Responsive browser results are based on CSS viewport dimensions. Evidence screenshots are rasterized at the integrated browser's 1.25 device-pixel ratio.

The 45-navigation sweep covered nine routes at five sizes. In the authenticated browser context, sign-in and signup requests redirected to the dashboard, so those responses are not counted as anonymous-page renders. Sign-in and password-reset pages were subsequently rendered anonymously at the exact viewports. Signup had passed an earlier width-based responsive check; its exact height combinations were not re-run anonymously.

## Functional browser checks

- Confirmed dashboard charts rendered on dashboard and reporting pages, with no browser JavaScript errors.
- Confirmed timer clock updates and timer page rendering.
- Confirmed Manage navigation behavior on desktop and mobile, and the subject-delete confirmation modal.
- Verified the login Remember Me switch and label layout geometrically at all five viewport sizes. Direct automated pointer interaction with the opacity-hidden checkbox was inconclusive in the resumed browser session; prior browser verification recorded the switch/label click behavior.
- No production-row mutation, load benchmark, parallel-request stress test, or separate Chrome/Firefox cross-browser run was performed.

## Evidence

Screenshots are in [`Test_Evidence/`](./Test_Evidence/):

- [`login-1366x768.png`](./Test_Evidence/login-1366x768.png)
- [`login-390x844.png`](./Test_Evidence/login-390x844.png)
- [`dashboard-390x844.png`](./Test_Evidence/dashboard-390x844.png)
- [`timer-1366x768.png`](./Test_Evidence/timer-1366x768.png)

Detailed functional coverage is documented in [`Test_Case_Documentation.md`](./Test_Case_Documentation.md). Defects and remediations are in [`Bug_and_Fix_Report.md`](./Bug_and_Fix_Report.md), security details in [`Security_Audit_Report.md`](./Security_Audit_Report.md), and post-fix verification in [`Regression_Test_Report.md`](./Regression_Test_Report.md).
