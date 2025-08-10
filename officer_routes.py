from flask import Blueprint, request, jsonify, render_template, session, redirect
import mysql.connector
import os
from shapely.geometry import Point, shape
import json
from werkzeug.utils import secure_filename
from config import get_connection
from collections import defaultdict

officer_bp = Blueprint('officer', __name__)

@officer_bp.route('/officer/update-status/<int:complaint_id>', methods=['GET', 'POST'])
def update_status(complaint_id):
    if 'officer_id' not in session:
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
            new_status = request.form.get('status')
            remarks = request.form.get('remarks')

            # Step 1: Fetch the current status before updating
            cursor.execute("SELECT status FROM complaints WHERE complaint_id = %s", (complaint_id,))
            result = cursor.fetchone()
            if not result:
                return "❌ Complaint not found", 404

            previous_status = result['status']

            # Step 2: Update status in complaints table
            cursor.execute("""
                UPDATE complaints 
                SET status = %s, last_updated = NOW()
                WHERE complaint_id = %s
            """, (new_status, complaint_id))

            # Step 3: Log this status change in complaint_logs
            cursor.execute("""
                INSERT INTO complaint_logs (complaint_id, changed_by_id, old_status, new_status, remarks, timestamp)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (complaint_id, session['officer_id'], previous_status, new_status, remarks))

            conn.commit()
            return redirect('/officer/view-complaints')

        # If it's a GET request — fetch current complaint info
        cursor.execute("SELECT complaint_id, status FROM complaints WHERE complaint_id = %s", (complaint_id,))
        complaint = cursor.fetchone()

        return render_template('officer/update_status.html', complaint=complaint)

    except Exception as e:
        return f"Error: {e}", 500

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


@officer_bp.route('/officer/view-comments/<int:complaint_id>')
def view_comments(complaint_id):
    if 'officer_id' not in session:
        return redirect('/login')

    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='DmKjayeshmysql@155',
            database='quotivate_db'
        )
        cursor = conn.cursor(dictionary=True)

        # Fetch comments for the complaint
        cursor.execute("""
            SELECT c.comment, c.created_at, u.name as user_name
            FROM comments c
            JOIN users u ON c.user_id = u.user_id
            WHERE c.complaint_id = %s
            ORDER BY c.created_at DESC
        """, (complaint_id,))
        comments = cursor.fetchall()

        return render_template('officer/view_comments.html', comments=comments, complaint_id=complaint_id)

    except Exception as e:
        return f"Error: {e}"

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


@officer_bp.route('/officer/view-timeline/<int:complaint_id>')
def view_timeline(complaint_id):
    if 'officer_id' not in session:
        return redirect('/login')

    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='DmKjayeshmysql@155',
            database='quotivate_db'
        )
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                cl.*, 
                o.name AS officer_name, 
                u.name AS user_name,
                a.name AS admin_name
            FROM complaint_logs cl
            LEFT JOIN officers o ON cl.changed_by_id = o.officer_id
            LEFT JOIN users u ON cl.changed_by_id = u.user_id
            LEFT JOIN admins a ON cl.changed_by_id = a.admin_id
            WHERE cl.complaint_id = %s
            ORDER BY cl.timestamp ASC
        """, (complaint_id,))
        logs = cursor.fetchall()

        return render_template('officer/view_timeline.html', logs=logs, complaint_id=complaint_id)

    except Exception as e:
        return f"Error: {e}"

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


@officer_bp.route('/officer/view-complaints')
def view_assigned_complaints():
    if 'officer_id' not in session:
        return redirect('/login')

    try:
        officer_id = session['officer_id']
        status_filter = request.args.get('status')  # optional: 'Pending', 'In Progress', 'Resolved'
        city_filter = request.args.get('city_id')
        issue_filter = request.args.get('issue_type_id')

        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='DmKjayeshmysql@155',  # ✅ replace this with actual password
            database='quotivate_db'
        )
        cursor = conn.cursor(dictionary=True)

        # Fetch cities and issues for filters
        cursor.execute("""
            SELECT DISTINCT ci.city_id, ci.city_name 
            FROM officer_city_issues oci
            JOIN cities ci ON oci.city_id = ci.city_id
            WHERE oci.officer_id = %s
        """, (officer_id,))
        cities = cursor.fetchall()

        cursor.execute("""
            SELECT DISTINCT ct.issue_type_id, ct.name 
            FROM officer_city_issues oci
            JOIN complaint_types ct ON oci.issue_type_id = ct.issue_type_id
            WHERE oci.officer_id = %s
        """, (officer_id,))
        issues = cursor.fetchall()

        # Get assigned complaints
        base_query = """
            SELECT c.*, ct.name AS issue_name, z.zone_name, ci.city_name
            FROM complaints c
            JOIN complaint_types ct ON c.issue_type_id = ct.issue_type_id
            JOIN zones z ON c.zone_id = z.zone_id
            JOIN cities ci ON c.city_id = ci.city_id
            WHERE c.assigned_officer_id = %s
        """
        values = [officer_id]

        if status_filter and status_filter.lower() != "all":
            base_query += " AND c.status = %s"
            values.append(status_filter)

        if city_filter:
            base_query += " AND c.city_id = %s"
            values.append(city_filter)

        if issue_filter:
            base_query += " AND c.issue_type_id = %s"
            values.append(issue_filter)

        base_query += " ORDER BY c.created_at DESC"

        cursor.execute(base_query, tuple(values))
        complaints = cursor.fetchall()

        return render_template(
            'officer/view_complaints.html',
            complaints=complaints,
            cities=cities,
            issues=issues,
            selected_status=status_filter,
            selected_city=city_filter,
            selected_issue=issue_filter
        )

    except Exception as e:
        return f"Error loading complaints: {e}", 500

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


@officer_bp.route('/officer/dashboard')
def officer_dashboard():
    if 'officer_id' not in session:
        return redirect('/login')
    return render_template('officer/dashboard_officer.html')  # your officer panel page

@officer_bp.route('/officer/performance')
def officer_performance():
    if 'officer_id' not in session:
        return redirect('/login')
    return "<h3>🚧 Officer Performance Report – Coming Soon</h3>"


@officer_bp.route('/officer/performance')
def officer_performance_view():  # ✅ NEW name
    return render_template('officer/performance.html')

@officer_bp.route('/officer/complaint-heatmap')
def officer_heatmap_view():  # ✅ Different name
    return render_template('officer/complaint_heatmap.html')


@officer_bp.route('/officer/complaint-heatmap')
def complaint_heatmap():
    if 'officer_id' not in session:
        return redirect('/login')
    return render_template('officer/complaint_heatmap.html')


@officer_bp.route('/officer/api/complaint-heatmap')
def get_officer_heatmap_data():
    if 'officer_id' not in session:
        return jsonify({"error": "Unauthorized"}), 403

    officer_id = session['officer_id']
    status = request.args.get('status')

    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='DmKjayeshmysql@155',
            database='quotivate_db'
        )
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT 
                c.complaint_id,
                c.latitude,
                c.longitude,
                c.description,
                c.created_at,
                c.status,
                ct.name AS issue_name,
                z.zone_name,
                cities.city_name
            FROM complaints c
            JOIN complaint_types ct ON c.issue_type_id = ct.issue_type_id
            JOIN zones z ON c.zone_id = z.zone_id
            JOIN cities ON c.city_id = cities.city_id
            WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL
              AND c.assigned_officer_id = %s
        """
        params = [officer_id]

        if status and status != 'all':
            query += " AND c.status = %s"
            params.append(status)

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
                "city_name": first["city_name"],
                "status": first["status"]
            })

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


