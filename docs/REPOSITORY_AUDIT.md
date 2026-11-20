# Repository audit

## Scope and repository condition

The audit reviewed routing, views, forms, templates, static assets, models and migrations, import services, the scheduler, PDF rendering, and deployment files. The supplied brief provided the academic design claims. The full academic PDF was unavailable, so its screenshots, test scenarios, reported results, and wording could not be independently checked.

The repository contained the Django project, pinned dependencies, and test modules. It lacked a root README, environment template, and public screenshot gallery. The documentation now links the architecture, scheduling behavior, and feature evidence. The [feature matrix](FEATURE_VERIFICATION.md) records differences from the brief, including the scheduling techniques, course availability checks, and plan comparison.

## Setup and deployment

| Finding | Recommended action |
| --- | --- |
| `DATABASE_URL` takes precedence over the individual PostgreSQL variables. Settings define no usable database if both configurations are absent. A local ignored SQLite file was present. | Use the PostgreSQL instructions in the README. Verify configuration before migrations and keep existing local databases out of demos and Git. |
| The [`Procfile`](../Procfile) targets `AUTOPOS.wsgi:application`. The project declares [`config.wsgi.application`](../config/wsgi.py). | Correct the WSGI target in a separate deployment change and verify a clean startup on the intended host. |
| [`build.sh`](../build.sh) assumes Debian-style system packages and permission to run `apt-get`, then installs dependencies, collects static files, and applies migrations. | Confirm the host's system dependency mechanism and pin its Python environment. Test build, startup, migrations, and static serving in that environment. |
| WhiteNoise uses manifest storage, so Django template rendering with debug off needs collected static assets. Bootstrap, icons, and fonts are loaded from external CDNs. | Run `collectstatic` before a debug-off test run. Check assets in the deployment environment and decide which third-party dependencies to serve locally. |
| Forms accept `.xls`, while pandas uses an additional legacy Excel reader that the pinned requirements and audit environment lack. Image OCR needs the separate Tesseract executable. | Prefer CSV or `.xlsx` for tabular files and text PDFs for grades. Add supported dependencies or narrow the accepted formats after testing. |

## Security and privacy

| Observation | Recommended action |
| --- | --- |
| `DEBUG` defaults to false. Settings include a predictable development fallback for the secret key. Django's deployment check also flagged HTTPS redirect, HSTS, and secure session and CSRF cookies. | Require an environment-specific secret outside development. Configure HTTPS, cookies, and proxy behavior for the target host, then rerun Django's deployment checks. |
| Custom routes use role checks. Detail, preview, and download scope plans to the current student. Password-change enforcement varies across routes. The POS guard order can leave anonymous requests without the intended login redirect. | Centralize ordered login, role, and password-change checks. Cover anonymous, wrong-role, first-login, and cross-student cases in authorization tests. |
| Onboarding derives predictable temporary credentials and includes them in welcome email. Bulk preview data also carries temporary credentials. Registration and email logging can include student identifiers. The helper labeled `async` sends inline. | Use expiring single-use enrollment links, keep reusable credentials out of previews, email, and logs, and deliver notifications after the database commit. |
| Upload forms enforce supported suffixes, a 10 MB maximum, and a nonempty file. Actual parsers provide additional format checks. Preview confirmation and error handling differ across the three upload routes. | Validate decoded content, cap parser workload and row counts, bind confirmations to a server-side preview, and handle malformed input and parser errors uniformly. |
| Manual grades are checked while being written, so an early validation return can preserve earlier writes in the same submission. Grade upload uses a separate save path that lacks the manual-entry protection for previously passed courses. | Validate the full submission before writing and share one grade policy across entry points. Keep provenance for student-entered grades and require institutional review where appropriate. |
| Student identifiers, enrollment details, grades, and PDF exports are sensitive in normal use. The report template includes identifying fields and the PDF attachment name includes the student identifier. | Apply retention and access rules for records and exports. Use synthetic fixtures and sanitized report excerpts for demonstrations. |

The tracked configuration uses environment variables for database and SMTP credentials. The local `.env`, SQLite file, media directory, virtual environment, and Python caches are ignored. A filename-level check of accessible Git history found no tracked `.env`, SQLite database, academic PDF, dump, or backup at the inspected paths. The audit did not inspect the contents of the local `.env` or local database and did not perform a full historical secret scan.

## Testing and verification

| Executed during the audit | Result |
| --- | --- |
| Dependency consistency | `python -m pip check` reported no broken requirements in the existing Python 3.14 environment. Installed versions matched all 38 pins. Git Bash accepted the syntax of `build.sh`. |
| Django system and migration checks | `check` passed. `makemigrations --check --dry-run` found no drift. `showmigrations --plan` resolved the migration graph, and `migrate` applied the schema to a fresh isolated PostgreSQL 17 database. |
| Static collection and deployment checks | `collectstatic --noinput` generated a manifest in a temporary directory. With debug off and a generated audit key, `check --deploy` reported `security.W004`, `W008`, `W012`, and `W016`. |
| Full Django test suite with static assets | The runner reported 15 results on PostgreSQL, including 13 passes, one welcome-email HTML assertion failure, and one `pos.tests` discovery error. `pos.tests` imports `get_student_pdf_display_name`, which is absent from `pos/pdf.py`. The email assertion expects a phrase absent from the current template. |
| Targeted academic tests | All 9 cases in `academics.tests` passed on PostgreSQL. An initial in-memory SQLite run without a collected static manifest caused two additional template errors. Those errors cleared after collecting static files. |
| Synthetic request smoke tests | Exercised both role logins, a cross-role redirect, student and curriculum CSV preview/confirmation, in-memory onboarding email, manual grades, text-PDF grade import, progress, retake and prerequisite placement, saved draft history, cross-student plan denial, HTML preview, and one-page PDF download. Used a temporary local PostgreSQL cluster. |
| PDF output review | WeasyPrint returned a readable PDF attachment. The rendered sample showed that the term summary displays a row count in the units column. The public excerpt shows the schedule with the header and identifying fields omitted. |

**Repository test coverage.** [Academic tests](../academics/tests.py) cover CSV headers, invalid boolean and grade values, parsing ambiguity, record updates, and manual grade re-entry. [Email tests](../academics/tests_email.py) cover message content and registration integration. [POS tests](../pos/tests.py) describe PDF template rules, original and failed-course display, and a scheduling scenario. The POS discovery error prevented those cases from running as shipped. The separate smoke test exercised core POS routes.

**Academic testing and unverified workflows.** The brief does not supply academic test results. The audit did not verify those results, representative academic records, browser responsiveness, real SMTP delivery, curriculum DOCX or PDF uploads, Excel variants, image OCR, complex dependency scenarios, multi-page PDF layout, or a hosted deployment. The browser capture host was unavailable. The README identifies the browser screens still needed.

## Cleanup and follow-up

1. Keep `.env`, virtual environments, SQLite sidecar files, Python caches, uploads, and collected output out of Git. The updated [ignore rules](../.gitignore) cover local environment variants and generated static files while allowing the placeholder [environment template](../.env.example).
2. Keep the academic PDF and any real student data in private storage. Review editor preferences and untracked tooling files before staging. The working tree already had an edited student import template and an untracked editor directory when the audit began.
3. Review the legacy dashboard home template and helper functions with no current route or caller before deciding whether to remove them. The welcome email helper prepares a login link and local image URLs that the current template does not consume. The template uses external image links. Replace them with verified assets and a link resolved from the login route if the welcome message needs direct navigation.
4. Repair stale test assertions and the POS import error. Add focused tests for cycle detection, corequisite alignment, unit totals, upload confirmation, and password-change enforcement. Add CI with a disposable PostgreSQL database and a controlled mail backend.
5. Add explicit course offerings, final schedule validation, and reviewable plan snapshots. Correct the PDF unit total and verify the report's branding and pagination on the intended host.
