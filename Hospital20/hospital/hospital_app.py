from flask import Flask, request, session, redirect, url_for, flash, render_template_string
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()  
app = Flask(__name__)

conn = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST"),
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
    port=int(os.getenv("MYSQL_PORT", 3306)),
    ssl_disabled=False  # Required for Aiven
)

cursor = conn.cursor(dictionary=True)


login_page = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Appointment Booking Portal</title>
  <style>
    
    body {
      margin: 0;
      padding: 0;
      font-family: Arial, sans-serif;
      background: linear-gradient(120deg, #fafbf8 0%, #e4e6e4 100%);
      background-size: cover;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column;
    }

    h1 {
      text-align: center;
      color: black;
      margin-top: 0px;
      font-size: 45px;
    }

    .login-container {
      background: rgba(255, 255, 255, 0.3);
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
      backdrop-filter: blur(15px);
      -webkit-backdrop-filter: blur(15px);
      border-radius: 16px;
      padding: 35px 30px;
      color: #000;
      border: 1px solid rgba(255, 255, 255, 0.25);
      transition: all 0.3s ease-in-out;
        
      width: 350px;
      margin: 60px auto;

    }
    .login-container:hover{
        transform: scale(1.02);
    }
    label {
      font-weight: bold;
      display: block;
      margin-top: 10px;
      margin-bottom: 5px;
    }

    input[type="email"],
    input[type="password"] {
      width: 100%;
      padding: 10px;
      margin-bottom: 15px;
      border: 1px solid #ccc;
      border-radius: 5px;
    }

    button {
      width: 100%;
      padding: 10px;
      font-size: 16px;
      border: none;
      color: white;
      border-radius: 5px;
      margin-top: 10px;
      cursor: pointer;
      transition: background 0.3s ease;
    }

    .login-btn {
      background-color: #d35400;
    }

    .register-btn {
      background-color: #558b2f;
    }

    .login-btn:hover {
      background-color: #e67e22;
    }

    .register-btn:hover {
      background-color: #66bb6a;
    }

    ul {
      color: red;
      padding-left: 0;
      list-style: none;
      margin-top: 10px;
      text-align: center;
    }
  </style>
</head>
<body>

  <h1>Appointment Booking Portal</h1>

  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <ul>{% for message in messages %}<li>{{ message }}</li>{% endfor %}</ul>
    {% endif %}
  {% endwith %}

  <div class="login-container">
    <form method="POST" action="/login">
      <label for="email">Email:</label>
      <input type="email" name="email" id="email" placeholder="you@example.com" required>

      <label for="password">Password:</label>
      <input type="password" name="password" id="password" placeholder="Enter your password" required>

      <button type="submit" class="login-btn">Login</button>
    </form>

    <form action="/register">
      <button type="submit" class="register-btn">Register</button>
    </form>
  </div>

</body>
</html>

'''

register_page = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Hospital Registration</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">

  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
      font-family: 'Poppins', sans-serif;
    }

    body {
      background: url('d7316505-0f58-4235-b1c3-c62304059ef7.png') no-repeat center center fixed;
      background-size: cover;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 20px;
    }

    h2 {
      color: #0a0a0a;
      font-size: 48px;
      margin-bottom: 20px;
      text-shadow: 1px 1px 2px #fff;
      text-align: center;
    }

    .form-box {
      background: rgba(255, 255, 255, 0.95);
      padding: 35px 30px;
      border-radius: 15px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
      width: 100%;
      max-width: 400px;
    }

    label {
      font-weight: 600;
      margin-bottom: 8px;
      display: block;
    }

    select, input {
      width: 100%;
      padding: 10px;
      margin-bottom: 18px;
      border: 1px solid #ccc;
      border-radius: 8px;
      font-size: 16px;
    }

    .btn {
      width: 100%;
      padding: 12px;
      margin-top: 10px;
      font-size: 16px;
      font-weight: bold;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      transition: 0.3s;
    }

    .register-btn {
      background-color: #388e3c;
      color: white;
    }

    .register-btn:hover {
      background-color: #43a047;
    }

    .login-btn {
      background-color: #d84315;
      color: white;
    }

    .login-btn:hover {
      background-color: #e64a19;
    }

    @media (max-width: 500px) {
      h2 {
        font-size: 36px;
      }

      .form-box {
        padding: 25px 20px;
      }
    }
  </style>
</head>
<body>

  <h2>Register</h2>

  <div class="form-box">
    <form method="POST" action="/register">
      <label for="role">Select Role</label>
      <select name="role" id="role" required>
        <option value="admin">Admin</option>
        <option value="doctor">Doctor</option>
        <option value="patient">Patient</option>
      </select>

      <label for="name">Full Name</label>
      <input type="text" id="name" name="name" placeholder="Enter your name" required>

      <label for="email">Email Address</label>
      <input type="email" id="email" name="email" placeholder="Enter your email" required>

      <label for="password">Password</label>
      <input type="password" id="password" name="password" placeholder="Create a password" required>

      <button type="submit" class="btn register-btn">Register</button>
      <button type="button" class="btn login-btn" onclick="window.location.href='/login'">Back to Login</button>
    </form>
  </div>

</body>
</html>

'''

dashboard_admin_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Admin Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <!-- Google Font -->
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">

  <style>
    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      font-family: 'Poppins', sans-serif;
      background: url('https://www.transparenttextures.com/patterns/grey-sandbag.png'), #e3eaf0;
      background-size: cover;
      background-repeat: repeat;
      padding: 40px 20px;
      color: #2c3e50;
    }

    .dashboard {
      max-width: 1100px;
      margin: auto;
      background: rgba(255, 255, 255, 0.96);
      border-radius: 16px;
      padding: 30px 40px;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
      animation: fadeIn 0.6s ease-in-out;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(20px); }
      to { opacity: 1; transform: translateY(0); }
    }

    h2 {
      text-align: center;
      font-size: 2.3em;
      margin-bottom: 10px;
      color: #2c3e50;
    }

    .welcome {
      text-align: right;
      font-size: 15px;
      margin-bottom: 25px;
    }

    .welcome a {
      color: #e74c3c;
      text-decoration: none;
      font-weight: 600;
      transition: color 0.3s ease;
    }

    .welcome a:hover {
      color: #c0392b;
    }

    h3 {
      font-size: 1.5em;
      color: #34495e;
      border-left: 5px solid #3498db;
      padding-left: 15px;
      margin-bottom: 20px;
    }

    table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0 12px;
    }

    thead th {
      background-color: #3498db;
      color: white;
      padding: 14px 16px;
      text-align: left;
      font-size: 15px;
      border-top-left-radius: 8px;
      border-top-right-radius: 8px;
    }

    tbody tr {
      background-color: #f7f9fa;
      border-radius: 8px;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    tbody tr:hover {
      transform: scale(1.005);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    }

    tbody tr.done {
      background-color: #dff0d8; /* light green */
    }

    tbody td {
      padding: 14px 16px;
      font-size: 14.5px;
      color: #2c3e50;
    }

    .badge {
      padding: 5px 10px;
      font-size: 12px;
      border-radius: 12px;
      font-weight: 600;
      display: inline-block;
    }

    .badge.done {
      background-color: #27ae60;
      color: white;
    }

    .badge.pending {
      background-color: #e67e22;
      color: white;
    }

    .reschedule-btn {
      background-color: #e74c3c;
      border: none;
      color: white;
      padding: 6px 10px;
      font-size: 12px;
      border-radius: 6px;
      cursor: pointer;
      transition: background-color 0.3s;
    }

    .reschedule-btn:hover {
      background-color: #c0392b;
    }

    .no-data {
      text-align: center;
      padding: 20px;
      color: #777;
      font-style: italic;
    }

    @media (max-width: 768px) {
      .dashboard {
        padding: 20px;
      }

      h2 {
        font-size: 1.8em;
      }

      table, thead, tbody, th, td, tr {
        display: block;
      }

      thead {
        display: none;
      }

      tbody tr {
        margin-bottom: 15px;
        padding: 10px;
        border: 1px solid #ddd;
        border-radius: 8px;
      }

      tbody td {
        display: flex;
        justify-content: space-between;
        padding: 10px;
        font-size: 14px;
      }

      tbody td::before {
        content: attr(data-label);
        font-weight: bold;
        color: #555;
        margin-right: 10px;
      }
    }
  </style>
</head>
<body>

  <div class="dashboard">
    <h2>Admin Dashboard</h2>
    <p class="welcome">
      Welcome {{ session.user['name'] }} |
      <a href="/logout">Logout</a>
    </p>

    <h3>All Appointments</h3>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Patient</th>
          <th>Doctor</th>
          <th>Date</th>
          <th>Time</th>
          <th>Status</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {% for a in appointments %}
        <tr class="{% if a.status == 'done' %}done{% endif %}">
          <td data-label="ID">{{ a.id }}</td>
          <td data-label="Patient">{{ a.patient_name }}</td>
          <td data-label="Doctor">{{ a.doctor_name }}</td>
          <td data-label="Date">{{ a.date }}</td>
          <td data-label="Time">{{ a.time }}</td>
          <td data-label="Status">
            {% if a.status == 'done' %}
              <span class="badge done">Done</span>
            {% else %}
              <span class="badge pending">Pending</span>
            {% endif %}
          </td>
          <td data-label="Action">
            {% if a.status != 'done' %}
            <form method="POST" action="/reschedule/{{ a.id }}">
              <button type="submit" class="reschedule-btn">Reschedule</button>
            </form>
            {% else %}
              —
            {% endif %}
          </td>
        </tr>
        {% else %}
        <tr>
          <td class="no-data" colspan="7">No appointments found.</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

</body>
</html>
'''

dashboard_doctor_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Doctor Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <!-- Google Fonts -->
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">

  <style>
    * {
      box-sizing: border-box;
    }

    body {
      font-family: 'Poppins', sans-serif;
      margin: 0;
      padding: 40px 20px;
      background: url('https://www.transparenttextures.com/patterns/white-wall-3.png'), #e6f0f7;
      background-size: cover;
      color: #2c3e50;
    }

    .dashboard {
      max-width: 1000px;
      margin: auto;
      background: rgba(255, 255, 255, 0.95);
      padding: 30px 40px;
      border-radius: 16px;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
      animation: fadeIn 0.5s ease;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(15px); }
      to { opacity: 1; transform: translateY(0); }
    }

    h2 {
      text-align: center;
      font-size: 2.2em;
      margin-bottom: 5px;
    }

    .welcome {
      text-align: right;
      font-size: 14px;
      margin-bottom: 25px;
    }

    .welcome a {
      color: #e74c3c;
      font-weight: 600;
      text-decoration: none;
    }

    .welcome a:hover {
      text-decoration: underline;
    }

    h3 {
      font-size: 1.5em;
      margin-bottom: 15px;
      color: #34495e;
      border-left: 5px solid #3498db;
      padding-left: 12px;
    }

    table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0 10px;
    }

    thead th {
      background-color: #3498db;
      color: white;
      padding: 12px;
      text-align: left;
      font-size: 15px;
      border-radius: 6px;
    }

    tbody tr {
      background-color: #f9f9f9;
      border-radius: 6px;
      transition: all 0.2s;
    }

    tbody tr.done {
      background-color: #d5f5e3; /* Light green */
    }

    tbody tr:hover {
      transform: scale(1.003);
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.06);
    }

    tbody td {
      padding: 12px;
      font-size: 14.5px;
    }

    .badge {
      padding: 5px 10px;
      border-radius: 12px;
      font-weight: 600;
      font-size: 12px;
      display: inline-block;
    }

    .badge.done {
      background-color: #27ae60;
      color: white;
    }

    .badge.pending {
      background-color: #f39c12;
      color: white;
    }

    .reschedule-btn {
      background-color: #e74c3c;
      border: none;
      padding: 6px 12px;
      font-size: 12px;
      color: white;
      border-radius: 6px;
      cursor: pointer;
      transition: background 0.3s;
    }

    .reschedule-btn:hover {
      background-color: #c0392b;
    }

    .no-data {
      text-align: center;
      font-style: italic;
      padding: 20px;
      color: #666;
    }

    @media (max-width: 768px) {
      table, thead, tbody, th, td, tr {
        display: block;
      }

      thead {
        display: none;
      }

      tbody tr {
        margin-bottom: 15px;
        border: 1px solid #ddd;
        border-radius: 6px;
        padding: 12px;
      }

      tbody td {
        display: flex;
        justify-content: space-between;
        padding: 10px;
      }

      tbody td::before {
        content: attr(data-label);
        font-weight: 600;
        margin-right: 10px;
        color: #34495e;
      }
    }
  </style>
</head>
<body>

  <div class="dashboard">
    <h2>Doctor Dashboard</h2>
    <p class="welcome">Welcome Dr. {{ session.user['name'] }} | <a href="/logout">Logout</a></p>

    <h3>Your Appointments</h3>
    <table>
      <thead>
        <tr>
          <th>Patient</th>
          <th>Date</th>
          <th>Time</th>
          <th>Status</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {% for a in appointments %}
        <tr class="{% if a.status == 'done' %}done{% endif %}">
          <td data-label="Patient">{{ a.patient_name }}</td>
          <td data-label="Date">{{ a.date }}</td>
          <td data-label="Time">{{ a.time }}</td>
          <td data-label="Status">
            {% if a.status == 'done' %}
              <span class="badge done">Done</span>
            {% else %}
              <span class="badge pending">Pending</span>
            {% endif %}
          </td>
          <td data-label="Action">
            {% if a.status != 'done' %}
              <form method="POST" action="/doctor/reschedule/{{ a.id }}">
                <button type="submit" class="reschedule-btn">Reschedule</button>
              </form>
            {% else %}
              —
            {% endif %}
          </td>
        </tr>
        {% else %}
        <tr>
          <td class="no-data" colspan="5">No appointments found.</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

</body>
</html>
'''

dashboard_patient_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Patient Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <!-- Google Fonts -->
  <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">

  <style>
    * {
      box-sizing: border-box;
    }

    body {
      font-family: 'Roboto', sans-serif;
      margin: 0;
      padding: 40px 20px;
      background: linear-gradient(to right, #e0f7fa, #f1f8e9);
      color: #2c3e50;
    }

    .dashboard {
      max-width: 1000px;
      margin: auto;
      background: white;
      padding: 30px 40px;
      border-radius: 16px;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.08);
    }

    h2 {
      text-align: center;
      font-size: 2.2em;
      margin-bottom: 5px;
    }

    .welcome {
      text-align: right;
      font-size: 14px;
      margin-bottom: 20px;
    }

    .welcome a {
      color: #e74c3c;
      font-weight: 600;
      text-decoration: none;
    }

    .book-btn {
      display: inline-block;
      background-color: #3498db;
      color: white;
      padding: 10px 18px;
      border-radius: 8px;
      text-decoration: none;
      font-weight: 600;
      margin: 10px 0 30px 0;
      transition: background 0.3s;
    }

    .book-btn:hover {
      background-color: #2980b9;
    }

    h3 {
      font-size: 1.5em;
      margin-bottom: 15px;
      color: #34495e;
      border-left: 5px solid #2ecc71;
      padding-left: 12px;
    }

    table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0 10px;
    }

    thead th {
      background-color: #2ecc71;
      color: white;
      padding: 12px;
      text-align: left;
      font-size: 15px;
      border-radius: 6px;
    }

    tbody tr {
      background-color: #f9f9f9;
      border-radius: 6px;
      transition: all 0.2s;
    }

    tbody tr:hover {
      transform: scale(1.002);
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
    }

    tbody td {
      padding: 12px;
      font-size: 14.5px;
    }

    .badge {
      padding: 5px 10px;
      border-radius: 12px;
      font-weight: 600;
      font-size: 12px;
      display: inline-block;
    }

    .badge.completed {
      background-color: #2ecc71;
      color: white;
    }

    .badge.upcoming {
      background-color: #f39c12;
      color: white;
    }

    .cancel-btn {
      background-color: #e74c3c;
      border: none;
      padding: 6px 12px;
      font-size: 12px;
      color: white;
      border-radius: 6px;
      cursor: pointer;
      transition: background 0.3s;
    }

    .cancel-btn:hover {
      background-color: #c0392b;
    }

    .no-data {
      text-align: center;
      font-style: italic;
      padding: 20px;
      color: #666;
    }

    @media (max-width: 768px) {
      table, thead, tbody, th, td, tr {
        display: block;
      }

      thead {
        display: none;
      }

      tbody tr {
        margin-bottom: 15px;
        border: 1px solid #ddd;
        border-radius: 6px;
        padding: 12px;
      }

      tbody td {
        display: flex;
        justify-content: space-between;
        padding: 10px;
      }

      tbody td::before {
        content: attr(data-label);
        font-weight: 600;
        margin-right: 10px;
        color: #34495e;
      }
    }
  </style>
</head>
<body>

  <div class="dashboard">
    <h2>Patient Dashboard</h2>
    <p class="welcome">Welcome {{ session.user['name'] }} | <a href="/logout">Logout</a></p>

    <a href="/book" class="book-btn">➕ Book Appointment</a>

    <h3>Your Appointments</h3>
    <table>
      <thead>
        <tr>
          <th>Doctor</th>
          <th>Date</th>
          <th>Time</th>
          <th>Status</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {% for a in appointments %}
        <tr>
          <td data-label="Doctor">{{ a.doctor_name }}</td>
          <td data-label="Date">{{ a.date }}</td>
          <td data-label="Time">{{ a.time }}</td>
          <td data-label="Status">
            {% if a.status == 'completed' %}
              <span class="badge completed">Completed</span>
            {% else %}
              <span class="badge upcoming">Upcoming</span>
            {% endif %}
          </td>
          <td data-label="Action">
            {% if a.status != 'completed' %}
              <form method="POST" action="/cancel/{{ a.id }}" style="margin: 0;">
                <button type="submit" class="cancel-btn">Cancel</button>
              </form>
            {% else %}
              —
            {% endif %}
          </td>
        </tr>
        {% else %}
        <tr>
          <td class="no-data" colspan="5">No appointments found.</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

</body>
</html>
'''

book_appointment_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Book Appointment</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <!-- Google Fonts -->
  <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;700&display=swap" rel="stylesheet">

  <!-- Flatpickr CSS (for beautiful date & time picker) -->
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/themes/material_blue.css">

  <style>
    body {
      margin: 0;
      font-family: 'Nunito', sans-serif;
      background: linear-gradient(135deg, #f5f7fa, #c3cfe2);
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
    }

    .card {
      background: rgba(255, 255, 255, 0.9);
      padding: 40px;
      border-radius: 18px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
      max-width: 500px;
      width: 100%;
    }

    h2 {
      text-align: center;
      color: #2c3e50;
      margin-bottom: 25px;
    }

    label {
      display: block;
      margin: 12px 0 6px;
      font-weight: bold;
      color: #34495e;
    }

    select, input {
      width: 100%;
      padding: 12px;
      font-size: 15px;
      border-radius: 10px;
      border: 1px solid #ccc;
      margin-bottom: 18px;
    }

    select:focus, input:focus {
      border-color: #2980b9;
      outline: none;
    }

    input[type="submit"] {
      background: linear-gradient(135deg, #27ae60, #2ecc71);
      color: white;
      border: none;
      cursor: pointer;
      transition: transform 0.2s ease;
      font-weight: bold;
    }

    input[type="submit"]:hover {
      transform: scale(1.02);
      background: linear-gradient(135deg, #229954, #27ae60);
    }

    .back-link {
      display: block;
      text-align: center;
      margin-top: 15px;
      text-decoration: none;
      color: #2980b9;
      font-weight: 600;
    }

    .back-link:hover {
      color: #1c5980;
    }
  </style>
</head>
<body>

  <div class="card">
    <h2>Book Appointment</h2>
    <form method="POST">
      <label for="doctor">Select Doctor:</label>
      <select name="doctor_id" id="doctor" required>
        <option value="" disabled selected>-- Choose a doctor --</option>
        {% for doc in doctors %}
          <option value="{{ doc.id }}">Dr. {{ doc.name }}</option>
        {% endfor %}
      </select>

      <label for="date">Select Date:</label>
      <input type="text" id="date" name="date" placeholder="Choose date" required>

      <label for="time">Select Time:</label>
      <input type="text" id="time" name="time" placeholder="Choose time" required>

      <input type="submit" value="Book Appointment">
    </form>

    <a href="/dashboard_patient" class="back-link">← Back to Dashboard</a>
  </div>

  <!-- Flatpickr JS -->
  <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
  <script>
    flatpickr("#date", {
      dateFormat: "Y-m-d",
      minDate: "today",
      disableMobile: true
    });

    flatpickr("#time", {
      enableTime: true,
      noCalendar: true,
      dateFormat: "h:i K",  // 12-hour format with AM/PM
      time_24hr: false,
      disableMobile: true
    });
  </script>
</body>
</html>
'''


@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form['role']
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        cursor.execute("INSERT INTO users (role, name, email, password) VALUES (%s, %s, %s, %s)",
                       (role, name, email, password))
        conn.commit()
        flash('Registered Successfully')
        return redirect(url_for('login'))
    return render_template_string(register_page)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()
        if user:
            session['user'] = user
            return redirect(url_for(f"dashboard_{user['role']}_view"))
        else:
            flash('Invalid credentials')
    return render_template_string(login_page)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/dashboard_admin')
def dashboard_admin_view():
    if session['user']['role'] != 'admin':
        return redirect(url_for('login'))
    cursor.execute('''
        SELECT a.*, 
               p.name AS patient_name, 
               d.name AS doctor_name 
        FROM appointments a 
        JOIN users p ON a.patient_id = p.id 
        JOIN users d ON a.doctor_id = d.id
    ''')
    appointments = cursor.fetchall()
    return render_template_string(dashboard_admin_template, appointments=appointments)


@app.route('/dashboard_doctor')
def dashboard_doctor_view():
    if session['user']['role'] != 'doctor':
        return redirect(url_for('login'))

    doctor_id = session['user']['id']
    cursor.execute('''
        SELECT a.*, 
               p.name AS patient_name 
        FROM appointments a 
        JOIN users p ON a.patient_id = p.id 
        WHERE a.doctor_id = %s
    ''', (doctor_id,))  # ✅ Pass the value as a tuple
    appointments = cursor.fetchall()
    return render_template_string(dashboard_doctor_template, appointments=appointments)

@app.route('/dashboard_patient')
def dashboard_patient_view():
    patient_id = session['user']['id']
    cursor.execute('''
        SELECT a.*, 
        d.name AS doctor_name 
        FROM appointments a 
        JOIN users d ON a.doctor_id = d.id 
        WHERE a.patient_id = %s
    ''', (patient_id,))
    appointments = cursor.fetchall()
    return render_template_string(dashboard_patient_template, appointments=appointments)



@app.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        patient_id = session['user']['id']
        doctor_id = request.form['doctor_id']
        date = request.form['date']
        time_raw = request.form['time']  # e.g. '11:15 AM'

        # Convert '11:15 AM' to 'HH:MM:SS' (24-hour)
        try:
            time_converted = datetime.strptime(time_raw, "%I:%M %p").strftime("%H:%M:%S")
        except ValueError:
            flash("Invalid time format.")
            return redirect(url_for('book'))

        cursor.execute("""
            INSERT INTO appointments (patient_id, doctor_id, date, time)
            VALUES (%s, %s, %s, %s)
        """, (patient_id, doctor_id, date, time_converted))
        conn.commit()
        flash('Appointment Booked')
        return redirect(url_for('dashboard_patient_view'))

    # Fetch doctors
    cursor.execute("SELECT * FROM users WHERE role='doctor'")
    doctors = cursor.fetchall()
    return render_template_string(book_appointment_template, doctors=doctors)

@app.route('/reschedule/<int:appointment_id>', methods=['POST'])
def reschedule(appointment_id):
    cursor.execute("UPDATE appointments SET status='done' WHERE id=%s", (appointment_id,))
    conn.commit()
    flash('Appointment marked as done')

    role = session['user']['role']
    
    routes = {
        'admin': 'dashboard_admin_view',
        'doctor': 'dashboard_doctor_view'
    }

    for r in routes:
        if role == r:
            return redirect(url_for(routes[r]))

    # fallback if no role matched
    return redirect(url_for('login'))

@app.route('/cancel/<int:appointment_id>', methods=['POST'])
def cancel_appointment(appointment_id):
    cursor.execute("DELETE FROM appointments WHERE id = %s", (appointment_id,))
    conn.commit()
    flash("Appointment cancelled successfully.")
    return redirect(url_for('dashboard_patient_view'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # Render sets this
    app.run(host='0.0.0.0', port=port)

