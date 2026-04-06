from datetime import date, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func, case

from models import (
    db,
    Faculty,
    Student,
    DailyLog,
    Assessment,
    ReadinessScore,
    MentorFeedback,
    AcademicProfile,
    AcademicBacklog,
    StudentSubjectRecord,
)
from routes import faculty_required


faculty_bp = Blueprint("faculty", __name__, url_prefix="/faculty")


def _get_faculty():
    return Faculty.query.get_or_404(current_user.id)


def _faculty_students_query(faculty):
    query = Student.query
    if faculty.department:
        query = query.filter(Student.department == faculty.department)
    return query


@faculty_bp.route("/dashboard")
@login_required
@faculty_required
def dashboard():
    faculty = _get_faculty()
    last_7 = date.today() - timedelta(days=7)

    student_query = _faculty_students_query(faculty)
    monitored_ids = [s.id for s in student_query.with_entities(Student.id).all()]
    total_students = len(monitored_ids)
    active_students = (
        Student.query.filter(Student.id.in_(monitored_ids), Student.last_logged_date >= last_7).count()
        if monitored_ids
        else 0
    )

    weak_academic_students = []
    consistency_risk = []
    for sid in monitored_ids:
        student = Student.query.get(sid)
        if not student:
            continue
        log_count = DailyLog.query.filter(DailyLog.student_id == sid, DailyLog.log_date >= last_7).count()
        consistency_percent = round((log_count / 7) * 100, 2)
        if consistency_percent < 70:
            consistency_risk.append((student, consistency_percent))

        profile = AcademicProfile.query.filter_by(student_id=sid).first()
        sgpa = float(profile.current_sgpa) if profile and profile.current_sgpa is not None else 0.0
        active_backlogs = AcademicBacklog.query.filter_by(student_id=sid, status="Active").count()
        min_readiness = db.session.query(func.min(ReadinessScore.score)).filter(ReadinessScore.student_id == sid).scalar()
        min_readiness_val = float(min_readiness) if min_readiness is not None else 100.0
        if sgpa < 6.5 or active_backlogs > 0 or min_readiness_val < 40:
            weak_academic_students.append((student, sgpa, active_backlogs, min_readiness_val))

    return render_template(
        "faculty/dashboard.html",
        faculty=faculty,
        total_students=total_students,
        active_students=active_students,
        consistency_risk=consistency_risk[:10],
        weak_academic_students=weak_academic_students,
    )


@faculty_bp.route("/students")
@login_required
@faculty_required
def students():
    faculty = _get_faculty()
    department = request.args.get("department", "").strip()
    student_id = request.args.get("student_id", type=int)

    query = _faculty_students_query(faculty)
    if department:
        query = query.filter(Student.department == department)
    all_students = query.order_by(Student.id.desc()).all()
    last_7 = date.today() - timedelta(days=7)
    consistency_map = {}
    support_reasons = {}

    for s in all_students:
        log_count = DailyLog.query.filter(DailyLog.student_id == s.id, DailyLog.log_date >= last_7).count()
        consistency = round((log_count / 7) * 100, 2)
        consistency_map[s.id] = consistency
        reasons = []
        if consistency < 70:
            reasons.append("Inconsistent daily activity")

        profile = AcademicProfile.query.filter_by(student_id=s.id).first()
        sgpa = float(profile.current_sgpa) if profile and profile.current_sgpa is not None else 0.0
        if sgpa < 6.5:
            reasons.append("Low SGPA")

        active_backlogs = AcademicBacklog.query.filter_by(student_id=s.id, status="Active").count()
        if active_backlogs > 0:
            reasons.append(f"{active_backlogs} active backlogs")

        min_readiness = db.session.query(func.min(ReadinessScore.score)).filter(ReadinessScore.student_id == s.id).scalar()
        if min_readiness is not None and float(min_readiness) < 40:
            reasons.append("Low placement readiness")

        if reasons:
            support_reasons[s.id] = ", ".join(reasons)

    selected = Student.query.get(student_id) if student_id else None
    if selected and faculty.department and selected.department != faculty.department:
        selected = None

    details = None
    if selected:
        selected_log_count = DailyLog.query.filter(DailyLog.student_id == selected.id, DailyLog.log_date >= last_7).count()
        details = {
            "logs": DailyLog.query.filter_by(student_id=selected.id).order_by(DailyLog.log_date.desc()).limit(14).all(),
            "assessments": Assessment.query.filter_by(student_id=selected.id).order_by(Assessment.created_at.desc()).limit(10).all(),
            "readiness": ReadinessScore.query.filter_by(student_id=selected.id).order_by(ReadinessScore.score.desc()).all(),
            "academic_profile": AcademicProfile.query.filter_by(student_id=selected.id).first(),
            "backlogs": AcademicBacklog.query.filter_by(student_id=selected.id).all(),
            "subject_records": StudentSubjectRecord.query.filter_by(student_id=selected.id).order_by(StudentSubjectRecord.updated_at.desc()).all(),
            "consistency": round((selected_log_count / 7) * 100, 2),
        }

    low_performance_students = (
        query.outerjoin(AcademicProfile, AcademicProfile.student_id == Student.id)
        .outerjoin(AcademicBacklog, AcademicBacklog.student_id == Student.id)
        .outerjoin(ReadinessScore, ReadinessScore.student_id == Student.id)
        .group_by(Student.id, AcademicProfile.current_sgpa)
        .having(
            (func.coalesce(AcademicProfile.current_sgpa, 0) < 6.5)
            | (func.sum(case((AcademicBacklog.status == "Active", 1), else_=0)) > 0)
            | (func.min(func.coalesce(ReadinessScore.score, 100)) < 40)
        )
        .order_by(Student.department.asc(), Student.full_name.asc())
        .all()
    )

    return render_template(
        "faculty/students.html",
        students=all_students,
        low_performance_students=low_performance_students,
        support_reasons=support_reasons,
        consistency_map=consistency_map,
        faculty=faculty,
        selected=selected,
        details=details,
        filters={"department": department},
    )


@faculty_bp.route("/feedback/<int:student_id>", methods=["GET", "POST"])
@login_required
@faculty_required
def feedback(student_id):
    faculty = _get_faculty()
    student = Student.query.get_or_404(student_id)

    if request.method == "POST":
        feedback_text = request.form.get("feedback", "").strip()
        if not feedback_text:
            flash("Feedback cannot be empty.", "danger")
            return redirect(url_for("faculty.feedback", student_id=student_id))

        db.session.add(MentorFeedback(mentor_id=faculty.id, student_id=student.id, feedback=feedback_text))
        db.session.commit()
        flash("Feedback sent.", "success")
        return redirect(url_for("faculty.feedback", student_id=student_id))

    feedback_list = MentorFeedback.query.filter_by(student_id=student.id).order_by(MentorFeedback.created_at.desc()).all()
    return render_template("faculty/feedback.html", student=student, feedback_list=feedback_list)
