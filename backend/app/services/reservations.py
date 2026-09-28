from decimal import Decimal
from typing import Any, Dict


async def calculate_monthly_revenue(
    property_id: str,
    tenant_id: str,
    month: int,
    year: int,
    db_session=None,
) -> Decimal:
    """Sum reservation totals for check-ins in the property's local month."""
    from sqlalchemy import text

    query = text("""
        WITH period AS (
            SELECT
                make_date(:year, :month, 1)::timestamp AS start_local,
                (make_date(:year, :month, 1) + INTERVAL '1 month')::timestamp AS end_local
        )
        SELECT COALESCE(SUM(r.total_amount), 0)
        FROM reservations AS r
        JOIN properties AS p
          ON p.id = r.property_id AND p.tenant_id = r.tenant_id
        CROSS JOIN period
        WHERE r.property_id = :property_id
          AND r.tenant_id = :tenant_id
          AND r.check_in_date >= (period.start_local AT TIME ZONE p.timezone)
          AND r.check_in_date < (period.end_local AT TIME ZONE p.timezone)
    """)
    params = {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "month": month,
        "year": year,
    }

    async def calculate(session) -> Decimal:
        result = await session.execute(query, params)
        return Decimal(str(result.scalar_one()))

    if db_session is not None:
        return await calculate(db_session)

    from app.core.database_pool import db_pool

    if db_pool.session_factory is None:
        await db_pool.initialize()
    if db_pool.session_factory is None:
        raise RuntimeError("Database pool is not available")

    async with db_pool.get_session() as session:
        return await calculate(session)


async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """Aggregate revenue and reservation count for a tenant's property."""
    from sqlalchemy import text
    from app.core.database_pool import db_pool

    if db_pool.session_factory is None:
        await db_pool.initialize()
    if db_pool.session_factory is None:
        raise RuntimeError("Database pool is not available")

    query = text("""
        SELECT COALESCE(SUM(total_amount), 0) AS total_revenue,
               COUNT(*) AS reservation_count
        FROM reservations
        WHERE property_id = :property_id AND tenant_id = :tenant_id
    """)
    async with db_pool.get_session() as session:
        result = await session.execute(query, {
            "property_id": property_id,
            "tenant_id": tenant_id,
        })
        row = result.one()

    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": str(Decimal(str(row.total_revenue))),
        "currency": "USD",
        "count": row.reservation_count,
    }
