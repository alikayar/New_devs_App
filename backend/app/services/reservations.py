from decimal import Decimal
from typing import Any, Dict


async def calculate_monthly_revenue(
    property_id: str,
    tenant_id: str,
    month: int,
    year: int,
    db_session=None,
) -> Dict[str, Any]:
    """Return check-in month revenue and reservation count by currency."""
    from sqlalchemy import text

    query = text("""
        WITH period AS (
            SELECT
                make_date(:year, :month, 1)::timestamp AS start_local,
                (make_date(:year, :month, 1) + INTERVAL '1 month')::timestamp AS end_local
        )
        SELECT UPPER(COALESCE(r.currency, 'UNKNOWN')) AS currency,
               SUM(r.total_amount) AS total_revenue,
               COUNT(*) AS reservation_count
        FROM reservations AS r
        JOIN properties AS p
          ON p.id = r.property_id AND p.tenant_id = r.tenant_id
        CROSS JOIN period
        WHERE r.property_id = :property_id
          AND r.tenant_id = :tenant_id
          AND r.check_in_date >= (period.start_local AT TIME ZONE p.timezone)
          AND r.check_in_date < (period.end_local AT TIME ZONE p.timezone)
        GROUP BY UPPER(COALESCE(r.currency, 'UNKNOWN'))
    """)
    params = {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "month": month,
        "year": year,
    }

    async def calculate(session) -> Dict[str, Any]:
        result = await session.execute(query, params)
        rows = result.all()
        return {
            "revenue_by_currency": {
                row.currency: str(Decimal(str(row.total_revenue)))
                for row in rows
            },
            "count": sum(row.reservation_count for row in rows),
        }

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
    """Return property revenue grouped by currency and its reservation count."""
    from sqlalchemy import text
    from app.core.database_pool import db_pool

    if db_pool.session_factory is None:
        await db_pool.initialize()
    if db_pool.session_factory is None:
        raise RuntimeError("Database pool is not available")

    query = text("""
        SELECT UPPER(COALESCE(currency, 'UNKNOWN')) AS currency,
               SUM(total_amount) AS total_revenue,
               COUNT(*) AS reservation_count
        FROM reservations
        WHERE property_id = :property_id AND tenant_id = :tenant_id
        GROUP BY UPPER(COALESCE(currency, 'UNKNOWN'))
    """)
    async with db_pool.get_session() as session:
        result = await session.execute(query, {
            "property_id": property_id,
            "tenant_id": tenant_id,
        })
        rows = result.all()

    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "revenue_by_currency": {
            row.currency: str(Decimal(str(row.total_revenue)))
            for row in rows
        },
        "count": sum(row.reservation_count for row in rows),
    }
