import re

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Student, Mentor, Faculty


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_authenticated_safe():
    try:
        return current_user.is_authenticated
    except Exception:
        db.session.rollback()
        return False


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if _is_authenticated_safe():
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        department = request.form.get("department", "").strip()

        if not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "danger")
            return render_template("auth/register.html")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("auth/register.html")
        if not full_name:
            flash("Full name is required.", "danger")
            return render_template("auth/register.html")

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("Email is already registered.", "warning")
            return render_template("auth/register.html")

        user = User(email=email, password_hash=generate_password_hash(password), role="student")
        db.session.add(user)
        db.session.flush()

        student = Student(id=user.id, full_name=full_name, department=department)
        db.session.add(student)
        db.session.commit()

        flash("Student registration successful. Please login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/admin-register", methods=["GET", "POST"])
def admin_register():
    if _is_authenticated_safe():
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        department = request.form.get("department", "").strip()

        if not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "danger")
            return render_template("auth/admin_register.html")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("auth/admin_register.html")
        if not full_name:
            flash("Full name is required.", "danger")
            return render_template("auth/admin_register.html")

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("Email is already registered.", "warning")
            return render_template("auth/admin_register.html")

        user = User(email=email, password_hash=generate_password_hash(password), role="admin")
        db.session.add(user)
        db.session.flush()

        admin_profile = Mentor(id=user.id, full_name=full_name, department=department)
        db.session.add(admin_profile)
        db.session.commit()

        flash("Admin registration successful. Please login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/admin_register.html")


@auth_bp.route("/faculty-register", methods=["GET", "POST"])
def faculty_register():
    if _is_authenticated_safe():
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        department = request.form.get("department", "").strip()

        if not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "danger")
            return render_template("auth/faculty_register.html")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("auth/faculty_register.html")
        if not full_name:
            flash("Full name is required.", "danger")
            return render_template("auth/faculty_register.html")

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("Email is already registered.", "warning")
            return render_template("auth/faculty_register.html")

        user = User(email=email, password_hash=generate_password_hash(password), role="faculty")
        db.session.add(user)
        db.session.flush()

        faculty_profile = Faculty(id=user.id, full_name=full_name, department=department)
        db.session.add(faculty_profile)
        db.session.commit()

        flash("Faculty registration successful. Please login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/faculty_register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if _is_authenticated_safe():
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "student")

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid credentials.", "danger")
            return render_template("auth/login.html")
        if role and user.role != role:
            flash(f"Logged in with your {user.role} account.", "info")

        login_user(user)
        flash("Login successful.", "success")

        if user.role == "student":
            return redirect(url_for("student.dashboard"))
        if user.role == "faculty":
            return redirect(url_for("faculty.dashboard"))
        return redirect(url_for("mentor.dashboard"))

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
