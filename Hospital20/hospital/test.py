# app.py
import os
from datetime import datetime, timedelta, time as dt_time
import random, string
from functools import wraps
from urllib.parse import quote_plus

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from flask import (
    Flask, request, session, redirect, url_for, flash,
    render_template_string, jsonify, send_file
)
from dotenv import load_dotenv
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize APScheduler
import pymysql

# Get database configuration
mysql_user = os.getenv("MYSQL_USER", "avnadmin")
mysql_password = os.getenv("MYSQL_PASSWORD", "AVNS_olPiVJTGPWoGFJSMGPc")
mysql_host = os.getenv("MYSQL_HOST", "mysql-18ab8524-hospitalapp.k.aivencloud.com")
mysql_port = os.getenv("MYSQL_PORT", "22582")
mysql_database = os.getenv("MYSQL_DATABASE", "defaultdb")

# Create the database URL with SSL disabled
db_config = {
    'drivername': 'mysql+pymysql',
    'username': mysql_user,
    'password': mysql_password,
    'host': mysql_host,
    'port': int(mysql_port),
    'database': mysql_database,
    'query': {'ssl_disabled': 'true'}
}

from sqlalchemy.engine.url import URL
db_url = URL.create(**db_config)

scheduler = BackgroundScheduler(
    jobstores={
        'default': SQLAlchemyJobStore(url=db_url)
    },
    executors={
        'default': ThreadPoolExecutor(20)
    },
    job_defaults={
        'coalesce': False,
        'max_instances': 3
    }
)

# Optional deps (gracefully degrade if missing)
try:
    from flask_mail import Mail, Message
    MAIL_AVAILABLE = True
except Exception:
    MAIL_AVAILABLE = False

# Import any additional required modules here
try:
    import requests  # For SMS API
except ImportError:
    pass

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# SMS configuration
SMS_API_KEY = os.getenv('SMS_API_KEY', '')
SMS_API_URL = os.getenv('SMS_API_URL', '')

# ---------------------------- Config & DB ----------------------------
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

load_dotenv()

app = Flask(__name__)
# app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

# Configure APScheduler
scheduler = BackgroundScheduler(
    jobstores={
        'default': SQLAlchemyJobStore(url=f'mysql+mysqlconnector://{os.getenv("MYSQL_USER")}:{os.getenv("MYSQL_PASSWORD")}@{os.getenv("MYSQL_HOST")}:{os.getenv("MYSQL_PORT")}/{os.getenv("MYSQL_DATABASE")}')
    },
    executors={
        'default': ThreadPoolExecutor(20)
    },
    job_defaults={
        'coalesce': False,
        'max_instances': 3
    }
)
app.permanent_session_lifetime = timedelta(minutes=int(os.getenv("SESSION_MINUTES", "60")))
app.secret_key = os.getenv('SECRET_KEY')
# Database config (from .env or defaults)
db_config = {
    "host": os.getenv("MYSQL_HOST"),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "port": int(os.getenv("MYSQL_PORT")),
    "ssl_disabled": False
}

# One persistent connection (optional, not strictly needed anymore)
db = mysql.connector.connect(**db_config)

def q(query, params=None, fetchone=False, fetchall=False, many=False, commit=False):
    cur = db.cursor(dictionary=True)  # ✅ this makes rows dicts, not tuples
    if many:
        cur.executemany(query, params or [])
    else:
        cur.execute(query, params or ())
    if commit:
        db.commit()
    if fetchone:
        return cur.fetchone()
    if fetchall:
        return cur.fetchall()
    return cur

# ---------------------------- Optional Mail ----------------------------
if MAIL_AVAILABLE:
    app.config.update(
        MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
        MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
        MAIL_USE_TLS=True if os.getenv("MAIL_USE_TLS", "1") == "1" else False,
        MAIL_USE_SSL=True if os.getenv("MAIL_USE_SSL", "0") == "1" else False,
        MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
        MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER", os.getenv("MAIL_USERNAME")),
    )
    mail = Mail(app)
else:
    mail = None

def send_email(to, subject, body):
    if not MAIL_AVAILABLE or not mail or not to:
        return False
    try:
        msg = Message(subject, recipients=[to])
        msg.body = body
        mail.send(msg)
        return True
    except Exception:
        return False

# No payment gateway configuration needed for demo version

def send_sms(phone_number, message):
    """Send SMS using configured SMS gateway"""
    print("\n=== SMS Debug Information ===")
    print(f"Attempting to send SMS to: {phone_number}")
    print(f"Message content: {message}")
    
    if not SMS_API_KEY or not SMS_API_URL:
        print("SMS Gateway not configured - Running in demo mode")
        print(f"Demo SMS -> Phone: {phone_number}")
        print(f"Demo SMS -> Message: {message}")
        print("=== End SMS Debug ===\n")
        return True
        
    try:
        print(f"Using SMS Gateway: {SMS_API_URL}")
        response = requests.post(SMS_API_URL, 
            json={
                'apikey': SMS_API_KEY,
                'phone': phone_number,
                'message': message
            }
        )
        success = response.status_code == 200
        print(f"SMS sending {'successful' if success else 'failed'}")
        print(f"Response status code: {response.status_code}")
        print("=== End SMS Debug ===\n")
        return success
    except Exception as e:
        print(f"SMS sending error: {str(e)}")
        print("=== End SMS Debug ===\n")
        return False

# ---------------------------- Helpers ----------------------------
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        session.permanent = True  # refresh lifetime
        return f(*args, **kwargs)
    return wrap

def role_required(*roles):
    def deco(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            user = session.get("user")
            if not user or user.get("role") not in roles:
                flash("Unauthorized")
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrap
    return deco

def log_action(role, user_id, action):
    q("INSERT INTO audit_logs (role, user_id, action) VALUES (%s,%s,%s)", (role, user_id, action))

def jitsi_room():
    # simple random room
    return "HospMeet-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def weekday_name(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    # Return 'Mon', 'Tue', ...
    return ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][dt.weekday()]

def time_to_str(t: dt_time):
    return t.strftime("%H:%M:%S")

def str_to_time(s: str) -> dt_time:
    return datetime.strptime(s, "%H:%M:%S").time()

def generate_slots(start: dt_time, end: dt_time, step_minutes=15):
    slots = []
    cur = datetime.combine(datetime.today(), start)
    end_dt = datetime.combine(datetime.today(), end)
    delta = timedelta(minutes=step_minutes)
    while cur + delta <= end_dt:
        slots.append(cur.time().strftime("%H:%M:%S"))
        cur += delta
    return slots
  
SEED_SQL = [
    (
        "INSERT IGNORE INTO departments (name) VALUES (%s)",
        [("Cardiology",), ("Neurology",), ("Orthopedics",), ("Pediatrics",), ("Dermatology",)]
    )
]

@app.route("/init_db")
def init_db():
    # ✅ Seed departments safely (ignore duplicates)
    for query, data in SEED_SQL:
        try:
            q(query, data, many=True, commit=True)
        except Exception as e:
            # Skip if duplicates exist
            print(f"Seed insert skipped: {e}")

    # ✅ Ensure default admin exists
    user = q("SELECT id FROM users WHERE email=%s LIMIT 1", ("admin@demo.com",), fetchone=True)
    if not user:
        pwd = generate_password_hash("admin123")
        q(
            "INSERT INTO users (role, name, email, password_hash) VALUES (%s, %s, %s, %s)",
            ("admin", "Super Admin", "admin@demo.com", pwd),
            commit=True
        )
        flash("Default admin created: admin@demo.com / admin123")
    else:
        flash("Admin already exists. Login with admin@demo.com / your password")

    return redirect(url_for("login"))

# ---------------------------- Templates (HTML/CSS/JS) ----------------------------

# PHONE CALL PAGE
phone_call_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contact Dr. {{ doctor_name }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body { 
            font-family: 'Inter', system-ui, sans-serif;
            margin: 0;
            min-height: 100vh;
            background: linear-gradient(135deg, #4776E6 0%, #8E54E9 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            color: #333;
            position: relative;
        }
        
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255, 255, 255, 0.1);
            z-index: 0;
        }

        .container {
            max-width: 480px;
            width: 100%;
            z-index: 1;
        }

        .card {
            background: #ffffff;
            border-radius: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
            padding: 32px;
            text-align: center;
            transition: transform 0.3s ease;
            position: relative;
            overflow: hidden;
            z-index: 1;
        }

        .card:hover {
            transform: translateY(-5px);
        }

        .header {
            margin-bottom: 24px;
        }

        .header h2 {
            color: #1a365d;
            font-size: 28px;
            margin-bottom: 8px;
        }

        .header p {
            color: #64748b;
            font-size: 16px;
        }

        .doctor-card {
            background: #ffffff;
            border-radius: 16px;
            padding: 24px;
            margin: 20px 0;
            border: 1px solid #e2e8f0;
            position: relative;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }

        .doctor-avatar {
            width: 100px;
            height: 100px;
            background: linear-gradient(135deg, #4776E6 0%, #8E54E9 100%);
            border-radius: 50%;
            margin: 0 auto 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 40px;
            font-weight: 600;
            animation: pulse 2s infinite;
            box-shadow: 0 4px 15px rgba(71, 118, 230, 0.3);
        }

        .doctor-info h3 {
            color: #2d3748;
            font-size: 26px;
            margin-bottom: 16px;
            font-weight: 600;
        }

        .contact-info {
            background: white;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 20px;
            border: 1px solid #e2e8f0;
        }

        .phone-number {
            font-size: 24px;
            color: #2d3748;
            font-weight: 600;
            margin: 12px 0;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }

        .phone-icon {
            font-size: 28px;
            color: #3498db;
            animation: tada 2s infinite;
        }

        .call-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 14px 32px;
            background: #38b2ac;
            color: white;
            text-decoration: none;
            border-radius: 12px;
            font-size: 18px;
            font-weight: 600;
            margin: 16px 0;
            transition: all 0.3s ease;
            border: none;
            cursor: pointer;
        }

        .call-btn:hover {
            background: #319795;
            transform: scale(1.05);
        }

        .call-btn:active {
            transform: scale(0.95);
        }

        .back-btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 12px 24px;
            background: transparent;
            color: #4a5568;
            text-decoration: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 500;
            margin-top: 16px;
            transition: all 0.3s ease;
            border: 2px solid #e2e8f0;
        }

        .back-btn:hover {
            background: #f7fafc;
            color: #2d3748;
        }

        .status-badge {
            display: inline-block;
            padding: 6px 12px;
            background: #e6fffa;
            color: #319795;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 16px;
        }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }

        @keyframes tada {
            0% { transform: scale(1) rotate(0); }
            10%, 20% { transform: scale(0.9) rotate(-3deg); }
            30%, 50%, 70%, 90% { transform: scale(1.1) rotate(3deg); }
            40%, 60%, 80% { transform: scale(1.1) rotate(-3deg); }
            100% { transform: scale(1) rotate(0); }
        }

        @media (max-width: 480px) {
            .card {
                padding: 24px;
                border-radius: 16px;
            }

            .header h2 {
                font-size: 24px;
            }

            .doctor-avatar {
                width: 70px;
                height: 70px;
                font-size: 28px;
            }

            .phone-number {
                font-size: 20px;
            }

            .call-btn {
                padding: 12px 24px;
                font-size: 16px;
            }
        }
    </style>
</head>
<body>
    <div class="container animate__animated animate__fadeIn">
        <div class="card">
            <div class="header">
                <h2>Contact Your Doctor</h2>
                <p>You can reach out to your doctor directly</p>
            </div>
            
            <div class="doctor-card animate__animated animate__fadeInUp">
                <div class="doctor-avatar">
                    {{ doctor_name[0] }}
                </div>
                <div class="doctor-info">
                    <div class="status-badge">Available for Call</div>
                    <h3>Dr. {{ doctor_name }}</h3>
                    <div class="contact-info">
                        <div class="phone-number">
                            <span class="phone-icon">📞</span>
                            {{ doctor_phone or 'No phone number available' }}
                        </div>
                        {% if doctor_phone %}
                            <a href="tel:{{ doctor_phone }}" class="call-btn">
                                <span>📱</span> Call Now
                            </a>
                        {% endif %}
                    </div>
                </div>
            </div>

            <a href="{{ url_for('dashboard_patient_view') }}" class="back-btn">
                <span>←</span> Return to Dashboard
            </a>
        </div>
    </div>
</body>
</html>
"""
# LOGIN
login_page = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Appointment Booking Portal</title>
  <style>
    body{margin:0;padding:0;font-family:Arial,sans-serif;background:linear-gradient(120deg,#fafbf8 0%,#e4e6e4 100%);min-height:100vh;display:flex;align-items:center;justify-content:center;flex-direction:column}
    h1{color:#000;margin:0 0 10px;font-size:40px}
    .box{background:rgba(255,255,255,.35);box-shadow:0 8px 32px rgba(0,0,0,.25);backdrop-filter:blur(15px);border-radius:16px;padding:30px;width:350px;border:1px solid rgba(255,255,255,.25)}
    label{font-weight:bold;display:block;margin:10px 0 5px}
    input{width:100%;padding:10px;margin-bottom:12px;border:1px solid #ccc;border-radius:6px}
    button{width:100%;padding:10px;border:none;border-radius:6px;color:#fff;font-weight:bold;cursor:pointer}
    .primary{background:#d35400}.primary:hover{background:#e67e22}
    .alt{background:#558b2f;margin-top:8px}.alt:hover{background:#66bb6a}
    ul{color:red;list-style:none;padding:0;text-align:center}
    a.tiny{margin-top:10px;display:inline-block;text-decoration:none}
  </style>
</head>
<body>
  <h1>Appointment Booking Portal</h1>
  {% with messages = get_flashed_messages() %}
    {% if messages %}<ul>{% for m in messages %}<li>{{m}}</li>{% endfor %}</ul>{% endif %}
  {% endwith %}
  <div class="box">
    <form method="POST">
      <label>Email</label><input type="email" name="email" required>
      <label>Password</label><input type="password" name="password" required>
      <button class="primary" type="submit">Login</button>
    </form>
    <form action="{{ url_for('register') }}"><button class="alt" type="submit">Register</button></form>
  </div>
  <a class="tiny" href="{{ url_for('init_db') }}">(dev) Init DB</a>
</body>
</html>
"""

# REGISTER
register_page = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Register</title>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
  <style>
    *{box-sizing:border-box}body{font-family:'Poppins',sans-serif;background:#f2f6ff;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
    .wrap{background:#fff;border-radius:14px;box-shadow:0 10px 30px rgba(0,0,0,.1);padding:30px;max-width:440px;width:100%}
    h2{text-align:center;margin:0 0 16px}
    label{font-weight:600;display:block;margin:10px 0 6px}
    select,input{width:100%;padding:10px;border:1px solid #ccc;border-radius:8px}
    .btn{width:100%;padding:12px;border:none;border-radius:8px;color:#fff;font-weight:700;margin-top:12px;cursor:pointer}
    .go{background:#388e3c}.go:hover{background:#43a047}
    .back{background:#d84315}.back:hover{background:#e64a19}
  </style>
</head>
<body>
  <div class="wrap">
    <h2>Create Account</h2>
    {% with messages = get_flashed_messages() %}
      {% if messages %}<ul style="color:red">{% for m in messages %}<li>{{m}}</li>{% endfor %}</ul>{% endif %}
    {% endwith %}
    <form method="POST">
      <label>Role</label>
      <select name="role" required>
        <option value="patient">Patient</option>
        <option value="doctor">Doctor</option>
      </select>
      <label>Full Name</label>
      <input name="name" required pattern="^[A-Za-z][A-Za-z\\s]{1,49}$" title="Letters and spaces only">
      <label>Email</label>
      <input type="email" name="email" required>
      <label>Phone (optional)</label>
      <input name="phone">
      <label>Password</label>
      <input type="password" name="password" required>
      <div id="doctorFields" style="display:none">
        <label>Department</label>
        <select name="department_id" id="deptSelect">
          <option value="">-- Select Department --</option>
          {% for d in departments %}
          <option value="{{ d.id }}">{{ d.name }}</option>
          {% endfor %}
        </select>
        <label>Consultation Fee (₹)</label>
        <input type="number" step="0.01" name="fee" placeholder="500">
      </div>
      <button class="btn go" type="submit">Register</button>
      <button type="button" class="btn back" onclick="location.href='{{ url_for('login') }}'">Back to Login</button>
    </form>
  </div>
  <script>
    const roleSel=document.querySelector('select[name=role]');
    const docBox=document.getElementById('doctorFields');
    function toggle(){ docBox.style.display = roleSel.value==='doctor' ? 'block':'none'; }
    roleSel.addEventListener('change', toggle); toggle();
  </script>
</body>
</html>
"""

# PATIENT DASHBOARD
dashboard_patient_template = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Patient Dashboard</title>
  <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
  <style>
    body{font-family:'Roboto',sans-serif;margin:0;padding:30px;background:linear-gradient(to right,#e0f7fa,#f1f8e9)}
    .notification-settings {
      background: white;
      padding: 15px;
      border-radius: 8px;
      margin: 20px 0;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .toggle-btn {
      background: #3498db;
      color: white;
      border: none;
      padding: 8px 16px;
      border-radius: 4px;
      cursor: pointer;
      margin-top: 10px;
    }
    .toggle-btn.disabled {
      background: #95a5a6;
    }
    .notification-status {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 4px;
      margin-left: 10px;
      font-size: 14px;
    }
    .status-enabled {
      background: #2ecc71;
      color: white;
    }
    .status-disabled {
      background: #e74c3c;
      color: white;
    }
    .top{display:flex;justify-content:space-between;align-items:center}
    a.btn{background:#3498db;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none}
    a.btn:hover{background:#2980b9}
    table{width:100%;border-collapse:separate;border-spacing:0 10px;margin-top:20px}
    thead th{background:#2ecc71;color:#fff;padding:10px;border-radius:6px;text-align:left}
    tbody tr{background:#fff}
    td{padding:10px}
    .cancel{background:#e74c3c;color:#fff;border:none;padding:6px 10px;border-radius:6px;cursor:pointer}
    .pay{background:#8e44ad;color:#fff;border:none;padding:6px 10px;border-radius:6px;cursor:pointer}
    .dl{background:#16a085;color:#fff;border:none;padding:6px 10px;border-radius:6px;cursor:pointer}
    .badge{padding:3px 8px;border-radius:10px;color:#fff;font-size:12px}
    .b-paid{background:#2ecc71}.b-unpaid{background:#e67e22}.b-em{background:#c0392b}
  </style>
</head>
<body>
  <div class="top">
    <h2>Welcome {{ session.user.name }}</h2>
    <div>
      <a class="btn" href="{{ url_for('book') }}">➕ Book Appointment</a>
      <a class="btn" href="{{ url_for('logout') }}">Logout</a>
    </div>
  </div>
  {% with messages = get_flashed_messages() %}
    {% if messages %}<ul style="color:#e74c3c">{% for m in messages %}<li>{{m}}</li>{% endfor %}</ul>{% endif %}
  {% endwith %}

  <div class="notification-settings">
    <h3>Appointment Reminders</h3>
    <p>Enable notifications to receive reminders before your appointments</p>
    <button id="notificationToggle" class="toggle-btn">
      Enable Notifications
    </button>
    <span id="notificationStatus" class="notification-status"></span>
  </div>

  <script>
    // Check if the browser supports notifications
    function checkNotificationSupport() {
      if (!('Notification' in window)) {
        alert('This browser does not support notifications');
        document.getElementById('notificationToggle').disabled = true;
        return false;
      }
      return true;
    }

    // Request notification permission
    async function requestNotificationPermission() {
      if (!checkNotificationSupport()) return;
      
      try {
        const permission = await Notification.requestPermission();
        updateNotificationStatus(permission === 'granted');
        
        if (permission === 'granted') {
          // Save preference to server
          await setReminderPreference(true);
        }
      } catch (err) {
        console.error('Error requesting notification permission:', err);
        updateNotificationStatus(false);
      }
    }

    // Update UI based on notification status
    function updateNotificationStatus(enabled) {
      const toggle = document.getElementById('notificationToggle');
      const status = document.getElementById('notificationStatus');
      
      toggle.textContent = enabled ? 'Disable Notifications' : 'Enable Notifications';
      toggle.className = `toggle-btn ${enabled ? '' : 'disabled'}`;
      
      status.textContent = enabled ? 'Enabled' : 'Disabled';
      status.className = `notification-status ${enabled ? 'status-enabled' : 'status-disabled'}`;
    }

    // Save reminder preference to server
    async function setReminderPreference(enabled) {
      try {
        const response = await fetch('/set_reminder_preference', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ enabled })
        });
        
        if (!response.ok) throw new Error('Failed to save preference');
        
        const result = await response.json();
        if (!result.success) throw new Error(result.error || 'Unknown error');
        
      } catch (err) {
        console.error('Error saving reminder preference:', err);
        alert('Failed to save notification preference');
      }
    }

    // Toggle notification state
    async function toggleNotifications() {
      if (!checkNotificationSupport()) return;
      
      const currentState = Notification.permission === 'granted';
      
      if (!currentState) {
        await requestNotificationPermission();
      } else {
        await setReminderPreference(false);
        updateNotificationStatus(false);
      }
    }

    // Initialize notification status
    document.addEventListener('DOMContentLoaded', () => {
      if (checkNotificationSupport()) {
        updateNotificationStatus(Notification.permission === 'granted');
        document.getElementById('notificationToggle').addEventListener('click', toggleNotifications);
      }
    });
  </script>

  <h3>Your Appointments</h3>
  <table>
    <thead><tr><th>Doctor</th><th>Dept</th><th>Date</th><th>Time</th><th>Status</th><th>Flags</th><th>Actions</th></tr></thead>
    <tbody>
      {% for a in appointments %}
      <tr>
        <td>Dr. {{ a.doctor_name }}</td>
        <td>{{ a.department_name }}</td>
        <td>{{ a.appointment_date }}</td>
        <td>{{ a.appointment_time }}</td>
        <td>{{ a.status }}</td>
        <td>
          {% if a.emergency %}<span class="badge b-em">Emergency</span>{% endif %}
          {% if a.paid %}<span class="badge b-paid">Paid</span>{% else %}<span class="badge b-unpaid">Unpaid</span>{% endif %}
        </td>
        <td style="display:flex;gap:6px">
          {% if not a.paid %}
            <form action="{{ url_for('pay_start', appointment_id=a.id) }}" method="POST"><button class="pay">Pay ₹{{ a.fee|int }}</button></form>
          {% endif %}
          {% if a.status in ['booked','in_progress'] %}
            <form action="{{ url_for('cancel_appointment', appointment_id=a.id) }}" method="POST"><button class="cancel">Cancel</button></form>
            <form action="{{ url_for('start_call', appointment_id=a.id) }}" method="POST">
              <button class="call" style="background:#3498db;color:#fff;border:none;padding:6px 10px;border-radius:6px;cursor:pointer">📞 Call Doctor</button>
            </form>
          {% endif %}
          {% if a.prescription_id %}
            <a href="{{ url_for('download_prescription', prescription_id=a.prescription_id) }}"><button class="dl">Prescription PDF</button></a>
          {% endif %}
        </td>
      </tr>
      {% else %}
      <tr><td colspan="7">No appointments yet.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""

# DOCTOR DASHBOARD
dashboard_doctor_template = """
<!DOCTYPE html>
<html lang="en"><head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Doctor Dashboard</title>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
  <style>
    body{font-family:'Poppins',sans-serif;margin:0;padding:30px;background:#eef5ff}
    .top{display:flex;justify-content:space-between;align-items:center}
    a.btn{background:#e74c3c;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none}
    a.btn:hover{opacity:.9}
    table{width:100%;border-collapse:separate;border-spacing:0 10px;margin-top:20px}
    thead th{background:#3498db;color:#fff;padding:10px;border-radius:6px;text-align:left}
    td{padding:10px;background:#fff}
    .act button{margin-right:6px;padding:6px 10px;border:none;border-radius:6px;color:#fff;cursor:pointer}
    .inprog{background:#f39c12}.done{background:#27ae60}.pres{background:#8e44ad}
  </style>
</head>
<body>
  <div class="top">
    <h2>Dr. {{ session.user.name }}</h2>
    <div>
      <a class="btn" href="{{ url_for('set_availability') }}">Set Availability</a>
      <a class="btn" href="{{ url_for('logout') }}">Logout</a>
    </div>
  </div>

  <h3>Today & Upcoming</h3>
  <table>
    <thead><tr><th>Patient</th><th>Date</th><th>Time</th><th>Emergency</th><th>Status</th><th>Actions</th></tr></thead>
    <tbody>
      {% for a in appointments %}
      <tr>
        <td>{{ a.patient_name }}</td>
        <td>{{ a.appointment_date }}</td>
        <td>{{ a.appointment_time }}</td>
        <td>{{ 'Yes' if a.emergency else 'No' }}</td>
        <td>{{ a.status }}</td>
        <td class="act">
          {% if a.status == 'booked' %}
            <form style="display:inline" method="POST" action="{{ url_for('mark_in_progress', appointment_id=a.id) }}"><button class="inprog">In-Progress</button></form>
          {% endif %}
          {% if a.status in ['booked','in_progress'] %}
            <form style="display:inline" method="POST" action="{{ url_for('mark_done', appointment_id=a.id) }}"><button class="done">Done</button></form>
          {% endif %}
          <a href="{{ url_for('prescription_form', appointment_id=a.id) }}"><button class="pres">Prescription</button></a>
        </td>
      </tr>
      {% else %}
      <tr><td colspan="6">No appointments.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""

# ADMIN DASHBOARD (simple KPIs)
dashboard_admin_template = """
<!DOCTYPE html>
<html lang="en"><head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Admin Dashboard</title>
  <style>
    body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:0;padding:30px;background:#f7fafc}
    .top{display:flex;justify-content:space-between;align-items:center}
    .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:16px}
    .card{background:#fff;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,.06);padding:14px}
    table{width:100%;border-collapse:separate;border-spacing:0 10px;margin-top:20px}
    thead th{background:#111827;color:#fff;padding:10px;border-radius:6px;text-align:left}
    td{padding:10px;background:#fff}
    a.btn{background:#e11d48;color:#fff;padding:8px 12px;border-radius:8px;text-decoration:none}
  </style>
</head>
<body>
  <div class="top">
    <h2>Admin – {{ session.user.name }}</h2>
    <a class="btn" href="{{ url_for('logout') }}">Logout</a>
  </div>
  <div class="kpis">
    <div class="card"><b>Total Appointments</b><div style="font-size:28px">{{ kpi.total }}</div></div>
    <div class="card"><b>Today</b><div style="font-size:28px">{{ kpi.today }}</div></div>
    <div class="card"><b>Paid</b><div style="font-size:28px">{{ kpi.paid }}</div></div>
    <div class="card"><b>Emergency</b><div style="font-size:28px">{{ kpi.emergency }}</div></div>
  </div>

  <h3>By Department (this week)</h3>
  <table>
    <thead><tr><th>Department</th><th>Appointments</th></tr></thead>
    <tbody>
      {% for r in by_dept %}
      <tr><td>{{ r.department_name }}</td><td>{{ r.c }}</td></tr>
      {% else %}
      <tr><td colspan="2">No data</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <h3>Recent Activity</h3>
  <table>
    <thead><tr><th>When</th><th>User Role</th><th>User ID</th><th>Action</th></tr></thead>
    <tbody>
      {% for a in audits %}
      <tr><td>{{ a.timestamp }}</td><td>{{ a.role }}</td><td>{{ a.user_id }}</td><td>{{ a.action }}</td></tr>
      {% else %}
      <tr><td colspan="4">No logs</td></tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""

# BOOK PAGE
book_appointment_template = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Book Appointment</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
<style>
body{font-family:Nunito,system-ui,Arial;margin:0;padding:30px;background:linear-gradient(135deg,#f5f7fa,#c3cfe2)}
.card{background:#fff;border-radius:14px;box-shadow:0 8px 24px rgba(0,0,0,.08);padding:24px;max-width:520px;margin:auto}
label{font-weight:700;display:block;margin:10px 0 6px}
select,input{width:100%;padding:10px;border:1px solid #ccc;border-radius:10px}
.row{display:flex;gap:12px}.row>div{flex:1}
.btn{width:100%;padding:12px;border:none;border-radius:10px;background:#27ae60;color:#fff;font-weight:800;margin-top:10px;cursor:pointer}
.avail-table{width:100%;border-collapse:collapse;margin:12px 0}
.avail-table th, .avail-table td{border:1px solid #ccc;padding:6px;text-align:center}
</style>
</head>
<body>
<div class="card">
  <h2>Book Appointment</h2>

  {% with messages = get_flashed_messages() %}
    {% if messages %}<ul style="color:#e74c3c">{% for m in messages %}<li>{{m}}</li>{% endfor %}</ul>{% endif %}
  {% endwith %}

  <!-- Department & Doctor Selection -->
  <form method="POST">
    <label>Department</label>
    <select id="dept" name="department_id" required>
      <option value="">-- Select Department --</option>
      {% for d in departments %}
      <option value="{{ d.id }}">{{ d.name }}</option>
      {% endfor %}
    </select>

    <label>Doctor</label>
    <select id="doctor" name="doctor_id" required>
      <option value="">-- Select Doctor --</option>
    </select>

    <div class="row">
      <div>
        <label>Date</label>
        <input id="date" name="date" placeholder="YYYY-MM-DD" required>
      </div>
      <div>
        <label>Time Slot</label>
        <select id="time" name="time" required><option value="">-- Pick Time --</option></select>
      </div>
    </div>

    <label>Emergency?</label>
    <select name="emergency" required><option value="0">No</option><option value="1">Yes</option></select>
    <label>Telemedicine?</label>
    <select name="telemedicine" required><option value="0">No</option><option value="1">Yes</option></select>

    <button class="btn" type="submit">Book</button>
  </form>

  <a href="{{ url_for('dashboard_patient_view') }}">← Back to Dashboard</a>
</div>

<script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
<script>
flatpickr("#date", { dateFormat: "Y-m-d", minDate: "today" });

const dept = document.getElementById('dept');
const docSel = document.getElementById('doctor');
const dateIn = document.getElementById('date');
const timeSel = document.getElementById('time');

let doctorAvailability = {}; // store weekly availability for selected doctor

// 1️⃣ Load doctors when department changes
dept.addEventListener('change', async () => {
    console.log('Department changed to:', dept.value);
    
    docSel.innerHTML = '<option value="">-- Select Doctor --</option>';
    timeSel.innerHTML = '<option value="">-- Pick Time --</option>';
    doctorAvailability = {};

    if (!dept.value) {
        console.log('No department selected');
        return;
    }

    try {
        console.log('Fetching doctors for department:', dept.value);
        const res = await fetch(`/api/doctors?department_id=${dept.value}`);
        
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        
        const doctors = await res.json();
        console.log('Received doctors:', doctors);

        if (doctors.error) {
            console.error('API error:', doctors.error);
            return;
        }

        if (doctors.length === 0) {
            docSel.innerHTML = '<option value="">No doctors available in this department</option>';
            return;
        }

        doctors.forEach(d => {
            const opt = document.createElement('option');
            opt.value = d.id;
            opt.textContent = `Dr. ${d.name} (₹${d.fee || 0})`;
            docSel.appendChild(opt);
        });
    } catch (error) {
        console.error('Error loading doctors:', error);
        docSel.innerHTML = '<option value="">Error loading doctors</option>';
    }
});

// 2️⃣ Load doctor availability when doctor is selected
docSel.addEventListener('change', async () => {
    console.log('Doctor selected:', docSel.value);
    timeSel.innerHTML = '<option value="">-- Pick Time --</option>';
    doctorAvailability = {};

    if (!docSel.value) return;

    try {
        const res = await fetch(`/api/availability?doctor_id=${docSel.value}`);
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        const data = await res.json();
        console.log('Received availability data:', data);
        doctorAvailability = data;

        // Optional: update availability table if exists
        ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].forEach(day => {
            const startCell = document.getElementById(`${day}_start`);
            const endCell = document.getElementById(`${day}_end`);
            if (startCell && endCell) {
                startCell.textContent = data[day]?.start || '--:--';
                endCell.textContent = data[day]?.end || '--:--';
            }
        });

        if (dateIn.value) {
            loadSlots();
        }
    } catch (error) {
        console.error('Error fetching doctor availability:', error);
    }
});

// 3️⃣ Load available slots based on doctor availability & booked slots
async function loadSlots() {
    console.log('Loading slots...');
    timeSel.innerHTML = '<option value="">-- Pick Time --</option>';
    const doctorId = docSel.value;
    const date = dateIn.value;
    if (!doctorId || !date) {
        console.log('Missing doctor or date');
        return;
    }

    // Determine weekday abbreviation
    const dayAbbr = new Date(date).toLocaleDateString('en-US', { weekday: 'short' });
    console.log('Day abbreviation:', dayAbbr);

    const avail = doctorAvailability[dayAbbr];
    console.log('Availability for day:', avail);
    
    if (!avail) {
        console.log('No availability for this day');
        timeSel.innerHTML = '<option value="">Doctor not available on this day</option>';
        return;
    }

    // Generate 30-min slots
    let slots = [];
    try {
        let [h, m] = avail.start.split(':').map(Number);
        let start = new Date(date); 
        start.setHours(h, m, 0, 0);
        
        [h, m] = avail.end.split(':').map(Number);
        let end = new Date(date); 
        end.setHours(h, m, 0, 0);
        
        console.log('Generating slots from', start, 'to', end);

        while (start < end) {
            slots.push(start.toTimeString().slice(0,5));
            start.setMinutes(start.getMinutes() + 30);
        }

        // Fetch already booked slots
        const res = await fetch(`/api/booked_slots?doctor_id=${doctorId}&date=${date}`);
        const booked = await res.json();
        console.log('Booked slots:', booked);

        slots = slots.filter(s => !booked.includes(s));
        console.log('Available slots:', slots);

        if (slots.length === 0) {
            timeSel.innerHTML = '<option value="">No available slots for this day</option>';
        } else {
            slots.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s;
                opt.textContent = s;
                timeSel.appendChild(opt);
            });
        }
    } catch (error) {
        console.error('Error generating slots:', error);
        timeSel.innerHTML = '<option value="">Error loading time slots</option>';
    }
}

// 4️⃣ Refresh slots when date changes
dateIn.addEventListener('change', loadSlots);
</script>

</body>
</html>

"""

# PRESCRIPTION FORM
prescription_form_tpl = """
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Prescription</title>
  <style>
    body{font-family:system-ui,Arial;margin:0;padding:30px;background:#f5f5f5}
    .card{max-width:700px;margin:auto;background:#fff;border-radius:12px;box-shadow:0 6px 20px rgba(0,0,0,.08);padding:20px}
    textarea{width:100%;min-height:120px;border:1px solid #ccc;border-radius:8px;padding:8px}
    input,button{padding:10px;border-radius:8px;border:1px solid #ccc}
    .row{display:flex;gap:10px}
  </style>
</head>
<body>
  <div class="card">
    <h2>Prescription for Appointment #{{ appt.id }}</h2>
    <p><b>Patient:</b> {{ appt.patient_name }} | <b>Doctor:</b> Dr. {{ appt.doctor_name }}</p>
    <form method="POST">
      <label>Diagnosis</label>
      <textarea name="diagnosis" required>{{ pres.diagnosis if pres else '' }}</textarea>
      <label>Medicines</label>
      <textarea name="medicines" required>{{ pres.medicines if pres else '' }}</textarea>
      <div class="row">
        <button type="submit">Save & Generate PDF</button>
        <a href="{{ url_for('dashboard_doctor_view') }}"><button type="button">Back</button></a>
      </div>
    </form>
    {% if pres and pres.pdf_path %}
      <p>PDF ready: <a href="{{ url_for('download_prescription', prescription_id=pres.id) }}">Download</a></p>
    {% endif %}
  </div>
</body>
</html>
"""

# PAYMENT PAGE (Demo Version)
payment_page = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Demo</title>
    <style>
        body { 
            font-family: system-ui, -apple-system, sans-serif; 
            margin: 0; 
            padding: 20px;
            background: #f7fafc; 
        }
        .payment-container {
            max-width: 500px;
            margin: 40px auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            padding: 25px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .amount {
            font-size: 32px;
            font-weight: bold;
            color: #2d3748;
            text-align: center;
            margin: 20px 0;
        }
        .payment-options {
            display: grid;
            gap: 15px;
            margin: 25px 0;
        }
        .payment-btn {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            transition: transform 0.1s;
        }
        .payment-btn:active {
            transform: scale(0.98);
        }
        .upi-btn { background: #6c63ff; color: white; }
        .card-btn { background: #38a169; color: white; }
        .cash-btn { background: #718096; color: white; }
        .back-btn {
            display: inline-block;
            padding: 10px 20px;
            color: #4a5568;
            text-decoration: none;
            margin-top: 20px;
        }
        .detail-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #edf2f7;
        }
        .detail-label { color: #4a5568; }
        .detail-value { font-weight: 600; }
    </style>
</head>
<body>
    <div class="payment-container">
        <div class="header">
            <h2 style="margin:0">Payment Details</h2>
            <p style="color:#4a5568;margin:5px 0">Choose your payment method</p>
        </div>

        <div class="detail-row">
            <span class="detail-label">Doctor</span>
            <span class="detail-value">Dr. {{ doctor_name }}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Appointment ID</span>
            <span class="detail-value">#{{ appointment_id }}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Fee</span>
            <span class="detail-value">₹{{ "%.2f"|format(amount/100) }}</span>
        </div>

        <div class="payment-options">
            <!-- Demo payment buttons -->
            <form action="{{ url_for('payment_success', appointment_id=appointment_id) }}" method="POST">
                <input type="hidden" name="payment_method" value="upi">
                <button type="submit" class="payment-btn upi-btn">
                    <span>Pay with UPI</span>
                </button>
            </form>

            <form action="{{ url_for('payment_success', appointment_id=appointment_id) }}" method="POST">
                <input type="hidden" name="payment_method" value="card">
                <button type="submit" class="payment-btn card-btn">
                    <span>Pay with Card</span>
                </button>
            </form>

            <form action="{{ url_for('payment_success', appointment_id=appointment_id) }}" method="POST">
                <input type="hidden" name="payment_method" value="cash">
                <button type="submit" class="payment-btn cash-btn">
                    <span>Pay at Hospital</span>
                </button>
            </form>
        </div>

        <a href="{{ url_for('dashboard_patient_view') }}" class="back-btn">← Back to Dashboard</a>
    </div>
</body>
</html>
"""

# ---------------------------- Reminders ----------------------------
def schedule_appointment_reminders(appointment_id):
    """Schedule reminders for an appointment"""
    try:
        # Get appointment details with patient info
        appt = q("""
            SELECT a.*, d.name as doctor_name, p.id as patient_id, 
                   p.phone as patient_phone, p.reminders_enabled,
                   p.email as patient_email, p.name as patient_name,
                   DATE_FORMAT(a.appointment_date, '%Y-%m-%d') as formatted_date,
                   TIME_FORMAT(a.appointment_time, '%H:%i') as formatted_time
            FROM appointments a
            JOIN users d ON d.id = a.doctor_id
            JOIN users p ON p.id = a.patient_id
            WHERE a.id = %s
        """, (appointment_id,), fetchone=True)
        
        if not appt:
            print(f"No appointment found with ID {appointment_id}")
            return
            
        print(f"Processing reminders for appointment {appointment_id}")
        print(f"Patient reminders enabled: {appt.get('reminders_enabled')}")
            
        # Calculate reminder times
        appt_datetime = datetime.strptime(
            f"{appt['formatted_date']} {appt['formatted_time']}", 
            '%Y-%m-%d %H:%M'
        )
        reminder_2hr = appt_datetime - timedelta(hours=2)
        reminder_30min = appt_datetime - timedelta(minutes=30)
        
        # Schedule reminders if they're in the future
        now = datetime.now()
        
        def send_appointment_reminder(appointment_data, reminder_type):
            """Helper function to send both SMS and browser notifications"""
            print("\n=== Appointment Reminder Debug ===")
            print(f"Processing reminder for appointment {appointment_data['id']}")
            print(f"Reminder type: {reminder_type}")
            print(f"Patient: {appointment_data['patient_name']}")
            print(f"Doctor: Dr. {appointment_data['doctor_name']}")
            print(f"Appointment time: {appointment_data['formatted_time']}")
            print(f"Patient phone: {appointment_data.get('patient_phone', 'Not provided')}")
            
            # Send SMS if phone number is available
            if appointment_data['patient_phone']:
                try:
                    message = (f"Your appointment with Dr. {appointment_data['doctor_name']} "
                             f"is {'in 2 hours' if reminder_type == '2hour' else 'in 30 minutes'} "
                             f"at {appointment_data['formatted_time']}")
                    print("\nAttempting to send SMS...")
                    send_sms(appointment_data['patient_phone'], message)
                except Exception as e:
                    print(f"Error sending SMS: {str(e)}")
                
            # Prepare browser notification data
            notification_data = {
                'title': 'Appointment Reminder',
                'message': (f"Your appointment with Dr. {appointment_data['doctor_name']} "
                          f"is {'in 2 hours' if reminder_type == '2hour' else 'in 30 minutes'} "
                          f"at {appointment_data['formatted_time']}"),
                'appointment_id': appointment_data['id']
            }
            print("\nPrepared browser notification:")
            print(f"Title: {notification_data['title']}")
            print(f"Message: {notification_data['message']}")
            print("=== End Reminder Debug ===\n")
            
            # Send browser notification through WebSocket or Server-Sent Events
            # (This will be handled by the frontend JavaScript)
            print(f"Browser notification prepared: {notification_data}")
            return notification_data
        
        print(f"Current time: {now}")
        print(f"2-hour reminder time: {reminder_2hr}")
        print(f"30-min reminder time: {reminder_30min}")
        
        if reminder_2hr > now:
            print(f"Scheduling 2-hour reminder for appointment {appointment_id}")
            scheduler.add_job(
                func=send_appointment_reminder,
                trigger='date',
                run_date=reminder_2hr,
                kwargs={
                    'appointment_data': appt,
                    'reminder_type': '2hour'
                },
                id=f'reminder_2hr_{appointment_id}'
            )
            
        if reminder_30min > now:
            print(f"Scheduling 30-minute reminder for appointment {appointment_id}")
            scheduler.add_job(
                func=send_appointment_reminder,
                trigger='date',
                run_date=reminder_30min,
                kwargs={
                    'appointment_data': appt,
                    'reminder_type': '30min'
                },
                id=f'reminder_30min_{appointment_id}'
            )
            
    except Exception as e:
        print(f"Error scheduling reminders: {str(e)}")

@app.route('/set_reminder_preference', methods=['POST'])
@login_required
def set_reminder_preference():
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)
        
        # Update user's reminder preference
        q("UPDATE users SET reminders_enabled = %s WHERE id = %s",
          (enabled, session['user']['id']),
          commit=True)
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error setting reminder preference: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/send_reminder_sms', methods=['POST'])
@login_required
def send_reminder_sms():
    try:
        data = request.get_json()
        appointment_id = data.get('appointment_id')
        reminder_type = data.get('reminder_type')
        
        # Get appointment details with patient phone
        appt = q("""
            SELECT a.*, d.name as doctor_name, p.phone as patient_phone
            FROM appointments a
            JOIN users d ON d.id = a.doctor_id
            JOIN users p ON p.id = a.patient_id
            WHERE a.id = %s AND a.patient_id = %s
        """, (appointment_id, session['user']['id']), fetchone=True)
        
        if not appt or not appt['patient_phone']:
            return jsonify({'success': False, 'error': 'Invalid appointment or no phone number'}), 400
            
        # Prepare reminder message
        if reminder_type == '2hour':
            message = f"Reminder: Your appointment with Dr. {appt['doctor_name']} is in 2 hours at {appt['appointment_time']}"
        else:
            message = f"Reminder: Your appointment with Dr. {appt['doctor_name']} is in 30 minutes at {appt['appointment_time']}"
            
        # Send SMS
        if send_sms(appt['patient_phone'], message):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to send SMS'}), 500
            
    except Exception as e:
        print(f"Error sending reminder SMS: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ---------------------------- Application Startup ----------------------------
def start_scheduler():
    try:
        if not scheduler.running:
            print(f"Attempting to start scheduler with URL: {db_url}")
            scheduler.start()
            print("Scheduler started successfully")
    except Exception as e:
        print(f"Error starting scheduler: {str(e)}")
        print(f"Database URL components:")
        print(f"Host: {mysql_host}")
        print(f"Port: {mysql_port}")
        print(f"User: {mysql_user}")
        print(f"Database: {mysql_database}")

# Start the scheduler
start_scheduler()

# ---------------------------- Routes: Auth ----------------------------
@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        user = q("SELECT * FROM users WHERE email=%s", (email,), fetchone=True)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid credentials")
            return render_template_string(login_page)

        # Login successful
        session["user"] = user
        log_action(user["role"], user["id"], "login")

        if user["role"] == "admin":
            return redirect(url_for("dashboard_admin_view"))
        elif user["role"] == "doctor":
            return redirect(url_for("dashboard_doctor_view"))
        else:
            return redirect(url_for("dashboard_patient_view"))

    return render_template_string(login_page)

@app.route("/logout")
def logout():
    u = session.get("user")
    if u:
        log_action(u["role"], u["id"], "logout")
    session.pop("user", None)
    flash("Logged out successfully")
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    # Fetch departments for doctor role
    departments = q("SELECT * FROM departments ORDER BY name", fetchall=True) or []

    if request.method == "POST":
        role = request.form["role"]
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        phone = request.form.get("phone")
        department_id = request.form.get("department_id") if role == "doctor" else None
        fee = float(request.form.get("fee", 0)) if role == "doctor" else 0

        # Check if email already exists
        if q("SELECT id FROM users WHERE email=%s", (email,), fetchone=True):
            flash("Email already registered")
            return render_template_string(register_page, departments=departments)

        # Hash password
        pwd_hash = generate_password_hash(password)

        # Insert user
        q(
            "INSERT INTO users (role, name, email, password_hash, phone, department_id, fee) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (role, name, email, pwd_hash, phone, department_id, fee),
            commit=True
        )

        flash("Account created successfully!")
        return redirect(url_for("login"))

    # Render the template with departments
    return render_template_string(register_page, departments=departments)

#------------------ Routes: Patient ----------------------------
@app.route("/dashboard_patient")
@login_required
@role_required("patient")
def dashboard_patient_view():
    pid = session["user"]["id"]
    cur = q("""
        SELECT a.*, d.name AS doctor_name, dp.name AS department_name,
               (SELECT id FROM prescriptions p WHERE p.appointment_id=a.id LIMIT 1) AS prescription_id,
               u.fee
        FROM appointments a
        JOIN users d ON d.id=a.doctor_id
        LEFT JOIN departments dp ON dp.id=d.department_id
        LEFT JOIN users u ON u.id=a.doctor_id
        WHERE a.patient_id=%s
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    """, (pid,))
    appointments = cur.fetchall()
    return render_template_string(dashboard_patient_template, appointments=appointments)

@app.route("/book", methods=["GET","POST"])
@login_required
@role_required("patient")
def book():
    if request.method == "POST":
        pid = session["user"]["id"]
        
        try:
            # Get form data with validation
            doc_id = request.form.get("doctor_id")
            if not doc_id:
                raise ValueError("Doctor must be selected")
                
            date = request.form.get("date")
            if not date:
                raise ValueError("Date must be selected")
                
            time = request.form.get("time")
            if not time:
                raise ValueError("Time must be selected")
                
            emergency = request.form.get("emergency", "0")
            telemedicine = request.form.get("telemedicine", "0")

            print("Form data received:", {
                'patient_id': pid,
                'doctor_id': doc_id,
                'date': date,
                'time': time,
                'emergency': emergency,
                'telemedicine': telemedicine
            })

            # Get department_id from the doctor's record
            doctor = q("SELECT department_id FROM users WHERE id=%s AND role='doctor'", 
                      (doc_id,), fetchone=True)
            if not doctor:
                raise ValueError("Invalid doctor selected")
            
            dept_id = doctor['department_id']
            print("Found doctor's department_id:", dept_id)

            # Validate department_id
            if not dept_id:
                raise ValueError("Doctor has no associated department")

            # Prevent double booking
            dup = q("SELECT id FROM appointments WHERE doctor_id=%s AND appointment_date=%s AND appointment_time=%s AND status!='cancelled'",
                    (doc_id, date, time), fetchall=True)
            if dup:
                raise ValueError("Slot already booked, please pick another")

            # Insert appointment
            insert_sql = """INSERT INTO appointments 
                (patient_id, doctor_id, department_id, appointment_date, appointment_time, emergency, status"""
            values_sql = """ VALUES (%s,%s,%s,%s,%s,%s,'booked'"""
            params = [pid, doc_id, dept_id, date, time, emergency]

            # Add telemedicine if column exists
            try:
                cur = db.cursor()
                cur.execute("SHOW COLUMNS FROM appointments LIKE 'telemedicine'")
                if cur.fetchone():
                    insert_sql += ", telemedicine"
                    values_sql += ",%s"
                    params.append(telemedicine)
            except Exception as e:
                print("Error checking telemedicine column:", str(e))

            # Complete the SQL
            insert_sql += ")" + values_sql + ")"
            
            # Execute the insert and get the appointment ID
            q(insert_sql, params, commit=True)
            appointment_id = q("SELECT LAST_INSERT_ID()", fetchone=True)['LAST_INSERT_ID()']
            
            # Schedule reminders for the new appointment
            try:
                schedule_appointment_reminders(appointment_id)
                print(f"Reminders scheduled for appointment {appointment_id}")
            except Exception as e:
                print(f"Error scheduling reminders: {str(e)}")
            
            flash("Appointment booked successfully")
            return redirect(url_for("dashboard_patient_view"))
            
        except ValueError as e:
            flash(str(e))
            return redirect(url_for("book"))
        except Exception as e:
            print("Database error:", str(e))
            flash(f"Booking error: {str(e)}")
            return redirect(url_for("book"))

        # Prevent double booking
        dup = q("SELECT id FROM appointments WHERE doctor_id=%s AND appointment_date=%s AND appointment_time=%s AND status!='cancelled'",
                (doc_id, date, time), fetchall=True)
        if dup:
            flash("Slot already booked, please pick another.")
            return redirect(url_for("book"))

        try:
            # Debug prints
            print("Booking appointment with values:", {
                'patient_id': pid,
                'doctor_id': doc_id,
                'department_id': dept_id,
                'date': date,
                'time': time,
                'emergency': emergency,
                'telemedicine': telemedicine
            })
            
            # Insert appointment with commit
            q("""INSERT INTO appointments 
                (patient_id, doctor_id, department_id, appointment_date, appointment_time, emergency, telemedicine, status) 
                VALUES (%s,%s,%s,%s,%s,%s,%s,'booked')""",
              (pid, doc_id, dept_id, date, time, emergency, telemedicine), commit=True)
            flash("Appointment booked successfully.")
            return redirect(url_for("dashboard_patient_view"))
        except Exception as e:
            error_msg = str(e)
            print("Error booking appointment:", error_msg)
            flash(f"Error booking appointment: {error_msg}")
            return redirect(url_for("book"))

    departments = q("SELECT id,name FROM departments ORDER BY name")
    return render_template_string(book_appointment_template, departments=departments)

@app.route("/cancel/<int:appointment_id>", methods=["POST"])
@login_required
@role_required("patient")
def cancel_appointment(appointment_id):
    pid = session["user"]["id"]
    q("UPDATE appointments SET status='cancelled' WHERE id=%s AND patient_id=%s", (appointment_id, pid))
    log_action("patient", pid, f"Cancelled appointment {appointment_id}")
    flash("Appointment cancelled.")
    return redirect(url_for("dashboard_patient_view"))

# ---------------------------- Phone Call ----------------------------
@app.route("/start_call/<int:appointment_id>", methods=["POST"])
@login_required
@role_required("patient")
def start_call(appointment_id):
    # Get appointment and doctor details
    appt = q("""
        SELECT a.*, d.name as doctor_name, d.phone as doctor_phone
        FROM appointments a 
        JOIN users d ON d.id = a.doctor_id 
        WHERE a.id=%s AND a.patient_id=%s 
        AND a.status IN ('booked', 'in_progress')
    """, (appointment_id, session["user"]["id"]), fetchone=True)
    
    if not appt:
        flash("Invalid appointment")
        return redirect(url_for("dashboard_patient_view"))
    
    # Show doctor's contact info
    return render_template_string(phone_call_template, 
        doctor_name=appt["doctor_name"],
        doctor_phone=appt["doctor_phone"],
        appointment_id=appointment_id
    )

# ---------------------------- Routes: Doctor ----------------------------
@app.route("/dashboard_doctor")
@login_required
@role_required("doctor")
def dashboard_doctor_view():
    did = session["user"]["id"]
    cur = q("""
        SELECT a.*, p.name AS patient_name, d.name AS doctor_name
        FROM appointments a
        JOIN users p ON p.id=a.patient_id
        JOIN users d ON d.id=a.doctor_id
        WHERE a.doctor_id=%s AND a.status IN ('booked','in_progress')
        ORDER BY a.appointment_date, a.appointment_time
    """, (did,))
    appointments = cur.fetchall()
    return render_template_string(dashboard_doctor_template, appointments=appointments)

@app.route("/doctor/availability", methods=["GET","POST"])
@login_required
@role_required("doctor")
def set_availability():
    did = session["user"]["id"]
    if request.method == "POST":
        try:
            print("Received POST request for doctor availability")
            print("Form data:", request.form)
            
            # Delete existing availability
            q("DELETE FROM doctor_availability WHERE doctor_id=%s", (did,), commit=True)
            print("Deleted existing availability for doctor", did)
            
            items = []
            for day in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
                st = request.form.get(f"{day}_start")
                et = request.form.get(f"{day}_end")
                print(f"Day {day}: start={st}, end={et}")
                
                if st and et:  # Only add if both start and end times are provided
                    try:
                        # Convert to HH:MM:SS format
                        st = datetime.strptime(st, "%H:%M").strftime("%H:%M:00")
                        et = datetime.strptime(et, "%H:%M").strftime("%H:%M:00")
                        items.append((did, day, st, et))
                        print(f"Added slot for {day}: {st} - {et}")
                    except ValueError as e:
                        print(f"Error parsing time for {day}:", e)
                        flash(f"Invalid time format for {day}")
                        return redirect(url_for("set_availability"))
            
            if items:
                try:
                    print("Inserting availability items:", items)
                    q("INSERT INTO doctor_availability (doctor_id,day_of_week,start_time,end_time) VALUES (%s,%s,%s,%s)", 
                      items, many=True, commit=True)
                    print("Successfully inserted availability")
                    flash("Availability updated successfully.")
                except Exception as e:
                    print("Database error:", e)
                    flash("Error saving availability. Please try again.")
                    return redirect(url_for("set_availability"))
            else:
                print("No availability items to insert")
                flash("Please set at least one day's availability.")
            
            print("Redirecting to dashboard")
            return redirect(url_for("dashboard_doctor_view"))
            
        except Exception as e:
            print("Unexpected error:", e)
            flash("An error occurred. Please try again.")
            return redirect(url_for("set_availability"))

    # Get current availability
    current = q("SELECT day_of_week, TIME_FORMAT(start_time, '%H:%i') as start_time, TIME_FORMAT(end_time, '%H:%i') as end_time FROM doctor_availability WHERE doctor_id=%s", (did,), fetchall=True) or []
    availability = {row['day_of_week']: row for row in current}

    form_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Set Availability</title>
        <style>
            body { font-family: system-ui, -apple-system, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; background: #f5f7fa; }
            .container { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
            h3 { margin-top: 0; color: #2c3e50; }
            .day-row { display: flex; align-items: center; margin: 15px 0; padding: 10px; border-radius: 8px; background: #f8fafc; }
            .day-label { flex: 0 0 80px; font-weight: bold; color: #2c3e50; }
            .time-inputs { flex: 1; display: flex; align-items: center; gap: 10px; }
            input[type="time"] { padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
            .btn-group { margin-top: 20px; display: flex; gap: 10px; }
            .btn { padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; }
            .btn-save { background: #2563eb; color: white; }
            .btn-back { background: #64748b; color: white; }
            .error { color: #dc2626; margin: 5px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h3>Set Weekly Availability</h3>
            {% with messages = get_flashed_messages() %}
                {% if messages %}
                    {% for msg in messages %}
                        <div class="error">{{ msg }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            <form method="POST" action="{{ url_for('set_availability') }}" id="availForm">
                {% for d in days %}
                <div class="day-row">
                    <div class="day-label">{{ d }}</div>
                    <div class="time-inputs">
                        <input name="{{ d }}_start" type="time" 
                               value="{{ availability[d].start_time if d in availability else '' }}"
                               id="{{ d }}_start">
                        <span>to</span>
                        <input name="{{ d }}_end" type="time" 
                               value="{{ availability[d].end_time if d in availability else '' }}"
                               id="{{ d }}_end">
                    </div>
                </div>
                {% endfor %}
                <div class="btn-group">
                    <button type="submit" class="btn btn-save">Save Changes</button>
                    <a href="{{ url_for('dashboard_doctor_view') }}" class="btn btn-back">Back</a>
                </div>
            </form>
        </div>
        <script>
        const form = document.getElementById('availForm');
        form.onsubmit = function(e) {
            e.preventDefault(); // Prevent default submission
            let valid = false;
            let formData = new FormData(form);
            
            document.querySelectorAll('.day-row').forEach(row => {
                const day = row.querySelector('.day-label').textContent.trim();
                const start = row.querySelector('input[type="time"]:first-child').value;
                const end = row.querySelector('input[type="time"]:last-child').value;
                
                console.log(`Checking ${day}: ${start} - ${end}`);
                
                if (start && end) {
                    valid = true;
                    if (start >= end) {
                        alert('End time must be after start time for ' + day);
                        return;
                    }
                }
            });
            
            if (!valid) {
                alert('Please set availability for at least one day');
                return;
            }
            
            // If validation passes, submit the form
            console.log('Submitting form...');
            form.submit();
        };
        </script>
    </body>
    </html>
    """
    return render_template_string(form_html, days=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"], availability=availability)

@app.route("/doctor/in-progress/<int:appointment_id>", methods=["POST"])
@login_required
@role_required("doctor")
def mark_in_progress(appointment_id):
    did = session["user"]["id"]
    q("UPDATE appointments SET status='in_progress' WHERE id=%s AND doctor_id=%s", (appointment_id, did))
    log_action("doctor", did, f"Marked in_progress {appointment_id}")
    return redirect(url_for("dashboard_doctor_view"))

@app.route("/doctor/done/<int:appointment_id>", methods=["POST"])
@login_required
@role_required("doctor")
def mark_done(appointment_id):
    did = session["user"]["id"]
    q("UPDATE appointments SET status='done', finalized=TRUE WHERE id=%s AND doctor_id=%s", (appointment_id, did))
    log_action("doctor", did, f"Marked done {appointment_id}")
    # Notify patient
    ap = q("SELECT p.email,p.name,d.name AS dname, a.appointment_date, a.appointment_time "
           "FROM appointments a JOIN users p ON p.id=a.patient_id JOIN users d ON d.id=a.doctor_id WHERE a.id=%s", (appointment_id,)).fetchone()
    if ap:
        send_email(ap["email"], "Appointment Completed",
                   f"Hi {ap['name']}, your appointment with Dr. {ap['dname']} on {ap['appointment_date']} {ap['appointment_time']} is marked done.")
    return redirect(url_for("dashboard_doctor_view"))

# ---------------------------- EMR: Prescriptions ----------------------------
@app.route("/doctor/prescription/<int:appointment_id>", methods=["GET","POST"])
@login_required
@role_required("doctor")
def prescription_form(appointment_id):
    did = session["user"]["id"]
    ap = q("""SELECT a.*, p.name AS patient_name, d.name AS doctor_name
              FROM appointments a
              JOIN users p ON p.id=a.patient_id
              JOIN users d ON d.id=a.doctor_id
              WHERE a.id=%s AND a.doctor_id=%s""", (appointment_id, did)).fetchone()
    if not ap: 
        flash("Not found")
        return redirect(url_for("dashboard_doctor_view"))

    pres = q("SELECT * FROM prescriptions WHERE appointment_id=%s", (appointment_id,)).fetchone()

    if request.method == "POST":
        diagnosis = request.form["diagnosis"]
        medicines = request.form["medicines"]
        if pres:
            q("UPDATE prescriptions SET diagnosis=%s, medicines=%s WHERE id=%s", (diagnosis, medicines, pres["id"]))
            pres_id = pres["id"]
        else:
            q("INSERT INTO prescriptions (appointment_id,diagnosis,medicines) VALUES (%s,%s,%s)", (appointment_id, diagnosis, medicines))
            pres_id = q("SELECT LAST_INSERT_ID() AS id").fetchone()["id"]

        # Generate PDF
        pdf_path = None
        if REPORTLAB_AVAILABLE:
            try:
                # Create prescriptions directory if it doesn't exist
                prescriptions_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prescriptions')
                if not os.path.exists(prescriptions_dir):
                    os.makedirs(prescriptions_dir)
                
                pdf_path = os.path.join(prescriptions_dir, f"prescription_{pres_id}.pdf")
                c = canvas.Canvas(pdf_path, pagesize=A4)
                width, height = A4
                
                # Add header
                c.setFont("Helvetica-Bold", 16)
                c.drawString(40, height-60, "Prescription")
                
                # Add patient and doctor info
                c.setFont("Helvetica", 12)
                c.drawString(40, height-90, f"Patient: {ap['patient_name']}")
                c.drawString(40, height-110, f"Doctor: Dr. {ap['doctor_name']}")
                c.drawString(40, height-130, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                
                # Add diagnosis
                c.drawString(40, height-160, "Diagnosis:")
                text = c.beginText(40, height-180)
                for line in diagnosis.splitlines():
                    text.textLine(line)
                c.drawText(text)
                
                # Add medicines
                c.drawString(40, height-320, "Medicines:")
                text2 = c.beginText(40, height-340)
                for line in medicines.splitlines():
                    text2.textLine(line)
                c.drawText(text2)
                
                c.showPage()
                c.save()
                print(f"PDF saved to: {pdf_path}")
            except Exception as e:
                print(f"Error generating PDF: {str(e)}")
                pdf_path = None

        if pdf_path:
            q("UPDATE prescriptions SET pdf_path=%s WHERE id=%s", (pdf_path, pres_id))

        flash("Prescription saved.")
        return redirect(url_for("dashboard_doctor_view"))

    return render_template_string(prescription_form_tpl, appt=ap, pres=pres)

@app.route("/prescriptions/<int:prescription_id>/download")
@login_required
def download_prescription(prescription_id):
    try:
        # Get prescription record
        pres = q("SELECT p.*, a.patient_id, a.doctor_id FROM prescriptions p JOIN appointments a ON a.id=p.appointment_id WHERE p.id=%s", 
                 (prescription_id,), fetchone=True)
        
        if not pres:
            flash("Prescription not found.")
            return redirect(request.referrer or url_for("home"))
        
        # Security check - only allow patient or their doctor to download
        if not (session["user"]["id"] == pres["patient_id"] or 
                session["user"]["id"] == pres["doctor_id"] or 
                session["user"]["role"] == "admin"):
            flash("Unauthorized to access this prescription.")
            return redirect(url_for("home"))
        
        # Check if PDF exists
        if not pres.get("pdf_path"):
            flash("PDF path not found in database.")
            return redirect(request.referrer or url_for("home"))
        
        # Get absolute path
        prescriptions_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prescriptions')
        pdf_path = os.path.join(prescriptions_dir, os.path.basename(pres["pdf_path"]))
        
        if not os.path.exists(pdf_path):
            flash("PDF file not found on server.")
            return redirect(request.referrer or url_for("home"))
            
        return send_file(pdf_path, 
                        as_attachment=True, 
                        download_name=f"prescription_{prescription_id}.pdf",
                        mimetype='application/pdf')
                        
    except Exception as e:
        print(f"Error downloading prescription: {str(e)}")
        flash("Error downloading prescription.")
        return redirect(request.referrer or url_for("home"))

# ---------------------------- Admin ----------------------------
@app.route("/dashboard_admin")
@login_required
@role_required("admin")
def dashboard_admin_view():
    kpi = {
        "total": q("SELECT COUNT(*) c FROM appointments").fetchone()["c"],
        "today": q("SELECT COUNT(*) c FROM appointments WHERE appointment_date=%s", (datetime.now().date(),)).fetchone()["c"],
        "paid": q("SELECT COUNT(*) c FROM appointments WHERE paid=1").fetchone()["c"],
        "emergency": q("SELECT COUNT(*) c FROM appointments WHERE emergency=1").fetchone()["c"],
    }
    by_dept = q("""
        SELECT dpt.name AS department_name, COUNT(*) c
        FROM appointments a
        JOIN users doc ON doc.id=a.doctor_id
        JOIN departments dpt ON dpt.id=doc.department_id
        WHERE a.appointment_date BETWEEN DATE_SUB(CURDATE(), INTERVAL 7 DAY) AND CURDATE()
        GROUP BY dpt.name
        ORDER BY c DESC
    """).fetchall()
    audits = q("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 20").fetchall()
    return render_template_string(dashboard_admin_template, kpi=kpi, by_dept=by_dept, audits=audits)

# ---------------------------- Application Startup ----------------------------
# Note: Scheduler is started right after initialization
# ---------------------------- API for booking workflow ----------------------------
@app.route("/api/doctors")
def api_doctors():
    try:
        department_id = request.args.get("department_id")
        print(f"Fetching doctors for department_id: {department_id}")
        
        if not department_id:
            print("No department_id provided")
            return jsonify([])

        query = """
            SELECT u.id, u.name, u.fee 
            FROM users u 
            WHERE u.role='doctor' 
            AND u.department_id=%s 
            ORDER BY u.name
        """
        print(f"Executing query: {query} with department_id={department_id}")
        
        doctors = q(query, (department_id,), fetchall=True) or []
        
        print(f"Found {len(doctors)} doctors:", doctors)
        response = jsonify(doctors)
        print(f"Sending response: {response.data}")
        return response
    except Exception as e:
        print(f"Error in api_doctors: {str(e)}")
        db.ping(reconnect=True)  # Try to reconnect if connection lost
        return jsonify({"error": str(e)}), 500

@app.route("/api/availability")
def api_availability():
    doctor_id = request.args.get("doctor_id")
    rows = q(
        "SELECT day_of_week, TIME_FORMAT(start_time, '%H:%i') as start_time, TIME_FORMAT(end_time, '%H:%i') as end_time FROM doctor_availability WHERE doctor_id=%s",
        (doctor_id,),
        fetchall=True
    ) or []

    availability = {}
    for r in rows:
        availability[r['day_of_week']] = {
            'start': r['start_time'],
            'end': r['end_time']
        }
        print(f"Added availability for {r['day_of_week']}: {r['start_time']} - {r['end_time']}")
    
    print("Final availability data:", availability)
    return jsonify(availability)

@app.route("/api/booked_slots")
def api_booked_slots():
    doctor_id = request.args.get("doctor_id")
    date = request.args.get("date")
    rows = q(
        "SELECT appointment_time FROM appointments WHERE doctor_id=%s AND appointment_date=%s AND status!='cancelled'",
        (doctor_id, date),
        fetchall=True
    ) or []

    slots = [r['appointment_time'].strftime("%H:%M") for r in rows]
    return jsonify(slots)

# This is handled by the main api_doctors route above

@app.route("/api/slots")
@login_required
def api_slots():
    doctor_id = request.args.get("doctor_id")
    date_str = request.args.get("date")
    if not doctor_id or not date_str:
        return jsonify([])

    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    day_abbr = date_obj.strftime("%a")

    avail = q("SELECT start_time,end_time FROM doctor_availability WHERE doctor_id=%s AND day_of_week=%s",
              (doctor_id, day_abbr))
    if not avail:
        return jsonify([])

    start = datetime.combine(date_obj, avail[0]["start_time"])
    end = datetime.combine(date_obj, avail[0]["end_time"])
    slots = []
    while start + timedelta(minutes=30) <= end:
        slots.append(start.strftime("%H:%M"))
        start += timedelta(minutes=30)

    booked = q("SELECT appointment_time FROM appointments WHERE doctor_id=%s AND appointment_date=%s AND status!='cancelled'",
               (doctor_id, date_str))
    booked_set = {b["appointment_time"].strftime("%H:%M") for b in booked}
    available = [s for s in slots if s not in booked_set]
    return jsonify(available)

# ---------------------------- Payments (Demo Version) ----------------------------
@app.route("/pay/<int:appointment_id>", methods=["POST"])
@login_required
@role_required("patient")
def pay_start(appointment_id):
    try:
        # Get appointment details
        ap = q("""SELECT a.*, d.name AS doctor_name, d.fee
                  FROM appointments a JOIN users d ON d.id=a.doctor_id
                  WHERE a.id=%s AND a.patient_id=%s""", 
                (appointment_id, session["user"]["id"])).fetchone()
                
        if not ap:
            flash("Appointment not found.")
            return redirect(url_for("dashboard_patient_view"))

        # Check if already paid
        if ap.get("paid"):
            flash("This appointment has already been paid for.")
            return redirect(url_for("dashboard_patient_view"))

        # Validate fee
        if not ap["fee"]:
            flash("No fee is set for this appointment.")
            return redirect(url_for("dashboard_patient_view"))

        amount = int(ap["fee"] * 100)  # Convert to paise/cents
            
        return render_template_string(payment_page, 
                                   doctor_name=ap["doctor_name"], 
                                   amount=amount,
                                   appointment_id=appointment_id)
            
    except Exception as e:
        print(f"Payment initialization error: {str(e)}")
        flash("Error initializing payment. Please try again later.")
        return redirect(url_for("dashboard_patient_view"))

@app.route("/payment-success/<int:appointment_id>", methods=["POST"])
@login_required
@role_required("patient")
def payment_success(appointment_id):
    try:
        # Get payment method from form
        payment_method = request.form.get('payment_method', 'unknown')
        
        # Update appointment as paid
        q("""UPDATE appointments 
            SET paid = CASE 
                    WHEN %s = 'cash' THEN 0 
                    ELSE 1 
                END,
                payment_method = %s,
                payment_date = NOW() 
            WHERE id=%s AND patient_id=%s""", 
          (payment_method, payment_method, appointment_id, session["user"]["id"]))
        
        # Show appropriate message based on payment method
        if payment_method == 'cash':
            flash("Payment pending. Please pay at the hospital.")
        else:
            flash(f"Payment successful via {payment_method}!")
            
        log_action("patient", session["user"]["id"], f"Payment processed for appointment {appointment_id} via {payment_method}")
        return redirect(url_for("dashboard_patient_view"))
        
    except Exception as e:
        print(f"Payment processing error: {str(e)}")
        flash("Error processing payment. Please try again.")
        return redirect(url_for("dashboard_patient_view"))

# ---------------------------- Admin finalize (optional) ----------------------------
@app.route("/admin/finalize/<int:appointment_id>", methods=["POST"])
@login_required
@role_required("admin")
def finalize_appointment(appointment_id):
    q("UPDATE appointments SET finalized=TRUE WHERE id=%s", (appointment_id,))
    flash("Finalized.")
    return redirect(url_for("dashboard_admin_view"))

@app.route("/register_doctor", methods=["GET", "POST"])
def register_doctor():
    # Fetch all departments from DB
    departments = q("SELECT * FROM departments ORDER BY name", fetchall=True) or []

    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        phone = request.form["phone"].strip()
        department_id = request.form["department_id"]
        fee = request.form.get("fee", 0)

        # Check if email already exists
        if q("SELECT id FROM users WHERE email=%s", (email,), fetchone=True):
            flash("Email already registered.")
            return render_template_string(register_page, departments=departments)

        # Hash password
        pwd_hash = generate_password_hash(password)

        # Insert doctor into users table
        q(
            "INSERT INTO users (role, name, email, password_hash, phone, department_id, fee) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("doctor", name, email, pwd_hash, phone, department_id, fee),
            commit=True
        )

        flash("Doctor registered successfully!")
        return redirect(url_for("login"))

    # Render form with departments
    return render_template_string(register_page, departments=departments)

@app.route("/get_doctors/<int:dept_id>")
def get_doctors(dept_id):
    # Fetch only doctors who are registered in this department
    doctors = q(
        "SELECT id, name FROM users WHERE role='doctor' AND department_id=%s ORDER BY name",
        (dept_id,),
        fetchall=True
    ) or []

    return jsonify(doctors)

# ---------------------------- Run ----------------------------
if __name__ == "__main__":
    app.run(debug=True)
