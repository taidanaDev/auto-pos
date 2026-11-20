# System architecture

BackonTrack is a server-rendered Django application. Django routes requests to function-based views, checks the session and role, and renders templates or redirects after a write. Services handle document parsing, progress calculations, schedule generation, and report rendering. The Django ORM connects these workflows to the configured relational database.

## Django modules

| Module | Responsibilities |
| --- | --- |
| [`config`](../config/urls.py) | Mounts the dashboard at `/`, accounts at `/accounts/`, academic workflows at `/academics/`, plans at `/pos/`, and Django admin at `/admin/`. Settings configure database connections, sessions, templates, static files, and SMTP. |
| [`accounts`](../accounts/urls.py) | Defines the email-based user model with student and administrator roles. Handles sign-in, role-specific redirects, POST logout, and the first-login password change screen. |
| [`dashboard`](../dashboard/views.py) | Renders the public landing page and role dashboards. The student dashboard reads the same progress service as the dedicated academic progress page. |
| [`academics`](../academics/urls.py) | Registers students, lists and creates curriculum data, previews and saves imports, records grades, and calculates academic progress. |
| [`pos`](../pos/urls.py) | Generates and stores plans, lists draft history, combines saved adjustments with academic data for review, and serves the HTML report preview and PDF attachment. |

The administrator dashboard uses BackonTrack's `admin` role. Django admin is a separate interface governed by Django's `is_staff` flag and model permissions. Academic and POS views also apply their own role guards. The password-change flag is enforced by the login flow and dashboards, with coverage gaps in direct workflow routes documented in the [audit](REPOSITORY_AUDIT.md#security-and-privacy).

## Data model

| Relationship | Purpose |
| --- | --- |
| `Department` → `Program` → `Curriculum` | Organizes curriculum versions by program. A curriculum may supply a total-unit value for progress. |
| `User` ↔ `Student` → `Curriculum` | Each student profile has one account and one assigned curriculum. The profile's section code supplies its recorded year level and term. |
| `Curriculum` → `CurriculumCourse` ← `Course` | Places a catalog course once per curriculum. The placement defines the year, term, display order, required flag, and optional standing text. The catalog course owns its title and unit count. |
| `CourseRequirement` → `Course` and required `Course` | Stores a directed prerequisite or co-requisite relationship. The relationship belongs to the catalog course, so curricula sharing the course also share its requirements. |
| `StudentCourseRecord` → `Student` and `Course` | Stores a grade attempt and credit status. A student/course/school-year/term combination is unique. |
| `POSPlan` → `Student` and `POSPlanItem` → `POSPlan` and `Course` | Stores draft history and the adjusted placement of each moved course or retake. An item may link to an old failed record. A conditional database constraint permits one current plan per student. |

The model definitions and migrations are in [academics](../academics/models.py), [accounts](../accounts/models.py), and [pos](../pos/models.py).

## Request and data flow

1. **Student onboarding.** An administrator submits the registration form or confirms spreadsheet rows. The workflow creates a Django user and linked student in a transaction and invokes the welcome email service. The email uses Django's configured SMTP backend. [Registration views](../academics/views.py), [student import](../academics/student_import_services.py), [email service](../academics/email_service.py).
2. **Curriculum and grade imports.** Django forms check file suffix and size. Format-specific parsers produce candidate rows. The preview sends editable data back through a confirmation form. Server-side validation checks the submitted rows before the save service writes them. Curriculum and student imports retain an upload preview in the session. Grade confirmation uses the school year from its session. [Forms](../academics/forms.py), [curriculum imports](../academics/upload_services.py), [grade imports](../academics/grade_upload_services.py).
3. **Academic evaluation.** Student course records derive their status and credit flag on save. The progress service combines those records with curriculum placements and supplies completed, failed, and remaining lists plus units, percentage, and year standing. [Academic models](../academics/models.py), [progress service](../academics/services.py).
4. **Schedule generation.** A student confirms generation with a POST. The service reads curriculum, dependency, and grade data, calculates adjusted slots, then atomically replaces the current-plan flag and inserts the new draft and its items. [Plan views](../pos/views.py), [scheduler](../pos/services.py).
5. **Review and export.** Detail, preview, and download look up a plan using the signed-in student's profile. The display builder combines saved placements with current academic data. The PDF preview displays shared report markup as HTML. The download view passes a dedicated HTML template to WeasyPrint and returns an `application/pdf` attachment. [Plan display](../pos/services.py), [PDF code](../pos/pdf.py), [report templates](../templates/pos/pdf/).

## Frontend and deployment

The shared [base template](../templates/base.html) provides page layout, messages, Bootstrap, Font Awesome, and the application stylesheet. Responsive components include mobile CSS breakpoints, scrollable tables, and collapsible POS term panels. The login template includes a password visibility control. Static assets are collected with Django and served through WhiteNoise. The repository declares a Gunicorn process and a Linux build script. See the [setup and deployment findings](REPOSITORY_AUDIT.md#setup-and-deployment) for the current deployment blockers.
