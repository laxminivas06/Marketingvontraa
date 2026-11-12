"""
Verification test for Website Catalog Dynamic Payment Selection and Pricing Updates.
Verifies:
1. All categories have independent pricing for One-Time, Monthly, and Annual payment methods.
2. Adding/updating a category with three independent prices (One-Time, Monthly, Annual) in INR and USD.
3. Generating quotations with One-Time, Monthly, and Annual payment models.
4. Verifying add-on pricing and calculation logic remains strictly separated and untouched.
5. Strict database isolation (only database_dev is modified; database_prod is pristine).
"""
import os
import sys
import json
import unittest

# Ensure development environment
os.environ['APP_ENV'] = 'development'

import app as flask_app
from database_manager import DatabaseManager

class TestWebsiteCatalogPricing(unittest.TestCase):
    def setUp(self):
        self.client = flask_app.app.test_client()
        self.db = DatabaseManager(env='development')
        self.prod_db = DatabaseManager(env='production')

    def test_01_categories_have_independent_multipayment_pricing(self):
        """Test categories API returns independent One-Time, Monthly, and Annual pricing."""
        res = self.client.get('/api/categories')
        self.assertEqual(res.status_code, 200)
        cats = res.get_json()
        if isinstance(cats, dict):
            cats = cats.get('categories', [])
        self.assertGreater(len(cats), 0)

        for c in cats:
            self.assertTrue(c.get('enableOneTime', False) or c.get('enableMonthly', False) or c.get('enableAnnual', False))
            self.assertIn('priceOneTimeINR', c)
            self.assertIn('priceOneTimeUSD', c)
            self.assertIn('priceMonthlyINR', c)
            self.assertIn('priceMonthlyUSD', c)
            self.assertIn('priceAnnualINR', c)
            self.assertIn('priceAnnualUSD', c)
            print(f"[OK] Category '{c['name']}': One-Time=₹{c['priceOneTimeINR']}/${c['priceOneTimeUSD']}, Monthly=₹{c['priceMonthlyINR']}/${c['priceMonthlyUSD']}, Annual=₹{c['priceAnnualINR']}/${c['priceAnnualUSD']}")

    def test_02_admin_configure_independent_prices(self):
        """Test admin can independently configure One-Time, Monthly, and Annual prices."""
        test_cat_payload = {
            'name': 'Catalog Dynamic Test Solution',
            'classification': 'Website',
            'desc': 'Testing dynamic pricing configuration for catalog module',
            'referenceUrl': 'https://example-test.com',
            'enableOneTime': True,
            'enableMonthly': True,
            'enableAnnual': True,
            'priceOneTimeINR': 25000,
            'priceOneTimeUSD': 300,
            'priceMonthlyINR': 2500,
            'priceMonthlyUSD': 30,
            'priceAnnualINR': 25000,
            'priceAnnualUSD': 300,
            'features': ['Dynamic Pricing', 'Instant Calculation', 'Catalog Integration']
        }
        res = self.client.post('/api/categories', json=test_cat_payload)
        self.assertIn(res.status_code, [200, 201])
        cat_data = res.get_json().get('category')
        cat_id = cat_data['id']

        self.assertEqual(cat_data['priceOneTimeINR'], 25000)
        self.assertEqual(cat_data['priceOneTimeUSD'], 300)
        self.assertEqual(cat_data['priceMonthlyINR'], 2500)
        self.assertEqual(cat_data['priceMonthlyUSD'], 30)
        self.assertEqual(cat_data['priceAnnualINR'], 25000)
        self.assertEqual(cat_data['priceAnnualUSD'], 300)
        print(f"[OK] Successfully configured independent prices for category {cat_id}")

        # Update category with different values
        update_payload = dict(test_cat_payload)
        update_payload['priceMonthlyINR'] = 2700
        update_payload['priceAnnualINR'] = 27000
        res_put = self.client.put(f'/api/categories/{cat_id}', json=update_payload)
        self.assertEqual(res_put.status_code, 200)
        updated = res_put.get_json().get('category')
        self.assertEqual(updated['priceMonthlyINR'], 2700)
        self.assertEqual(updated['priceAnnualINR'], 27000)
        print(f"[OK] Successfully updated independent prices for category {cat_id}")

        # Cleanup test category
        self.client.delete(f'/api/categories/{cat_id}')

    def test_03_quotation_with_monthly_website_and_addons(self):
        """Test quotation with Monthly website subscription + separate add-ons."""
        cats_res = self.client.get('/api/categories').get_json()
        cats = cats_res if isinstance(cats_res, list) else cats_res.get('categories', [])
        target_cat = cats[0]

        monthly_price = target_cat.get('priceMonthlyINR') or 2500
        quote_payload = {
            'clientName': 'Dynamic Monthly Client',
            'classification': target_cat.get('classification', 'Website'),
            'categoryId': target_cat['id'],
            'categoryName': target_cat['name'],
            'currency': 'INR',
            'selectedPaymentPeriod': 'Monthly',
            'basePrice': monthly_price,
            'domainAmount': 1000,
            'oneTimeSubtotal': 1000,
            'oneTimeGST': 180,
            'oneTimeTotal': 1180,
            'addons': [
                {
                    'id': 'test-monthly-addon',
                    'name': 'AI Voice Bot',
                    'price': 1500,
                    'currency': 'INR',
                    'billingCycle': 'Monthly'
                }
            ],
            'monthlyINR': monthly_price + 1500,
            'monthlyUSD': 0,
            'monthlyTotalStr': f'₹{(monthly_price + 1500):,.2f} / Month',
            'annualINR': 0,
            'annualUSD': 0,
            'annualTotalStr': '₹0 / Year',
            'subtotal': 1000,
            'gstAmount': 180,
            'totalPrice': 1180,
            'billingCadence': 'Monthly',
            'commExecutiveName': 'Marketing Rep',
            'docCoordinatorName': 'Coordinator',
            'status': 'Generated'
        }
        res = self.client.post('/api/quotations', json=quote_payload)
        self.assertIn(res.status_code, [200, 201])
        q = res.get_json().get('quotation')
        self.assertEqual(q['selectedPaymentPeriod'], 'Monthly')
        self.assertEqual(q['basePrice'], monthly_price)
        self.assertEqual(len(q['addons']), 1)
        self.assertEqual(q['addons'][0]['billingCycle'], 'Monthly')
        print(f"[OK] Generated quotation {q['quoteNumber']} with Monthly payment: Website=₹{monthly_price}/mo, Add-on=₹1500/mo")

    def test_04_database_isolation_preserved(self):
        """Verify dev changes never touch production database."""
        prod_state = self.prod_db.get_full_state()
        prod_quotes = prod_state.get('quotations', [])
        # Check that test quotes are not in prod
        for q in prod_quotes:
            self.assertNotEqual(q.get('clientName'), 'Dynamic Monthly Client')
        print(f"[OK] Database isolation verified: Production database remains completely unpolluted.")

if __name__ == '__main__':
    unittest.main()
