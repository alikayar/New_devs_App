import unittest
import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import text

from app.core.database_pool import db_pool
from app.api.v1.dashboard import get_properties
from app.services.reservations import calculate_monthly_revenue, calculate_total_revenue


class RevenueCacheIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_property_id_uses_separate_tenant_cache_entries(self):
        class MemoryRedis:
            def __init__(self):
                self.values = {}

            async def get(self, key):
                return self.values.get(key)

            async def setex(self, key, _ttl, value):
                self.values[key] = value

        redis = MemoryRedis()
        revenue = AsyncMock(side_effect=[
            {"property_id": "prop-001", "tenant_id": "tenant-a", "revenue_by_currency": {"USD": "2250.000"}, "count": 4},
            {"property_id": "prop-001", "tenant_id": "tenant-b", "revenue_by_currency": {}, "count": 0},
        ])

        with patch("app.services.cache.redis_client", redis), patch(
            "app.services.reservations.calculate_total_revenue", revenue
        ):
            from app.services.cache import get_revenue_summary

            sunset = await get_revenue_summary("prop-001", "tenant-a")
            ocean = await get_revenue_summary("prop-001", "tenant-b")
            sunset_cached = await get_revenue_summary("prop-001", "tenant-a")
            ocean_cached = await get_revenue_summary("prop-001", "tenant-b")

        self.assertEqual(sunset["revenue_by_currency"], {"USD": "2250.000"})
        self.assertEqual(ocean["revenue_by_currency"], {})
        self.assertEqual(sunset_cached, sunset)
        self.assertEqual(ocean_cached, ocean)
        self.assertEqual(revenue.await_count, 2)
        self.assertIn("revenue:tenant-a:prop-001", redis.values)
        self.assertIn("revenue:tenant-b:prop-001", redis.values)


class SeededRevenueRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.loop)
        cls.loop.run_until_complete(cls.initialize_pool())

    @classmethod
    async def initialize_pool(cls):
        if db_pool.session_factory is None:
            await db_pool.initialize()
        if db_pool.session_factory is None:
            raise RuntimeError("Database pool must be available")

    @classmethod
    def tearDownClass(cls):
        cls.loop.run_until_complete(db_pool.close())
        cls.loop.close()
        asyncio.set_event_loop(None)

    def test_paris_timezone_boundary_is_in_march(self):
        result = self.loop.run_until_complete(
            calculate_monthly_revenue("prop-001", "tenant-a", 3, 2024)
        )

        self.assertEqual(result["revenue_by_currency"], {"USD": "2250.000"})
        self.assertEqual(result["count"], 4)

    def test_fractional_reservations_sum_without_float_rounding(self):
        result = self.loop.run_until_complete(
            calculate_total_revenue("prop-001", "tenant-a")
        )

        self.assertEqual(result["revenue_by_currency"]["USD"], "2250.000")
        self.assertEqual(
            Decimal(result["revenue_by_currency"]["USD"]) - Decimal("1250.000"),
            Decimal("1000.000"),
        )

        async def get_decimal_total():
            async with db_pool.get_session() as session:
                decimal_sum = await session.execute(text("""
                    SELECT SUM(total_amount)
                    FROM reservations
                    WHERE id IN ('res-dec-1', 'res-dec-2', 'res-dec-3')
                      AND tenant_id = 'tenant-a'
                """))
                return decimal_sum.scalar_one()

        decimal_total = self.loop.run_until_complete(get_decimal_total())

        self.assertEqual(decimal_total, Decimal("1000.000"))

    def test_property_list_is_scoped_to_tenant(self):
        async def get_tenant_properties():
            sunset = await get_properties(SimpleNamespace(tenant_id="tenant-a"))
            ocean = await get_properties(SimpleNamespace(tenant_id="tenant-b"))
            return sunset["items"], ocean["items"]

        sunset, ocean = self.loop.run_until_complete(get_tenant_properties())

        self.assertIn({"id": "prop-001", "name": "Beach House Alpha"}, sunset)
        self.assertNotIn({"id": "prop-001", "name": "Mountain Lodge Beta"}, sunset)
        self.assertIn({"id": "prop-001", "name": "Mountain Lodge Beta"}, ocean)
        self.assertNotIn({"id": "prop-001", "name": "Beach House Alpha"}, ocean)


if __name__ == "__main__":
    unittest.main()
