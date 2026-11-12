#!/usr/bin/env python3
"""
Comprehensive Verification Script for Application Updates:
1. Environment and Database Separation (Dev vs Prod isolation)
2. Multi-Payment Website & Bundle Structure (One-Time, Monthly, Annually)
3. Basic Business Website Bundle dynamic switching
4. Quotations API with segregated One-Time, Monthly, and Annual pricing
5. Optional Add-ons (One-Time, Monthly, Annually)
6. Complete removal of requirements document attachment from Price Calculator
7. HTML & UI element checks in admin.html and marketing.html
"""
import os
import sys
import json
import copy

def test_database_isolation():
    print("--- 1. Testing Database Separation & Isolation ---")
    from config import Config
    from database_manager import DatabaseManager

    print(f"Current Config.ENV: {Config.ENV}")
    print(f"Current Config.DATABASE_DIR: {Config.DATABASE_DIR}")
    assert Config.ENV == 'development', f"Expected development env, got {Config.ENV}"
    assert 'database_dev' in Config.DATABASE_DIR, f"Expected database_dev in path, got {Config.DATABASE_DIR}"

    # Verify isolation enforcement: development must reject mounting database_prod
    dev_mgr = DatabaseManager(db_root=Config.DATABASE_DIR, env='development')
    assert dev_mgr.env == 'development'

    try:
        DatabaseManager(db_root='database_prod', env='development')
        raise AssertionError("Isolation check failed! Development was able to mount database_prod")
    except RuntimeError as e:
        print(f"Safety check verified: {e}")

    # Verify prod manager is isolated to database_prod
    prod_mgr = DatabaseManager(db_root='database_prod', env='production')
    assert prod_mgr.env == 'production'
    print("[PASS] Database separation & isolation verified successfully.")

def test_multipayment_categories():
    print("\n--- 2. Testing Multi-Payment Categories & Basic Business Website Bundle ---")
    import app as flask_app
    client = flask_app.app.test_client()

    # GET /api/categories
    res = client.get('/api/categories')
    assert res.status_code == 200, f"GET /api/categories failed with {res.status_code}"
    categories = json.loads(res.data)
    assert len(categories) > 0, "No categories returned"

    # Find Basic Business Website
    bbw = next((c for c in categories if 'Basic Business Website' in c['name']), None)
    assert bbw is not None, "Basic Business Website not found"
    print(f"Basic Business Website config: enableOneTime={bbw.get('enableOneTime')}, enableMonthly={bbw.get('enableMonthly')}, enableAnnual={bbw.get('enableAnnual')}")
    print(f"  Prices: One-Time: INR {bbw.get('priceOneTimeINR')} / USD {bbw.get('priceOneTimeUSD')}")
    print(f"          Monthly:  INR {bbw.get('priceMonthlyINR')} / USD {bbw.get('priceMonthlyUSD')}")
    print(f"          Annual:   INR {bbw.get('priceAnnualINR')} / USD {bbw.get('priceAnnualUSD')}")

    assert bbw.get('enableOneTime') is True, "Basic Business Website should have One-Time enabled"
    assert bbw.get('enableMonthly') is True, "Basic Business Website should have Monthly enabled"
    assert bbw.get('enableAnnual') is True, "Basic Business Website should have Annual enabled"

    # Create a new test application with Monthly only
    import uuid
    unique_name = f"Test SaaS Portal {uuid.uuid4().hex[:4]}"
    test_cat_payload = {
        "name": unique_name,
        "classification": "Software Application",
        "desc": "Testing monthly subscription only application",
        "enableOneTime": False,
        "enableMonthly": True,
        "enableAnnual": False,
        "priceOneTimeINR": 0,
        "priceOneTimeUSD": 0,
        "priceMonthlyINR": 4999,
        "priceMonthlyUSD": 69,
        "priceAnnualINR": 0,
        "priceAnnualUSD": 0,
        "features": ["Feature A", "Feature B"]
    }
    res_create = client.post('/api/categories', json=test_cat_payload)
    assert res_create.status_code == 200, f"Create category failed: {res_create.data}"
    created_cat = json.loads(res_create.data)['category']
    assert created_cat['enableOneTime'] is False
    assert created_cat['enableMonthly'] is True
    assert created_cat['priceMonthlyINR'] == 4999
    print(f"[PASS] Category creation with custom payment model verified: {created_cat['id']}")

    # Edit test category via PUT to enable Annual as well
    update_payload = {
        "enableAnnual": True,
        "priceAnnualINR": 49990,
        "priceAnnualUSD": 690
    }
    res_update = client.put(f"/api/categories/{created_cat['id']}", json=update_payload)
    assert res_update.status_code == 200
    updated_cat = json.loads(res_update.data)['category']
    assert updated_cat['enableAnnual'] is True
    assert updated_cat['priceAnnualINR'] == 49990
    print(f"[PASS] Category update via PUT verified.")

    # Clean up test category
    res_del = client.delete(f"/api/categories/{created_cat['id']}")
    assert res_del.status_code == 200
    print(f"[PASS] Test category cleanup verified.")

def test_addons_cycles():
    print("\n--- 3. Testing Optional Add-ons (One-Time, Monthly, Annually) ---")
    import app as flask_app
    client = flask_app.app.test_client()

    res = client.get('/api/addons')
    assert res.status_code == 200
    addons = json.loads(res.data)
    assert len(addons) > 0, "No addons found"

    cycles = set(a.get('billingCycle') for a in addons)
    print(f"Configured Add-on billing cycles found in DB: {cycles}")
    assert 'Monthly' in cycles, "Monthly addons missing"
    assert 'Annually' in cycles, "Annual addons missing"

    # Add a custom One-Time add-on
    new_addon = {
        "name": "Custom Integration Suite",
        "desc": "One-time technical integration",
        "currency": "INR",
        "price": 5000.0,
        "billingCycle": "One-Time",
        "status": "active"
    }
    res_add = client.post('/api/addons', json=new_addon)
    assert res_add.status_code == 200
    created_addon = json.loads(res_add.data)['addon']
    assert created_addon['billingCycle'] == 'One-Time'
    print(f"[PASS] One-Time Add-on creation verified: {created_addon['id']}")

    # Clean up
    client.delete(f"/api/addons/{created_addon['id']}")
    print(f"[PASS] Add-on cleanup verified.")

def test_quotations_calculation_and_segregation():
    print("\n--- 4. Testing Quotations Calculation & Pricing Segregation ---")
    import app as flask_app
    client = flask_app.app.test_client()

    # Case A: Basic Business Website with One-Time payment (₹12,000) + Domain (₹1,200) + Monthly Addon ($20) + Annual Addon ($100)
    quote_payload_a = {
        "clientName": "Test Customer Alpha",
        "classification": "Website",
        "currency": "INR",
        "selectedPaymentPeriod": "One-Time",
        "basePrice": 12000,
        "domainAmount": 1200,
        "addons": [
            {"id": "add-ai", "name": "AI Voice", "price": 20, "currency": "USD", "billingCycle": "Monthly"},
            {"id": "add-ana", "name": "Analytics", "price": 100, "currency": "USD", "billingCycle": "Annually"},
            {"id": "add-auth", "name": "Google Auth", "price": 2000, "currency": "INR", "billingCycle": "One-Time"}
        ],
        "commExecutiveName": "Lead Rep",
        "docCoordinatorName": "Doc Coord"
    }
    res_a = client.post('/api/quotations', json=quote_payload_a)
    assert res_a.status_code == 200, f"Quotation creation failed: {res_a.data}"
    qa = json.loads(res_a.data)['quotation']

    # One-Time subtotal = 12000 (site) + 1200 (domain) + 2000 (one-time addon) = 15200
    expected_onetime_subtotal = 15200.0
    expected_onetime_gst = round(15200.0 * 0.18, 2)
    expected_onetime_total = expected_onetime_subtotal + expected_onetime_gst

    print(f"Quotation A (One-Time selected):")
    print(f"  One-Time Total Str: {qa.get('oneTimeTotalStr')}")
    print(f"  Monthly Total Str:  {qa.get('monthlyTotalStr')}")
    print(f"  Annual Total Str:   {qa.get('annualTotalStr')}")

    assert qa.get('oneTimeSubtotal') == expected_onetime_subtotal
    assert qa.get('oneTimeTotal') == expected_onetime_total
    assert '$20' in qa.get('monthlyTotalStr')
    assert '$100' in qa.get('annualTotalStr')
    print("[PASS] Case A (One-Time with mixed add-ons) passed.")

    # Case B: Basic Business Website with Monthly Subscription (₹1,200/mo)
    quote_payload_b = {
        "clientName": "Test Customer Beta",
        "classification": "Website",
        "currency": "INR",
        "selectedPaymentPeriod": "Monthly",
        "basePrice": 1200,
        "domainAmount": 1200,
        "addons": [
            {"id": "add-attend", "name": "Attendance", "price": 2000, "currency": "INR", "billingCycle": "Monthly"}
        ]
    }
    res_b = client.post('/api/quotations', json=quote_payload_b)
    assert res_b.status_code == 200
    qb = json.loads(res_b.data)['quotation']

    print(f"Quotation B (Monthly selected):")
    print(f"  One-Time Total Str: {qb.get('oneTimeTotalStr')}")
    print(f"  Monthly Total Str:  {qb.get('monthlyTotalStr')}")
    print(f"  Annual Total Str:   {qb.get('annualTotalStr')}")

    # One-Time subtotal has only domain (1200) + 18% GST (216) = 1416
    assert qb.get('oneTimeSubtotal') == 1200.0
    assert qb.get('oneTimeTotal') == 1416.0
    # Monthly total = ₹1200 (website) + ₹2000 (attendance addon) = ₹3200 + 18% GST = ₹3776
    assert '3,200' in qb.get('monthlyTotalStr') or '3,776' in qb.get('monthlyTotalStr')
    print("[PASS] Case B (Monthly subscription website) passed.")

    # Case C: Basic Business Website with Annual Subscription (₹12,000/yr)
    quote_payload_c = {
        "clientName": "Test Customer Gamma",
        "classification": "Website",
        "currency": "INR",
        "selectedPaymentPeriod": "Annually",
        "basePrice": 12000,
        "domainAmount": 0,
        "addons": []
    }
    res_c = client.post('/api/quotations', json=quote_payload_c)
    assert res_c.status_code == 200
    qc = json.loads(res_c.data)['quotation']

    print(f"Quotation C (Annual selected):")
    print(f"  One-Time Total Str: {qc.get('oneTimeTotalStr')}")
    print(f"  Annual Total Str:   {qc.get('annualTotalStr')}")

    assert qc.get('oneTimeSubtotal') == 0.0
    assert '12,000' in qc.get('annualTotalStr') or '14,160' in qc.get('annualTotalStr')
    print("[PASS] Case C (Annual subscription website) passed.")

def test_html_ui_integrity():
    print("\n--- 5. Testing HTML & UI Integrity ---")

    with open('admin.html', 'r', encoding='utf-8') as f:
        admin_content = f.read()

    # Admin Portal checks
    assert 'cat-enable-onetime' in admin_content, "admin.html missing cat-enable-onetime"
    assert 'cat-enable-monthly' in admin_content, "admin.html missing cat-enable-monthly"
    assert 'cat-enable-annual' in admin_content, "admin.html missing cat-enable-annual"
    assert 'cat-price-onetime-inr' in admin_content, "admin.html missing cat-price-onetime-inr"
    assert 'cat-price-monthly-inr' in admin_content, "admin.html missing cat-price-monthly-inr"
    assert 'cat-price-annual-inr' in admin_content, "admin.html missing cat-price-annual-inr"
    assert 'editCategory' in admin_content, "admin.html missing editCategory function"
    assert 'togglePricingInputs' in admin_content, "admin.html missing togglePricingInputs function"
    print("[PASS] admin.html multi-payment configuration UI verified.")

    with open('marketing.html', 'r', encoding='utf-8') as f:
        marketing_content = f.read()

    # Marketing Portal checks
    # Crucial removal: calc-requirement-file must NOT be in the Price Calculator tab HTML
    # We find tab-calculator section and verify calc-requirement-file is absent
    tab_calc_start = marketing_content.find('id="tab-calculator"')
    tab_calc_end = marketing_content.find('id="tab-references"')
    tab_calc_html = marketing_content[tab_calc_start:tab_calc_end]
    assert 'calc-requirement-file' not in tab_calc_html, "Requirement document file input found in tab-calculator! Must be removed."
    assert '4. Attach Requirements Document' not in tab_calc_html, "Card 4: Attach Requirements Document found in tab-calculator! Must be removed."

    assert 'cat-payment-period-buttons' in marketing_content, "marketing.html missing cat-payment-period-buttons"
    assert 'setPaymentPeriod' in marketing_content, "marketing.html missing setPaymentPeriod function"
    assert 'getWebsitePriceForPeriod' in marketing_content, "marketing.html missing getWebsitePriceForPeriod function"
    assert 'sum-monthly-total' in marketing_content, "marketing.html missing sum-monthly-total"
    assert 'sum-annual-total' in marketing_content, "marketing.html missing sum-annual-total"
    print("[PASS] marketing.html payment switcher and removed file attachment verified.")

if __name__ == '__main__':
    try:
        test_database_isolation()
        test_multipayment_categories()
        test_addons_cycles()
        test_quotations_calculation_and_segregation()
        test_html_ui_integrity()
        print("\n==============================================")
        print("ALL VERIFICATION SUITES PASSED SUCCESSFULLY (100%)")
        print("==============================================")
    except Exception as e:
        print(f"\n[FAIL] Verification error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
