import csv
from datetime import date, timedelta, datetime
from io import StringIO

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, case
from werkzeug.security import generate_password_hash

from models import (
    db,
    Mentor,
    User,
    Faculty,
    Student,
    Company,
    DailyLog,
    Project,
    Certificate,
    Assessment,
    ReadinessScore,
    QuestionBank,
    MentorFeedback,
    AcademicProfile,
    StudentSubjectRecord,
    AcademicBacklog,
    AcademicEvent,
)
from routes import mentor_required
from routes.student import _save_upload


mentor_bp = Blueprint("mentor", __name__, url_prefix="/admin")


def _get_mentor():
    return Mentor.query.get_or_404(current_user.id)


def _consistency_percent(student_id, days=7):
    start_date = date.today() - timedelta(days=days - 1)
    logged_days = DailyLog.query.filter(
        DailyLog.student_id == student_id,
        DailyLog.log_date >= start_date,
        DailyLog.log_date <= date.today(),
    ).count()
    return round((logged_days / days) * 100, 2)


@mentor_bp.route("/dashboard")
@login_required
@mentor_required
def dashboard():
    mentor = _get_mentor()
    today = date.today()
    last_7 = today - timedelta(days=7)

    total_students = Student.query.count()
    active_students = Student.query.filter(Student.last_logged_date >= last_7).count()
    upcoming_drives = Company.query.filter(Company.drive_date >= today).count()
    total_faculty = Faculty.query.count()
    total_admins = User.query.filter_by(role="admin").count()
    academic_risk_students = (
        db.session.query(Student)
        .outerjoin(AcademicProfile, AcademicProfile.student_id == Student.id)
        .outerjoin(AcademicBacklog, AcademicBacklog.student_id == Student.id)
        .group_by(Student.id, AcademicProfile.current_sgpa)
        .having((func.coalesce(AcademicProfile.current_sgpa, 0) < 6.5) | (func.sum(case((AcademicBacklog.status == "Active", 1), else_=0)) > 0))
        .count()
    )

    min_scores = (
        db.session.query(
            ReadinessScore.student_id.label("student_id"),
            func.min(ReadinessScore.score).label("min_score"),
        )
        .group_by(ReadinessScore.student_id)
        .subquery()
    )

    weak_students = (
        db.session.query(Student, ReadinessScore)
        .join(min_scores, min_scores.c.student_id == Student.id)
        .join(
            ReadinessScore,
            (ReadinessScore.student_id == Student.id)
            & (ReadinessScore.score == min_scores.c.min_score),
        )
        .filter(min_scores.c.min_score < 40)
        .order_by(min_scores.c.min_score.asc())
        .limit(10)
        .all()
    )

    key_companies = Company.query.filter(Company.drive_date >= today).order_by(Company.drive_date.asc()).limit(5).all()

    return render_template(
        "mentor/dashboard.html",
        mentor=mentor,
        total_students=total_students,
        active_students=active_students,
        upcoming_drives=upcoming_drives,
        total_faculty=total_faculty,
        total_admins=total_admins,
        academic_risk_students=academic_risk_students,
        weak_students=weak_students,
        key_companies=key_companies,
    )


@mentor_bp.route("/staff", methods=["GET", "POST"])
@login_required
@mentor_required
def staff():
    if request.method == "POST":
        action = request.form.get("action", "").strip()
        if action == "update_faculty_department":
            faculty_id = request.form.get("faculty_id", type=int)
            department = request.form.get("department", "").strip()
            faculty = Faculty.query.get_or_404(faculty_id)
            faculty.department = department
            db.session.commit()
            flash("Faculty monitoring department updated.", "success")
            return redirect(url_for("mentor.staff"))

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        full_name = request.form.get("full_name", "").strip()
        department = request.form.get("department", "").strip()

        if action not in {"add_faculty", "add_admin"}:
            flash("Invalid action.", "danger")
            return redirect(url_for("mentor.staff"))
        if not email or "@" not in email:
            flash("Valid email is required.", "danger")
            return redirect(url_for("mentor.staff"))
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return redirect(url_for("mentor.staff"))
        if User.query.filter_by(email=email).first():
            flash("Email already exists.", "warning")
            return redirect(url_for("mentor.staff"))

        if action == "add_admin":
            user = User(email=email, password_hash=generate_password_hash(password), role="admin")
            db.session.add(user)
            db.session.flush()
            db.session.add(Mentor(id=user.id, full_name=full_name or "Admin", department=department or "Placement Cell"))
            db.session.commit()
            flash("Admin added successfully.", "success")
            return redirect(url_for("mentor.staff"))

        user = User(email=email, password_hash=generate_password_hash(password), role="faculty")
        db.session.add(user)
        db.session.flush()
        db.session.add(Faculty(id=user.id, full_name=full_name or "Faculty", department=department or "General"))
        db.session.commit()
        flash("Faculty added successfully.", "success")
        return redirect(url_for("mentor.staff"))

    staff_departments = sorted({d for (d,) in db.session.query(Faculty.department).distinct().all() if d})
    faculties = Faculty.query.order_by(Faculty.department.asc(), Faculty.full_name.asc()).all()
    admins = Mentor.query.order_by(Mentor.department.asc(), Mentor.full_name.asc()).all()
    faculty_stats = {}
    for f in faculties:
        student_query = Student.query
        if f.department:
            student_query = student_query.filter(Student.department == f.department)
        monitored_students = student_query.count()
        weak_students = (
            student_query.outerjoin(AcademicProfile, AcademicProfile.student_id == Student.id)
            .outerjoin(AcademicBacklog, AcademicBacklog.student_id == Student.id)
            .group_by(Student.id, AcademicProfile.current_sgpa)
            .having((func.coalesce(AcademicProfile.current_sgpa, 0) < 6.5) | (func.sum(case((AcademicBacklog.status == "Active", 1), else_=0)) > 0))
            .count()
        )
        faculty_stats[f.id] = {
            "monitored_students": monitored_students,
            "weak_students": weak_students,
        }

    return render_template(
        "mentor/staff.html",
        faculties=faculties,
        admins=admins,
        staff_departments=staff_departments,
        faculty_stats=faculty_stats,
    )


@mentor_bp.route("/companies", methods=["GET", "POST"])
@login_required
@mentor_required
def companies():
    mentor = _get_mentor()

    if request.method == "POST":
        action = request.form.get("action")

        if action in {"add", "edit"}:
            company_id = request.form.get("company_id", type=int)
            name = request.form.get("name", "").strip()
            drive_date = request.form.get("drive_date", "").strip()
            required_skills = request.form.get("required_skills", "").strip()
            eligibility_criteria = request.form.get("eligibility_criteria", "").strip()
            focus_topics = request.form.get("focus_topics", "").strip()
            package_details = request.form.get("package_details", "").strip()

            if not name:
                flash("Company name is required.", "danger")
                return redirect(url_for("mentor.companies"))

            dt = None
            if drive_date:
                try:
                    dt = datetime.strptime(drive_date, "%Y-%m-%d").date()
                except ValueError:
                    flash("Invalid drive date.", "danger")
                    return redirect(url_for("mentor.companies"))

            if action == "edit" and company_id:
                company = Company.query.get_or_404(company_id)
            else:
                company = Company(created_by=mentor.id)
                db.session.add(company)

            company.name = name
            company.drive_date = dt
            company.required_skills = required_skills
            company.eligibility_criteria = eligibility_criteria
            company.focus_topics = focus_topics
            company.package_details = package_details

            logo = request.files.get("logo")
            if logo and logo.filename:
                path = _save_upload(logo, "company_logos", current_app.config["ALLOWED_IMAGE_EXTENSIONS"])
                if not path:
                    flash("Logo must be jpg/jpeg/png.", "danger")
                    return redirect(url_for("mentor.companies"))
                company.logo_path = path

            db.session.commit()
            flash("Company saved successfully.", "success")
            return redirect(url_for("mentor.companies"))

        if action == "delete":
            company_id = request.form.get("company_id", type=int)
            company = Company.query.get_or_404(company_id)
            ReadinessScore.query.filter_by(company_id=company_id).delete(synchronize_session=False)
            Assessment.query.filter_by(company_id=company_id).delete(synchronize_session=False)
            db.session.delete(company)
            db.session.commit()
            flash("Company deleted.", "info")
            return redirect(url_for("mentor.companies"))

        if action == "add_question":
            company_id = request.form.get("company_id", type=int) or None
            skill_category = request.form.get("skill_category", "").strip()
            question_type = request.form.get("question_type", "").strip()
            question_text = request.form.get("question_text", "").strip()
            options_raw = request.form.get("options", "").strip()
            correct_answer = request.form.get("correct_answer", "").strip()
            difficulty = request.form.get("difficulty", "").strip()

            if not skill_category or not question_text or question_type not in {"MCQ", "Coding", "Aptitude"}:
                flash("Question data is invalid.", "danger")
                return redirect(url_for("mentor.companies"))

            options = None
            if options_raw:
                options = [x.strip() for x in options_raw.split("|") if x.strip()]

            qb = QuestionBank(
                company_id=company_id,
                skill_category=skill_category,
                question_type=question_type,
                question_text=question_text,
                options=options,
                correct_answer=correct_answer,
                difficulty=difficulty if difficulty in {"Easy", "Medium", "Hard"} else None,
                created_by=mentor.id,
            )
            db.session.add(qb)
            db.session.commit()
            flash("Question added.", "success")
            return redirect(url_for("mentor.companies"))

        if action == "upload_csv":
            csv_file = request.files.get("questions_csv")
            company_id = request.form.get("company_id", type=int) or None
            if not csv_file or not csv_file.filename.endswith(".csv"):
                flash("Please upload a valid CSV file.", "danger")
                return redirect(url_for("mentor.companies"))

            decoded = csv_file.stream.read().decode("utf-8", errors="ignore")
            reader = csv.DictReader(StringIO(decoded))
            count = 0
            skipped = 0
            allowed_types = {"MCQ", "Coding", "Aptitude"}
            allowed_difficulty = {"Easy", "Medium", "Hard"}
            for raw_row in reader:
                try:
                    row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items()}

                    options = []
                    for key in ["option_a", "option_b", "option_c", "option_d"]:
                        if row.get(key):
                            options.append(row[key])
                    if not options and row.get("options"):
                        raw_options = row.get("options", "")
                        delimiter = "|" if "|" in raw_options else ","
                        options = [x.strip() for x in raw_options.split(delimiter) if x.strip()]

                    raw_type = (row.get("question_type") or row.get("type") or "MCQ").strip().lower()
                    if raw_type in {"mcq"}:
                        q_type = "MCQ"
                    elif raw_type in {"coding", "code"}:
                        q_type = "Coding"
                    elif raw_type in {"aptitude", "verbal"}:
                        q_type = "Aptitude"
                    else:
                        q_type = "MCQ"
                    if q_type not in allowed_types:
                        q_type = "MCQ"

                    diff = (row.get("difficulty") or "Medium").strip().capitalize()
                    if diff not in allowed_difficulty:
                        diff = "Medium"

                    text = (row.get("question_text") or row.get("question") or "").strip()
                    if not text:
                        skipped += 1
                        continue

                    skill = (row.get("skill_category") or row.get("skill") or "General").strip()
                    correct_answer = (row.get("correct_answer") or row.get("answer") or "").strip()

                    qb = QuestionBank(
                        company_id=company_id,
                        skill_category=skill,
                        question_type=q_type,
                        question_text=text,
                        options=options if options else None,
                        correct_answer=correct_answer,
                        difficulty=diff,
                        created_by=mentor.id,
                    )
                    db.session.add(qb)
                    count += 1
                except Exception:
                    db.session.rollback()
                    skipped += 1

            db.session.commit()
            flash(f"{count} questions imported from CSV. Skipped: {skipped}.", "success")
            return redirect(url_for("mentor.companies"))

    companies_list = Company.query.order_by(Company.drive_date.asc()).all()
    questions = QuestionBank.query.order_by(QuestionBank.id.desc()).limit(20).all()
    return render_template("mentor/manage_companies.html", companies=companies_list, questions=questions)


@mentor_bp.route("/students")
@login_required
@mentor_required
def students():
    department = request.args.get("department", "").strip()
    skill = request.args.get("skill", "").strip()
    student_id = request.args.get("student_id", type=int)

    query = Student.query
    if department:
        query = query.filter(Student.department == department)
    if skill:
        query = query.filter(Student.skills.ilike(f"%{skill}%"))

    all_students = query.order_by(Student.id.desc()).all()
    consistency_map = {s.id: _consistency_percent(s.id, 7) for s in all_students}

    selected = Student.query.get(student_id) if student_id else None
    details = None
    if selected:
        details = {
            "logs": DailyLog.query.filter_by(student_id=selected.id).order_by(DailyLog.log_date.desc()).limit(14).all(),
            "projects": Project.query.filter_by(student_id=selected.id).order_by(Project.created_at.desc()).all(),
            "certificates": Certificate.query.filter_by(student_id=selected.id).order_by(Certificate.uploaded_at.desc()).all(),
            "readiness": ReadinessScore.query.filter_by(student_id=selected.id).order_by(ReadinessScore.score.desc()).all(),
            "assessments": Assessment.query.filter_by(student_id=selected.id).order_by(Assessment.created_at.desc()).limit(10).all(),
            "academic_profile": AcademicProfile.query.filter_by(student_id=selected.id).first(),
            "subject_records": StudentSubjectRecord.query.filter_by(student_id=selected.id).order_by(StudentSubjectRecord.updated_at.desc()).all(),
            "backlogs": AcademicBacklog.query.filter_by(student_id=selected.id).order_by(AcademicBacklog.created_at.desc()).all(),
            "events": AcademicEvent.query.filter_by(student_id=selected.id).order_by(AcademicEvent.due_date.asc()).all(),
            "consistency": _consistency_percent(selected.id, 7),
        }

    weak_students = (
        db.session.query(Student, ReadinessScore)
        .join(ReadinessScore, ReadinessScore.student_id == Student.id)
        .filter(ReadinessScore.score < 40)
        .order_by(ReadinessScore.score.asc())
        .limit(20)
        .all()
    )
    weak_academic_students = (
        db.session.query(Student)
        .outerjoin(AcademicProfile, AcademicProfile.student_id == Student.id)
        .outerjoin(AcademicBacklog, AcademicBacklog.student_id == Student.id)
        .group_by(Student.id, AcademicProfile.current_sgpa)
        .having((func.coalesce(AcademicProfile.current_sgpa, 0) < 6.5) | (func.sum(case((AcademicBacklog.status == "Active", 1), else_=0)) > 0))
        .all()
    )

    companies_list = Company.query.order_by(Company.name.asc()).all()
    top_per_company = {}
    for company in companies_list:
        rows = (
            db.session.query(Student, ReadinessScore)
            .join(ReadinessScore, ReadinessScore.student_id == Student.id)
            .filter(ReadinessScore.company_id == company.id)
            .order_by(ReadinessScore.score.desc())
            .limit(10)
            .all()
        )
        top_per_company[company.id] = rows

    return render_template(
        "mentor/students.html",
        students=all_students,
        consistency_map=consistency_map,
        selected=selected,
        details=details,
        weak_students=weak_students,
        weak_academic_students=weak_academic_students,
        companies=companies_list,
        top_per_company=top_per_company,
        filters={"department": department, "skill": skill},
    )


@mentor_bp.route("/feedback/<int:student_id>", methods=["GET", "POST"])
@login_required
@mentor_required
def feedback(student_id):
    mentor = _get_mentor()
    student = Student.query.get_or_404(student_id)

    if request.method == "POST":
        feedback_text = request.form.get("feedback", "").strip()
        if not feedback_text:
            flash("Feedback cannot be empty.", "danger")
            return redirect(url_for("mentor.feedback", student_id=student_id))

        fb = MentorFeedback(mentor_id=mentor.id, student_id=student.id, feedback=feedback_text)
        db.session.add(fb)
        db.session.commit()
        flash("Feedback sent to student.", "success")
        return redirect(url_for("mentor.feedback", student_id=student_id))

    feedback_list = (
        MentorFeedback.query.filter_by(student_id=student.id)
        .order_by(MentorFeedback.created_at.desc())
        .all()
    )
    return render_template("mentor/feedback.html", student=student, feedback_list=feedback_list)
