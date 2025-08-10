from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
import mysql.connector
import os
from shapely.geometry import Point, shape
import json
from werkzeug.utils import secure_filename
from config import get_connection
from collections import defaultdict

# ✅ Define blueprint
user_bp = Blueprint('user', __name__)

# ✅ File upload config
UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads'))
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ✅ Complaint form route with dynamic issue types
@user_bp.route('/submit-form')
def show_complaint_form():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT issue_type_id, name FROM complaint_types")
        issue_types = cursor.fetchall()
        return render_template('citizen/submit_complaint.html', issue_types=issue_types)
    except Exception as e:
        return f"Error loading form: {str(e)}"
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@user_bp.route('/dashboard/citizen')
def citizen_dashboard():
    return render_template('citizen/dashboard_citizen.html')

# ✅ Detect zone & city using lat/lng
@user_bp.route('/detect-location')
def detect_location():
    try:
        lat = float(request.args.get('lat'))
        lng = float(request.args.get('lng'))
        point = Point(lng, lat)

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT zone_id, city_id, boundary_geojson FROM zones WHERE boundary_geojson IS NOT NULL")
        zones = cursor.fetchall()

        for zone in zones:
            geometry = shape(json.loads(zone['boundary_geojson']))
            if geometry.contains(point):
                return jsonify({"zone_id": zone['zone_id'], "city_id": zone['city_id']})

        return jsonify({"zone_id": None, "city_id": None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@user_bp.route('/view-complaints')
def view_my_complaints():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Fetch all complaints filed by this user
        cursor.execute("""
            SELECT c.*, ct.name AS issue_name, z.zone_name, cities.city_name,
                   o.name AS officer_name, o.email AS officer_email
            FROM complaints c
            JOIN complaint_types ct ON c.issue_type_id = ct.issue_type_id
            JOIN zones z ON c.zone_id = z.zone_id
            JOIN cities ON c.city_id = cities.city_id
            LEFT JOIN officers o ON c.assigned_officer_id = o.officer_id
            WHERE c.user_id = %s
            ORDER BY c.created_at DESC
        """, (user_id,))
        complaints = cursor.fetchall()

        # Fetch all comments for the current user's complaints
        complaint_ids = [c['complaint_id'] for c in complaints]
        if complaint_ids:
            format_strings = ','.join(['%s'] * len(complaint_ids))
            cursor.execute(f"""
                SELECT cm.comment_id, cm.complaint_id, cm.comment, cm.created_at,
                       u.user_id, u.name AS user_name
                FROM comments cm
                JOIN users u ON cm.user_id = u.user_id
                WHERE cm.complaint_id IN ({format_strings})
                ORDER BY cm.created_at ASC
            """, tuple(complaint_ids))
            all_comments = cursor.fetchall()
        else:
            all_comments = []

        # Attach comments to their respective complaints
        comments_map = {}
        for comment in all_comments:
            comp_id = comment['complaint_id']
            # Determine label based on who commented
            if comment['user_id'] == user_id:
                display_name = "Me"
            else:
                display_name = "Anonymous"

            comment_data = {
                'comment': comment['comment'],
                'created_at': comment['created_at'],
                'user_name': display_name
            }

            if comp_id not in comments_map:
                comments_map[comp_id] = []
            comments_map[comp_id].append(comment_data)

        # Add comments to each complaint
        for complaint in complaints:
            complaint['comments'] = comments_map.get(complaint['complaint_id'], [])

        return render_template('citizen/view_complaints.html', complaints=complaints)

    except Exception as e:
        return f"Error loading complaints: {e}"

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


@user_bp.route('/submit-complaint', methods=['POST'])
def submit_complaint():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect('/login')

        city_id = request.form.get('city_id')
        issue_type_id = request.form.get('issue_type_id')
        zone_id = request.form.get('zone_id')
        description = request.form.get('description')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')

        if not all([user_id, city_id, issue_type_id, zone_id, description, latitude, longitude]):
            return jsonify({"error": "Missing required fields"}), 400

        photo_path = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(file_path)
                photo_path = f'static/uploads/{filename}'

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT oci.officer_id
            FROM officer_city_issues oci
            LEFT JOIN complaints c ON oci.officer_id = c.assigned_officer_id
            WHERE oci.city_id = %s AND oci.issue_type_id = %s
            GROUP BY oci.officer_id
            ORDER BY COUNT(c.complaint_id) ASC
            LIMIT 1
        """, (city_id, issue_type_id))
        result = cursor.fetchone()

        if result:
            assigned_officer_id = result[0]
            cursor.execute("""
                INSERT INTO complaints (
                    user_id, issue_type_id, zone_id, city_id,
                    description, photo_path, latitude, longitude,
                    assigned_officer_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id, issue_type_id, zone_id, city_id,
                description, photo_path, latitude, longitude,
                assigned_officer_id
            ))
            conn.commit()
            return jsonify({"message": "Complaint submitted successfully and assigned!"})
        else:
            return jsonify({"error": "No officer available for selected city and issue type."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@user_bp.route('/public-complaints')
def public_complaints():
    city_filter = request.args.get('city_id')
    issue_filter = request.args.get('issue_type_id')
    session_user_id = session.get('user_id')  # For "Me" or "Anonymous"

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Get cities and issues for dropdown
        cursor.execute("SELECT city_id, city_name FROM cities")
        cities = cursor.fetchall()

        cursor.execute("SELECT issue_type_id, name FROM complaint_types")
        issues = cursor.fetchall()

        # Prepare base complaint query
        query = """
            SELECT c.*, ct.name AS issue_name, z.zone_name, ci.city_name, o.name AS officer_name
            FROM complaints c
            JOIN complaint_types ct ON c.issue_type_id = ct.issue_type_id
            JOIN zones z ON c.zone_id = z.zone_id
            JOIN cities ci ON c.city_id = ci.city_id
            LEFT JOIN officers o ON c.assigned_officer_id = o.officer_id
            WHERE c.status != 'Deleted'
        """

        # Apply filters if provided
        conditions, values = [], []
        if city_filter:
            conditions.append("c.city_id = %s")
            values.append(city_filter)
        if issue_filter:
            conditions.append("c.issue_type_id = %s")
            values.append(issue_filter)
        if conditions:
            query += " AND " + " AND ".join(conditions)
        query += " ORDER BY c.created_at DESC"

        # Fetch all complaints
        cursor.execute(query, tuple(values))
        complaints = cursor.fetchall()

        # Fetch all comments for visible complaints in one go
        complaint_ids = [c['complaint_id'] for c in complaints]
        if complaint_ids:
            format_strings = ','.join(['%s'] * len(complaint_ids))
            cursor.execute(f"""
                SELECT cm.comment_id, cm.complaint_id, cm.comment, cm.created_at, u.user_id
                FROM comments cm
                JOIN users u ON cm.user_id = u.user_id
                WHERE cm.complaint_id IN ({format_strings})
                ORDER BY cm.created_at ASC
            """, tuple(complaint_ids))
            all_comments = cursor.fetchall()
        else:
            all_comments = []

        # Map comments to complaints and determine display name
        comment_map = {}
        for comment in all_comments:
            comp_id = comment['complaint_id']
            is_self = session_user_id and session_user_id == comment['user_id']
            comment_entry = {
                'comment': comment['comment'],
                'created_at': comment['created_at'],
                'user_name': "Me" if is_self else "Anonymous"
            }
            if comp_id not in comment_map:
                comment_map[comp_id] = []
            comment_map[comp_id].append(comment_entry)

        # Attach comments to complaints
        for complaint in complaints:
            complaint['comments'] = comment_map.get(complaint['complaint_id'], [])

        return render_template(
            'citizen/public_complaints.html',
            complaints=complaints,
            cities=cities,
            issues=issues,
            selected_city=city_filter,
            selected_issue=issue_filter
        )

    except Exception as e:
        return f"❌ Error loading public complaints: {e}"

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()



@user_bp.route('/complaint-heatmap')
def complaint_heatmap():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT city_id, city_name FROM cities")
        cities = cursor.fetchall()
        cursor.execute("SELECT issue_type_id, name FROM complaint_types")
        issue_types = cursor.fetchall()
        return render_template('citizen/complaint_heatmap.html', cities=cities, issue_types=issue_types)
    except Exception as e:
        return f"Error loading heatmap page: {e}", 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@user_bp.route('/api/complaint-locations-with-details')
def get_complaint_locations_with_details():
    try:
        issue_type_id = request.args.get('issue_type_id')
        city_id = request.args.get('city_id')

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT c.complaint_id, c.latitude, c.longitude, c.description, c.created_at,
                   ct.name AS issue_name, z.zone_name, cities.city_name
            FROM complaints c
            JOIN complaint_types ct ON c.issue_type_id = ct.issue_type_id
            JOIN zones z ON c.zone_id = z.zone_id
            JOIN cities ON c.city_id = cities.city_id
            WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL
        """
        params = []
        if city_id and city_id != 'all':
            query += " AND c.city_id = %s"
            params.append(city_id)
        if issue_type_id and issue_type_id != 'all':
            query += " AND c.issue_type_id = %s"
            params.append(issue_type_id)

        cursor.execute(query, tuple(params))
        complaints = cursor.fetchall()

        grouped = defaultdict(lambda: {"count": 0, "details": []})
        for c in complaints:
            key = (round(c["latitude"], 3), round(c["longitude"], 3))
            grouped[key]["count"] += 1
            grouped[key]["details"].append(c)

        response = []
        for (lat, lng), value in grouped.items():
            first = value["details"][0]
            response.append({
                "latitude": lat,
                "longitude": lng,
                "intensity": value["count"],
                "complaint_id": first["complaint_id"],
                "description": first["description"],
                "created_at": first["created_at"],
                "issue_name": first["issue_name"],
                "zone_name": first["zone_name"],
                "city_name": first["city_name"]
            })

        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


@user_bp.route('/user/add-comment/<int:complaint_id>', methods=['GET', 'POST'])
def add_comment(complaint_id):
    if 'user_id' not in session:
        return redirect('/login')

    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='DmKjayeshmysql@155',
            database='quotivate_db'
        )
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            comment = request.form.get('comment')
            if not comment.strip():
                return "⚠️ Comment cannot be empty."

            # Insert the comment
            cursor.execute("""
                INSERT INTO comments (user_id, complaint_id, comment, created_at)
                VALUES (%s, %s, %s, NOW())
            """, (session['user_id'], complaint_id, comment))

            conn.commit()
            return redirect(url_for('user.view_my_complaints'))  # Updated to named route

        return render_template('citizen/add_comment.html', complaint_id=complaint_id)

    except Exception as e:
        return f"❌ Error: {e}"

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@user_bp.route('/user/add-comment-public/<int:complaint_id>', methods=['POST'])
def add_comment_public(complaint_id):
    # Ensure user is logged in
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    comment = request.form.get('comment')
    if not comment:
        return "Comment cannot be empty", 400

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Insert comment into database
        cursor.execute("""
            INSERT INTO comments (user_id, complaint_id, comment, created_at)
            VALUES (%s, %s, %s, NOW())
        """, (user_id, complaint_id, comment))

        conn.commit()

        # Redirect back to the same public complaints page
        return redirect(request.referrer or url_for('user.public_complaints'))

    except Exception as e:
        return f"❌ Error adding comment: {e}"

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
