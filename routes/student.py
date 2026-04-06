import os
import re
import uuid
from datetime import date, timedelta, datetime
from decimal import Decimal

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import func, and_

from models import (
    db,
    Student,
    Company,
    DailyLog,
    Project,
    Certificate,
    Registration,
    QuestionBank,
    Assessment,
    ReadinessScore,
    MentorFeedback,
    AcademicProfile,
    AcademicSubject,
    StudentSubjectRecord,
    AcademicBacklog,
    AcademicEvent,
    AcademicDocument,
)
from routes import student_required


student_bp = Blueprint("student", __name__, url_prefix="/student")


def _random_order_expr():
    # SQLite uses RANDOM(), MySQL uses RAND().
    engine_name = db.engine.dialect.name
    if engine_name == "sqlite":
        return func.random()
    return func.rand()


def _is_valid_url(value):
    if not value:
        return True
    pattern = re.compile(r"^https?://[^\s/$.?#].[^\s]*$")
    return bool(pattern.match(value))


def _allowed_file(filename, allowed):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def _save_upload(file_storage, subfolder, allowed_extensions):
    if not file_storage or not file_storage.filename:
        return None
    if not _allowed_file(file_storage.filename, allowed_extensions):
        return None

    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], subfolder)
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, secure_filename(unique_name))
    file_storage.save(file_path)

    return file_path.replace("\\", "/")


def _parse_list_field(value):
    if not value:
        return []
    value = value.strip()
    if not value:
        return []
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [x.strip().strip('"').strip("'") for x in value.split(",") if x.strip()]


def _parse_cgpa_threshold(criteria_text):
    if not criteria_text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", criteria_text)
    if match:
        return Decimal(match.group(1))
    return None


def _student_eligible(student, company):
    cgpa_threshold = _parse_cgpa_threshold(company.eligibility_criteria)
    student_cgpa = student.cgpa if student.cgpa is not None else Decimal("0.00")
    cgpa_ok = cgpa_threshold is None or student_cgpa >= cgpa_threshold

    student_skills = {s.lower() for s in _parse_list_field(student.skills)}
    required_skills = {s.lower() for s in _parse_list_field(company.required_skills)}
    skill_ok = True if not required_skills else bool(student_skills.intersection(required_skills))
    return cgpa_ok and skill_ok


def _company_domain_matches(company):
    req = " ".join(_parse_list_field(company.required_skills)).lower()
    focus = (company.focus_topics or "").lower()
    blob = f"{req} {focus}"

    domains = set()
    if any(k in blob for k in ["web", "frontend", "backend", "javascript", "flask", "django"]):
        domains.add("Web")
    if any(k in blob for k in ["ai", "deep learning", "nlp"]):
        domains.add("AI")
    if any(k in blob for k in ["ml", "machine learning", "data science"]):
        domains.add("ML")
    if any(k in blob for k in ["android", "ios", "mobile", "app"]):
        domains.add("App")
    if any(k in blob for k in ["cloud", "aws", "azure", "gcp", "devops"]):
        domains.add("Cloud")
    if any(k in blob for k in ["security", "cyber", "network security"]):
        domains.add("Cybersecurity")
    return domains


def _compute_readiness(student, company):
    company_assessments = (
        Assessment.query.filter_by(student_id=student.id, company_id=company.id)
        .order_by(Assessment.created_at.desc())
        .limit(5)
        .all()
    )
    if not company_assessments:
        recent_assessments = (
            Assessment.query.filter_by(student_id=student.id)
            .order_by(Assessment.created_at.desc())
            .limit(5)
            .all()
        )
    else:
        recent_assessments = company_assessments

    assessment_score = 0.0
    if recent_assessments:
        ratios = []
        for a in recent_assessments:
            if a.max_score and a.max_score > 0:
                ratios.append((a.total_score / a.max_score) * 100.0)
        assessment_score = sum(ratios) / len(ratios) if ratios else 0.0

    student_skills = {s.lower() for s in _parse_list_field(student.skills)}
    req_skills = {s.lower() for s in _parse_list_field(company.required_skills)}
    if req_skills:
        overlap = len(student_skills.intersection(req_skills))
        skill_match_score = (overlap / len(req_skills)) * 100.0
    else:
        skill_match_score = 0.0

    company_domains = _company_domain_matches(company)
    project_query = Project.query.filter(Project.student_id == student.id)
    if company_domains:
        project_query = project_query.filter(Project.domain.in_(list(company_domains)))
    project_count = project_query.count()
    project_score = min(project_count * 20.0, 100.0)

    cert_categories = []
    for skill in req_skills:
        if skill in {"coding", "dsa", "programming"}:
            cert_categories.append("Coding")
        if skill in {"dbms", "sql"}:
            cert_categories.append("DBMS")
        if skill in {"cloud", "aws", "azure"}:
            cert_categories.append("Cloud")
        if skill in {"ai", "ml"}:
            cert_categories.append("AI")
        if skill in {"communication", "english"}:
            cert_categories.append("Communication")
    cert_categories = list(set(cert_categories))
    cert_count_query = Certificate.query.filter_by(student_id=student.id)
    if cert_categories:
        cert_count_query = cert_count_query.filter(Certificate.skill_category.in_(cert_categories))
    cert_count = cert_count_query.count()
    cert_score = min(cert_count * 25.0, 100.0)

    streak_factor = min((student.streak_current or 0) / 100.0, 1.0)
    streak_score = streak_factor * 100.0

    has_company_assessment = bool(company_assessments)
    assessment_weight = 0.50 if has_company_assessment else 0.35
    skill_weight = 0.30
    project_weight = 0.12
    cert_weight = 0.08
    streak_weight = 0.05

    final_score = (
        assessment_weight * assessment_score
        + skill_weight * skill_match_score
        + project_weight * project_score
        + cert_weight * cert_score
        + streak_weight * streak_score
    )

    if not _student_eligible(student, company):
        final_score *= 0.7

    readiness = ReadinessScore.query.filter_by(student_id=student.id, company_id=company.id).first()
    if readiness:
        readiness.score = round(final_score, 2)
        readiness.calculated_at = datetime.utcnow()
    else:
        readiness = ReadinessScore(
            student_id=student.id,
            company_id=company.id,
            score=round(final_score, 2),
        )
        db.session.add(readiness)

    components = {
        "assessment_score": round(assessment_score, 2),
        "skill_match_score": round(skill_match_score, 2),
        "project_score": round(project_score, 2),
        "cert_score": round(cert_score, 2),
        "streak_score": round(streak_score, 2),
    }
    return round(final_score, 2), components


def _get_student():
    return Student.query.get_or_404(current_user.id)


def _academic_snapshot(student):
    profile = AcademicProfile.query.filter_by(student_id=student.id).first()
    records = (
        StudentSubjectRecord.query.filter_by(student_id=student.id)
        .order_by(StudentSubjectRecord.updated_at.desc())
        .all()
    )
    weighted_points = 0.0
    total_credits = 0
    for r in records:
        credits = r.subject.credits if r.subject else 0
        gp = float(r.grade_point or 0)
        weighted_points += gp * credits
        total_credits += credits
    cgpa_estimate = round(weighted_points / total_credits, 2) if total_credits else 0.0

    active_backlogs = AcademicBacklog.query.filter_by(student_id=student.id, status="Active").count()
    pending_events = AcademicEvent.query.filter_by(student_id=student.id, status="Pending").count()
    passed_subjects = StudentSubjectRecord.query.filter_by(student_id=student.id, pass_status="Pass").count()
    total_subjects = len(records)
    pass_rate = round((passed_subjects / total_subjects) * 100, 2) if total_subjects else 0

    risk = "Low"
    if active_backlogs >= 2 or cgpa_estimate < 6.5:
        risk = "High"
    elif active_backlogs == 1 or cgpa_estimate < 7.2:
        risk = "Medium"

    return {
        "profile": profile,
        "cgpa_estimate": cgpa_estimate,
        "active_backlogs": active_backlogs,
        "pending_events": pending_events,
        "pass_rate": pass_rate,
        "records": records,
        "risk": risk,
    }


@student_bp.route("/dashboard")
@login_required
@student_required
def dashboard():
    student = _get_student()
    today = date.today()
    next_30 = today + timedelta(days=30)

    upcoming_companies = (
        Company.query.filter(Company.drive_date >= today, Company.drive_date <= next_30)
        .order_by(Company.drive_date.asc())
        .all()
    )

    readiness_map = {}
    for company in upcoming_companies:
        score, _ = _compute_readiness(student, company)
        readiness_map[company.id] = score
    db.session.commit()

    logs = (
        DailyLog.query.filter_by(student_id=student.id)
        .order_by(DailyLog.log_date.asc())
        .limit(30)
        .all()
    )
    log_chart = {
        "labels": [l.log_date.strftime("%Y-%m-%d") for l in logs],
        "coding": [float(l.coding_hours or 0) for l in logs],
        "aptitude": [float(l.aptitude_hours or 0) for l in logs],
    }

    readiness_rows = (
        ReadinessScore.query.filter_by(student_id=student.id)
        .join(Company, Company.id == ReadinessScore.company_id)
        .order_by(Company.name.asc())
        .all()
    )
    readiness_chart = {
        "labels": [r.company.name for r in readiness_rows],
        "scores": [float(r.score) for r in readiness_rows],
    }

    feedbacks = (
        MentorFeedback.query.filter_by(student_id=student.id)
        .order_by(MentorFeedback.created_at.desc())
        .limit(5)
        .all()
    )

    academic = _academic_snapshot(student)
    next_event = (
        AcademicEvent.query.filter_by(student_id=student.id, status="Pending")
        .order_by(AcademicEvent.due_date.asc())
        .first()
    )
    avg_readiness = round(sum(readiness_chart["scores"]) / len(readiness_chart["scores"]), 2) if readiness_chart["scores"] else 0
    academic_health = round((academic["cgpa_estimate"] / 10.0) * 100, 2)
    balanced_score = round((0.55 * academic_health) + (0.45 * avg_readiness), 2)

    badge = "None"
    if student.streak_current >= 90:
        badge = "Gold"
    elif student.streak_current >= 30:
        badge = "Silver"
    elif student.streak_current >= 7:
        badge = "Bronze"

    return render_template(
        "student/dashboard.html",
        student=student,
        upcoming_companies=upcoming_companies,
        readiness_map=readiness_map,
        log_chart=log_chart,
        readiness_chart=readiness_chart,
        feedbacks=feedbacks,
        badge=badge,
        today=today,
        academic=academic,
        next_event=next_event,
        avg_readiness=avg_readiness,
        academic_health=academic_health,
        balanced_score=balanced_score,
    )


@student_bp.route("/profile", methods=["GET", "POST"])
@login_required
@student_required
def profile():
    student = _get_student()

    if request.method == "POST":
        student.full_name = request.form.get("full_name", "").strip()
        student.department = request.form.get("department", "").strip()
        cgpa_value = request.form.get("cgpa", "").strip()
        student.skills = request.form.get("skills", "").strip()
        student.linkedin_url = request.form.get("linkedin_url", "").strip()
        student.github_url = request.form.get("github_url", "").strip()

        if not student.full_name:
            flash("Full name is required.", "danger")
            return redirect(url_for("student.profile"))
        if cgpa_value:
            try:
                cgpa = Decimal(cgpa_value)
                if cgpa < 0 or cgpa > 10:
                    raise ValueError
                student.cgpa = cgpa
            except Exception:
                flash("CGPA must be between 0 and 10.", "danger")
                return redirect(url_for("student.profile"))

        if not _is_valid_url(student.linkedin_url) or not _is_valid_url(student.github_url):
            flash("LinkedIn/GitHub URLs must be valid http/https links.", "danger")
            return redirect(url_for("student.profile"))

        resume = request.files.get("resume")
        if resume and resume.filename:
            path = _save_upload(resume, "resumes", current_app.config["ALLOWED_DOC_EXTENSIONS"])
            if not path:
                flash("Resume must be a PDF file.", "danger")
                return redirect(url_for("student.profile"))
            student.resume_path = path

        profile_pic = request.files.get("profile_pic")
        if profile_pic and profile_pic.filename:
            path = _save_upload(profile_pic, "profile_pics", current_app.config["ALLOWED_IMAGE_EXTENSIONS"])
            if not path:
                flash("Profile picture must be jpg/jpeg/png.", "danger")
                return redirect(url_for("student.profile"))
            student.profile_pic_path = path

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("student.profile"))

    return render_template("student/profile.html", student=student)


@student_bp.route("/academics", methods=["GET", "POST"])
@login_required
@student_required
def academics():
    student = _get_student()
    profile = AcademicProfile.query.filter_by(student_id=student.id).first()
    if not profile:
        profile = AcademicProfile(student_id=student.id, semester=1, total_credits=0, credits_completed=0)
        db.session.add(profile)
        db.session.commit()

    if request.method == "POST":
        action = request.form.get("action", "").strip()

        if action == "update_profile":
            profile.section = request.form.get("section", "").strip()
            profile.regulation = request.form.get("regulation", "").strip()
            profile.graduation_year = request.form.get("graduation_year", type=int)
            profile.semester = request.form.get("semester", type=int) or profile.semester
            profile.total_credits = request.form.get("total_credits", type=int) or 0
            profile.credits_completed = request.form.get("credits_completed", type=int) or 0
            tg = request.form.get("target_cgpa", "").strip()
            if tg:
                try:
                    tgv = Decimal(tg)
                    if tgv < 0 or tgv > 10:
                        raise ValueError
                    profile.target_cgpa = tgv
                except Exception:
                    flash("Target CGPA must be between 0 and 10.", "danger")
                    return redirect(url_for("student.academics"))
            db.session.commit()
            flash("Academic profile updated.", "success")
            return redirect(url_for("student.academics"))

        if action == "add_subject_record":
            subject_code = request.form.get("subject_code", "").strip().upper()
            subject_name = request.form.get("subject_name", "").strip()
            sem = request.form.get("subject_semester", type=int) or 1
            credits = request.form.get("credits", type=int) or 3
            subject_type = request.form.get("subject_type", "Theory")
            grade_point = request.form.get("grade_point", type=float) or 0.0
            pass_status = request.form.get("pass_status", "Pending")

            if not subject_code or not subject_name:
                flash("Subject code and name are required.", "danger")
                return redirect(url_for("student.academics"))

            subject = AcademicSubject.query.filter_by(subject_code=subject_code, semester=sem).first()
            if not subject:
                subject = AcademicSubject(
                    subject_code=subject_code,
                    subject_name=subject_name,
                    semester=sem,
                    credits=credits,
                    subject_type=subject_type if subject_type in {"Theory", "Lab", "Elective"} else "Theory",
                )
                db.session.add(subject)
                db.session.flush()

            record = StudentSubjectRecord.query.filter_by(student_id=student.id, subject_id=subject.id).first()
            payload = {
                "cia_marks": request.form.get("cia_marks", type=float) or 0.0,
                "assignment_marks": request.form.get("assignment_marks", type=float) or 0.0,
                "lab_marks": request.form.get("lab_marks", type=float) or 0.0,
                "attendance_percent": request.form.get("attendance_percent", type=float) or 0.0,
                "end_sem_marks": request.form.get("end_sem_marks", type=float) or 0.0,
                "grade_point": grade_point,
                "pass_status": pass_status if pass_status in {"Pass", "Fail", "Pending"} else "Pending",
            }
            if record:
                for k, v in payload.items():
                    setattr(record, k, v)
            else:
                db.session.add(StudentSubjectRecord(student_id=student.id, subject_id=subject.id, **payload))
            db.session.commit()
            flash("Subject performance saved.", "success")
            return redirect(url_for("student.academics"))

        if action == "add_backlog":
            name = request.form.get("backlog_subject", "").strip()
            sem = request.form.get("backlog_semester", type=int)
            if not name:
                flash("Backlog subject name is required.", "danger")
                return redirect(url_for("student.academics"))
            db.session.add(AcademicBacklog(student_id=student.id, subject_name=name, semester=sem, status="Active"))
            db.session.commit()
            flash("Backlog added.", "success")
            return redirect(url_for("student.academics"))

        if action == "toggle_backlog":
            backlog_id = request.form.get("backlog_id", type=int)
            backlog = AcademicBacklog.query.filter_by(id=backlog_id, student_id=student.id).first_or_404()
            if backlog.status == "Active":
                backlog.status = "Cleared"
                backlog.cleared_on = date.today()
            else:
                backlog.status = "Active"
                backlog.cleared_on = None
            db.session.commit()
            flash("Backlog status updated.", "info")
            return redirect(url_for("student.academics"))

        if action == "add_event":
            title = request.form.get("event_title", "").strip()
            event_type = request.form.get("event_type", "").strip()
            due_date = request.form.get("due_date", "").strip()
            if not title or not due_date:
                flash("Event title and due date are required.", "danger")
                return redirect(url_for("student.academics"))
            try:
                dd = datetime.strptime(due_date, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid due date format.", "danger")
                return redirect(url_for("student.academics"))
            db.session.add(
                AcademicEvent(
                    student_id=student.id,
                    title=title,
                    event_type=event_type if event_type in {"Internal", "Assignment", "Lab Viva", "Semester Exam"} else "Assignment",
                    due_date=dd,
                    status="Pending",
                )
            )
            db.session.commit()
            flash("Academic event added.", "success")
            return redirect(url_for("student.academics"))

        if action == "upload_document":
            file = request.files.get("academic_file")
            if not file or not file.filename:
                flash("Please select a file.", "danger")
                return redirect(url_for("student.academics"))
            allowed = current_app.config["ALLOWED_DOC_EXTENSIONS"].union(current_app.config["ALLOWED_IMAGE_EXTENSIONS"])
            path = _save_upload(file, "academic_docs", allowed)
            if not path:
                flash("Only PDF/JPG/JPEG/PNG allowed.", "danger")
                return redirect(url_for("student.academics"))
            db.session.add(
                AcademicDocument(
                    student_id=student.id,
                    semester=request.form.get("doc_semester", type=int),
                    doc_type=request.form.get("doc_type", "Marksheet"),
                    file_path=path,
                )
            )
            db.session.commit()
            flash("Academic document uploaded.", "success")
            return redirect(url_for("student.academics"))

    snapshot = _academic_snapshot(student)
    records = snapshot["records"]
    backlogs = AcademicBacklog.query.filter_by(student_id=student.id).order_by(AcademicBacklog.created_at.desc()).all()
    events = AcademicEvent.query.filter_by(student_id=student.id).order_by(AcademicEvent.due_date.asc()).all()
    documents = AcademicDocument.query.filter_by(student_id=student.id).order_by(AcademicDocument.uploaded_at.desc()).all()

    sem_map = {}
    for r in records:
        sem = r.subject.semester if r.subject else 0
        sem_map.setdefault(sem, {"sum": 0.0, "count": 0})
        sem_map[sem]["sum"] += float(r.grade_point or 0)
        sem_map[sem]["count"] += 1
    sem_labels = sorted(sem_map.keys())
    sgpa_trend = {
        "labels": [f"Sem {s}" for s in sem_labels],
        "values": [round(sem_map[s]["sum"] / sem_map[s]["count"], 2) if sem_map[s]["count"] else 0 for s in sem_labels],
    }

    return render_template(
        "student/academics.html",
        profile=profile,
        records=records,
        backlogs=backlogs,
        events=events,
        documents=documents,
        snapshot=snapshot,
        sgpa_trend=sgpa_trend,
    )


@student_bp.route("/daily_log", methods=["GET", "POST"])
@login_required
@student_required
def daily_log():
    student = _get_student()
    today = date.today()
    fields = [
        "coding_hours",
        "aptitude_hours",
        "oops_hours",
        "dbms_hours",
        "os_hours",
        "networks_hours",
        "communication_hours",
        "mock_interview_hours",
    ]

    existing_today = DailyLog.query.filter_by(student_id=student.id, log_date=today).first()

    if request.method == "POST":
        values = {}
        for f in fields:
            values[f] = Decimal("1") if request.form.get(f) else Decimal("0")

        was_already_logged_today = student.last_logged_date == today

        if existing_today:
            for f, val in values.items():
                setattr(existing_today, f, val)
        else:
            new_log = DailyLog(student_id=student.id, log_date=today, **values)
            db.session.add(new_log)

        if not was_already_logged_today:
            yesterday = today - timedelta(days=1)
            if student.last_logged_date == yesterday:
                student.streak_current = (student.streak_current or 0) + 1
            else:
                student.streak_current = 1
            if student.streak_current > (student.streak_longest or 0):
                student.streak_longest = student.streak_current
            student.last_logged_date = today

        db.session.commit()
        flash(
            f"Daily log saved. Current streak: {student.streak_current}, Longest streak: {student.streak_longest}.",
            "success",
        )
        return redirect(url_for("student.daily_log"))

    return render_template("student/daily_log.html", existing_today=existing_today)


@student_bp.route("/projects", methods=["GET", "POST"])
@login_required
@student_required
def projects():
    student = _get_student()
    edit_project = None

    if request.method == "POST":
        action = request.form.get("action")
        project_id = request.form.get("project_id")

        if action == "delete" and project_id:
            project = Project.query.filter_by(id=project_id, student_id=student.id).first_or_404()
            db.session.delete(project)
            db.session.commit()
            flash("Project deleted.", "info")
            return redirect(url_for("student.projects"))

        title = request.form.get("title", "").strip()
        domain = request.form.get("domain", "").strip()
        if not title or domain not in {"Web", "AI", "ML", "App", "Cloud", "Cybersecurity"}:
            flash("Title and valid domain are required.", "danger")
            return redirect(url_for("student.projects"))

        payload = {
            "title": title,
            "domain": domain,
            "technologies_used": request.form.get("technologies_used", "").strip(),
            "description": request.form.get("description", "").strip(),
            "github_link": request.form.get("github_link", "").strip(),
            "live_demo_link": request.form.get("live_demo_link", "").strip(),
            "project_type": request.form.get("project_type", "").strip() or None,
            "status": request.form.get("status", "").strip() or None,
        }

        if not _is_valid_url(payload["github_link"]) or not _is_valid_url(payload["live_demo_link"]):
            flash("GitHub/Live demo links must be valid URLs.", "danger")
            return redirect(url_for("student.projects"))

        if action == "edit" and project_id:
            project = Project.query.filter_by(id=project_id, student_id=student.id).first_or_404()
            for k, v in payload.items():
                setattr(project, k, v)
            flash("Project updated.", "success")
        else:
            db.session.add(Project(student_id=student.id, **payload))
            flash("Project added.", "success")

        db.session.commit()
        return redirect(url_for("student.projects"))

    edit_id = request.args.get("edit_id", type=int)
    if edit_id:
        edit_project = Project.query.filter_by(id=edit_id, student_id=student.id).first()

    all_projects = Project.query.filter_by(student_id=student.id).order_by(Project.created_at.desc()).all()
    return render_template("student/projects.html", projects=all_projects, edit_project=edit_project)


@student_bp.route("/certificates", methods=["GET", "POST"])
@login_required
@student_required
def certificates():
    student = _get_student()

    if request.method == "POST":
        action = request.form.get("action")
        cert_id = request.form.get("cert_id")

        if action == "delete" and cert_id:
            cert = Certificate.query.filter_by(id=cert_id, student_id=student.id).first_or_404()
            db.session.delete(cert)
            db.session.commit()
            flash("Certificate deleted.", "info")
            return redirect(url_for("student.certificates"))

        file = request.files.get("certificate_file")
        category = request.form.get("skill_category", "").strip()
        platform_name = request.form.get("platform_name", "").strip()
        completion_date = request.form.get("completion_date", "").strip()

        if category not in {"Coding", "DBMS", "Cloud", "AI", "Communication", "Internship"}:
            flash("Invalid certificate category.", "danger")
            return redirect(url_for("student.certificates"))

        if not file or not file.filename:
            flash("Certificate file is required.", "danger")
            return redirect(url_for("student.certificates"))

        allowed = current_app.config["ALLOWED_DOC_EXTENSIONS"].union(current_app.config["ALLOWED_IMAGE_EXTENSIONS"])
        path = _save_upload(file, "certificates", allowed)
        if not path:
            flash("Certificate must be PDF/JPG/JPEG/PNG.", "danger")
            return redirect(url_for("student.certificates"))

        dt = None
        if completion_date:
            try:
                dt = datetime.strptime(completion_date, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid completion date.", "danger")
                return redirect(url_for("student.certificates"))

        cert = Certificate(
            student_id=student.id,
            file_path=path,
            skill_category=category,
            platform_name=platform_name,
            completion_date=dt,
        )
        db.session.add(cert)
        db.session.commit()
        flash("Certificate uploaded.", "success")
        return redirect(url_for("student.certificates"))

    certs = Certificate.query.filter_by(student_id=student.id).order_by(Certificate.uploaded_at.desc()).all()
    return render_template("student/certificates.html", certificates=certs)


@student_bp.route("/companies")
@login_required
@student_required
def companies():
    student = _get_student()
    today = date.today()

    companies_list = Company.query.filter(Company.drive_date >= today).order_by(Company.drive_date.asc()).all()
    registered_company_ids = {
        r.company_id for r in Registration.query.filter_by(student_id=student.id).all()
    }

    company_rows = []
    for company in companies_list:
        score, _ = _compute_readiness(student, company)
        company_rows.append({
            "company": company,
            "eligible": _student_eligible(student, company),
            "registered": company.id in registered_company_ids,
            "readiness_score": score,
        })

    db.session.commit()
    return render_template("student/companies.html", company_rows=company_rows)


@student_bp.route("/register_company/<int:company_id>", methods=["POST"])
@login_required
@student_required
def register_company(company_id):
    student = _get_student()
    company = Company.query.get_or_404(company_id)

    if not _student_eligible(student, company):
        flash("You are not eligible for this drive.", "danger")
        return redirect(url_for("student.companies"))

    existing = Registration.query.filter_by(student_id=student.id, company_id=company.id).first()
    if existing:
        flash("Already registered for this company.", "warning")
        return redirect(url_for("student.companies"))

    reg = Registration(student_id=student.id, company_id=company.id)
    db.session.add(reg)
    db.session.commit()
    flash("Registered successfully.", "success")
    return redirect(url_for("student.companies"))


@student_bp.route("/assessment", methods=["GET", "POST"])
@login_required
@student_required
def assessment():
    student = _get_student()

    if request.method == "POST":
        question_ids = request.form.getlist("question_ids")
        company_id = request.form.get("company_id", type=int)
        company = Company.query.get(company_id) if company_id else None

        questions = QuestionBank.query.filter(QuestionBank.id.in_(question_ids)).all() if question_ids else []
        if not questions:
            flash("No questions submitted.", "warning")
            return redirect(url_for("student.assessment"))

        total = 0
        max_score = len(questions)
        skill_result = {}

        for q in questions:
            ans = request.form.get(f"answer_{q.id}", "").strip()
            is_correct = ans.lower() == (q.correct_answer or "").strip().lower()
            if is_correct:
                total += 1
            skill = q.skill_category or "General"
            skill_result.setdefault(skill, {"correct": 0, "total": 0})
            skill_result[skill]["total"] += 1
            if is_correct:
                skill_result[skill]["correct"] += 1

        breakdown = {}
        weak = []
        for skill, stat in skill_result.items():
            percent = round((stat["correct"] / stat["total"]) * 100, 2) if stat["total"] else 0
            breakdown[skill] = percent
            if percent < 60:
                weak.append(skill)

        suggestions = "Focus on: " + ", ".join(weak) if weak else "Great performance. Keep practicing mixed-level questions."

        assessment_row = Assessment(
            student_id=student.id,
            company_id=company.id if company else None,
            assessment_date=date.today(),
            total_score=total,
            max_score=max_score,
            skill_breakdown=breakdown,
            weak_areas=", ".join(weak),
            suggestions=suggestions,
        )
        db.session.add(assessment_row)

        reg_companies = (
            Company.query.join(Registration, Registration.company_id == Company.id)
            .filter(Registration.student_id == student.id)
            .all()
        )
        for c in reg_companies:
            _compute_readiness(student, c)

        db.session.commit()

        return render_template(
            "student/assessment.html",
            mode="result",
            result={
                "score": total,
                "max_score": max_score,
                "breakdown": breakdown,
                "weak_areas": weak,
                "suggestions": suggestions,
            },
        )

    selected_company_id = request.args.get("company_id", type=int)
    selected_company = Company.query.get(selected_company_id) if selected_company_id else None

    last_7 = date.today() - timedelta(days=7)
    logs = DailyLog.query.filter(
        DailyLog.student_id == student.id,
        DailyLog.log_date >= last_7,
    ).all()

    avg_map = {
        "Coding": 0,
        "Aptitude": 0,
        "Technical": 0,
    }
    if logs:
        avg_map["Coding"] = float(sum([float(l.coding_hours or 0) for l in logs]) / len(logs))
        avg_map["Aptitude"] = float(sum([float(l.aptitude_hours or 0) for l in logs]) / len(logs))
        tech = [
            float(l.oops_hours or 0) + float(l.dbms_hours or 0) + float(l.os_hours or 0) + float(l.networks_hours or 0)
            for l in logs
        ]
        avg_map["Technical"] = float(sum(tech) / len(logs))

    weakest = sorted(avg_map.items(), key=lambda x: x[1])[:2]
    target_categories = [w[0] for w in weakest]

    if selected_company and _parse_list_field(selected_company.required_skills):
        company_skill_blob = " ".join(_parse_list_field(selected_company.required_skills)).lower()
        if any(k in company_skill_blob for k in ["aptitude", "reasoning"]):
            target_categories.append("Aptitude")
        if any(k in company_skill_blob for k in ["coding", "dsa", "programming"]):
            target_categories.append("Coding")
        if any(k in company_skill_blob for k in ["dbms", "oops", "os", "network"]):
            target_categories.append("Technical")

    target_categories = list(set(target_categories))

    if selected_company:
        # Priority: directly use mentor-uploaded question bank for selected company.
        questions = (
            QuestionBank.query.filter(
                QuestionBank.company_id == selected_company.id,
                QuestionBank.question_type.in_(["MCQ", "Aptitude", "Coding"]),
            )
            .order_by(_random_order_expr())
            .limit(10)
            .all()
        )
        # If company has fewer questions, top up from global/adaptive pool.
        if len(questions) < 10:
            existing_ids = {q.id for q in questions}
            filler = (
                QuestionBank.query.filter(
                    QuestionBank.question_type.in_(["MCQ", "Aptitude", "Coding"]),
                    QuestionBank.skill_category.in_(target_categories),
                )
                .order_by(_random_order_expr())
                .limit(20)
                .all()
            )
            for q in filler:
                if q.id not in existing_ids:
                    questions.append(q)
                    existing_ids.add(q.id)
                if len(questions) >= 10:
                    break
    else:
        query = QuestionBank.query.filter(
            QuestionBank.skill_category.in_(target_categories),
            QuestionBank.question_type.in_(["MCQ", "Aptitude", "Coding"]),
        )
        questions = query.order_by(_random_order_expr()).limit(10).all()

        if not questions:
            questions = (
                QuestionBank.query.filter(QuestionBank.question_type.in_(["MCQ", "Aptitude", "Coding"]))
                .order_by(_random_order_expr())
                .limit(10)
                .all()
            )

    today_log = DailyLog.query.filter_by(student_id=student.id, log_date=date.today()).first()
    needs_coding = bool(today_log and (today_log.coding_hours or 0) > 0)
    if needs_coding:
        existing_ids = {q.id for q in questions}
        coding_query = QuestionBank.query.filter(QuestionBank.question_type.in_(["MCQ", "Coding"]))
        if selected_company:
            coding_query = coding_query.filter(QuestionBank.company_id == selected_company.id)
        coding_questions = coding_query.order_by(_random_order_expr()).limit(4).all()

        coding_in_list = [q for q in questions if q.question_type in ["MCQ", "Coding"] and (q.skill_category or "").lower() == "coding"]
        need = max(0, 2 - len(coding_in_list))
        if need > 0 and coding_questions:
            add_pool = [q for q in coding_questions if q.id not in existing_ids]
            for q in add_pool[:need]:
                if len(questions) < 10:
                    questions.append(q)
                else:
                    # Replace from the end to keep size 10
                    questions.pop()
                    questions.append(q)

    # Show all upcoming companies so students can target any company question bank.
    companies_list = Company.query.filter(Company.drive_date >= date.today()).order_by(Company.name.asc()).all()

    return render_template(
        "student/assessment.html",
        mode="test",
        questions=questions,
        companies=companies_list,
        selected_company_id=selected_company_id,
    )


@student_bp.route("/readiness")
@login_required
@student_required
def readiness():
    student = _get_student()
    companies_list = Company.query.order_by(Company.name.asc()).all()

    rows = []
    for company in companies_list:
        score, components = _compute_readiness(student, company)
        strengths = [k for k, v in components.items() if v >= 70]
        weak = [k for k, v in components.items() if v < 50]
        recommendation = "Improve " + ", ".join(weak) if weak else "Maintain consistency and attempt more assessments."
        rows.append({
            "company": company,
            "score": score,
            "components": components,
            "strengths": strengths,
            "weak_areas": weak,
            "recommendation": recommendation,
        })

    db.session.commit()
    return render_template("student/readiness.html", rows=rows, ranking_mode=False)


@student_bp.route("/ranking/<int:company_id>")
@login_required
@student_required
def ranking(company_id):
    company = Company.query.get_or_404(company_id)

    top_rows = (
        db.session.query(ReadinessScore, Student)
        .join(Student, Student.id == ReadinessScore.student_id)
        .filter(ReadinessScore.company_id == company.id)
        .order_by(ReadinessScore.score.desc())
        .limit(10)
        .all()
    )

    rankings = [{
        "name": row[1].full_name or row[1].user.email,
        "department": row[1].department or "-",
        "cgpa": str(row[1].cgpa) if row[1].cgpa is not None else "-",
        "skills": ", ".join(_parse_list_field(row[1].skills)) if row[1].skills else "-",
        "streak": row[1].streak_current or 0,
        "projects": Project.query.filter_by(student_id=row[1].id).count(),
        "certificates": Certificate.query.filter_by(student_id=row[1].id).count(),
        "score": float(row[0].score),
    } for row in top_rows]

    return render_template(
        "student/readiness.html",
        ranking_mode=True,
        company=company,
        rankings=rankings,
    )
