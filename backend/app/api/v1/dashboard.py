from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from app.services.cache import get_revenue_summary
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()

@router.get("/properties")
async def get_properties(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    from sqlalchemy import text
    from app.core.database_pool import db_pool

    tenant_id = getattr(current_user, "tenant_id", "default_tenant") or "default_tenant"

    if db_pool.session_factory is None:
        await db_pool.initialize()
    if db_pool.session_factory is None:
        raise RuntimeError("Database pool is not available")

    query = text("""
        SELECT id, name
        FROM properties
        WHERE tenant_id = :tenant_id
        ORDER BY id
    """)
    async with db_pool.get_session() as session:
        result = await session.execute(query, {"tenant_id": tenant_id})
        properties = result.all()

    items = [{"id": row.id, "name": row.name} for row in properties]
    return {"items": items, "total": len(items)}

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    
    tenant_id = getattr(current_user, "tenant_id", "default_tenant") or "default_tenant"
    
    revenue_data = await get_revenue_summary(property_id, tenant_id)
    
    return {
        "property_id": revenue_data['property_id'],
        "revenue_by_currency": revenue_data['revenue_by_currency'],
        "reservations_count": revenue_data['count']
    }
