from datetime import datetime
import json

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy import UniqueConstraint, Index
from sqlalchemy.orm import relationship


db = SQLAlchemy()
login_manager = LoginManager()


def parse_list_field(value):
    if not value:
        return []
    value = value.strip()
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    return [x.strip() for x in value.split(",") if x.strip()]


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum("student", "faculty", "admin", name="role_enum"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student_profile = relationship("Student", uselist=False, back_populates="user")
    mentor_profile = relationship("Mentor", uselist=False, back_populates="user")
    faculty_profile = relationship("Faculty", uselist=False, back_populates="user")


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        # If DB is unavailable/misconfigured, avoid crashing public pages.
        db.session.rollback()
        return None


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    full_name = db.Column(db.String(100))
    department = db.Column(db.String(50))
    cgpa = db.Column(db.Numeric(3, 2))
    skills = db.Column(db.Text)
    linkedin_url = db.Column(db.String(255))
    github_url = db.Column(db.String(255))
    resume_path = db.Column(db.String(255))
    profile_pic_path = db.Column(db.String(255))
    streak_current = db.Column(db.Integer, default=0, nullable=False)
    streak_longest = db.Column(db.Integer, default=0, nullable=False)
    last_logged_date = db.Column(db.Date)

    user = relationship("User", back_populates="student_profile")
    projects = relationship("Project", back_populates="student", cascade="all, delete-orphan")
    certificates = relationship("Certificate", back_populates="student", cascade="all, delete-orphan")
    logs = relationship("DailyLog", back_populates="student", cascade="all, delete-orphan")
    assessments = relationship("Assessment", back_populates="student", cascade="all, delete-orphan")
    readiness_scores = relationship("ReadinessScore", back_populates="student", cascade="all, delete-orphan")
    academic_profile = relationship("AcademicProfile", uselist=False, back_populates="student", cascade="all, delete-orphan")
    subject_records = relationship("StudentSubjectRecord", back_populates="student", cascade="all, delete-orphan")
    backlogs = relationship("AcademicBacklog", back_populates="student", cascade="all, delete-orphan")
    academic_events = relationship("AcademicEvent", back_populates="student", cascade="all, delete-orphan")
    academic_documents = relationship("AcademicDocument", back_populates="student", cascade="all, delete-orphan")

    def skill_list(self):
        return parse_list_field(self.skills)


class Mentor(db.Model):
    __tablename__ = "mentors"

    id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    full_name = db.Column(db.String(100))
    department = db.Column(db.String(50))

    user = relationship("User", back_populates="mentor_profile")
    companies = relationship("Company", back_populates="creator", cascade="all, delete-orphan")


class Faculty(db.Model):
    __tablename__ = "faculties"

    id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    full_name = db.Column(db.String(100))
    department = db.Column(db.String(50))

    user = relationship("User", back_populates="faculty_profile")


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    drive_date = db.Column(db.Date, index=True)
    required_skills = db.Column(db.Text)
    eligibility_criteria = db.Column(db.Text)
    focus_topics = db.Column(db.Text)
    package_details = db.Column(db.String(255))
    logo_path = db.Column(db.String(255))
    created_by = db.Column(db.Integer, db.ForeignKey("mentors.id"))

    creator = relationship("Mentor", back_populates="companies")
    registrations = relationship("Registration", back_populates="company", cascade="all, delete-orphan")
    question_bank = relationship("QuestionBank", back_populates="company", cascade="all, delete-orphan")
    assessments = relationship("Assessment", back_populates="company")
    readiness_scores = relationship("ReadinessScore", back_populates="company")

    def required_skill_list(self):
        return parse_list_field(self.required_skills)


class Registration(db.Model):
    __tablename__ = "registrations"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("student_id", "company_id", name="uq_registration_student_company"),
    )

    company = relationship("Company", back_populates="registrations")


class DailyLog(db.Model):
    __tablename__ = "daily_logs"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    log_date = db.Column(db.Date, nullable=False, index=True)

    coding_hours = db.Column(db.Numeric(3, 1), default=0)
    aptitude_hours = db.Column(db.Numeric(3, 1), default=0)
    oops_hours = db.Column(db.Numeric(3, 1), default=0)
    dbms_hours = db.Column(db.Numeric(3, 1), default=0)
    os_hours = db.Column(db.Numeric(3, 1), default=0)
    networks_hours = db.Column(db.Numeric(3, 1), default=0)
    communication_hours = db.Column(db.Numeric(3, 1), default=0)
    mock_interview_hours = db.Column(db.Numeric(3, 1), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("student_id", "log_date", name="uq_daily_log_student_date"),
        Index("idx_daily_log_student_date", "student_id", "log_date"),
    )

    student = relationship("Student", back_populates="logs")


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    domain = db.Column(
        db.Enum("Web", "AI", "ML", "App", "Cloud", "Cybersecurity", name="project_domain_enum"),
        nullable=False,
    )
    technologies_used = db.Column(db.Text)
    description = db.Column(db.Text)
    github_link = db.Column(db.String(255))
    live_demo_link = db.Column(db.String(255))
    project_type = db.Column(
        db.Enum("Academic", "Personal", "Internship", name="project_type_enum"),
        nullable=True,
    )
    status = db.Column(db.Enum("Completed", "Ongoing", name="project_status_enum"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="projects")


class Certificate(db.Model):
    __tablename__ = "certificates"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    file_path = db.Column(db.String(255), nullable=False)
    skill_category = db.Column(
        db.Enum("Coding", "DBMS", "Cloud", "AI", "Communication", "Internship", name="certificate_skill_enum"),
        nullable=False,
    )
    platform_name = db.Column(db.String(100))
    completion_date = db.Column(db.Date)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="certificates")


class QuestionBank(db.Model):
    __tablename__ = "question_bank"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True, index=True)
    skill_category = db.Column(db.String(50), index=True)
    question_type = db.Column(
        db.Enum("MCQ", "Coding", "Aptitude", name="question_type_enum"),
        nullable=False,
    )
    question_text = db.Column(db.Text, nullable=False)
    options = db.Column(db.JSON)
    correct_answer = db.Column(db.Text)
    difficulty = db.Column(db.Enum("Easy", "Medium", "Hard", name="difficulty_enum"))
    created_by = db.Column(db.Integer, db.ForeignKey("mentors.id"))

    company = relationship("Company", back_populates="question_bank")


class Assessment(db.Model):
    __tablename__ = "assessments"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True, index=True)
    assessment_date = db.Column(db.Date, nullable=False)
    total_score = db.Column(db.Integer, default=0)
    max_score = db.Column(db.Integer, default=0)
    skill_breakdown = db.Column(db.JSON)
    weak_areas = db.Column(db.Text)
    suggestions = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="assessments")
    company = relationship("Company", back_populates="assessments")


class ReadinessScore(db.Model):
    __tablename__ = "readiness_scores"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    score = db.Column(db.Numeric(5, 2), nullable=False)
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("student_id", "company_id", name="uq_readiness_student_company"),
    )

    student = relationship("Student", back_populates="readiness_scores")
    company = relationship("Company", back_populates="readiness_scores")


class MentorFeedback(db.Model):
    __tablename__ = "mentor_feedback"

    id = db.Column(db.Integer, primary_key=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    feedback = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AcademicProfile(db.Model):
    __tablename__ = "academic_profiles"

    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), primary_key=True)
    section = db.Column(db.String(20))
    semester = db.Column(db.Integer, default=1)
    regulation = db.Column(db.String(20))
    graduation_year = db.Column(db.Integer)
    total_credits = db.Column(db.Integer, default=0)
    credits_completed = db.Column(db.Integer, default=0)
    current_sgpa = db.Column(db.Numeric(4, 2))
    target_cgpa = db.Column(db.Numeric(4, 2))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = relationship("Student", back_populates="academic_profile")


class AcademicSubject(db.Model):
    __tablename__ = "academic_subjects"

    id = db.Column(db.Integer, primary_key=True)
    subject_code = db.Column(db.String(30), nullable=False, index=True)
    subject_name = db.Column(db.String(120), nullable=False)
    semester = db.Column(db.Integer, nullable=False, index=True)
    credits = db.Column(db.Integer, default=3)
    subject_type = db.Column(db.Enum("Theory", "Lab", "Elective", name="subject_type_enum"), default="Theory")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("subject_code", "semester", name="uq_subject_code_sem"),
    )


class StudentSubjectRecord(db.Model):
    __tablename__ = "student_subject_records"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("academic_subjects.id"), nullable=False, index=True)
    cia_marks = db.Column(db.Numeric(5, 2), default=0)
    assignment_marks = db.Column(db.Numeric(5, 2), default=0)
    lab_marks = db.Column(db.Numeric(5, 2), default=0)
    attendance_percent = db.Column(db.Numeric(5, 2), default=0)
    end_sem_marks = db.Column(db.Numeric(5, 2), default=0)
    grade_point = db.Column(db.Numeric(3, 2), default=0)
    pass_status = db.Column(db.Enum("Pass", "Fail", "Pending", name="pass_status_enum"), default="Pending")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", name="uq_student_subject"),
    )

    student = relationship("Student", back_populates="subject_records")
    subject = relationship("AcademicSubject")


class AcademicBacklog(db.Model):
    __tablename__ = "academic_backlogs"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    subject_name = db.Column(db.String(120), nullable=False)
    semester = db.Column(db.Integer)
    status = db.Column(db.Enum("Active", "Cleared", name="backlog_status_enum"), default="Active")
    cleared_on = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="backlogs")


class AcademicEvent(db.Model):
    __tablename__ = "academic_events"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    event_type = db.Column(db.Enum("Internal", "Assignment", "Lab Viva", "Semester Exam", name="academic_event_type"), nullable=False)
    due_date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.Enum("Pending", "Done", name="academic_event_status"), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="academic_events")


class AcademicDocument(db.Model):
    __tablename__ = "academic_documents"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    semester = db.Column(db.Integer)
    doc_type = db.Column(db.Enum("Marksheet", "Transcript", "HallTicket", name="academic_doc_type"), default="Marksheet")
    file_path = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="academic_documents")
