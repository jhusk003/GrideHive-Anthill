import unittest

from gridhive_core import (
    ASSETS,
    scenario,
    outage_states,
    affected_customers,
    repair_gain,
    repair_plan,
    verified_max
)


class TestGridHive(unittest.TestCase):

    def test_unique_leaf_customers(self):
        self.assertEqual(
            sum(n["customers"] for n in ASSETS),
            5750
        )

        self.assertTrue(all(
            n["customers"] == 0
            for n in ASSETS
            if n["kind"] != "Service zone"
        ))

    def test_storm_exposure_increases(self):
        low = scenario(1, "Miami coast")
        high = scenario(5, "Miami coast")

        self.assertTrue(all(
            b["risk"] >= a["risk"]
            for a, b in zip(low, high)
        ))

    def test_upstream_failure_propagates(self):
        nodes = scenario(
            1, "Miami coast",
            extra_failures={"M-S"}
        )

        states = outage_states(nodes)

        self.assertTrue(states["M-A"]["offline"])
        self.assertTrue(states["M-B"]["offline"])

    def test_unique_customers_no_double_count(self):
        nodes = scenario(
            1, "Miami coast",
            extra_failures={"M-S", "M-F"}
        )

        self.assertEqual(
            affected_customers(nodes),
            2430
        )

    def test_repair_blocked_by_second_fault(self):
        nodes = scenario(
            1, "Miami coast",
            extra_failures={"M-S", "M-F"}
        )

        self.assertEqual(
            repair_gain(nodes, "M-S"),
            0
        )

        self.assertEqual(
            repair_gain(nodes, "M-F"),
            0
        )

        self.assertEqual(
            repair_gain(
                nodes, "M-S", repaired={"M-F"}
            ),
            2430
        )

    def test_repair_plan_reaches_zero(self):
        nodes = scenario(
            4, "Miami coast",
            extra_failures={"M-S"}
        )

        for strategy in (
            "Balanced",
            "Customers first",
            "Fastest restoration",
            "Critical facilities"
        ):
            plan = repair_plan(nodes, strategy)

            self.assertEqual(
                plan["schedule"][-1]["affected_after"],
                0
            )

            self.assertGreaterEqual(
                plan["customer_hours"],
                0
            )

    def test_only_approved_inspections(self):
        records = [
            {
                "asset_id": "M-A",
                "severity": 95,
                "verified": False
            },
            {
                "asset_id": "M-A",
                "severity": 85,
                "verified": True
            }
        ]

        self.assertEqual(
            verified_max(records)["M-A"],
            85
        )

    def test_assets_topologically_ordered(self):
        seen = set()

        for asset in ASSETS:
            self.assertTrue(
                asset["parent"] is None
                or asset["parent"] in seen
            )
            seen.add(asset["id"])


if __name__ == "__main__":
    unittest.main()