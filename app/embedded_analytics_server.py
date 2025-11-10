from flask import Flask, render_template, request, redirect
import jwt
import time

app = Flask(__name__)

# Superset configuration
SUPERSET_URL = "http://localhost:8088"
SUPERSET_SECRET_KEY = "your_secret_key_here"

# Map tenant IDs to dashboard IDs
TENANT_DASHBOARDS = {
    "tenant_0": 1,
    "tenant_1": 2,
    # ... etc
}


@app.route("/analytics/<tenant_id>")
def tenant_analytics(tenant_id):
    """Serve embedded analytics for a specific tenant"""

    # In production, verify the user is authorized to see this tenant's data
    # For demo, we'll just generate the token

    dashboard_id = TENANT_DASHBOARDS.get(tenant_id)

    if not dashboard_id:
        return "Tenant not found", 404

    # Generate JWT for Superset guest token
    payload = {
        "user": {
            "username": f"guest_{tenant_id}",
            "first_name": "Guest",
            "last_name": "User",
        },
        "resources": [{"type": "dashboard", "id": str(dashboard_id)}],
        "rls": [],  # RLS handled at DB level
        "exp": int(time.time()) + 300,  # Token expires in 5 minutes
    }

    token = jwt.encode(payload, SUPERSET_SECRET_KEY, algorithm="HS256")

    embed_url = f"{SUPERSET_URL}/guest_token/{token}"

    return render_template("analytics.html", embed_url=embed_url, tenant_id=tenant_id)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
