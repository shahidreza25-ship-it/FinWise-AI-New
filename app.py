
import os
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "local-dev-only-change-me"
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("RENDER", "").lower() == "true"
)

database_url = os.environ.get("DATABASE_URL", "sqlite:///finwise.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://", "postgresql://", 1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(
        db.String(255), unique=True, nullable=False, index=True
    )
    password_hash = db.Column(db.String(255), nullable=False)
    monthly_budget = db.Column(
        db.Float, nullable=False, default=15000.0
    )
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"),
        nullable=False, index=True
    )
    title = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    kind = db.Column(db.String(10), nullable=False)
    category = db.Column(
        db.String(60), nullable=False, default="Other"
    )
    txn_date = db.Column(
        db.Date, nullable=False, default=date.today
    )
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )


class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"),
        nullable=False, index=True
    )
    title = db.Column(db.String(120), nullable=False)
    target = db.Column(db.Float, nullable=False)
    saved = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )


with app.app_context():
    db.create_all()


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_current_user() is None:
            session.clear()
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.get("/")
def index():
    if get_current_user():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if get_current_user():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or len(name) > 80:
            flash("Please enter your name (up to 80 characters).", "error")
            return render_template("auth.html", mode="signup")

        if not email or len(email) > 255 or "@" not in email:
            flash("Please enter a valid email address.", "error")
            return render_template("auth.html", mode="signup")

        if len(password) < 8:
            flash("Your password must contain at least 8 characters.", "error")
            return render_template("auth.html", mode="signup")

        if User.query.filter_by(email=email).first():
            flash(
                "An account with this email already exists. "
                "Please log in or use another email.",
                "error"
            )
            return render_template("auth.html", mode="signup")

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("Could not create user")
            flash("Account creation failed. Please try again.", "error")
            return render_template("auth.html", mode="signup")

        session.clear()
        session["user_id"] = user.id
        session["user_name"] = user.name
        session.permanent = True
        return redirect(url_for("dashboard"))

    return render_template("auth.html", mode="signup")


@app.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session["user_id"] = user.id
            session["user_name"] = user.name
            session.permanent = True
            return redirect(url_for("dashboard"))

        flash(
            "Email or password is incorrect. Please try again "
            "or create an account.",
            "error"
        )

    return render_template("auth.html", mode="login")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    today = date.today()
    first_day = today.replace(day=1)

    month_transactions = Transaction.query.filter(
        Transaction.user_id == user.id,
        Transaction.txn_date >= first_day,
        Transaction.txn_date <= today
    ).all()

    income = sum(
        t.amount for t in month_transactions if t.kind == "income"
    )
    expenses = sum(
        t.amount for t in month_transactions if t.kind == "expense"
    )

    transactions = (
        Transaction.query
        .filter_by(user_id=user.id)
        .order_by(Transaction.txn_date.desc(), Transaction.id.desc())
        .limit(100)
        .all()
    )

    goals = (
        Goal.query
        .filter_by(user_id=user.id)
        .order_by(Goal.id.desc())
        .all()
    )

    return render_template(
        "dashboard.html",
        user=user,
        transactions=transactions,
        goals=goals,
        income=income,
        expenses=expenses,
        balance=income - expenses,
        month_label=today.strftime("%B %Y"),
        today=today.isoformat()
    )


@app.post("/transaction/add")
@login_required
def add_transaction():
    user = get_current_user()
    title = request.form.get("title", "").strip()
    kind = request.form.get("kind", "expense")
    category = request.form.get("category", "Other").strip() or "Other"
    amount_raw = request.form.get("amount", "").strip()
    date_raw = request.form.get("txn_date", "").strip()

    try:
        amount = float(amount_raw)
        txn_date = date.fromisoformat(date_raw) if date_raw else date.today()
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash("Please enter a valid amount and date.", "error")
        return redirect(url_for("dashboard"))

    if not title or len(title) > 120 or kind not in {"income", "expense"}:
        flash("Please check the transaction details.", "error")
        return redirect(url_for("dashboard"))

    txn = Transaction(
        user_id=user.id,
        title=title,
        amount=amount,
        kind=kind,
        category=category[:60],
        txn_date=txn_date
    )
    db.session.add(txn)
    db.session.commit()

    flash("Transaction added successfully.", "success")
    return redirect(url_for("dashboard"))


@app.post("/transaction/<int:txn_id>/delete")
@login_required
def delete_transaction(txn_id):
    txn = Transaction.query.filter_by(
        id=txn_id, user_id=session["user_id"]
    ).first_or_404()

    db.session.delete(txn)
    db.session.commit()
    flash("Transaction deleted.", "success")
    return redirect(url_for("dashboard"))


@app.post("/budget")
@login_required
def update_budget():
    user = get_current_user()

    try:
        amount = float(request.form.get("monthly_budget", ""))
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash("Please enter a budget greater than zero.", "error")
        return redirect(url_for("dashboard"))

    user.monthly_budget = amount
    db.session.commit()

    flash("Monthly budget updated.", "success")
    return redirect(url_for("dashboard"))


@app.post("/goal/add")
@login_required
def add_goal():
    user = get_current_user()
    title = request.form.get("title", "").strip()

    try:
        target = float(request.form.get("target", ""))
        saved = float(request.form.get("saved", "0") or 0)
        if target <= 0 or saved < 0:
            raise ValueError
    except (ValueError, TypeError):
        flash("Please enter a valid savings target and saved amount.", "error")
        return redirect(url_for("dashboard"))

    if not title or len(title) > 120:
        flash("Please enter a goal name (up to 120 characters).", "error")
        return redirect(url_for("dashboard"))

    goal = Goal(
        user_id=user.id,
        title=title,
        target=target,
        saved=min(saved, target)
    )
    db.session.add(goal)
    db.session.commit()

    flash("Savings goal added.", "success")
    return redirect(url_for("dashboard"))


@app.post("/goal/<int:goal_id>/delete")
@login_required
def delete_goal(goal_id):
    goal = Goal.query.filter_by(
        id=goal_id, user_id=session["user_id"]
    ).first_or_404()

    db.session.delete(goal)
    db.session.commit()
    flash("Savings goal deleted.", "success")
    return redirect(url_for("dashboard"))


@app.get("/health")
def health():
    return jsonify(status="ok")


if __name__ == "__main__":
    app.run(debug=True)
