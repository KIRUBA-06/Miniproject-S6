# Career Success Tracker (Flask + MySQL)

Production-style placement preparation tracker for students and mentors.

## Features
- Role-based authentication (`student`, `mentor`) with `Flask-Login`.
- Student modules:
  - Profile management with resume/profile uploads.
  - Daily activity logging with streak logic and badges.
  - Project and certificate CRUD.
  - Company eligibility + registration.
  - Adaptive assessment engine.
  - Company-wise readiness scoring and ranking.
- Mentor modules:
  - Dashboard analytics (active/weak students, upcoming drives).
  - Company CRUD.
  - Question bank management (manual + CSV upload).
  - Student deep monitoring and personalized feedback.
- Security:
  - Password hashing.
  - CSRF token protection (manual token implementation).
  - Server-side validation.
  - 5MB upload limit and extension filtering.
  - SQLAlchemy ORM to prevent SQL injection.

## Setup
1. Create DB:
```sql
CREATE DATABASE career_success_tracker CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure env vars:
```powershell
$env:SECRET_KEY="your-strong-secret-key"
$env:DATABASE_URL="mysql+pymysql://root:password@localhost/career_success_tracker"
```

4. Initialize DB:
```bash
flask --app app.py init-db
```

5. Run:
```bash
flask --app app.py run
```

## Render Deployment Notes
- Set `SECRET_KEY` in Render environment variables.
- Set `DATABASE_URL` using `mysql+pymysql://...`
- `AUTO_INIT_DB=true` is enabled by default, so the app attempts to create tables on startup.
- If deployment still fails, check Render logs for database host/username/password issues.

## Mentor Creation
Mentor accounts are created manually in DB as specified.
- Insert into `users` with role `mentor`.
- Insert into `mentors` with same id.
