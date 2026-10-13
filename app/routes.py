import hashlib
import os
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, current_app)
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Location, Deposit
from app.ml import predict

bp = Blueprint("main", __name__)

POINTS = {
    "pet_bottle": 10,
    "plastic_container": 8,
    "plastic_bag": 5,
    "non_recyclable_plastic": 0,
    "not_plastic": 0,
}

ALLOWED_EXT = {"jpg", "jpeg", "png"}

@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered.", "danger")
        else:
            user = User(name=name, email=email)
            user.set_password(password)
            # DEV ONLY: first account becomes admin
            user.role = "admin" if User.query.count() == 0 else "user"
            db.session.add(user)
            db.session.commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("main.login"))

    return render_template("register.html")

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(request.form["password"]):
            login_user(user)
            return redirect(url_for("main.home"))
        flash("Wrong email or password.", "danger")
    return render_template("login.html")

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.login"))

@bp.route("/")
@login_required
def home():
    deposits = (Deposit.query.filter_by(user_id=current_user.id)
                .order_by(Deposit.created_at.desc()).limit(5).all())
    return render_template("home.html", deposits=deposits)

@bp.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    locations = Location.query.all()
    if request.method == "POST":
        file = request.files.get("photo")
        location_id = request.form.get("location_id", type=int)

        if not file or not file.filename:
            flash("Please choose a photo.", "danger")
            return redirect(url_for("main.deposit"))

        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_EXT:
            flash("Only JPG or PNG images are allowed.", "danger")
            return redirect(url_for("main.deposit"))

        data = file.read()
        image_hash = hashlib.sha256(data).hexdigest()

        # Anti-cheat 1: same photo twice
        if Deposit.query.filter_by(image_hash=image_hash).first():
            flash("This photo was already used.", "danger")
            return redirect(url_for("main.deposit"))

        # Anti-cheat 2: rate limit
        since = datetime.utcnow() - timedelta(hours=1)
        recent = Deposit.query.filter(
            Deposit.user_id == current_user.id, Deposit.created_at >= since
        ).count()
        if recent >= current_app.config["MAX_DEPOSITS_PER_HOUR"]:
            flash("Too many deposits this hour. Try later.", "danger")
            return redirect(url_for("main.deposit"))

        # ENSURE UPLOAD FOLDER EXISTS
        upload_dir = current_app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_dir, exist_ok=True)

        path = os.path.join(upload_dir, f"{image_hash}.{ext}")
        with open(path, "wb") as f:
            f.write(data)

        try:
            label, confidence = predict(path)

            # Anti-cheat 3: low confidence
            if confidence < current_app.config["CONFIDENCE_THRESHOLD"]:
                flash("Not sure what this is. Please retake a clearer photo.", "warning")
                return redirect(url_for("main.deposit"))

            points = POINTS.get(label, 0)
            dep = Deposit(user_id=current_user.id, location_id=location_id,
                          plastic_type=label, confidence=confidence,
                          points_awarded=points, image_hash=image_hash)
            current_user.points += points
            db.session.add(dep)
            db.session.commit()

            flash(f"Detected: {label.replace('_', ' ')} "
                  f"({confidence:.0%} sure). You earned {points} points!", "success")
            return redirect(url_for("main.home"))

        finally:
            # CLEANUP: Always remove temporary file safely if it exists
            if os.path.exists(path):
                os.remove(path)

    return render_template("deposit.html", locations=locations)