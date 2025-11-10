"""
Guest Token Service - Generate Superset guest tokens for embedded analytics
"""

import os
import jwt
import time
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class GuestTokenService:
    """
    Service for generating Superset guest tokens with tenant context

    Guest tokens allow embedding Superset dashboards with:
    - Tenant-specific RLS filters
    - Time-limited access
    - No user authentication required
    """

    def __init__(self):
        self.superset_url = os.getenv("SUPERSET_URL", "http://superset:8088")
        self.secret_key = os.getenv(
            "SUPERSET_SECRET_KEY", "superset_secret_key_change_me_in_production"
        )
        self.token_expiration = int(
            os.getenv("GUEST_TOKEN_EXPIRATION", 300)
        )  # 5 minutes

    def generate_token(
        self,
        tenant_id: str,
        user_email: str,
        dashboard_id: Optional[int] = None,
        rls_rules: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Generate a JWT guest token for Superset embedded analytics

        Args:
            tenant_id: UUID of the tenant
            user_email: Email of the user accessing the dashboard
            dashboard_id: Optional specific dashboard ID to embed
            rls_rules: Optional custom RLS rules (overrides tenant default)

        Returns:
            Dictionary with token and dashboard URL
        """
        try:
            # Current timestamp
            now = int(time.time())

            # Build RLS rules for tenant isolation
            if not rls_rules:
                rls_rules = [
                    {
                        "clause": f"tenant_id = '{tenant_id}'",
                    }
                ]

            # Guest token payload
            payload = {
                "user": {
                    "username": user_email,
                    "first_name": user_email.split("@")[0],
                    "last_name": "Guest",
                },
                "resources": [
                    {
                        "type": "dashboard",
                        "id": str(dashboard_id)
                        if dashboard_id
                        else "1",  # Default dashboard
                    }
                ],
                "rls": rls_rules,
                "iat": now,
                "exp": now + self.token_expiration,
                "aud": "superset",
                "type": "guest",
            }

            # Generate JWT token
            token = jwt.encode(payload, self.secret_key, algorithm="HS256")

            # Build dashboard URL
            dashboard_url = self._build_dashboard_url(dashboard_id, token)

            logger.info(
                f"Generated guest token for tenant {tenant_id}, user {user_email}"
            )

            return {
                "token": token,
                "dashboard_url": dashboard_url,
                "expires_in": self.token_expiration,
            }

        except Exception as e:
            logger.error(f"Error generating guest token: {str(e)}")
            return {"error": str(e)}

    def _build_dashboard_url(self, dashboard_id: Optional[int], token: str) -> str:
        """
        Build the embedded dashboard URL with guest token

        Args:
            dashboard_id: Dashboard ID to embed
            token: JWT guest token

        Returns:
            Full URL for embedded dashboard
        """
        dashboard_id = dashboard_id or 1

        # Superset guest token URL format
        url = f"{self.superset_url}/guest_token"

        # In production, you'd use the actual embedded dashboard endpoint:
        # url = f"{self.superset_url}/superset/dashboard/{dashboard_id}/?guest_token={token}"

        return url

    def validate_token(self, token: str) -> Optional[Dict]:
        """
        Validate and decode a guest token

        Args:
            token: JWT guest token to validate

        Returns:
            Decoded token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token, self.secret_key, algorithms=["HS256"], audience="superset"
            )
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            return None

    def refresh_token(
        self, old_token: str, extend_seconds: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Refresh an existing guest token

        Args:
            old_token: Current token to refresh
            extend_seconds: Optional seconds to extend (default: use configured expiration)

        Returns:
            New token data if successful
        """
        try:
            # Decode old token (allow expired for refresh)
            payload = jwt.decode(
                old_token,
                self.secret_key,
                algorithms=["HS256"],
                options={"verify_exp": False},
            )

            # Extract tenant_id from RLS rules
            tenant_id = None
            if payload.get("rls") and len(payload["rls"]) > 0:
                clause = payload["rls"][0].get("clause", "")
                # Parse tenant_id from clause: "tenant_id = 'uuid'"
                if "=" in clause:
                    tenant_id = clause.split("=")[1].strip().strip("'")

            if not tenant_id:
                logger.error("Cannot extract tenant_id from token")
                return None

            # Extract dashboard_id
            dashboard_id = None
            if payload.get("resources") and len(payload["resources"]) > 0:
                resource = payload["resources"][0]
                if resource.get("type") == "dashboard":
                    dashboard_id = int(resource.get("id", 1))

            # Generate new token
            return self.generate_token(
                tenant_id=tenant_id,
                user_email=payload["user"]["username"],
                dashboard_id=dashboard_id,
                rls_rules=payload.get("rls"),
            )

        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            return None
