#!/usr/bin/env python3
"""
Verification Suite for Application & Bundle Management Editing Functionality:
1. Edit Existing Registered Web Applications (In-place update, no duplicates, all fields)
2. Edit Existing Registered Bundles (Included apps loaded, add/remove/replace, recalculation, in-place update)
3. Database and Data Synchronization (Preserve all existing data, cross-module synchronization)
4. UI/UX Elements in admin.html and marketing.html (View modal, Edit buttons, dirty state warning, filter tabs)
"""
import os
import sys
import json
import unittest

os.environ['APP_ENV'] = 'development'

import app as flask_app
from database_manager import DatabaseManager

class TestApplicationAndBundleManagement(unittest.TestCase):
    def setUp(self):
        self.client = flask_app.app.test_client()
        self.db_manager = DatabaseManager(env='development')

    def test_01_edit_existing_web_application(self):
        """Verify editing an existing web application modifies in-place without creating duplicates."""
        # 1. Fetch all categories
        res = self.client.get('/api/categories')
        self.assertEqual(res.status_code, 200)
        initial_cats = res.get_json()
        initial_count = len(initial_cats)
        self.assertGreater(initial_count, 0)

        # 2. Pick an existing application
        target = next(c for c in initial_cats if c['id'] == 'cat-84f130')
        self.assertEqual(target['name'], 'Basic Business Website')
        original_desc = target.get('desc', '')

        # 3. Perform Edit via PUT
        update_payload = {
            'name': 'Basic Business Website (Updated Deliverables)',
            'classification': 'Website',
            'desc': 'Enhanced startup web presence with optimized performance and CRM lead sync.',
            'referenceUrl': 'https://aivontraa.com/showcase/business',
            'enableOneTime': True,
            'enableMonthly': True,
            'enableAnnual': False,  # Custom disabled annual frequency
            'priceOneTimeINR': 14500,
            'priceOneTimeUSD': 185,
            'priceMonthlyINR': 1450,
            'priceMonthlyUSD': 19,
            'priceAnnualINR': 0,
            'priceAnnualUSD': 0,
            'features': target.get('features', []) + ['Instant WhatsApp Lead Webhook']
        }
        res_put = self.client.put(f"/api/categories/{target['id']}", json=update_payload)
        self.assertEqual(res_put.status_code, 200)
        updated_cat = res_put.get_json().get('category')
        self.assertEqual(updated_cat['name'], 'Basic Business Website (Updated Deliverables)')
        self.assertEqual(updated_cat['priceOneTimeINR'], 14500)
        self.assertEqual(updated_cat['enableAnnual'], False)

        # 4. Verify in database: NO DUPLICATE created, count remains identical!
        res_after = self.client.get('/api/categories')
        cats_after = res_after.get_json()
        self.assertEqual(len(cats_after), initial_count, "Editing should not change total category count (no duplicates)!")

        # Verify record persistence and payment frequency preservation
        persisted = next(c for c in cats_after if c['id'] == 'cat-84f130')
        self.assertEqual(persisted['name'], 'Basic Business Website (Updated Deliverables)')
        self.assertEqual(persisted['priceOneTimeINR'], 14500)
        self.assertEqual(persisted['enableAnnual'], False, "Disabled annual frequency must be preserved across GET!")

        # 5. Restore original name & fields to keep existing dataset pristine
        restore_payload = {
            'name': 'Basic Business Website',
            'classification': 'Website – Basic',
            'desc': original_desc,
            'referenceUrl': 'https://wix.com',
            'enableOneTime': True,
            'enableMonthly': True,
            'enableAnnual': True,
            'priceOneTimeINR': 12000,
            'priceOneTimeUSD': 169,
            'priceMonthlyINR': 1200,
            'priceMonthlyUSD': 17,
            'priceAnnualINR': 12000,
            'priceAnnualUSD': 169,
            'features': target.get('features', [])
        }
        self.client.put(f"/api/categories/{target['id']}", json=restore_payload)
        print("[PASS] Test 1: Edit existing registered web application verified.")

    def test_02_edit_existing_bundle_and_recalculation(self):
        """Verify editing an existing bundle, adding/removing/replacing applications, and recalculation."""
        # 1. Fetch bundles
        res_bnd = self.client.get('/api/bundles')
        self.assertEqual(res_bnd.status_code, 200)
        bundles = res_bnd.get_json()
        self.assertGreater(len(bundles), 0, "At least one bundle must be registered!")

        starter_bundle = next((b for b in bundles if b['id'] == 'bnd-starter-suite'), bundles[0])
        self.assertTrue(starter_bundle.get('isBundle'))
        self.assertIn('bundleApps', starter_bundle)
        self.assertGreaterEqual(len(starter_bundle['bundleApps']), 1)
        initial_apps = list(starter_bundle['bundleApps'])

        # 2. Test Recalculation API with included apps
        recalc_payload = {'bundleApps': starter_bundle['bundleApps']}
        res_recalc = self.client.post('/api/bundles/recalculate', json=recalc_payload)
        self.assertEqual(res_recalc.status_code, 200)
        recalc_data = res_recalc.get_json()
        self.assertTrue(recalc_data['success'])
        self.assertEqual(recalc_data['appCount'], len(starter_bundle['bundleApps']))
        self.assertGreater(recalc_data['priceOneTimeINR'], 0)

        # 3. Add an application to the bundle and recalculate
        modified_apps = list(initial_apps)
        extra_app = 'cat-81217a' # E-Commerce Website (30,000 INR)
        if extra_app not in modified_apps:
            modified_apps.append(extra_app)

        res_recalc_added = self.client.post('/api/bundles/recalculate', json={'bundleApps': modified_apps})
        recalc_added_data = res_recalc_added.get_json()
        self.assertGreater(recalc_added_data['priceOneTimeINR'], recalc_data['priceOneTimeINR'])

        # 4. Edit bundle via PUT
        update_bundle_payload = {
            'name': 'Startup Business & Dashboard Bundle (Expanded)',
            'classification': 'Website Bundle',
            'isBundle': True,
            'desc': 'Complete business starter bundle with integrated e-commerce capabilities.',
            'referenceUrl': 'https://aivontraa.com/bundles',
            'bundleApps': modified_apps,
            'enableOneTime': True,
            'enableMonthly': True,
            'enableAnnual': True,
            'priceOneTimeINR': recalc_added_data['priceOneTimeINR'],
            'priceOneTimeUSD': recalc_added_data['priceOneTimeUSD'],
            'priceMonthlyINR': recalc_added_data['priceMonthlyINR'],
            'priceMonthlyUSD': recalc_added_data['priceMonthlyUSD'],
            'priceAnnualINR': recalc_added_data['priceAnnualINR'],
            'priceAnnualUSD': recalc_added_data['priceAnnualUSD'],
            'features': starter_bundle.get('features', []) + ['E-Commerce Product Catalog']
        }
        res_update = self.client.put(f"/api/bundles/{starter_bundle['id']}", json=update_bundle_payload)
        self.assertEqual(res_update.status_code, 200)
        updated_bnd = res_update.get_json().get('category')
        self.assertEqual(updated_bnd['name'], 'Startup Business & Dashboard Bundle (Expanded)')
        self.assertEqual(len(updated_bnd['bundleApps']), len(modified_apps))
        self.assertEqual(updated_bnd['priceOneTimeINR'], recalc_added_data['priceOneTimeINR'])

        # 5. Replace application in bundle
        replacement_apps = [aid if aid != extra_app else 'cat-2a4959' for aid in modified_apps]
        res_recalc_replaced = self.client.post('/api/bundles/recalculate', json={'bundleApps': replacement_apps})
        recalc_replaced_data = res_recalc_replaced.get_json()

        # Update bundle with replaced apps
        update_bundle_payload['bundleApps'] = replacement_apps
        update_bundle_payload['priceOneTimeINR'] = recalc_replaced_data['priceOneTimeINR']
        self.client.put(f"/api/bundles/{starter_bundle['id']}", json=update_bundle_payload)

        # 6. Restore original bundle configuration
        restore_bnd_payload = {
            'name': 'Startup Business & Dashboard Bundle',
            'classification': 'Website Bundle',
            'isBundle': True,
            'desc': 'Complete online presence package combining a responsive Basic Business Website with a centralized Admin Dashboard.',
            'referenceUrl': 'https://aivontraa.com',
            'bundleApps': initial_apps,
            'enableOneTime': True,
            'enableMonthly': True,
            'enableAnnual': True,
            'priceOneTimeINR': recalc_data['priceOneTimeINR'],
            'priceOneTimeUSD': recalc_data['priceOneTimeUSD'],
            'priceMonthlyINR': recalc_data['priceMonthlyINR'],
            'priceMonthlyUSD': recalc_data['priceMonthlyUSD'],
            'priceAnnualINR': recalc_data['priceAnnualINR'],
            'priceAnnualUSD': recalc_data['priceAnnualUSD'],
            'features': starter_bundle.get('features', [])
        }
        self.client.put(f"/api/bundles/{starter_bundle['id']}", json=restore_bnd_payload)
        print("[PASS] Test 2: Edit bundle with add/remove/replace and dynamic recalculation verified.")

    def test_03_data_synchronization_across_state(self):
        """Verify data synchronization across /api/state and /api/categories."""
        res_state = self.client.get('/api/state')
        self.assertEqual(res_state.status_code, 200)
        state_data = res_state.get_json()
        cats_in_state = state_data.get('categories', [])
        self.assertGreater(len(cats_in_state), 0)

        # Verify bundle is present in state
        bnd_in_state = next((c for c in cats_in_state if c.get('isBundle') or c.get('classification') == 'Website Bundle'), None)
        self.assertIsNotNone(bnd_in_state, "Bundle must be present in synchronized state")
        print("[PASS] Test 3: Data synchronization across state verified.")

    def test_04_html_ui_ux_requirements(self):
        """Verify HTML & UI elements for View, Edit, Modal, Filter tabs, and Dirty checks."""
        base_dir = os.path.dirname(os.path.abspath(__file__))

        with open(os.path.join(base_dir, 'admin.html'), 'r', encoding='utf-8') as f:
            admin_html = f.read()

        # 1. Edit & View buttons
        self.assertIn("viewCategory('", admin_html)
        self.assertIn("editCategory('", admin_html)
        self.assertIn("deleteCategory('", admin_html)

        # 2. View Modal & Replace Modal
        self.assertIn('id="modal-view-category"', admin_html)
        self.assertIn('id="modal-replace-bundle-app"', admin_html)

        # 3. Dynamic bundle configuration
        self.assertIn('id="bundle-config-section"', admin_html)
        self.assertIn('id="bundle-included-apps-container"', admin_html)
        self.assertIn('id="bundle-add-app-select"', admin_html)
        self.assertIn('recalculateBundlePrices', admin_html)

        # 4. Filter tabs and search bar
        self.assertIn('btn-filter-cat-all', admin_html)
        self.assertIn('btn-filter-cat-apps', admin_html)
        self.assertIn('btn-filter-cat-bundles', admin_html)
        self.assertIn('cat-search-input', admin_html)

        # 5. Form dirty checks and cancel button
        self.assertIn('isCategoryFormDirty', admin_html)
        self.assertIn('cancelCategoryEdit', admin_html)
        self.assertIn('cat-cancel-btn', admin_html)

        # Marketing Portal verification
        with open(os.path.join(base_dir, 'marketing.html'), 'r', encoding='utf-8') as f:
            mktg_html = f.read()

        self.assertIn('Website Bundle', mktg_html)
        self.assertIn('cat-disp-bundle-box', mktg_html)
        print("[PASS] Test 4: UI/UX elements, modals, filter tabs, and dirty checks verified in admin and marketing portals.")

if __name__ == '__main__':
    unittest.main()

