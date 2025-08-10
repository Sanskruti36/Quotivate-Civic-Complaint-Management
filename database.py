import mysql.connector

def get_db_connection():
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='DmKjayeshmysql@155',
        database='quotivate_db'
    )
    return conn