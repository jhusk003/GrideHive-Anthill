import unittest
from gridhive_core import ASSETS, LINKS, STORMS, simulate, economic_impact, _network_status


class DemoTest(unittest.TestCase):
    def test_normal_has_no_outages(self):
        r = simulate('Normal', 'Miami coast')
        self.assertEqual(r['failed_assets'], 0)
        self.assertEqual(r['affected_customers'], 0)

    def test_higher_storm_not_less_risky(self):
        prior = -1
        for s in STORMS:
            r = simulate(s, 'Miami coast')
            self.assertGreaterEqual(r['avg_hazard'], prior)
            prior = r['avg_hazard']

    def test_confirmed_inspection_triggers_failure(self):
        before = simulate('Normal', 'Miami coast')
        r = simulate('Normal','Miami coast',[dict(asset_id='MIA-F2',status='Confirmed damage',severity=92)])
        self.assertIn('MIA-F2', r['direct_failures'])
        self.assertIn('MIA-T2', r['offline'])
        self.assertGreater(r['affected_customers'], before['affected_customers'])

    def test_clear_visual_overrides_hypothetical_direct_failure(self):
        baseline = simulate('Category 5','Miami coast')
        target = baseline['direct_failures'][0]
        r = simulate('Category 5','Miami coast',[dict(asset_id=target,status='No visible damage',severity=0)])
        self.assertNotIn(target,r['direct_failures'])

    def test_network_propagates_only_downstream(self):
        r = _network_status({'MIA-F2'})
        self.assertIn('MIA-T2', r)
        self.assertNotIn('MIA-S1', r)
        self.assertNotIn('MIA-F1', r)

    def test_score_linked_to_immediate_restoration(self):
        r=simulate('Normal','Miami coast',[dict(asset_id='MIA-F2',status='Confirmed damage',severity=95)])
        item=next(a for a in r['queue'] if a['asset_id']=='MIA-F2')
        self.assertEqual(item['customers_restored'],2050)

    def test_economic_math(self):
        r=simulate('Normal','Miami coast',[dict(asset_id='MIA-F2',status='Confirmed damage',severity=95)])
        e=economic_impact(r,12,8,25)
        self.assertEqual(e['outage_customer_hours'], 24600)
        self.assertEqual(e['scenario_cost'], 196800)
        self.assertEqual(e['hypothetical_avoided_cost'],49200)

    def test_unique_ids_and_acyclic(self):
        ids={n['id'] for n in ASSETS}
        self.assertEqual(len(ASSETS),len(ids))
        self.assertTrue(all(a in ids and b in ids for a,b in LINKS))


if __name__ == '__main__':
    unittest.main()
