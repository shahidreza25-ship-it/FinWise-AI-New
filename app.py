import os
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-before-deploying")

database_url = os.environ.get("DATABASE_URL", "sqlite:///finwise.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("RENDER", "") == "true"

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    monthly_budget = db.Column(db.Float, nullable=False, default=15000)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    kind = db.Column(db.String(10), nullable=False)  # income / expense
    category = db.Column(db.String(60), nullable=False, default="Other")
    txn_date = db.Column(db.Date, nullable=False, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    target = db.Column(db.Float, nullable=False)
    saved = db.Column(db.Float, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None

@app.get("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name, a valid email, and a password with at least 8 characters.", "error")
            return render_template("auth.html", mode="signup")
        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists. Try logging in or use another email.", "error")
            return render_template("auth.html", mode="signup")
        user = User(name=name, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("Signup failed")
            flash("We couldn't create the account. Please try again.", "error")
            return render_template("auth.html", mode="signup")
        session.clear()
        session["user_id"] = user.id
        session["user_name"] = user.name
        session.permanent = True
        return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="signup")

@app.route("/login", methods=["GET", "POST"])
def login():
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
        flash("Email or password is incorrect. Check your details or create an account.", "error")
    return render_template("auth.html", mode="login")

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.get("/dashboard")
@login_required
def dashboard():
    user = current_user()
    transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.txn_date.desc(), Transaction.id.desc()).limit(50).all()
    goals = Goal.query.filter_by(user_id=user.id).order_by(Goal.id.desc()).all()
    month_start = date.today().replace(day=1)
    month_txns = Transaction.query.filter(
        Transaction.user_id == user.id,
        Transaction.txn_date >= month_start
    ).all()
    income = sum(t.amount for t in month_txns if t.kind == "income")
    expenses = sum(t.amount for t in month_txns if t.kind == "expense")
    return render_template("dashboard.html", user=user, transactions=transactions, goals=goals,
                           income=income, expenses=expenses, balance=income-expenses,
                           month_label=date.today().strftime("%B %Y"))

@app.post("/transaction/add")
@login_required
def add_transaction():
    user = current_user()
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
        flash("Enter a valid positive amount and date.", "error")
        return redirect(url_for("dashboard"))
    if not title or kind not in ("income", "expense"):
        flash("Please complete the transaction details.", "error")
        return redirect(url_for("dashboard"))
    db.session.add(Transaction(user_id=user.id, title=title, amount=amount, kind=kind, category=category, txn_date=txn_date))
    db.session.commit()
    flash("Transaction added.", "success")
    return redirect(url_for("dashboard"))

@app.post("/transaction/<int:txn_id>/delete")
@login_required
def delete_transaction(txn_id):
    txn = Transaction.query.filter_by(id=txn_id, user_id=session["user_id"]).first_or_404()
    db.session.delete(txn)
    db.session.commit()
    flash("Transaction deleted.", "success")
    return redirect(url_for("dashboard"))

@app.post("/budget")
@login_required
def update_budget():
    user = current_user()
    try:
        amount = float(request.form.get("monthly_budget", ""))
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash("Enter a valid budget greater than zero.", "error")
        return redirect(url_for("dashboard"))
    user.monthly_budget = amount
    db.session.commit()
    flash("Monthly budget updated.", "success")
    return redirect(url_for("dashboard"))

@app.post("/goal/add")
@login_required
def add_goal():
    user = current_user()
    title = request.form.get("title", "").strip()
    try:
        target = float(request.form.get("target", ""))
        saved = float(request.form.get("saved", "0") or 0)
        if target <= 0 or saved < 0:
            raise ValueError
    except (ValueError, TypeError):
        flash("Enter a valid target and saved amount.", "error")
        return redirect(url_for("dashboard"))
    if not title:
        flash("Enter a goal name.", "error")
        return redirect(url_for("dashboard"))
    db.session.add(Goal(user_id=user.id, title=title, target=target, saved=min(saved, target)))
    db.session.commit()
    flash("Savings goal added.", "success")
    return redirect(url_for("dashboard"))

@app.post("/goal/<int:goal_id>/delete")
@login_required
def delete_goal(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=session["user_id"]).first_or_404()
    db.session.delete(goal)
    db.session.commit()
    flash("Goal deleted.", "success")
    return redirect(url_for("dashboard"))

@app.get("/health")
def health():
    return jsonify(status="ok")

if __name__ == "__main__":
    app.run(debug=True)
