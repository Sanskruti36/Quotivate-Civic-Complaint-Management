import mysql.connector

# Connect to database
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="DmKjayeshmysql@155",  # 🔁 Replace with your actual password
    database="quotivate_db"
)

cursor = conn.cursor()

# Get all cities with their IDs
cursor.execute("SELECT city_id, city_name FROM cities")
cities = cursor.fetchall()

# Get all issue types
cursor.execute("SELECT issue_type_id, name FROM complaint_types ORDER BY issue_type_id")
issue_types = cursor.fetchall()

# Get all officers with 'officer' role
cursor.execute("SELECT officer_id, name, email FROM officers WHERE role = 'officer'")
officers = cursor.fetchall()

# Map officers to city based on their name or email
city_officers = {}

for city_id, city_name in cities:
    city_key = city_name.lower()  # e.g., 'pune', 'bangalore'
    city_officers[city_id] = []

    for officer in officers:
        officer_id, officer_name, officer_email = officer
        if city_key in officer_name.lower() or city_key in officer_email.lower():
            city_officers[city_id].append((officer_id, officer_name))

# Assign officers to issue types
for city_id in city_officers:
    matched_officers = city_officers[city_id]

    if len(matched_officers) < len(issue_types):
        print(f"❌ Not enough officers found for city_id {city_id}. Skipping...")
        continue

    for i, issue in enumerate(issue_types):
        issue_type_id = issue[0]
        officer_id = matched_officers[i][0]

        try:
            cursor.execute("""
                INSERT INTO officer_city_issues (officer_id, city_id, issue_type_id)
                VALUES (%s, %s, %s)
            """, (officer_id, city_id, issue_type_id))
        except mysql.connector.Error as err:
            print(f"⚠️ Error assigning officer {officer_id} for city {city_id}, issue {issue_type_id}: {err}")

# Finalize
conn.commit()
cursor.close()
conn.close()

print("✅ Officer-city-issue assignments completed based on city name mapping.")
