import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="DmKjayeshmysql@155",
        database="quotivate_db"
    )
