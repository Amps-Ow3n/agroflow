from getpass import getpass
from app.core.db import get_db
from app.core.auth import hash_password

name=input("Admin name: ").strip()
email=input("Admin email: ").strip()
password=getpass("Password: ")
conn,cursor=get_db()
try:
    cursor.execute("INSERT INTO users(name,email,password,status,is_system_admin) VALUES(%s,%s,%s,'ACTIVE',TRUE)", (name,email,hash_password(password)))
    conn.commit()
    print("System administrator created successfully.")
except Exception:
    conn.rollback(); raise
finally:
    conn.close()
