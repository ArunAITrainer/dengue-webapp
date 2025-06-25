from flask import Flask, render_template, request, redirect, url_for, session, send_file
import joblib
import numpy as np
import sqlite3
from flask import send_file
import csv
import io
from datetime import datetime
import pytz
from itsdangerous import URLSafeTimedSerializer
import qrcode
from io import BytesIO
import base64
import os
from itsdangerous import BadSignature, SignatureExpired

app = Flask(__name__)
secret_key = "supersecretkey123"  # use a strong key
serializer = URLSafeTimedSerializer(secret_key)
app.secret_key = 'ram_singh'
# Admin username/passwords
ADMIN_USERS = {
    "admin": "admin123",
    "arun": "jai"
}
model = joblib.load("dengue_model.pkl")

# Save to DB and return Patient ID
def save_to_db(name, mobile, temp, shiv, sys, dia, head, result):
    ist = pytz.timezone('Asia/Kolkata')
    timestamp = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')

    conn = sqlite3.connect("patient_records.db")
    c = conn.cursor()
    c.execute('''
        INSERT INTO patients (
            patient_name, mobile_number, temperature, shivering,
            bp_systolic, bp_diastolic, headache, prediction, prediction_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, mobile, temp, shiv, sys, dia, head, result, timestamp))
    conn.commit()
    patient_id = c.lastrowid
    conn.close()
    return patient_id


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    try:
        name = request.form['name']
        mobile = request.form['mobile']
        temp = float(request.form['temperature'])
        shivering = 1 if request.form['shivering'].lower() == 'yes' else 0
        bp_sys = float(request.form['bp_systolic'])
        bp_dia = float(request.form['bp_diastolic'])
        headache = 1 if request.form['headache'].lower() == 'yes' else 0

        input_features = np.array([[temp, shivering, bp_sys, bp_dia, headache]])
        prediction = model.predict(input_features)[0]
        result = "🦠 Dengue Positive" if prediction == 1 else "✅ Dengue Negative"

        patient_id = save_to_db(name, mobile, temp, shivering, bp_sys, bp_dia, headache, result)

        return render_template('index.html', prediction_text=f"{result} for {name}", patient_id=patient_id)
    except:
        return render_template('index.html', prediction_text="❌ Error: Please fill all fields correctly.")

@app.route('/download_csv')
def download_csv():
    conn = sqlite3.connect("patient_records.db")
    c = conn.cursor()
    c.execute("SELECT * FROM patients")
    rows = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Mobile", "Temp", "Shivering", "BP_Systolic", "BP_Diastolic", "Headache", "Prediction", "Time"])
    writer.writerows(rows)
    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='patient_records.csv'
    )


@app.route("/generate_qr")
def generate_qr():
    if 'admin' not in session:
        return redirect(url_for('login'))
    
    token = serializer.dumps("admin")
    qr_url = f"http://192.168.1.4:5000/qr-login/{token}"

    # Generate QR code
    img = qrcode.make(qr_url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return render_template("qr_code.html", qr_img=qr_b64, qr_url=qr_url)

@app.route("/qr-login/<token>")
def qr_login(token):
    try:
        username = serializer.loads(token, max_age=300)  # valid for 5 minutes
        session['admin'] = username
        return redirect(url_for("dashboard"))
    except SignatureExpired:
        return "Token expired. Please generate a new QR code.", 403
    except BadSignature:
        return "Invalid token.", 403

@app.route("/dashboard")
def dashboard():
    if 'admin' not in session:
        return redirect(url_for('login'))
    return render_template("dashboard.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        if uname in ADMIN_USERS and ADMIN_USERS[uname] == pwd:
            session['admin'] = uname
            return redirect(url_for('patients'))
        else:
            return render_template('login.html', error="❌ Invalid credentials")
    return render_template('login.html')
@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route('/patients')
def patients():
    if 'admin' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect("patient_records.db")
    c = conn.cursor()
    c.execute("SELECT * FROM patients ORDER BY prediction_time DESC")
    rows = c.fetchall()
    conn.close()
    return render_template('patients.html', patients=rows)


if __name__ == "__main__":
    app.run(host='192.168.1.4', port=5000, debug=True)
    port = int(os.environ.get('PORT', 5000))  # Render will set PORT
    app.run(host='0.0.0.0', port=port)
    app.run(debug=True)
