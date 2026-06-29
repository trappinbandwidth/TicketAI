#!/usr/bin/env python3
"""
Set Firebase custom claims for staff/reviewer/admin users.

Usage:
  python scripts/set_staff_role.py <email> <role>

Roles: reviewer | staff | admin | super_admin

Requires Application Default Credentials or FIREBASE_SERVICE_ACCOUNT_JSON.
"""
import sys
import os


def main():
    if len(sys.argv) != 3:
        print("Usage: python set_staff_role.py <email> <role>")
        print("Roles: reviewer | staff | admin | super_admin")
        sys.exit(1)

    email = sys.argv[1]
    role = sys.argv[2]

    valid_roles = {"reviewer", "staff", "admin", "super_admin"}
    if role not in valid_roles:
        print(f"Invalid role '{role}'. Must be one of: {', '.join(sorted(valid_roles))}")
        sys.exit(1)

    # Initialize Firebase Admin
    project_id = os.getenv("FIREBASE_PROJECT_ID", "rigresolve")
    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

    import firebase_admin
    from firebase_admin import credentials, auth

    if not firebase_admin._apps:
        if service_account_json:
            import json
            cred = credentials.Certificate(json.loads(service_account_json))
        else:
            cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {"projectId": project_id})

    try:
        user = auth.get_user_by_email(email)
    except auth.UserNotFoundError:
        print(f"Error: No Firebase user with email '{email}'.")
        sys.exit(1)

    auth.set_custom_user_claims(user.uid, {"role": role})
    print(f"✓ Set role='{role}' for {email} (uid={user.uid})")
    print("The user must sign out and back in for the new claim to take effect.")


if __name__ == "__main__":
    main()
