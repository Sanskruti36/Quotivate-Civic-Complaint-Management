from flask import Blueprint, request, render_template, redirect, session, url_for
from config import get_connection

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def home():
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        confirm = request.form['confirm_password']
        role = request.form['role']

        if password != confirm:
            return "❌ Passwords do not match!"

        # 🔓 Store plain password directly (NOT SAFE for production)
        password_plain = password

        conn = get_connection()
        cursor = conn.cursor()

        try:
            if role == 'citizen':
                cursor.execute(
                    "INSERT INTO users (name, email, phone, password_hash) VALUES (%s, %s, %s, %s)",
                    (name, email, phone, password_plain)
                )
            elif role in ['officer', 'senior_officer']:
                cursor.execute(
                    "INSERT INTO officers (name, email, phone, password_hash, role) VALUES (%s, %s, %s, %s, %s)",
                    (name, email, phone, password_plain, role)
                )
            elif role == 'admin':
                cursor.execute(
                    "INSERT INTO admins (name, email, phone, password_hash) VALUES (%s, %s, %s, %s)",
                    (name, email, phone, password_plain)
                )

            conn.commit()
            return redirect('/login')

        except Exception as e:
            return f"❌ Registration Error: {e}"

        finally:
            cursor.close()
            conn.close()

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        user = None
        role = None

        # Check in users
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if user and user['password_hash'] == password:
            role = 'citizen'

        # Check in officers
                # Check in officers
        if not user:
            cursor.execute("SELECT * FROM officers WHERE email = %s", (email,))
            user = cursor.fetchone()
            if user and user['password_hash'] == password:
                role = user['role'].strip().lower()
                session['officer_id'] = user['officer_id']  # ✅ Store officer_id

                # After senior officer login
                if role == 'senior_officer':
                    cursor.execute("""
                        SELECT DISTINCT s.state_id
                        FROM officers senior
                        JOIN officer_hierarchy h ON senior.officer_id = h.reports_to
                        JOIN officer_city_issues oci ON h.officer_id = oci.officer_id
                        JOIN cities c ON oci.city_id = c.city_id
                        JOIN states s ON c.state_id = s.state_id
                        WHERE senior.email = %s
                        LIMIT 1
                    """, (email,))
                    result = cursor.fetchone()
                    if result:
                        session['state_id'] = result['state_id']
                # ✅ Store state_id


        # Check in admins
        if not user:
            cursor.execute("SELECT * FROM admins WHERE email = %s", (email,))
            user = cursor.fetchone()
            if user and user['password_hash'] == password:
                role = 'admin'

        cursor.close()
        conn.close()

        if user:
            session['user_id'] = user.get('user_id') or user.get('id') or user.get('officer_id') or user.get('admin_id')
            session['role'] = role

            if role == 'citizen':
                return redirect('/dashboard/citizen')
            elif role == 'officer':
                return redirect('/dashboard/officer')
            elif role == 'senior_officer':
                return redirect('/dashboard/senior_officer')
            elif role == 'admin':
                return redirect('/dashboard/admin')
            else:
                return "✅ Logged in, but unknown role."
        else:
            return "❌ Invalid email or password."

    return render_template('login.html')


@auth_bp.route('/dashboard/<role>')
def dashboard(role):
    return render_template(f'{role}/dashboard_{role}.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect('/login')
