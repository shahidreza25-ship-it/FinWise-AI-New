# FinWise — Fresh Starter

A responsive black-and-white personal finance tracker built with Flask.

## Features
- Create an account and log in securely (passwords are hashed)
- Separate data for each user
- Monthly income, expenses, net amount, and budget remaining
- Add/delete transactions
- Set a monthly budget
- Create/delete savings goals
- Responsive design for phones, tablets, and laptops
- SQLAlchemy supports SQLite locally and PostgreSQL when `DATABASE_URL` is set

## Run on your computer

1. Install Python 3.10 or newer.
2. Open Terminal in this folder.
3. Create and activate a virtual environment (optional but recommended):

   **Mac/Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   **Windows**
   ```bat
   python -m venv .venv
   .venv\\Scripts\\activate
   ```

4. Install packages:
   ```bash
   pip install -r requirements.txt
   ```
5. Set a secret key (recommended):
   ```bash
   export SECRET_KEY="put-a-long-random-secret-here"
   ```
   On Windows PowerShell use:
   ```powershell
   $env:SECRET_KEY="put-a-long-random-secret-here"
   ```
6. Start the app:
   ```bash
   python app.py
   ```
7. Open http://127.0.0.1:5000

## Deploy to Render

1. Create a **new GitHub repository** and upload these project files.
2. In Render, create a **new Web Service** and connect that repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variable `SECRET_KEY` with a long random value.
6. For durable user accounts and data, create a PostgreSQL database on Render and set `DATABASE_URL` in the web service to its **Internal Database URL**. If Render gives a URL beginning `postgres://`, the app normalizes it.
7. Deploy and open the `onrender.com` URL.

**Important:** SQLite data on a typical Render free web service can be lost when the service is redeployed or restarted. Use PostgreSQL for persistent accounts and transactions. A free Render web service may sleep when idle, so its first request after a quiet period can take a little longer.

## Routes
- `/signup` — create account
- `/login` — log in
- `/dashboard` — private dashboard
- `/logout` — log out
- `/health` — health check

This is an educational personal finance organizer, not a bank or financial adviser.
