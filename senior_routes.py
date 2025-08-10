from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db_connection

senior_bp = Blueprint("senior", __name__, url_prefix="/senior")

# 🛠 Manage Complaint Types (Add + Edit + Delete with safety + friendly messages)
@senior_bp.route('/complaint-types', methods=['GET', 'POST'])
def manage_complaint_types():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if request.method == 'POST':
            # 🔴 Handle Delete
            if 'delete_id' in request.form:
                delete_id = request.form['delete_id']

                # Check if in complaints
                cursor.execute("SELECT COUNT(*) AS count FROM complaints WHERE issue_type_id = %s", (delete_id,))
                complaint_count = cursor.fetchone()['count']

                if complaint_count > 0:
                    flash("❌ Cannot delete. This complaint type is used in registered complaints.", "danger")
                else:
                    try:
                        # Delete from SLA config (if any)
                        cursor.execute("DELETE FROM sla_config WHERE issue_type_id = %s", (delete_id,))
                        # Delete from complaint_types
                        cursor.execute("DELETE FROM complaint_types WHERE issue_type_id = %s", (delete_id,))
                        conn.commit()
                        flash("✅ Complaint type deleted successfully!", "success")
                    except Exception as db_err:
                        if "foreign key constraint fails" in str(db_err).lower():
                            flash("❌ Cannot delete. This issue type is assigned to officers. Please unassign it first.", "danger")
                        else:
                            raise db_err

                return redirect(url_for('senior.manage_complaint_types'))

            # 🟢 Handle Add/Edit
            name = request.form.get('issue_name', '').strip()
            description = request.form.get('description', '').strip() or None
            issue_type_id = request.form.get('issue_type_id')

            if not name:
                flash("⚠️ Issue type name cannot be empty.", "warning")
            else:
                if issue_type_id:  # Edit
                    cursor.execute("""
                        UPDATE complaint_types
                        SET name = %s, description = %s
                        WHERE issue_type_id = %s
                    """, (name, description, issue_type_id))
                    flash("✅ Complaint type updated successfully!", "success")
                else:  # Add
                    cursor.execute("""
                        INSERT INTO complaint_types (name, description)
                        VALUES (%s, %s)
                    """, (name, description))
                    flash("✅ New complaint type added!", "success")

                conn.commit()
                return redirect(url_for('senior.manage_complaint_types'))

        # 📦 Fetch for display
        cursor.execute("SELECT * FROM complaint_types ORDER BY issue_type_id")
        complaint_types = cursor.fetchall()

    except Exception as e:
        conn.rollback()
        flash("❌ Unexpected error. Please try again or contact admin.", "danger")
        complaint_types = []

    finally:
        conn.close()

    return render_template('senior_officer/complaint_types.html', complaint_types=complaint_types)


# ⏱ SLA Configuration – Per-state SLA for each issue type
@senior_bp.route('/sla-config', methods=['GET', 'POST'])
def sla_config():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 🏛 Get the current senior officer's state_id (ensure this is stored in session at login)
    state_id = session.get('state_id')
    if not state_id:
        flash("State context missing. Please log in again.", "danger")
        return redirect(url_for('auth.logout'))

    try:
        # 🔄 Handle SLA update
        if request.method == 'POST':
            issue_type_id = request.form.get('issue_type_id')
            sla_hours = request.form.get('sla_hours')

            if not issue_type_id or not sla_hours:
                flash("Both fields are required.", "warning")
            else:
                cursor.execute("""
                    INSERT INTO sla_config (state_id, issue_type_id, sla_hours)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE sla_hours = %s
                """, (state_id, issue_type_id, sla_hours, sla_hours))
                conn.commit()
                flash("✅ SLA updated successfully!", "success")
            return redirect(url_for('senior.sla_config'))

        # 📥 Fetch all complaint types with existing SLA (if any) for this state
        cursor.execute("""
            SELECT 
                ct.issue_type_id, 
                ct.name AS issue_name, 
                sc.sla_hours
            FROM 
                complaint_types ct
            LEFT JOIN 
                sla_config sc 
            ON 
                ct.issue_type_id = sc.issue_type_id AND sc.state_id = %s
            ORDER BY 
                ct.issue_type_id
        """, (state_id,))
        data = cursor.fetchall()

    except Exception as e:
        conn.rollback()
        flash(f"❌ Unexpected error: {str(e)}", "danger")
        data = []

    finally:
        conn.close()

    return render_template('senior_officer/sla_config.html', data=data)
