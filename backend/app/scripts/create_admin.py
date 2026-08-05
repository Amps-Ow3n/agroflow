from app.core.db import get_db
from app.core.auth import hash_password
from getpass import getpass

name = input("Admin name: ")
email = input("Admin email: ")
password = getpass("Password: ")
hashed_password = hash_password(password)

conn, cursor = get_db()
cursor.execute("""
INSERT INTO users
(
    name,
    email,
    password,
    role
)
VALUES
(
    %s,
    %s,
    %s,
    %s
)
""",
(
    name,
    email,
    hashed_password,
    "admin"
))

conn.commit()
conn.close()
print("Admin created successfully.")