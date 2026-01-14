import os
from datetime import datetime, timedelta, time as dt_time
import random, string, time, hashlib
from functools import wraps
from urllib.parse import quote_plus

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from flask import (
    Flask, request, session, redirect, url_for, flash,
    render_template, render_template_string, jsonify, send_file
)
from dotenv import load_dotenv
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash

import pymysql
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
mysql_user = os.getenv("MYSQL_USER", "avnadmin")
mysql_password = os.getenv("MYSQL_PASSWORD", "AVNS_olPiVJTGPWoGFJSMGPc")
mysql_host = os.getenv("MYSQL_HOST", "mysql-18ab8524-hospitalapp.k.aivencloud.com")
mysql_port = os.getenv("MYSQL_PORT", "22582")
mysql_database = os.getenv("MYSQL_DATABASE", "defaultdb")

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
        'default': ThreadPoolExecutor(max_workers=5)  
    },
    job_defaults={
        'coalesce': True,  
        'max_instances': 1, 
        'misfire_grace_time': 3600  
    }
)

try:
    from flask_mail import Mail, Message
    MAIL_AVAILABLE = True
except Exception:
    MAIL_AVAILABLE = False

try:
    import requests
except ImportError:
    pass

try:
    from gen_pdf import generate_prescription
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

load_dotenv()

app = Flask(__name__)

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
db_config = {
    "host": os.getenv("MYSQL_HOST"),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "port": int(os.getenv("MYSQL_PORT")),
    "ssl_disabled": False
}

db = mysql.connector.connect(**db_config)

def q(query, params=None, fetchone=False, fetchall=False, many=False, commit=False):
    global db
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            if not db.is_connected():
                print("Reconnecting to database...")
                db = mysql.connector.connect(**db_config)
            
            cur = db.cursor(dictionary=True)
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
            
        except mysql.connector.Error as err:
            retry_count += 1
            print(f"Database error: {err}, attempt {retry_count} of {max_retries}")
            if retry_count == max_retries:
                raise
            time.sleep(1)  
            try:
                db = mysql.connector.connect(**db_config)
            except:
                continue

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


def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        session.permanent = True
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

def weekday_name(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
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
    # Run your seed SQL if any
    for query, data in SEED_SQL:
        try:
            q(query, data, many=True, commit=True)
        except Exception as e:
            print(f"Seed insert skipped: {e}")

    # Delete old admin users (optional, if you want a clean reset)
    try:
        q("DELETE FROM users WHERE role='admin'", commit=True)
        print("Old admin users deleted successfully.")
    except Exception as e:
        print(f"Error deleting old admins: {e}")

    # Check if admin already exists
    user = q(
        "SELECT id FROM users WHERE email=%s LIMIT 1",
        ("PankajaChavan@1965.com",),
        fetchone=True
    )

    if not user:
        pwd_hash = generate_password_hash("Pankaja1965")
        try:
            q(
                "INSERT INTO users (role, name, email, password_hash) VALUES (%s, %s, %s, %s)",
                ("admin", "Pankaja", "PankajaChavan@1965.com", pwd_hash),
                commit=True
            )
            flash("Default admin created: PankajaChavan@1965.com / your password")
        except Exception as e:
            print(f"Error creating admin: {e}")
            flash("Failed to create admin. Check logs.")
    else:
        flash("Admin already exists. Login with PankajaChavan@1965.com / your password")

    return redirect(url_for("login"))

def schedule_appointment_reminders(appointment_id):
    try:
        appt = q("""
            SELECT a.*, d.name as doctor_name, p.id as patient_id, 
                   p.reminders_enabled,
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
         
        appt_datetime = datetime.strptime(
            appt['formatted_date'] + ' ' + appt['formatted_time'], 
            '%Y-%m-%d %H:%M'
        )
        reminder_2hr = appt_datetime - timedelta(hours=2)
        reminder_30min = appt_datetime - timedelta(minutes=30)
        
        now = datetime.now()
        
        def send_appointment_reminder(appointment_data, reminder_type):

            print("\n=== Appointment Reminder Debug ===")
            print(f"Processing reminder for appointment {appointment_data['id']}")
            print(f"Reminder type: {reminder_type}")
            print(f"Patient: {appointment_data['patient_name']}")
            print(f"Doctor: Dr. {appointment_data['doctor_name']}")
            print(f"Appointment time: {appointment_data['formatted_time']}")
            print(f"Patient email: {appointment_data['patient_email']}")
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

        appt = q("""
            SELECT a.*, d.name as doctor_name, p.phone as patient_phone
            FROM appointments a
            JOIN users d ON d.id = a.doctor_id
            JOIN users p ON p.id = a.patient_id
            WHERE a.id = %s AND a.patient_id = %s
        """, 
        (appointment_id, session['user']['id']), fetchone=True)
        
        if not appt or not appt['patient_phone']:
            return jsonify({'success': False, 'error': 'Invalid appointment or no phone number'}), 400
        if reminder_type not in ['2hour', '30min']:
            return jsonify({'success': False, 'error': 'Invalid reminder type'}), 400
        if reminder_type == '2hour':
            message = f"Reminder: Your appointment with Dr. {appt['doctor_name']} is in 2 hours at {appt['appointment_time']}"
        else:
            message = f"Reminder: Your appointment with Dr. {appt['doctor_name']} is in 30 minutes at {appt['appointment_time']}"
        print(f"Sending SMS to {appt['patient_phone']}: {message}")
        if send_sms(appt['patient_phone'], message):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to send SMS'}), 500
            
    except Exception as e:
        print(f"Error sending reminder SMS: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def start_scheduler():
    global scheduler
    
    try:
        if scheduler and scheduler.running:
            print("Scheduler already running")
            return
            
        print(f"Attempting to start scheduler with URL: {db_url}")
        scheduler.start(paused=True)  
        try:
            scheduler._jobstores['default'].get_due_jobs(now=datetime.now())
            scheduler.resume()  
            print("Scheduler started successfully")
        except Exception as db_err:
            print(f"Scheduler database error: {db_err}")
            scheduler.shutdown()
            scheduler = None  
            
    except Exception as e:
        print(f"Error starting scheduler: {str(e)}")
        scheduler = None 

start_scheduler()

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
            return render_template('login.html')

        session["user"] = user
        log_action(user["role"], user["id"], "login")

        if user["role"] == "admin":
            return redirect(url_for("dashboard_admin_view"))
        elif user["role"] == "doctor":
            return redirect(url_for("dashboard_doctor_view"))
        else:
            return redirect(url_for("dashboard_patient_view"))

    return render_template('login.html')

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
    
    departments = q("SELECT * FROM departments ORDER BY name", fetchall=True) or []

    if request.method == "POST":
        role = request.form["role"]
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        department_id = request.form.get("department_id") if role == "doctor" else None
        fee = float(request.form.get("fee", 0)) if role == "doctor" else 0

        if q("SELECT id FROM users WHERE email=%s", (email,), fetchone=True):
            flash("Email already registered")
            return render_template('register.html', departments=departments)

        pwd_hash = generate_password_hash(password)

        q(
            "INSERT INTO users (role, name, email, password_hash, department_id, fee) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (role, name, email, pwd_hash, department_id, fee),
            commit=True
        )

        flash("Account created successfully!")
        return redirect(url_for("login"))

    return render_template('register.html', departments=departments)

@app.route("/dashboard_patient")
@login_required
@role_required("patient")
def dashboard_patient_view():
    pid = session["user"]["id"]

    cur = q("""
        SELECT a.*, d.name AS doctor_name, dp.name AS department_name,
               (SELECT id FROM prescriptions p WHERE p.appointment_id=a.id LIMIT 1) AS prescription_id,
               u.fee, a.telemedicine
        FROM appointments a
        JOIN users d ON d.id=a.doctor_id
        LEFT JOIN departments dp ON dp.id=d.department_id
        LEFT JOIN users u ON u.id=a.doctor_id
        WHERE a.patient_id=%s AND a.deleted=0
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    """, (pid,))

    appointments = cur.fetchall()
    return render_template('dashboard_patient.html', appointments=appointments)

def cleanup_old_cancelled():
    try:
        q("""
            DELETE FROM appointments
            WHERE status='cancelled'
              AND cancelled_at < NOW() - INTERVAL 30 DAY
        """, commit=True)
        print("Auto-clean: Old cancelled appointments removed")
    except Exception as e:
        print("Cleanup error:", e)

if scheduler:
    scheduler.add_job(
        cleanup_old_cancelled,
        trigger="cron",
        hour=2,   # runs at 2 AM daily
        id="cleanup_cancelled_jobs",
        replace_existing=True
    )

@app.route("/book", methods=["GET","POST"])
@login_required
@role_required("patient")
def book():
    if request.method == "POST":
        pid = session["user"]["id"]

        try:
            
            doc_id = request.form.get("doctor_id")
            date = request.form.get("date")
            time = request.form.get("time")
            emergency = request.form.get("emergency", "0")
            telemedicine = request.form.get("telemedicine", "0")

            if not doc_id or not date or not time:
                raise ValueError("Doctor, date and time are required")

            print("Form data received:", {
                'patient_id': pid,
                'doctor_id': doc_id,
                'date': date,
                'time': time,
                'emergency': emergency,
                'telemedicine': telemedicine
            })

            doctor = q(
                "SELECT department_id FROM users WHERE id=%s AND role='doctor'",
                (doc_id,), fetchone=True
            )
            if not doctor or not doctor['department_id']:
                raise ValueError("Invalid doctor or no department assigned")

            dept_id = doctor['department_id']
            print("Found doctor's department_id:", dept_id)
            appt_date = datetime.strptime(date, "%Y-%m-%d").date()
            dup = q("""SELECT id FROM appointments 
                       WHERE doctor_id=%s AND appointment_date=%s 
                       AND appointment_time=%s AND status!='cancelled'""",
                    (doc_id, date, time), fetchall=True)
            if dup:
                raise ValueError("Slot already booked, please pick another")

            q("""INSERT INTO appointments 
                    (patient_id, doctor_id, department_id, appointment_date, appointment_time, emergency, telemedicine, status) 
                 VALUES (%s,%s,%s,%s,%s,%s,%s,'booked')""",
              (pid, doc_id, dept_id, date, time, emergency, telemedicine),
              commit=True)

            appointment_id = q("SELECT LAST_INSERT_ID()", fetchone=True)['LAST_INSERT_ID()']

            try:
                schedule_appointment_reminders(appointment_id)
                print(f"Reminders scheduled for appointment {appointment_id}")
            except Exception as e:
                print(f"Error scheduling reminders: {e}")

            flash("Appointment booked successfully")
            return redirect(url_for("dashboard_patient_view"))

        except ValueError as e:
            flash(str(e))
            return redirect(url_for("book"))
        except Exception as e:
            print("Booking error:", str(e))
            flash("Booking error: " + str(e))
            return redirect(url_for("book"))

    departments = q("SELECT id,name FROM departments ORDER BY name", fetchall=True)
    return render_template('book_appointment.html', departments=departments)

@app.route("/cancel/<int:appointment_id>", methods=["POST"])
@login_required
@role_required("patient")
def cancel_appointment(appointment_id):

    ap = q("""
        SELECT paid, status
        FROM appointments
        WHERE id=%s AND patient_id=%s AND deleted=0
    """, (appointment_id, session["user"]["id"]), fetchone=True)

    if not ap:
        flash("Appointment not found")
        return redirect(url_for("dashboard_patient_view"))

    if ap["paid"]:
        flash("Paid appointment cannot be cancelled")
        return redirect(url_for("dashboard_patient_view"))

    q("""
        UPDATE appointments
        SET status='cancelled',
            deleted=1,
            cancelled_at=NOW()
        WHERE id=%s
    """, (appointment_id,), commit=True)

    flash("Appointment cancelled successfully")
    return redirect(url_for("dashboard_patient_view"))

@app.route("/start_video_call/<int:appointment_id>", methods=["POST"])
@login_required
def start_video_call(appointment_id):
    
    query = """
        SELECT a.*, d.name as doctor_name,
               DATE_FORMAT(a.appointment_date, '%Y-%m-%d') as formatted_date,
               TIME_FORMAT(a.appointment_time, '%H:%i') as formatted_time
        FROM appointments a
        JOIN users d ON d.id = a.doctor_id
        WHERE a.id = %s AND (a.patient_id = %s OR a.doctor_id = %s)
        AND a.status IN ('booked', 'in_progress')
        AND a.telemedicine = 1
    """
    appt = q(query, (appointment_id, session['user']['id'], session['user']['id']), fetchone=True)

    if not appt:
        flash("Invalid appointment or not a telemedicine appointment")
        return redirect(url_for("dashboard_patient_view" if session['user']['role'] == 'patient' else "dashboard_doctor_view"))

    room_id = f"hospital-{appointment_id}-{hashlib.sha256(str(appt['formatted_date'] + appt['formatted_time']).encode()).hexdigest()[:10]}"

    return render_template('video_call.html',
                     doctor_name=appt['doctor_name'],
                     appointment_date=appt['formatted_date'],
                     appointment_time=appt['formatted_time'],
                     room_id=room_id)



@app.route("/start_call/<int:appointment_id>", methods=["POST"])
@login_required
@role_required("patient")
def start_call(appointment_id):
    
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
    
    return render_template('phone_call.html',
        doctor_name=appt["doctor_name"],
        doctor_phone=appt["doctor_phone"],
        appointment_id=appointment_id
    )

@app.route("/dashboard_doctor")
@login_required
@role_required("doctor")
def dashboard_doctor_view():
    did = session["user"]["id"]
    cur = q("""
        SELECT a.*, p.name AS patient_name, d.name AS doctor_name, a.telemedicine
        FROM appointments a
        JOIN users p ON p.id=a.patient_id
        JOIN users d ON d.id=a.doctor_id
        WHERE a.doctor_id=%s AND a.status IN ('booked','in_progress')
        ORDER BY a.appointment_date, a.appointment_time
    """, (did,))
    appointments = cur.fetchall()
    return render_template('dashboard_doctor.html', appointments=appointments)

@app.route("/doctor/availability", methods=["GET","POST"])
@login_required
@role_required("doctor")
def set_availability():
    did = session["user"]["id"]
    if request.method == "POST":
        try:
            print("Received POST request for doctor availability")
            print("Form data:", request.form)
            
            q("DELETE FROM doctor_availability WHERE doctor_id=%s", (did,), commit=True)
            print("Deleted existing availability for doctor", did)
            
            items = []
            for day in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
                st = request.form.get(f"{day}_start")
                et = request.form.get(f"{day}_end")
                print(f"Day {day}: start={st}, end={et}")
                
                if st and et: 
                    try:
                        
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

    q("""
        UPDATE appointments
        SET status='in_progress'
        WHERE id=%s AND doctor_id=%s AND deleted=0
    """, (appointment_id, session["user"]["id"]), commit=True)

    return redirect(url_for("dashboard_doctor_view"))

@app.route("/doctor/done/<int:appointment_id>", methods=["POST"])
@login_required
@role_required("doctor")
def mark_done(appointment_id):

    q("""
        UPDATE appointments
        SET status='done'
        WHERE id=%s AND doctor_id=%s AND deleted=0
    """, (appointment_id, session["user"]["id"]), commit=True)

    flash("Appointment completed")
    return redirect(url_for("dashboard_doctor_view"))

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

        pdf_path = None
        try:
            if REPORTLAB_AVAILABLE:
                from gen_pdf import generate_prescription
                print("Generating prescription PDF using reportlab...")
                prescriptions_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prescriptions')
                if not os.path.exists(prescriptions_dir):
                    os.makedirs(prescriptions_dir)
                
                pdf_path = os.path.join(prescriptions_dir, f"prescription_{pres_id}.pdf")
                print(f"PDF will be saved to: {pdf_path}")
                success = generate_prescription(
                    pres_id=pres_id,
                    patient_name=ap['patient_name'],
                    doctor_name=ap['doctor_name'],
                    diagnosis=diagnosis,
                    medicines=medicines,
                    output_path=pdf_path
                )
                
                if not success:
                    raise Exception("Failed to generate PDF")
                print(f"PDF saved to: {pdf_path}")
        except Exception as e:
            print(f"Error generating PDF: {str(e)}")
            pdf_path = None
        
        if pdf_path:
            q("UPDATE prescriptions SET pdf_path=%s WHERE id=%s", (pdf_path, pres_id))

        flash("Prescription saved.")
        return redirect(url_for("dashboard_doctor_view"))

    return render_template('prescription_form.html', appt=ap, pres=pres)

@app.route("/prescriptions/<int:prescription_id>/download")
@login_required
def download_prescription(prescription_id):
    try:
        pres = q("SELECT p.*, a.patient_id, a.doctor_id FROM prescriptions p JOIN appointments a ON a.id=p.appointment_id WHERE p.id=%s", 
                 (prescription_id,), fetchone=True)
        
        if not pres:
            flash("Prescription not found.")
            return redirect(request.referrer or url_for("home"))
        
        if not (session["user"]["id"] == pres["patient_id"] or 
                session["user"]["id"] == pres["doctor_id"] or 
                session["user"]["role"] == "admin"):
            flash("Unauthorized to access this prescription.")
            return redirect(url_for("home"))
        
        if not pres.get("pdf_path"):
            flash("PDF path not found in database.")
            return redirect(request.referrer or url_for("home"))
        
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

@app.route("/dashboard_admin")
@login_required
@role_required("admin")
def dashboard_admin_view():

    kpi = {
        "total": q("SELECT COUNT(*) c FROM appointments").fetchone()["c"],
        "today": q("SELECT COUNT(*) c FROM appointments WHERE appointment_date=%s",
                   (datetime.now().date(),)).fetchone()["c"],
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

    cancelled = q("""
        SELECT a.id, p.name AS patient_name, d.name AS doctor_name,
               a.appointment_date, a.appointment_time, a.cancelled_at
        FROM appointments a
        JOIN users p ON p.id=a.patient_id
        JOIN users d ON d.id=a.doctor_id
        WHERE a.status='cancelled'
        ORDER BY a.cancelled_at DESC
    """).fetchall()

    audits = q("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 20").fetchall()

    return render_template(
        'dashboard_admin.html',
        kpi=kpi,
        by_dept=by_dept,
        cancelled=cancelled,
        audits=audits
    )

@app.route("/admin/hide-cancelled/<int:appointment_id>", methods=["POST"])
@login_required
@role_required("admin")
def admin_hide_cancelled(appointment_id):

    q("""
        UPDATE appointments
        SET deleted=1
        WHERE id=%s AND status='cancelled'
    """, (appointment_id,), commit=True)

    flash("Cancelled appointment hidden from patient dashboard")
    return redirect(url_for("admin_cancelled_appointments"))

@app.route("/admin/cancelled-appointments")
@login_required
@role_required("admin")
def admin_cancelled_appointments():

    rows = q("""
        SELECT a.id, p.name AS patient_name, d.name AS doctor_name,
               a.appointment_date, a.appointment_time, a.cancelled_at
        FROM appointments a
        JOIN users p ON p.id = a.patient_id
        JOIN users d ON d.id = a.doctor_id
        WHERE a.status='cancelled'
        ORDER BY a.cancelled_at DESC
    """, fetchall=True)

    return redirect(url_for("dashboard_admin_view"))


@app.route("/api/doctors")
def api_doctors():
    try:
        department_id = request.args.get("department_id")
        print(f"Fetching doctors for department_id: {department_id}")
        
        if not department_id:
            print("No department_id provided")
            return jsonify([])

        query = """
            SELECT u.id, u.name, CAST(u.fee AS DECIMAL(10,2)) as fee 
            FROM users u 
            WHERE u.role='doctor' 
            AND u.department_id=%s 
            ORDER BY u.name
        """
        print(f"Executing query: {query} with department_id={department_id}")
        
        doctors = q(query, (department_id,), fetchall=True) or []
        
        for doctor in doctors:
            if doctor['fee'] is not None:
                doctor['fee'] = float(doctor['fee'])
        
        print(f"Found {len(doctors)} doctors:", doctors)
        return jsonify(doctors)
    except Exception as e:
        print(f"Error in api_doctors: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/availability")
def api_availability():
    try:
        doctor_id = request.args.get("doctor_id")
        if not doctor_id:
            return jsonify({"error": "Doctor ID is required"}), 400

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
    except Exception as e:
        print(f"Error in api_availability: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/booked_slots")
def api_booked_slots():
    try:
        doctor_id = request.args.get("doctor_id")
        date = request.args.get("date")
        if not doctor_id or not date:
            return jsonify({"error": "Missing doctor_id or date"}), 400

        rows = q(
            "SELECT TIME_FORMAT(appointment_time, '%H:%i') as time FROM appointments WHERE doctor_id=%s AND appointment_date=%s AND status!='cancelled'",
            (doctor_id, date),
            fetchall=True
        ) or []

        slots = [r['time'] for r in rows]
        print(f"Found booked slots for doctor {doctor_id} on {date}:", slots)
        return jsonify(slots)
    except Exception as e:
        print(f"Error in api_booked_slots: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/slots")
@login_required
def api_slots():
    try:
        doctor_id = request.args.get("doctor_id")
        date_str = request.args.get("date")
        if not doctor_id or not date_str:
            return jsonify([])

        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_abbr = date_obj.strftime("%a")

        avail = q("SELECT start_time,end_time FROM doctor_availability WHERE doctor_id=%s AND day_of_week=%s",
                  (doctor_id, day_abbr), fetchall=True)
        if not avail:
            return jsonify([])

        start = datetime.combine(date_obj, avail[0]["start_time"])
        end = datetime.combine(date_obj, avail[0]["end_time"])
        slots = []
        while start + timedelta(minutes=30) <= end:
            slots.append(start.strftime("%H:%M"))
            start += timedelta(minutes=30)

        booked = q("SELECT TIME_FORMAT(appointment_time, '%H:%i') as time FROM appointments WHERE doctor_id=%s AND appointment_date=%s AND status!='cancelled'",
                   (doctor_id, date_str), fetchall=True)
        booked_set = {b["time"] for b in booked}
        available = [s for s in slots if s not in booked_set]
        return jsonify(available)
    except Exception as e:
        print(f"Error in api_slots: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/pay/<int:appointment_id>", methods=["POST"])
@login_required
@role_required("patient")
def pay_start(appointment_id):

    ap = q("""
        SELECT a.*, d.name AS doctor_name, d.fee
        FROM appointments a
        JOIN users d ON d.id = a.doctor_id
        WHERE a.id=%s AND a.patient_id=%s AND a.paid=0
    """, (appointment_id, session["user"]["id"]), fetchone=True)

    if not ap:
        flash("Invalid appointment or already paid")
        return redirect(url_for("dashboard_patient_view"))

    amount = int(ap["fee"] * 100)  # Stripe uses paise

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "inr",
                "product_data": {
                    "name": f"Doctor Consultation – Dr. {ap['doctor_name']}"
                },
                "unit_amount": amount,
            },
            "quantity": 1,
        }],
        metadata={
            "appointment_id": appointment_id,
            "patient_id": session["user"]["id"]
        },
        success_url=url_for(
            "stripe_success",
            appointment_id=appointment_id,
            _external=True
        ),
        cancel_url=url_for(
            "dashboard_patient_view",
            _external=True
        )
    )

    return redirect(checkout_session.url)

@app.route("/stripe-success/<int:appointment_id>")
@login_required
@role_required("patient")
def stripe_success(appointment_id):

    q("""
        UPDATE appointments
        SET paid=1,
            payment_status='completed',
            payment_method='stripe',
            payment_date=NOW()
        WHERE id=%s AND patient_id=%s
    """, (appointment_id, session["user"]["id"]), commit=True)

    flash("Payment successful via Stripe 🎉")
    return redirect(url_for("dashboard_patient_view"))


@app.route("/payment-success/<int:appointment_id>", methods=["POST"])
@login_required
@role_required("patient")
def payment_success(appointment_id):

    payment_method = request.form.get("payment_method", "demo")

    q("""
        UPDATE appointments
        SET paid=1,
            payment_status='completed',
            payment_method=%s,
            payment_date=NOW()
        WHERE id=%s AND patient_id=%s
    """, (payment_method, appointment_id, session["user"]["id"]), commit=True)

    flash("Payment successful")
    return redirect(url_for("dashboard_patient_view"))


@app.route("/admin/finalize/<int:appointment_id>", methods=["POST"])
@login_required
@role_required("admin")
def finalize_appointment(appointment_id):
    q("UPDATE appointments SET finalized=TRUE WHERE id=%s", (appointment_id,))
    flash("Finalized.")
    return redirect(url_for("dashboard_admin_view"))

@app.route("/register_doctor", methods=["GET", "POST"])
def register_doctor():
    
    departments = q("SELECT * FROM departments ORDER BY name", fetchall=True) or []

    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        phone = request.form["phone"].strip()
        department_id = request.form["department_id"]
        fee = request.form.get("fee", 0)

        if q("SELECT id FROM users WHERE email=%s", (email,), fetchone=True):
            flash("Email already registered.")
            return render_template('register.html', departments=departments)

        pwd_hash = generate_password_hash(password)

        q(
            "INSERT INTO users (role, name, email, password_hash, phone, department_id, fee) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("doctor", name, email, pwd_hash, phone, department_id, fee),
            commit=True
        )

        flash("Doctor registered successfully!")
        return redirect(url_for("login"))

    return render_template_string(register_page, departments=departments)

@app.route("/get_doctors/<int:dept_id>")
def get_doctors(dept_id):
    
    doctors = q(
        "SELECT id, name FROM users WHERE role='doctor' AND department_id=%s ORDER BY name",
        (dept_id,),
        fetchall=True
    ) or []

    return jsonify(doctors)


from flask import send_file, flash, redirect, url_for
from hospital.gen_pdf import generate_prescription
import os

@app.route('/download_prescription/<int:pres_id>', methods=['GET'])
def download_prescription_route(pres_id):
    """
    Generate and download a prescription PDF using data from the database.
    """
    try:
        prescription = Prescription.query.get(pres_id)
        if not prescription:
            flash("Prescription not found!", "danger")
            return redirect(url_for('dashboard'))
        pdf_path = os.path.join(prescriptions_dir, f"prescription_{pres_id}.pdf")

        success = generate_prescription(
            pres_id=prescription.id,
            patient_name=prescription.patient_name,
            doctor_name=prescription.doctor_name,
            diagnosis=prescription.diagnosis,
            medicines=prescription.medicines,
            output_path=pdf_path
        )

        if not success or not os.path.exists(pdf_path):
            flash("Failed to generate prescription PDF!", "danger")
            return redirect(url_for('dashboard'))
        return send_file(pdf_path, as_attachment=True)

    except Exception as e:
        flash(f"Error while generating PDF: {e}", "danger")
        return redirect(url_for('dashboard'))
    
    
@app.route("/contact_doctor/<int:doctor_id>")
def contact_doctor(doctor_id):
    doctor = q("SELECT * FROM users WHERE id=%s", (doctor_id,), fetchone=True)
    
    if not doctor:
        flash("Doctor not found.")
        return redirect(url_for("dashboard_patient_view"))
    
    # Pass both name and phone number to template
    return render_template(
        "contact_doctor.html",
        doctor_name=doctor["name"],
        doctor_phone=doctor.get("phone")
    )

if __name__ == "__main__":
    app.run(debug=True)
