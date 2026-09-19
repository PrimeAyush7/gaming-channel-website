#!/usr/bin/env python3
import sys
import os
import argparse
import getpass

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import init_db, get_db
from app.services.auth import hash_password

def main():
    init_db()
    parser = argparse.ArgumentParser(description="Create or update an admin user for Nexus Gaming portal.")
    parser.add_argument("--username", help="Admin username")
    parser.add_argument("--password", help="Admin password")
    args = parser.parse_args()

    username = args.username or os.getenv("ADMIN_USERNAME")
    password = args.password or os.getenv("ADMIN_PASSWORD")

    if not username:
        username = input("Enter admin username: ").strip()
    if not password:
        password = getpass.getpass("Enter admin password: ").strip()

    if not username or not password:
        print("Error: Both username and password must be non-empty.")
        sys.exit(1)

    if len(password) < 6:
        print("Error: Password should be at least 6 characters.")
        sys.exit(1)

    pwd_hash, salt = hash_password(password)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM admins WHERE username = ?;", (username,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE admins SET password_hash = ?, salt = ? WHERE id = ?;
            """, (pwd_hash, salt, existing["id"]))
            print(f"✓ Password updated successfully for admin '{username}'.")
        else:
            cursor.execute("""
                INSERT INTO admins (username, password_hash, salt) VALUES (?, ?, ?);
            """, (username, pwd_hash, salt))
            print(f"✓ Admin user '{username}' created successfully!")

if __name__ == "__main__":
    main()
