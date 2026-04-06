import os
import secrets
import pymysql
from datetime import date, timedelta

import click
from flask import Flask, render_template, redirect, url_for, session, request, abort
from flask_login import current_user
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError
from werkzeug.security import generate_password_hash

from config import Config
from models import db, login_manager, User, Student, Mentor, Faculty, Company, QuestionBank, AcademicProfile
from routes.auth import auth_bp
from routes.student import student_bp
from routes.mentor import mentor_bp
from routes.faculty import faculty_bp

pymysql.install_as_MySQLdb()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(mentor_bp)
    app.register_blueprint(faculty_bp)

    def _ensure_database_schema():
        if not app.config.get("AUTO_INIT_DB", False):
            return
        with app.app_context():
            try:
                db.create_all()
                app.logger.info("Database schema ensured on startup.")
            except SQLAlchemyError as exc:
                app.logger.exception("Database schema initialization failed: %s", exc)

    _ensure_database_schema()

    def _ensure_demo_bootstrap():
        if not app.config.get("AUTO_SEED_DEMO", False):
            return
        with app.app_context():
            try:
                admin_email = "admin@college.com"
                faculty_email = "faculty@college.com"

                admin_user = User.query.filter_by(email=admin_email).first()
                if not admin_user:
                    admin_user = User(
                        email=admin_email,
                        password_hash=generate_password_hash("Admin@123"),
                        role="admin",
                    )
                    db.session.add(admin_user)
                    db.session.flush()
                else:
                    admin_user.password_hash = generate_password_hash("Admin@123")
                    admin_user.role = "admin"

                admin_profile = Mentor.query.get(admin_user.id)
                if not admin_profile:
                    db.session.add(Mentor(id=admin_user.id, full_name="Placement Admin", department="Placement Cell"))
                else:
                    admin_profile.full_name = "Placement Admin"
                    admin_profile.department = "Placement Cell"

                faculty_user = User.query.filter_by(email=faculty_email).first()
                if not faculty_user:
                    faculty_user = User(
                        email=faculty_email,
                        password_hash=generate_password_hash("Faculty@123"),
                        role="faculty",
                    )
                    db.session.add(faculty_user)
                    db.session.flush()
                else:
                    faculty_user.password_hash = generate_password_hash("Faculty@123")
                    faculty_user.role = "faculty"

                faculty_profile = Faculty.query.get(faculty_user.id)
                if not faculty_profile:
                    db.session.add(Faculty(id=faculty_user.id, full_name="Faculty User", department="CSE"))
                else:
                    faculty_profile.full_name = "Faculty User"
                    faculty_profile.department = "CSE"

                demo_students = [
                    {"name": "Aarav Shah", "email": "student1@demo.com", "password": "Student@123", "department": "CSE", "cgpa": 8.2, "skills": "Python,Java,Problem Solving,DBMS"},
                    {"name": "Diya Nair", "email": "student2@demo.com", "password": "Student@123", "department": "IT", "cgpa": 7.8, "skills": "Java,DSA,OOPS,SQL"},
                    {"name": "Ishaan Verma", "email": "student3@demo.com", "password": "Student@123", "department": "CSE", "cgpa": 8.6, "skills": "Python,ML,Data Science,SQL"},
                    {"name": "Ananya Rao", "email": "student4@demo.com", "password": "Student@123", "department": "ECE", "cgpa": 7.2, "skills": "C,Embedded,Problem Solving,DBMS"},
                    {"name": "Rahul Mehta", "email": "student5@demo.com", "password": "Student@123", "department": "CSE", "cgpa": 9.0, "skills": "Java,Spring,OOPS,DSA"},
                    {"name": "Sneha Iyer", "email": "student6@demo.com", "password": "Student@123", "department": "IT", "cgpa": 8.0, "skills": "Python,Flask,Web,SQL"},
                    {"name": "Karthik S", "email": "student7@demo.com", "password": "Student@123", "department": "CSE", "cgpa": 6.9, "skills": "C++,DSA,Problem Solving,DBMS"},
                    {"name": "Meera Joshi", "email": "student8@demo.com", "password": "Student@123", "department": "EEE", "cgpa": 7.5, "skills": "Python,Cloud,AWS,Communication"},
                    {"name": "Vikram Patel", "email": "student9@demo.com", "password": "Student@123", "department": "CSE", "cgpa": 8.4, "skills": "JavaScript,Web,React,Problem Solving"},
                    {"name": "Priya Gupta", "email": "student10@demo.com", "password": "Student@123", "department": "IT", "cgpa": 7.9, "skills": "Java,DBMS,OS,Networks"},
                    {"name": "Rohan Kulkarni", "email": "student11@demo.com", "password": "Student@123", "department": "CSE", "cgpa": 8.1, "skills": "Python,FastAPI,DBMS,Aptitude"},
                    {"name": "Nisha Menon", "email": "student12@demo.com", "password": "Student@123", "department": "AIML", "cgpa": 8.8, "skills": "Python,ML,TensorFlow,SQL"},
                    {"name": "Aditya Rao", "email": "student13@demo.com", "password": "Student@123", "department": "IT", "cgpa": 7.4, "skills": "Java,OOPS,OS,Communication"},
                    {"name": "Keerthi R", "email": "student14@demo.com", "password": "Student@123", "department": "CSE", "cgpa": 8.5, "skills": "C++,DSA,Problem Solving,Networks"},
                    {"name": "Harini Das", "email": "student15@demo.com", "password": "Student@123", "department": "ECE", "cgpa": 7.7, "skills": "Python,Cloud,AWS,Communication"},
                ]

                for item in demo_students:
                    existing_user = User.query.filter_by(email=item["email"]).first()
                    if not existing_user:
                        existing_user = User(
                            email=item["email"],
                            password_hash=generate_password_hash(item["password"]),
                            role="student",
                        )
                        db.session.add(existing_user)
                        db.session.flush()
                    else:
                        existing_user.password_hash = generate_password_hash(item["password"])
                        existing_user.role = "student"

                    student = Student.query.get(existing_user.id)
                    if not student:
                        student = Student(id=existing_user.id)
                        db.session.add(student)
                    student.full_name = item["name"]
                    student.department = item["department"]
                    student.cgpa = item["cgpa"]
                    student.skills = item["skills"]
                    student.linkedin_url = f"https://linkedin.com/in/{item['name'].lower().replace(' ', '')}"
                    student.github_url = f"https://github.com/{item['email'].split('@')[0]}"
                    student.streak_current = student.streak_current or 5
                    student.streak_longest = student.streak_longest or 12

                    academic_profile = AcademicProfile.query.filter_by(student_id=existing_user.id).first()
                    if not academic_profile:
                        db.session.add(
                            AcademicProfile(
                                student_id=existing_user.id,
                                semester=5,
                                section="A",
                                regulation="R2021",
                                graduation_year=2027,
                                total_credits=160,
                                credits_completed=92,
                                current_sgpa=item["cgpa"],
                                target_cgpa=8.5,
                            )
                        )

                demo_companies = [
                    {
                        "name": "TCS",
                        "drive_date": date.today() + timedelta(days=10),
                        "required_skills": "Python,Java,Problem Solving,DBMS",
                        "eligibility_criteria": "CGPA >= 6.0",
                        "focus_topics": "Problem Solving, DSA, OOPS, SQL, Communication",
                        "package_details": "3.6 LPA",
                    },
                    {
                        "name": "Infosys",
                        "drive_date": date.today() + timedelta(days=18),
                        "required_skills": "Java,Python,DSA,OOPS,OS,Networks",
                        "eligibility_criteria": "CGPA >= 6.5",
                        "focus_topics": "DSA, OOPS, OS, CN, Problem Solving",
                        "package_details": "4.2 LPA",
                    },
                    {
                        "name": "Wipro",
                        "drive_date": date.today() + timedelta(days=25),
                        "required_skills": "Python,Java,Aptitude,Communication",
                        "eligibility_criteria": "CGPA >= 6.0",
                        "focus_topics": "Aptitude, Verbal, DSA basics, Problem Solving",
                        "package_details": "3.8 LPA",
                    },
                ]

                sample_questions = [
                    {
                        "skill_category": "Coding",
                        "question_type": "MCQ",
                        "question_text": "What is time complexity of binary search?",
                        "options": ["O(n)", "O(log n)", "O(n log n)", "O(1)"],
                        "correct_answer": "O(log n)",
                        "difficulty": "Easy",
                    },
                    {
                        "skill_category": "Aptitude",
                        "question_type": "Aptitude",
                        "question_text": "If train speed doubles, travel time becomes?",
                        "options": ["Double", "Half", "Same", "Quadruple"],
                        "correct_answer": "Half",
                        "difficulty": "Easy",
                    },
                    {
                        "skill_category": "Technical",
                        "question_type": "MCQ",
                        "question_text": "Which normal form removes transitive dependency?",
                        "options": ["1NF", "2NF", "3NF", "BCNF"],
                        "correct_answer": "3NF",
                        "difficulty": "Medium",
                    },
                ]

                for company_data in demo_companies:
                    company = Company.query.filter_by(name=company_data["name"]).first()
                    if not company:
                        company = Company(created_by=admin_user.id)
                        db.session.add(company)
                    for key, value in company_data.items():
                        setattr(company, key, value)
                    db.session.flush()

                    if QuestionBank.query.filter_by(company_id=company.id).count() == 0:
                        for question in sample_questions:
                            db.session.add(QuestionBank(company_id=company.id, created_by=admin_user.id, **question))

                db.session.commit()
                app.logger.info("Demo bootstrap data ensured on startup.")
            except SQLAlchemyError as exc:
                db.session.rollback()
                app.logger.exception("Demo bootstrap failed: %s", exc)

    _ensure_demo_bootstrap()

    def generate_csrf_token():
        if "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_urlsafe(32)
        return session["_csrf_token"]

    @app.before_request
    def csrf_protect():
        if request.method in ("POST", "PUT", "DELETE"):
            if request.endpoint == "static":
                return
            token = session.get("_csrf_token")
            sent_token = request.form.get("_csrf_token") or request.headers.get("X-CSRFToken")
            if not token or token != sent_token:
                abort(400, description="Invalid or missing CSRF token.")

    app.jinja_env.globals["csrf_token"] = generate_csrf_token

    @app.context_processor
    def inject_auth_state():
        try:
            return {
                "is_authenticated": current_user.is_authenticated,
                "current_role": getattr(current_user, "role", None),
            }
        except Exception:
            db.session.rollback()
            session.clear()
            return {"is_authenticated": False, "current_role": None}

    @app.route("/")
    def index():
        try:
            authed = current_user.is_authenticated
            role = getattr(current_user, "role", None)
        except Exception:
            db.session.rollback()
            session.clear()
            authed = False
            role = None

        if authed:
            if role == "student":
                return redirect(url_for("student.dashboard"))
            if role == "faculty":
                return redirect(url_for("faculty.dashboard"))
            return redirect(url_for("mentor.dashboard"))
        return render_template("index.html")

    @app.cli.command("init-db")
    def init_db():
        with app.app_context():
            db.create_all()
            print("Database tables created.")

    @app.cli.command("reset-db")
    def reset_db():
        """Drop and recreate all tables (useful after schema changes)."""
        with app.app_context():
            db.drop_all()
            db.create_all()
            print("Database reset complete.")

    @app.cli.command("create-admin")
    @click.option("--email", required=True, help="Admin email")
    @click.option("--password", required=True, help="Admin password")
    @click.option("--name", default="Admin User", help="Admin full name")
    @click.option("--department", default="Placement Cell", help="Admin department")
    def create_admin(email, password, name, department):
        with app.app_context():
            existing = User.query.filter_by(email=email.strip().lower()).first()
            if existing:
                print("User already exists with this email.")
                return

            user = User(
                email=email.strip().lower(),
                password_hash=generate_password_hash(password),
                role="admin",
            )
            db.session.add(user)
            db.session.flush()

            mentor = Mentor(
                id=user.id,
                full_name=name.strip(),
                department=department.strip(),
            )
            db.session.add(mentor)
            db.session.commit()
            print(f"Admin created: {email}")

    @app.cli.command("create-faculty")
    @click.option("--email", required=True, help="Faculty email")
    @click.option("--password", required=True, help="Faculty password")
    @click.option("--name", default="Faculty User", help="Faculty full name")
    @click.option("--department", default="CSE", help="Faculty department")
    def create_faculty(email, password, name, department):
        with app.app_context():
            existing = User.query.filter_by(email=email.strip().lower()).first()
            if existing:
                print("User already exists with this email.")
                return

            user = User(
                email=email.strip().lower(),
                password_hash=generate_password_hash(password),
                role="faculty",
            )
            db.session.add(user)
            db.session.flush()

            faculty = Faculty(
                id=user.id,
                full_name=name.strip(),
                department=department.strip(),
            )
            db.session.add(faculty)
            db.session.commit()
            print(f"Faculty created: {email}")

    @app.cli.command("create-mentor")
    @click.option("--email", required=True, help="Admin email")
    @click.option("--password", required=True, help="Admin password")
    @click.option("--name", default="Admin User", help="Admin full name")
    @click.option("--department", default="Placement Cell", help="Admin department")
    def create_mentor_alias(email, password, name, department):
        """Backward-compatible alias: mentor == admin."""
        with app.app_context():
            existing = User.query.filter_by(email=email.strip().lower()).first()
            if existing:
                print("User already exists with this email.")
                return

            user = User(
                email=email.strip().lower(),
                password_hash=generate_password_hash(password),
                role="admin",
            )
            db.session.add(user)
            db.session.flush()

            admin_profile = Mentor(
                id=user.id,
                full_name=name.strip(),
                department=department.strip(),
            )
            db.session.add(admin_profile)
            db.session.commit()
            print(f"Admin created (mentor alias): {email}")

    @app.cli.command("seed-demo")
    @click.option("--mentor-email", default="admin@college.com", help="Existing admin email")
    def seed_demo(mentor_email):
        with app.app_context():
            mentor_user = User.query.filter_by(email=mentor_email.strip().lower(), role="admin").first()
            if not mentor_user:
                print("Admin not found. Create one first with create-admin.")
                return

            mentor_id = mentor_user.id
            today = date.today()
            demo_companies = [
                {
                    "name": "TCS",
                    "drive_date": today + timedelta(days=10),
                    "required_skills": "Python,Java,Problem Solving,DBMS",
                    "eligibility_criteria": "CGPA >= 6.0",
                    "focus_topics": "Problem Solving, DSA, OOPS, SQL, Communication",
                    "package_details": "3.6 LPA",
                },
                {
                    "name": "Infosys",
                    "drive_date": today + timedelta(days=18),
                    "required_skills": "Java,Python,DSA,OOPS,OS,Networks",
                    "eligibility_criteria": "CGPA >= 6.5",
                    "focus_topics": "DSA, OOPS, OS, CN, Problem Solving",
                    "package_details": "4.2 LPA",
                },
                {
                    "name": "Wipro",
                    "drive_date": today + timedelta(days=25),
                    "required_skills": "Python,Java,Aptitude,Communication",
                    "eligibility_criteria": "CGPA >= 6.0",
                    "focus_topics": "Aptitude, Verbal, DSA basics, Problem Solving",
                    "package_details": "3.8 LPA",
                },
            ]

            created_companies = []
            for item in demo_companies:
                existing_company = Company.query.filter_by(name=item["name"], drive_date=item["drive_date"]).first()
                if existing_company:
                    for k, v in item.items():
                        setattr(existing_company, k, v)
                    created_companies.append(existing_company)
                    continue
                c = Company(created_by=mentor_id, **item)
                db.session.add(c)
                db.session.flush()
                created_companies.append(c)

            for c in created_companies:
                if QuestionBank.query.filter_by(company_id=c.id).count() > 0:
                    continue
                sample_questions = [
                    {
                        "skill_category": "Coding",
                        "question_type": "MCQ",
                        "question_text": "What is time complexity of binary search?",
                        "options": ["O(n)", "O(log n)", "O(n log n)", "O(1)"],
                        "correct_answer": "O(log n)",
                        "difficulty": "Easy",
                    },
                    {
                        "skill_category": "Aptitude",
                        "question_type": "Aptitude",
                        "question_text": "If train speed doubles, travel time becomes?",
                        "options": ["Double", "Half", "Same", "Quadruple"],
                        "correct_answer": "Half",
                        "difficulty": "Easy",
                    },
                    {
                        "skill_category": "Technical",
                        "question_type": "MCQ",
                        "question_text": "Which normal form removes transitive dependency?",
                        "options": ["1NF", "2NF", "3NF", "BCNF"],
                        "correct_answer": "3NF",
                        "difficulty": "Medium",
                    },
                ]
                for q in sample_questions:
                    db.session.add(QuestionBank(company_id=c.id, created_by=mentor_id, **q))

            db.session.commit()
            print("Demo data seeded (companies + questions).")

    @app.cli.command("seed-students")
    def seed_students():
        with app.app_context():
            demo_students = [
                {"name": "Aarav Shah", "email": "student1@demo.com", "password": "Student@123", "department": "CSE", "cgpa": 8.2, "skills": "Python,Java,Problem Solving,DBMS"},
                {"name": "Diya Nair", "email": "student2@demo.com", "password": "Student@123", "department": "IT", "cgpa": 7.8, "skills": "Java,DSA,OOPS,SQL"},
                {"name": "Ishaan Verma", "email": "student3@demo.com", "password": "Student@123", "department": "CSE", "cgpa": 8.6, "skills": "Python,ML,Data Science,SQL"},
                {"name": "Ananya Rao", "email": "student4@demo.com", "password": "Student@123", "department": "ECE", "cgpa": 7.2, "skills": "C,Embedded,Problem Solving,DBMS"},
                {"name": "Rahul Mehta", "email": "student5@demo.com", "password": "Student@123", "department": "CSE", "cgpa": 9.0, "skills": "Java,Spring,OOPS,DSA"},
                {"name": "Sneha Iyer", "email": "student6@demo.com", "password": "Student@123", "department": "IT", "cgpa": 8.0, "skills": "Python,Flask,Web,SQL"},
                {"name": "Karthik S", "email": "student7@demo.com", "password": "Student@123", "department": "CSE", "cgpa": 6.9, "skills": "C++,DSA,Problem Solving,DBMS"},
                {"name": "Meera Joshi", "email": "student8@demo.com", "password": "Student@123", "department": "EEE", "cgpa": 7.5, "skills": "Python,Cloud,AWS,Communication"},
                {"name": "Vikram Patel", "email": "student9@demo.com", "password": "Student@123", "department": "CSE", "cgpa": 8.4, "skills": "JavaScript,Web,React,Problem Solving"},
                {"name": "Priya Gupta", "email": "student10@demo.com", "password": "Student@123", "department": "IT", "cgpa": 7.9, "skills": "Java,DBMS,OS,Networks"},
                {"name": "Rohan Kulkarni", "email": "student11@demo.com", "password": "Student@123", "department": "CSE", "cgpa": 8.1, "skills": "Python,FastAPI,DBMS,Aptitude"},
                {"name": "Nisha Menon", "email": "student12@demo.com", "password": "Student@123", "department": "AIML", "cgpa": 8.8, "skills": "Python,ML,TensorFlow,SQL"},
                {"name": "Aditya Rao", "email": "student13@demo.com", "password": "Student@123", "department": "IT", "cgpa": 7.4, "skills": "Java,OOPS,OS,Communication"},
                {"name": "Keerthi R", "email": "student14@demo.com", "password": "Student@123", "department": "CSE", "cgpa": 8.5, "skills": "C++,DSA,Problem Solving,Networks"},
                {"name": "Harini Das", "email": "student15@demo.com", "password": "Student@123", "department": "ECE", "cgpa": 7.7, "skills": "Python,Cloud,AWS,Communication"},
            ]

            created = 0
            for s in demo_students:
                existing = User.query.filter_by(email=s["email"]).first()
                if existing:
                    if existing.role != "student":
                        continue
                    existing_student = Student.query.get(existing.id)
                    if existing_student:
                        existing_student.full_name = s["name"]
                        existing_student.department = s["department"]
                        existing_student.cgpa = s["cgpa"]
                        existing_student.skills = s["skills"]
                        existing_student.linkedin_url = f"https://linkedin.com/in/{s['name'].lower().replace(' ', '')}"
                        existing_student.github_url = f"https://github.com/{s['email'].split('@')[0]}"
                        existing_student.streak_current = existing_student.streak_current or 5
                        existing_student.streak_longest = existing_student.streak_longest or 12
                        ap = AcademicProfile.query.filter_by(student_id=existing.id).first()
                        if not ap:
                            db.session.add(
                                AcademicProfile(
                                    student_id=existing.id,
                                    semester=5,
                                    section="A",
                                    regulation="R2021",
                                    graduation_year=2027,
                                    total_credits=160,
                                    credits_completed=92,
                                    current_sgpa=s["cgpa"],
                                    target_cgpa=8.5,
                                )
                            )
                    continue
                user = User(
                    email=s["email"],
                    password_hash=generate_password_hash(s["password"]),
                    role="student",
                )
                db.session.add(user)
                db.session.flush()
                student = Student(
                    id=user.id,
                    full_name=s["name"],
                    department=s["department"],
                    cgpa=s["cgpa"],
                    skills=s["skills"],
                    linkedin_url=f"https://linkedin.com/in/{s['name'].lower().replace(' ', '')}",
                    github_url=f"https://github.com/{s['email'].split('@')[0]}",
                    streak_current=5,
                    streak_longest=12,
                )
                db.session.add(student)
                db.session.add(
                    AcademicProfile(
                        student_id=user.id,
                        semester=5,
                        section="A",
                        regulation="R2021",
                        graduation_year=2027,
                        total_credits=160,
                        credits_completed=92,
                        current_sgpa=s["cgpa"],
                        target_cgpa=8.5,
                    )
                )
                created += 1

            db.session.commit()
            print(f"Seeded {created} demo students.")
            print("Login emails: student1@demo.com ... student15@demo.com")
            print("Login password for all demo students: Student@123")

    @app.errorhandler(OperationalError)
    @app.errorhandler(ProgrammingError)
    def handle_db_operational_error(_error):
        app.logger.exception("Database error: %s", _error)
        db.session.rollback()
        retry_url = request.referrer or url_for("index")
        return render_template("db_unavailable.html", retry_url=retry_url), 503

    @app.errorhandler(SQLAlchemyError)
    def handle_sqlalchemy_error(_error):
        app.logger.exception("SQLAlchemy error: %s", _error)
        db.session.rollback()
        retry_url = request.referrer or url_for("index")
        return render_template("db_unavailable.html", retry_url=retry_url), 503

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
