from werkzeug.security import generate_password_hash, check_password_hash
from config import get_connection

class UserModel:
    @staticmethod
    def create_user(name, email, phone, password):
        conn = get_connection()
        cursor = conn.cursor()
        hashed_pw = generate_password_hash(password)

        query = """INSERT INTO users (name, email, phone, password_hash)
                   VALUES (%s, %s, %s, %s)"""
        cursor.execute(query, (name, email, phone, hashed_pw))
        conn.commit()
        cursor.close()
        conn.close()

    @staticmethod
    def get_user_by_email(email):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM users WHERE email = %s"
        cursor.execute(query, (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user

    @staticmethod
    def verify_password(stored_hash, password):
        return check_password_hash(stored_hash, password)

    @staticmethod
    def get_user_by_id(user_id):
        db = get_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        db.close()
        return user
