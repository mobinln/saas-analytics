"""
API Service - Tenant Provisioning and Guest Token Generation
FastAPI service for managing tenants and generating Superset guest tokens
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
import logging

from tenant_service import TenantService
from guest_token_service import GuestTokenService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Multi-Tenant Analytics API",
    description="API for tenant provisioning and embedded analytics",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services
tenant_service = TenantService()
guest_token_service = GuestTokenService()


# Request/Response models
class TenantCreate(BaseModel):
    tenant_name: str = Field(..., min_length=3, max_length=255)
    tier: str = Field(default="standard", pattern="^(standard|premium|enterprise)$")
    industry: Optional[str] = None
    seats: Optional[int] = Field(default=10, ge=1)


class TenantResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    tier: str
    status: str
    created_at: str
    metadata: dict


class GuestTokenRequest(BaseModel):
    tenant_id: str
    user_email: str
    dashboard_id: Optional[int] = None
    rls_rules: Optional[List[dict]] = None


class GuestTokenResponse(BaseModel):
    token: str
    dashboard_url: str
    expires_in: int


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "multi-tenant-analytics-api",
        "version": "1.0.0",
    }


# Tenant endpoints
@app.post("/api/v1/tenants", response_model=TenantResponse, status_code=201)
async def create_tenant(tenant: TenantCreate):
    """
    Create a new tenant

    This provisions:
    1. Tenant record in database
    2. RLS policies in PostgreSQL
    3. RLS rules in Superset
    """
    try:
        logger.info(f"Creating tenant: {tenant.tenant_name}")

        # Create tenant in database
        tenant_data = tenant_service.create_tenant(
            tenant_name=tenant.tenant_name,
            tier=tenant.tier,
            metadata={"industry": tenant.industry, "seats": tenant.seats},
        )

        if "error" in tenant_data:
            raise HTTPException(status_code=400, detail=tenant_data["error"])

        logger.info(f"Tenant created successfully: {tenant_data['tenant_id']}")

        return TenantResponse(**tenant_data)

    except Exception as e:
        logger.error(f"Error creating tenant: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: str):
    """Get tenant by ID"""
    try:
        tenant_data = tenant_service.get_tenant(tenant_id)

        if not tenant_data:
            raise HTTPException(status_code=404, detail="Tenant not found")

        return TenantResponse(**tenant_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tenant: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/tenants", response_model=List[TenantResponse])
async def list_tenants(status: Optional[str] = None, tier: Optional[str] = None):
    """List all tenants with optional filters"""
    try:
        tenants = tenant_service.list_tenants(status=status, tier=tier)
        return [TenantResponse(**t) for t in tenants]

    except Exception as e:
        logger.error(f"Error listing tenants: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/tenants/{tenant_id}", status_code=204)
async def delete_tenant(tenant_id: str):
    """
    Delete (deactivate) a tenant

    This:
    1. Sets tenant status to 'inactive'
    2. Removes RLS rules in Superset
    """
    try:
        success = tenant_service.delete_tenant(tenant_id)

        if not success:
            raise HTTPException(status_code=404, detail="Tenant not found")

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tenant: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Guest token endpoints
@app.post("/api/v1/guest-token", response_model=GuestTokenResponse)
async def generate_guest_token(request: GuestTokenRequest):
    """
    Generate a Superset guest token for embedded analytics

    The token includes:
    1. Tenant context for RLS
    2. User identity
    3. Dashboard access permissions
    4. Expiration (5 minutes)
    """
    try:
        logger.info(f"Generating guest token for tenant: {request.tenant_id}")

        # Verify tenant exists
        tenant = tenant_service.get_tenant(request.tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Generate guest token
        token_data = guest_token_service.generate_token(
            tenant_id=request.tenant_id,
            user_email=request.user_email,
            dashboard_id=request.dashboard_id,
            rls_rules=request.rls_rules,
        )

        if "error" in token_data:
            raise HTTPException(status_code=400, detail=token_data["error"])

        logger.info(f"Guest token generated successfully for {request.user_email}")

        return GuestTokenResponse(**token_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating guest token: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Analytics endpoints
@app.get("/api/v1/tenants/{tenant_id}/usage")
async def get_tenant_usage(tenant_id: str, days: int = 7):
    """
    Get usage metrics for a tenant

    Returns aggregated event data for the specified time period
    """
    try:
        usage_data = tenant_service.get_tenant_usage(tenant_id, days)

        if "error" in usage_data:
            raise HTTPException(status_code=400, detail=usage_data["error"])

        return usage_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tenant usage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/tenants/{tenant_id}/cost")
async def get_tenant_cost(tenant_id: str, days: int = 30):
    """
    Get cost attribution for a tenant

    Returns estimated query costs based on resource usage
    """
    try:
        cost_data = tenant_service.get_tenant_cost(tenant_id, days)

        if "error" in cost_data:
            raise HTTPException(status_code=400, detail=cost_data["error"])

        return cost_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tenant cost: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
