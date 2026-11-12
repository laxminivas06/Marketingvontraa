import os
import json
import uuid
import jwt
import base64
import hashlib
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, send_from_directory, Response

app = Flask(__name__, static_folder='.', static_url_path='')

COMPANY_NAME = "Aivontraa Automation Pvt. Ltd."
COMPANY_WEBSITE = "www.aivontraa.com"
ROOT_ADMIN_EMAIL = os.environ.get("ROOT_ADMIN_EMAIL", "laxminivasmorishetty143@gmail.com")
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "laxminivasmorishetty143@gmail.com,admin@aivontraa.com").split(",") if e.strip()}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'database.json')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
PAYMENT_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'payments')
DOCUMENTS_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'documents')
CHANGE_REQ_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'change_requests')
SIGNOFF_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'signoffs')

for f in [UPLOAD_FOLDER, PAYMENT_UPLOAD_FOLDER, DOCUMENTS_UPLOAD_FOLDER, CHANGE_REQ_UPLOAD_FOLDER, SIGNOFF_UPLOAD_FOLDER]:
    os.makedirs(f, exist_ok=True)

MAX_DOCUMENT_SIZE = 500 * 1024  # 500 KB strict limit for requirements & change requests (.docx, .pdf, .zip)
MAX_PAYMENT_SIZE = 5 * 1024 * 1024  # 5 MB limit for payment proof screenshots

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "524356808349-31ele7mkqr9bn0uqt28bod9m638978eh.apps.googleusercontent.com")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

# -------------------------------------------------------------
# DATABASE & DATA ENCRYPTION AT REST
# -------------------------------------------------------------
ENCRYPTION_KEY = hashlib.sha256(b"Aivontraa_Automation_Pvt_Ltd_Secure_Vault_2026").digest()

def encrypt_sensitive(data_str: str) -> str:
    """Encrypts sensitive fields (payment credentials, security tokens) before persisting"""
    if not data_str:
        return ""
    raw = data_str.encode('utf-8')
    encrypted = bytes([b ^ ENCRYPTION_KEY[i % len(ENCRYPTION_KEY)] for i, b in enumerate(raw)])
    return "ENC_" + base64.b64encode(encrypted).decode('ascii')

def decrypt_sensitive(enc_str: str) -> str:
    """Decrypts sensitive fields at rest"""
    if not enc_str or not enc_str.startswith("ENC_"):
        return enc_str
    try:
        raw = base64.b64decode(enc_str[4:])
        decrypted = bytes([b ^ ENCRYPTION_KEY[i % len(ENCRYPTION_KEY)] for i, b in enumerate(raw)])
        return decrypted.decode('utf-8')
    except Exception:
        return enc_str

# -------------------------------------------------------------
# SHARDED MULTI-MODULE DATABASE MANAGER (70MB Soft / 100MB Hard)
# -------------------------------------------------------------
from database_manager import DatabaseManager, MODULES, SOFT_LIMIT_BYTES, HARD_LIMIT_BYTES

db_manager = DatabaseManager(base_dir=BASE_DIR, soft_limit_bytes=SOFT_LIMIT_BYTES, hard_limit_bytes=HARD_LIMIT_BYTES)
if os.path.exists(DB_FILE):
    try:
        db_manager.migrate_from_json(DB_FILE)
    except Exception as e:
        print(f"Notice during migration check: {e}")

def load_db():
    try:
        state = db_manager.get_full_state()
        if state and state.get('users'):
            return state
    except Exception as e:
        print(f"Notice: db_manager fallback: {e}")
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {DB_FILE}: {e}")
        return {}

def save_db(data):
    # 1. Update sharded multi-module databases with encryption & rotation checks
    try:
        db_manager.save_full_state(data)
    except Exception as e:
        print(f"Error persisting to db_manager: {e}")

    # 2. Atomic mirror to database.json for backward compatibility (with Windows OneDrive lock resilience)
    temp_file = f"{DB_FILE}.tmp"
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        try:
            os.replace(temp_file, DB_FILE)
        except (PermissionError, OSError):
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
    except Exception as e:
        print(f"Notice mirroring to {DB_FILE}: {e}")


# -------------------------------------------------------------
# CORS HEADERS
# -------------------------------------------------------------
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,X-User-Role,X-User-Id,X-User-Name'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response

@app.route('/api/<path:path>', methods=['OPTIONS'])
def options_handler(path):
    return ('', 204)


# -------------------------------------------------------------
# STATIC ROUTES FOR CLEAN URLS (History API & Direct Refresh)
# -------------------------------------------------------------
@app.route('/')
@app.route('/login')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/admin')
@app.route('/admin/<path:subpath>')
def admin_portal(subpath=None):
    return send_from_directory('.', 'admin.html')

@app.route('/marketing')
@app.route('/marketing/<path:subpath>')
def marketing_portal(subpath=None):
    return send_from_directory('.', 'marketing.html')

@app.route('/developer')
@app.route('/developer/<path:subpath>')
def developer_portal(subpath=None):
    return send_from_directory('.', 'developer.html')

@app.route('/uploads/<folder>/<path:filename>')
def serve_uploaded_file(folder, filename):
    folder_map = {
        'payments': PAYMENT_UPLOAD_FOLDER,
        'documents': DOCUMENTS_UPLOAD_FOLDER,
        'change_requests': CHANGE_REQ_UPLOAD_FOLDER,
        'signoffs': SIGNOFF_UPLOAD_FOLDER
    }
    target_dir = folder_map.get(folder, UPLOAD_FOLDER)
    return send_from_directory(target_dir, secure_filename(filename))


# -------------------------------------------------------------
# GOOGLE AUTHENTICATION ONLY (No Username/Password)
# -------------------------------------------------------------
def decode_google_token(token_str: str) -> dict:
    """
    Decodes Google ID token payload reliably across all Python environments
    (including PythonAnywhere, different PyJWT versions, or without cryptography).
    """
    if not token_str or not isinstance(token_str, str):
        return {}

    # Method 1: Standard library base64url decode (100% reliable, zero external dependencies)
    try:
        parts = token_str.split('.')
        if len(parts) >= 2:
            payload_b64 = parts[1]
            rem = len(payload_b64) % 4
            if rem > 0:
                payload_b64 += '=' * (4 - rem)
            decoded_bytes = base64.urlsafe_b64decode(payload_b64.encode('ascii'))
            data = json.loads(decoded_bytes.decode('utf-8'))
            if isinstance(data, dict) and data.get('email'):
                return data
    except Exception as e:
        print("Notice: standard base64url decode failed:", e)

    # Method 2: PyJWT 2.x format
    try:
        return jwt.decode(token_str, options={"verify_signature": False})
    except Exception:
        pass

    # Method 3: PyJWT 1.x legacy format (common on PythonAnywhere)
    try:
        return jwt.decode(token_str, verify=False)
    except Exception:
        pass

    return {}

@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    # Username/password login is completely prohibited per requirement 15
    return jsonify({
        "success": False,
        "message": "Username and password authentication is disabled. Aivontraa uses Google Authentication only."
    }), 400

@app.route('/api/auth/google', methods=['POST'])
def api_auth_google():
    """
    Validates Google Authentication against the registered users database.
    Supports multiple administrator emails (including primary root admin and team admins).
    """
    payload = request.get_json() or {}
    email = payload.get('email', '').strip().lower()
    name = payload.get('name', '').strip()
    token = payload.get('credential', '')

    if token:
        decoded = decode_google_token(token)
        if decoded:
            email = decoded.get('email', email).strip().lower()
            name = decoded.get('name', name).strip()

    if not email:
        return jsonify({"success": False, "message": "No verified Google email received."}), 400

    db = load_db()
    users = db.get('users', [])
    user = next((u for u in users if u.get('email', '').lower() == email), None)

    # Admin Auto-Initialization if logging in for the first time
    if not user and (email == ROOT_ADMIN_EMAIL.lower() or email in ADMIN_EMAILS):
        is_root = (email == ROOT_ADMIN_EMAIL.lower())
        user = {
            "id": "usr-admin-root" if is_root else f"usr-admin-{uuid.uuid4().hex[:6]}",
            "name": name or ("Laxminivas Morishetty" if is_root else "System Administrator"),
            "email": email,
            "username": email.split('@')[0],
            "role": "admin",
            "authMethod": "google",
            "status": "active",
            "responsibilities": ["Full System Administration"],
            "createdAt": datetime.now().strftime("%Y-%m-%d")
        }
        users.insert(0, user)
        db['users'] = users
        save_db(db)

    if not user:
        return jsonify({
            "success": False,
            "message": f"Access Restricted. The Google Account ({email}) is not registered in Aivontraa Automation Pvt. Ltd. Please contact the administrator ({ROOT_ADMIN_EMAIL})."
        }), 403

    if user.get('status') == 'inactive':
        return jsonify({
            "success": False,
            "message": "Access Restricted. Your account has been deactivated by the administrator."
        }), 403

    # If the user is configured in ADMIN_EMAILS or already role 'admin', ensure role is admin
    user_role = user.get("role", "marketing")
    if email == ROOT_ADMIN_EMAIL.lower() or email in ADMIN_EMAILS:
        user_role = "admin"

    safe_user = {
        "id": user["id"],
        "name": user.get("name", name or user.get("username", "")),
        "email": user.get("email", email),
        "username": user.get("username", ""),
        "role": user_role,
        "authMethod": "google",
        "responsibilities": user.get("responsibilities", ["Full System Administration"] if user_role == "admin" else [])
    }
    redirect_url = "/admin" if safe_user["role"] == "admin" else ("/developer" if safe_user["role"] == "developer" else "/marketing")
    return jsonify({"success": True, "user": safe_user, "redirectUrl": redirect_url})


# -------------------------------------------------------------
# FULL STATE API (With Marketing Privacy Masking)
# -------------------------------------------------------------
@app.route('/api/state', methods=['GET'])
def api_state():
    db = load_db()
    role = request.headers.get('X-User-Role', '')

    projects = db.get('projects', [])
    quotations = db.get('quotations', [])

    # CRITICAL PRIVACY REQUIREMENT:
    # Marketing team must NOT see the engineering developer's name!
    # Mask engineer details if user is marketing.
    if role.startswith('marketing'):
        masked_projs = []
        for p in projects:
            p_copy = dict(p)
            if p_copy.get('assignedDevId'):
                p_copy['assignedDevName'] = "Engineering Team Assigned"
                p_copy.pop('assignedDevEmail', None)
                p_copy['assignmentHistory'] = []
            masked_projs.append(p_copy)
        projects = masked_projs

    return jsonify({
        "categories": db.get('categories', []),
        "commissionSlabsINR": db.get('commissionSlabsINR', []),
        "commissionSlabsUSD": db.get('commissionSlabsUSD', []),
        "addons": db.get('addons', []),
        "quotations": quotations,
        "projects": projects,
        "users": [
            {
                "id": u["id"],
                "name": u.get("name", u.get("displayName", "")),
                "email": u.get("email", ""),
                "username": u.get("username", ""),
                "role": u.get("role", "marketing"),
                "authMethod": "google",
                "status": u.get("status", "active"),
                "responsibilities": u.get("responsibilities", []),
                "createdAt": u.get("createdAt", "")
            }
            for u in db.get('users', [])
        ]
    })


# -------------------------------------------------------------
# CATEGORIES API (Preserve 7 Categories & Reference Websites)
# -------------------------------------------------------------
@app.route('/api/categories', methods=['GET', 'POST'])
def api_categories():
    db = load_db()
    if request.method == 'GET':
        return jsonify(db.get('categories', []))

    payload = request.get_json() or {}
    name = payload.get('name', '').strip()
    classification = payload.get('classification', 'Website').strip()
    desc = payload.get('desc', '').strip()
    ref_url = payload.get('referenceUrl', '').strip()
    base_inr = int(payload.get('basePriceINR') or 0)
    base_usd = int(payload.get('basePriceUSD') or 0)
    features = payload.get('features') or []

    if not name:
        return jsonify({"success": False, "message": "Category Name is required"}), 400

    categories = db.setdefault('categories', [])
    if any(c.get('name', '').lower() == name.lower() for c in categories):
        return jsonify({"success": False, "message": f"Category '{name}' already exists"}), 400

    new_cat = {
        "id": f"cat-{uuid.uuid4().hex[:6]}",
        "name": name,
        "classification": classification,
        "desc": desc,
        "referenceUrl": ref_url,
        "basePriceINR": base_inr,
        "basePriceUSD": base_usd,
        "features": features
    }

    categories.append(new_cat)
    save_db(db)
    return jsonify({"success": True, "category": new_cat})

@app.route('/api/categories/<cat_id>', methods=['PUT', 'DELETE'])
def api_category_item(cat_id):
    db = load_db()
    categories = db.get('categories', [])
    idx = next((i for i, c in enumerate(categories) if c['id'] == cat_id), None)

    if idx is None:
        return jsonify({"success": False, "message": "Category not found"}), 404

    if request.method == 'PUT':
        payload = request.get_json() or {}
        categories[idx]['name'] = payload.get('name', categories[idx]['name']).strip()
        categories[idx]['classification'] = payload.get('classification', categories[idx].get('classification', 'Website'))
        categories[idx]['desc'] = payload.get('desc', categories[idx]['desc']).strip()
        if 'referenceUrl' in payload:
            categories[idx]['referenceUrl'] = payload.get('referenceUrl', '').strip()
        categories[idx]['basePriceINR'] = int(payload.get('basePriceINR', categories[idx].get('basePriceINR', 0)))
        categories[idx]['basePriceUSD'] = int(payload.get('basePriceUSD', categories[idx].get('basePriceUSD', 0)))
        if 'features' in payload:
            categories[idx]['features'] = payload['features']
        save_db(db)
        return jsonify({"success": True, "category": categories[idx]})

    elif request.method == 'DELETE':
        deleted = categories.pop(idx)
        save_db(db)
        return jsonify({"success": True, "deleted": deleted})

@app.route('/api/categories/template', methods=['GET'])
def api_categories_template():
    csv_content = "Category Name,Classification,Description,Reference Website,INR Price,USD Price,Included Features\n"
    csv_content += "Basic Business Website,Website,5-page corporate online presence,https://stripe.com,15000,250,Responsive Design|Google Sign-in|Contact Form|Dashboard\n"
    csv_content += "Custom SaaS Platform,Software Application,Multi-tenant recurring platform,https://linear.app,75000,1000,Multi-Tenant|Stripe Billing|REST API|Role Access\n"
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=aivontraa_categories_template.csv"}
    )

def safe_parse_number(val, default=0):
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return int(round(val))
    s = str(val).strip()
    if not s:
        return default
    s = s.replace('₹', '').replace('$', '').replace('€', '').replace('£', '').replace(',', '').strip()
    try:
        return int(round(float(s)))
    except (ValueError, TypeError):
        return default

def get_flex_field(row: dict, candidate_keys: list, default=''):
    if not isinstance(row, dict):
        return default
    clean_candidates = [k.lower().replace(' ', '').replace('_', '').replace('-', '') for k in candidate_keys]
    
    # 1. Exact match first
    for k in candidate_keys:
        if k in row and row[k] is not None and str(row[k]).strip() != '':
            return row[k]
            
    # 2. Normalized match (handles headers with trailing spaces like 'Category Name ')
    for row_key, val in row.items():
        if val is None or str(val).strip() == '':
            continue
        clean_row_key = str(row_key).lower().replace(' ', '').replace('_', '').replace('-', '')
        if clean_row_key in clean_candidates:
            return val

    return default

def parse_features_list(raw_feats):
    if raw_feats is None:
        return []
    if isinstance(raw_feats, list):
        return [str(f).strip() for f in raw_feats if str(f).strip()]
    s = str(raw_feats).strip()
    if not s:
        return []
    parts = s.replace('\n', '|').replace(';', '|').replace(',', '|').replace('•', '|').split('|')
    return [p.strip() for p in parts if p.strip()]

@app.route('/api/categories/bulk-upload', methods=['POST'])
def api_categories_bulk_upload():
    try:
        payload = request.get_json() or {}
        items = payload.get('categories', [])
        if not items or not isinstance(items, list):
            return jsonify({"success": False, "message": "No category records provided in uploaded Excel file"}), 400

        db = load_db()
        existing_cats = db.setdefault('categories', [])
        existing_names = {c.get('name', '').lower() for c in existing_cats}
        added, skipped = [], []

        for idx, row in enumerate(items, start=1):
            if not isinstance(row, dict):
                continue

            name = str(get_flex_field(row, ['Category Name', 'name', 'category', 'service name', 'title'])).strip()
            if not name:
                continue

            if name.lower() in existing_names:
                skipped.append(name)
                continue

            raw_feats = get_flex_field(row, ['Included Features', 'features', 'key features', 'feature list'])
            features = parse_features_list(raw_feats)

            inr_val = get_flex_field(row, ['INR Price', 'basePriceINR', 'price inr', 'inr', 'price (inr)', 'base price inr', 'price', 'cost inr'])
            usd_val = get_flex_field(row, ['USD Price', 'basePriceUSD', 'price usd', 'usd', 'price (usd)', 'base price usd', 'cost usd'])

            classification = str(get_flex_field(row, ['Classification', 'classification', 'type', 'category type'], 'Website')).strip()
            desc = str(get_flex_field(row, ['Description', 'desc', 'details', 'summary'], '')).strip()
            ref_url = str(get_flex_field(row, ['Reference Website', 'referenceUrl', 'reference url', 'website', 'url', 'reference link'], '')).strip()

            new_cat = {
                "id": f"cat-{uuid.uuid4().hex[:6]}",
                "name": name,
                "classification": classification or "Website",
                "desc": desc,
                "referenceUrl": ref_url,
                "basePriceINR": safe_parse_number(inr_val, 0),
                "basePriceUSD": safe_parse_number(usd_val, 0),
                "features": features
            }
            existing_cats.append(new_cat)
            existing_names.add(name.lower())
            added.append(new_cat)

        save_db(db)
        return jsonify({
            "success": True,
            "importedCount": len(added),
            "skippedDuplicates": skipped,
            "message": f"Successfully imported {len(added)} categories"
        })
    except Exception as e:
        print("Error in api_categories_bulk_upload:", e)
        return jsonify({"success": False, "message": f"Bulk upload failed: {str(e)}"}), 500

@app.route('/api/users/bulk-upload', methods=['POST'])
def api_users_bulk_upload():
    try:
        payload = request.get_json() or {}
        items = payload.get('users', [])
        if not items or not isinstance(items, list):
            return jsonify({"success": False, "message": "No user records provided"}), 400

        db = load_db()
        users = db.setdefault('users', [])
        existing_emails = {u.get('email', '').lower() for u in users}
        added, skipped = [], []

        for row in items:
            if not isinstance(row, dict):
                continue
            email = str(get_flex_field(row, ['Google Email Address', 'email', 'Google Account Email', 'user email', 'mail'])).strip().lower()
            name = str(get_flex_field(row, ['Full Name', 'name', 'user name', 'employee name'])).strip()
            role = str(get_flex_field(row, ['Role Category', 'role', 'user role'], 'marketing')).strip().lower()
            if not email or '@' not in email:
                continue
            if email in existing_emails:
                skipped.append(email)
                continue

            raw_resp = get_flex_field(row, ['Assigned Responsibilities', 'responsibilities', 'responsibility', 'duties'])
            resps = parse_features_list(raw_resp) if raw_resp else (["Full System Administration"] if role == 'admin' else ["Marketing Executive"])

            new_user = {
                "id": f"usr-{role[:3]}-{uuid.uuid4().hex[:6]}",
                "name": name or email.split('@')[0],
                "email": email,
                "username": email.split('@')[0],
                "role": role if role in ('admin', 'developer', 'marketing') else 'marketing',
                "authMethod": "google",
                "status": "active",
                "responsibilities": resps,
                "createdAt": datetime.now().strftime("%Y-%m-%d")
            }
            users.append(new_user)
            existing_emails.add(email)
            added.append(new_user)

        save_db(db)
        return jsonify({
            "success": True,
            "importedCount": len(added),
            "skippedDuplicates": skipped
        })
    except Exception as e:
        print("Error in api_users_bulk_upload:", e)
        return jsonify({"success": False, "message": f"User bulk upload failed: {str(e)}"}), 500


# -------------------------------------------------------------
# COMMISSION SLABS API (Side-by-Side: INR & USD, Max 10%)
# -------------------------------------------------------------
@app.route('/api/commission/slabs', methods=['GET', 'POST'])
def api_commission_slabs():
    db = load_db()
    if request.method == 'GET':
        return jsonify({
            "inr": db.get('commissionSlabsINR', []),
            "usd": db.get('commissionSlabsUSD', [])
        })

    payload = request.get_json() or {}
    title = payload.get('title', '').strip()
    currency = payload.get('currency', 'INR').upper()
    min_price = float(payload.get('minPrice', 0))
    max_price = float(payload.get('maxPrice', 0))
    rate = min(10.0, max(0.0, float(payload.get('rate', 0))))

    new_slab = {
        "id": f"slab-{currency.lower()}-{uuid.uuid4().hex[:6]}",
        "title": title or f"{currency} Slab",
        "minPrice": min_price,
        "maxPrice": max_price,
        "rate": rate
    }

    key = 'commissionSlabsUSD' if currency == 'USD' else 'commissionSlabsINR'
    db.setdefault(key, []).append(new_slab)
    save_db(db)
    return jsonify({"success": True, "slab": new_slab, "currency": currency})

@app.route('/api/commission/slabs/<slab_id>', methods=['PUT', 'DELETE'])
def api_commission_slab_item(slab_id):
    db = load_db()
    is_usd = 'usd' in slab_id.lower()
    key = 'commissionSlabsUSD' if is_usd else 'commissionSlabsINR'
    slabs = db.get(key, [])
    idx = next((i for i, s in enumerate(slabs) if s['id'] == slab_id), None)

    if idx is None:
        alt_key = 'commissionSlabsINR' if is_usd else 'commissionSlabsUSD'
        slabs = db.get(alt_key, [])
        idx = next((i for i, s in enumerate(slabs) if s['id'] == slab_id), None)
        if idx is not None: key = alt_key

    if idx is None:
        return jsonify({"success": False, "message": "Slab not found"}), 404

    if request.method == 'PUT':
        payload = request.get_json() or {}
        slabs[idx]['title'] = payload.get('title', slabs[idx]['title']).strip()
        slabs[idx]['minPrice'] = float(payload.get('minPrice', slabs[idx]['minPrice']))
        slabs[idx]['maxPrice'] = float(payload.get('maxPrice', slabs[idx]['maxPrice']))
        slabs[idx]['rate'] = min(10.0, max(0.0, float(payload.get('rate', slabs[idx]['rate']))))
        save_db(db)
        return jsonify({"success": True, "slab": slabs[idx]})

    elif request.method == 'DELETE':
        deleted = slabs.pop(idx)
        save_db(db)
        return jsonify({"success": True, "deleted": deleted})


# -------------------------------------------------------------
# MARKETING TEAM & MULTIPLE RESPONSIBILITIES API
# -------------------------------------------------------------
MARKETING_RESPONSIBILITIES = [
    "Marketing Executive",
    "Client Communication",
    "Payment Collection",
    "Customer Follow-up",
    "Requirement Collection",
    "Documentation",
    "Project Coordination",
    "Other Responsibilities"
]

@app.route('/api/marketing/responsibilities-list', methods=['GET'])
def api_marketing_responsibilities_list():
    return jsonify(MARKETING_RESPONSIBILITIES)

@app.route('/api/users', methods=['GET', 'POST'])
def api_users():
    db = load_db()
    if request.method == 'GET':
        return jsonify(db.get('users', []))

    payload = request.get_json() or {}
    name = payload.get('name', '').strip()
    email = payload.get('email', '').strip().lower()
    role = payload.get('role', 'marketing').strip().lower()
    resps = payload.get('responsibilities', [])

    if not name or not email:
        return jsonify({"success": False, "message": "Name and Email are required"}), 400

    users = db.get('users', [])
    if any(u.get('email', '').lower() == email for u in users):
        return jsonify({"success": False, "message": f"Email '{email}' is already registered"}), 400

    new_user = {
        "id": f"usr-{role[:3]}-{uuid.uuid4().hex[:6]}",
        "name": name,
        "email": email,
        "username": email.split('@')[0],
        "role": role,
        "authMethod": "google",
        "status": payload.get('status', 'active'),
        "responsibilities": resps if role == 'marketing' else (["Full System Administration"] if role == 'admin' else ["Software Engineering"]),
        "createdAt": datetime.now().strftime("%Y-%m-%d")
    }
    users.append(new_user)
    save_db(db)
    return jsonify({"success": True, "user": new_user})

@app.route('/api/users/<user_id>', methods=['PUT', 'DELETE'])
def api_user_item(user_id):
    db = load_db()
    users = db.get('users', [])
    idx = next((i for i, u in enumerate(users) if u['id'] == user_id), None)
    if idx is None:
        return jsonify({"success": False, "message": "User not found"}), 404

    if request.method == 'PUT':
        payload = request.get_json() or {}
        users[idx]['name'] = payload.get('name', users[idx]['name']).strip()
        users[idx]['email'] = payload.get('email', users[idx]['email']).strip().lower()
        users[idx]['role'] = payload.get('role', users[idx]['role'])
        if 'responsibilities' in payload:
            users[idx]['responsibilities'] = payload['responsibilities']
        users[idx]['status'] = payload.get('status', users[idx]['status'])
        save_db(db)
        return jsonify({"success": True, "user": users[idx]})

    elif request.method == 'DELETE':
        user_email = users[idx].get('email', '').lower()
        if user_email == ROOT_ADMIN_EMAIL.lower():
            return jsonify({"success": False, "message": "Cannot delete primary root administrator account"}), 400
        deleted = users.pop(idx)
        save_db(db)
        return jsonify({"success": True, "deleted": deleted})

@app.route('/api/users/<user_id>/responsibilities', methods=['PUT'])
def api_update_user_responsibilities(user_id):
    """
    Updates employee responsibilities.
    """
    db = load_db()
    users = db.get('users', [])
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    payload = request.get_json() or {}
    assign_all = payload.get('all', False)
    resps = payload.get('responsibilities', [])

    if assign_all:
        user['responsibilities'] = list(MARKETING_RESPONSIBILITIES)
    else:
        user['responsibilities'] = resps

    save_db(db)
    return jsonify({"success": True, "user": user, "responsibilities": user['responsibilities']})

@app.route('/api/users/<user_id>/toggle-status', methods=['POST'])
def api_user_toggle_status(user_id):
    db = load_db()
    users = db.get('users', [])
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404
    if user.get('email', '').lower() == ROOT_ADMIN_EMAIL.lower():
        return jsonify({"success": False, "message": "Cannot deactivate primary root admin"}), 400

    user['status'] = 'inactive' if user.get('status') == 'active' else 'active'
    save_db(db)
    return jsonify({"success": True, "status": user['status']})

    user['status'] = 'inactive' if user.get('status') == 'active' else 'active'
    save_db(db)
    return jsonify({"success": True, "status": user['status']})


# -------------------------------------------------------------
# ADD-ONS CONFIGURATION (Deprecated - returns empty list)
# -------------------------------------------------------------
@app.route('/api/addons', methods=['GET', 'POST'])
def api_addons():
    if request.method == 'GET':
        return jsonify([])
    return jsonify({"success": True, "addons": []})

@app.route('/api/addons/<add_id>', methods=['PUT', 'DELETE'])
def api_addon_item(add_id):
    return jsonify({"success": True})


# -------------------------------------------------------------
# QUOTATIONS API (GST 18%, Strict Lifecycle, Permanent Records)
# -------------------------------------------------------------
@app.route('/api/quotations', methods=['GET', 'POST'])
def api_quotations():
    db = load_db()
    role = request.headers.get('X-User-Role', '')
    if request.method == 'GET':
        quotes = db.get('quotations', [])
        return jsonify(quotes)

    payload = request.get_json() or {}
    client_name = payload.get('clientName', '').strip()
    if not client_name:
        return jsonify({"success": False, "message": "Client Name is required"}), 400

    quote_num = payload.get('quoteNumber') or f"AIV-QT-2026-{uuid.uuid4().hex[:4].upper()}"
    today_str = datetime.now().strftime("%Y-%m-%d")

    currency = payload.get('currency', 'INR').upper()
    if currency not in ['INR', 'USD']:
        currency = 'INR'

    billing_cadence = payload.get('billingCadence', 'annual').lower()
    base_price = float(payload.get('basePrice', 0))
    domain_amount = float(payload.get('domainAmount', 0))
    addons = payload.get('addons', [])

    # Calculate separate totals for INR and USD
    inr_addons = [a for a in addons if str(a.get('currency', '')).upper() == 'INR']
    usd_addons = [a for a in addons if str(a.get('currency', '')).upper() == 'USD']
    addons_inr = round(sum(float(a.get('price', 0)) for a in inr_addons), 2)
    addons_usd = round(sum(float(a.get('price', 0)) for a in usd_addons), 2)

    # Base price and domain belong to the base quotation currency
    base_inr = (base_price + domain_amount) if currency == 'INR' else 0.0
    base_usd = (base_price + domain_amount) if currency == 'USD' else 0.0

    subtotal_inr = round(base_inr + addons_inr, 2)
    subtotal_usd = round(base_usd + addons_usd, 2)

    gst_inr = round(subtotal_inr * 0.18, 2) if subtotal_inr > 0 else 0.0
    total_inr = round(subtotal_inr + gst_inr, 2) if subtotal_inr > 0 else 0.0

    gst_usd = round(subtotal_usd * 0.18, 2) if subtotal_usd > 0 else 0.0
    total_usd = round(subtotal_usd + gst_usd, 2) if subtotal_usd > 0 else 0.0

    is_mixed_currency = (subtotal_inr > 0 and subtotal_usd > 0)

    # Primary fields based on base currency or single currency
    if currency == 'USD':
        subtotal = subtotal_usd
        gst_amount = gst_usd
        total_price = total_usd
    else:
        subtotal = subtotal_inr
        gst_amount = gst_inr
        total_price = total_inr

    # Automatic Commission Calculation based on currency slabs
    slabs_inr = db.get('commissionSlabsINR', [])
    matched_slab_inr = next((s for s in slabs_inr if subtotal_inr >= s.get('minPrice', 0) and subtotal_inr <= s.get('maxPrice', 99999999)), None)
    rate_inr = min(10.0, matched_slab_inr.get('rate', 7.0)) if matched_slab_inr else 7.0
    commission_amount_inr = round((subtotal_inr * rate_inr) / 100, 2)

    slabs_usd = db.get('commissionSlabsUSD', [])
    matched_slab_usd = next((s for s in slabs_usd if subtotal_usd >= s.get('minPrice', 0) and subtotal_usd <= s.get('maxPrice', 99999999)), None)
    rate_usd = min(10.0, matched_slab_usd.get('rate', 7.0)) if matched_slab_usd else 7.0
    commission_amount_usd = round((subtotal_usd * rate_usd) / 100, 2)

    commission_amount = commission_amount_usd if currency == 'USD' else commission_amount_inr
    rate = rate_usd if currency == 'USD' else rate_inr

    cat_id = payload.get('categoryId', '')
    cat = next((c for c in db.get('categories', []) if c['id'] == cat_id), None)
    reference_url = cat.get('referenceUrl', '') if cat else payload.get('referenceUrl', '')

    new_quote = {
        "id": f"qt-{uuid.uuid4().hex[:6]}",
        "quoteNumber": quote_num,
        "clientName": client_name,
        "classification": payload.get('classification', 'Website'),
        "categoryId": cat_id,
        "categoryName": payload.get('categoryName', ''),
        "referenceUrl": reference_url,
        "currency": currency,
        "billingCadence": billing_cadence,
        "basePrice": base_price,
        "domainAmount": domain_amount,
        "addons": addons,
        "addonsINR": addons_inr,
        "addonsUSD": addons_usd,
        "subtotal": subtotal,
        "subtotalINR": subtotal_inr,
        "subtotalUSD": subtotal_usd,
        "gstRate": 18.0,
        "gstAmount": gst_amount,
        "gstINR": gst_inr,
        "gstUSD": gst_usd,
        "totalPrice": total_price,
        "totalINR": total_inr,
        "totalUSD": total_usd,
        "isMixedCurrency": is_mixed_currency,
        "commissionRate": rate,
        "commissionAmount": commission_amount,
        "commissionAmountINR": commission_amount_inr,
        "commissionAmountUSD": commission_amount_usd,
        "commExecutiveName": payload.get('commExecutiveName', 'Client Communication Exec'),
        "docCoordinatorName": payload.get('docCoordinatorName', 'Project Documentation Coordinator'),
        "assignedMarketing": payload.get('assignedMarketing', []),
        "requirementsFiles": payload.get('requirementsFiles', []),
        "status": payload.get('status', 'Generated'),  # Draft, Generated, Sent to Customer, Accepted, Rejected
        "assignmentStatus": "none",
        "terms": payload.get('terms', "50% advance on kickoff, 50% upon deployment. 30 days post-launch support included. All prices subject to 18% GST."),
        "createdAt": today_str,
        "updatedAt": today_str
    }

    db.setdefault('quotations', []).insert(0, new_quote)
    save_db(db)
    return jsonify({"success": True, "quotation": new_quote}), 201

@app.route('/api/quotations/<quote_id>', methods=['DELETE'])
def api_delete_quotation(quote_id):
    # Requirement 5: Important: Quotations must NOT have a delete option. Maintain quotation history permanently.
    return jsonify({
        "success": False,
        "message": "Quotations cannot be deleted. All quotation records are permanently preserved."
    }), 403

@app.route('/api/quotations/<quote_id>/status', methods=['PUT'])
def api_update_quotation_status(quote_id):
    """
    Quotation lifecycle: Draft -> Generated -> Sent to Customer -> Accepted -> Rejected.
    On 'Accepted': Automatically generates project record, enables engineering handover, enables payment workflow.
    """
    db = load_db()
    quotations = db.get('quotations', [])
    quote = next((q for q in quotations if q['id'] == quote_id), None)
    if not quote:
        return jsonify({"success": False, "message": "Quotation not found"}), 404

    payload = request.get_json() or {}
    new_status = payload.get('status', quote.get('status'))
    quote['status'] = new_status
    quote['updatedAt'] = datetime.now().strftime("%Y-%m-%d")

    # If status becomes Accepted: automatically activate project and payment workflow
    if new_status == 'Accepted':
        quote['assignmentStatus'] = 'pending_assignment'
        projects = db.setdefault('projects', [])
        existing_proj = next((p for p in projects if p.get('quoteId') == quote_id), None)
        if not existing_proj:
            new_proj = {
                "id": f"proj-{uuid.uuid4().hex[:6]}",
                "quoteId": quote['id'],
                "quoteNumber": quote['quoteNumber'],
                "clientName": quote['clientName'],
                "projectName": quote['categoryName'] or "Client Project",
                "categoryName": quote['categoryName'] or "Website Solution",
                "referenceUrl": quote.get('referenceUrl', ''),
                "requirements": [
                    f"{quote.get('classification', 'Website')} Frontend Architecture & UI Components",
                    "Responsive Cross-Device Layouts (Mobile, Tablet, Desktop)",
                    "REST API Integration & Secure Cloud Database",
                    "18% GST Compliance & Invoicing",
                    "Cross-Browser QA & Performance Optimization"
                ],
                "commExecutiveName": quote.get('commExecutiveName', ''),
                "docCoordinatorName": quote.get('docCoordinatorName', ''),
                "assignedMarketing": quote.get('assignedMarketing', []),
                "assignedDevId": "",
                "assignedDevName": "Unassigned",
                "assignedDevEmail": "",
                "startDate": datetime.now().strftime("%Y-%m-%d"),
                "expectedEndDate": "",
                "assignmentStatus": "pending_assignment",
                "assignmentRequestedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "assignmentRequestedBy": quote.get('commExecutiveName', 'Marketing Team'),
                "assignmentHistory": [],
                "status": "Assigned",
                "progress": 0,
                "workDescription": "Accepted by customer. Pending engineering allocation by Admin.",
                "remarks": "",
                "testingUrl": "",
                "finalUrl": "",
                "testingStatus": "Pending",
                "finalApprovalStatus": "Not Submitted",
                "zipFiles": [],
                "requirementsFiles": quote.get('requirementsFiles', []),
                "changeRequests": [],
                "payment": {
                    "quoteNumber": quote['quoteNumber'],
                    "projectName": quote['categoryName'],
                    "clientName": quote['clientName'],
                    "subtotal": quote.get('subtotal', quote.get('totalPrice', 0)),
                    "gstAmount": quote.get('gstAmount', 0),
                    "totalAmount": quote.get('totalPrice', 0),
                    "amountPaid": 0,
                    "currency": quote.get('currency', 'INR'),
                    "status": "Payment Pending",
                    "method": "PhonePe",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "refNumber": "",
                    "screenshotFilename": "",
                    "screenshotUrl": "",
                    "notes": "Awaiting kickoff payment.",
                    "verifiedBy": "",
                    "verifiedAt": "",
                    "uploadedBy": "",
                    "uploadedAt": ""
                },
                "lastUpdated": datetime.now().strftime("%Y-%m-%d")
            }
            projects.insert(0, new_proj)

    save_db(db)
    return jsonify({"success": True, "quotation": quote})

@app.route('/api/quotations/<quote_id>/request-assignment', methods=['POST'])
def api_request_developer_assignment(quote_id):
    """
    Marketing clicks ASSIGN. Requests engineering handover from Administrator.
    Preserves all customer details, requirements, and quotation data.
    """
    db = load_db()
    quotations = db.get('quotations', [])
    quote = next((q for q in quotations if q['id'] == quote_id), None)
    if not quote:
        return jsonify({"success": False, "message": "Quotation not found"}), 404

    quote['status'] = 'Accepted'
    quote['assignmentStatus'] = 'pending_assignment'
    quote['assignmentRequestedAt'] = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Ensure project record exists
    projects = db.setdefault('projects', [])
    existing_proj = next((p for p in projects if p.get('quoteId') == quote_id), None)
    if existing_proj:
        existing_proj['assignmentStatus'] = 'pending_assignment'
        existing_proj['assignmentRequestedAt'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        target_project = existing_proj
    else:
        target_project = {
            "id": f"proj-{uuid.uuid4().hex[:6]}",
            "quoteId": quote['id'],
            "quoteNumber": quote['quoteNumber'],
            "clientName": quote['clientName'],
            "projectName": quote['categoryName'] or "Client Project",
            "categoryName": quote['categoryName'] or "Website Solution",
            "referenceUrl": quote.get('referenceUrl', ''),
            "requirements": [
                f"{quote.get('classification', 'Website')} Deliverable Implementation",
                "Cross-Platform Responsive Mobile Interface",
                "Backend APIs and Secure Data Storage"
            ],
            "commExecutiveName": quote.get('commExecutiveName', ''),
            "docCoordinatorName": quote.get('docCoordinatorName', ''),
            "assignedMarketing": quote.get('assignedMarketing', []),
            "assignedDevId": "",
            "assignedDevName": "Unassigned",
            "assignedDevEmail": "",
            "startDate": datetime.now().strftime("%Y-%m-%d"),
            "expectedEndDate": "",
            "assignmentStatus": "pending_assignment",
            "assignmentRequestedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "assignmentRequestedBy": quote.get('commExecutiveName', 'Marketing Team'),
            "assignmentHistory": [],
            "status": "Assigned",
            "progress": 0,
            "workDescription": "Accepted by customer. Pending engineering allocation by Admin.",
            "remarks": "",
            "testingUrl": "",
            "finalUrl": "",
            "testingStatus": "Pending",
            "finalApprovalStatus": "Not Submitted",
            "zipFiles": [],
            "requirementsFiles": quote.get('requirementsFiles', []),
            "changeRequests": [],
            "payment": {
                "quoteNumber": quote['quoteNumber'],
                "projectName": quote['categoryName'],
                "clientName": quote['clientName'],
                "subtotal": quote.get('subtotal', quote.get('totalPrice', 0)),
                "gstAmount": quote.get('gstAmount', 0),
                "totalAmount": quote.get('totalPrice', 0),
                "amountPaid": 0,
                "currency": quote.get('currency', 'INR'),
                "status": "Payment Pending",
                "method": "PhonePe",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "refNumber": "",
                "screenshotFilename": "",
                "screenshotUrl": "",
                "notes": "Awaiting kickoff payment.",
                "verifiedBy": "",
                "verifiedAt": "",
                "uploadedBy": "",
                "uploadedAt": ""
            },
            "lastUpdated": datetime.now().strftime("%Y-%m-%d")
        }
        projects.insert(0, target_project)

    save_db(db)
    return jsonify({
        "success": True,
        "message": "Engineering handover request submitted to Administrator.",
        "project": target_project
    })

@app.route('/api/quotations/<quote_id>/documents', methods=['POST'])
def api_upload_quotation_document(quote_id):
    """
    Upload requirements document (.docx, .pdf, .zip <= 500 KB) attached to quotation.
    Automatically synced to engineering project files upon handover.
    """
    db = load_db()
    quotations = db.get('quotations', [])
    quote = next((q for q in quotations if q['id'] == quote_id), None)
    if not quote:
        return jsonify({"success": False, "message": "Quotation not found"}), 404

    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file uploaded"}), 400

    file = request.files['file']
    if not file or not file.filename:
        return jsonify({"success": False, "message": "Empty file received"}), 400

    orig_name = file.filename
    ext = os.path.splitext(orig_name)[1].lower()
    if ext not in ['.docx', '.pdf', '.zip', '.png', '.jpg', '.jpeg']:
        return jsonify({"success": False, "message": "Unsupported file format. Allowed: .docx, .pdf, .zip, .png, .jpg"}), 400

    file_bytes = file.read()
    if len(file_bytes) > MAX_DOCUMENT_SIZE:
        return jsonify({"success": False, "message": f"File exceeds maximum allowed size of 500 KB (Size: {round(len(file_bytes)/1024, 1)} KB)"}), 400

    clean_name = f"quote_{quote_id}_{uuid.uuid4().hex[:6]}_{secure_filename(orig_name)}"
    save_path = os.path.join(DOCUMENTS_UPLOAD_FOLDER, clean_name)
    with open(save_path, 'wb') as f:
        f.write(file_bytes)

    uploaded_by = request.form.get('uploadedBy') or request.headers.get('X-User-Name', 'Marketing Team')
    doc_entry = {
        "id": f"doc-{uuid.uuid4().hex[:6]}",
        "filename": clean_name,
        "originalName": orig_name,
        "sizeKb": round(len(file_bytes) / 1024, 1),
        "uploadedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "uploadedBy": uploaded_by,
        "url": f"/uploads/documents/{clean_name}"
    }

    quote.setdefault('requirementsFiles', []).append(doc_entry)

    # Sync to project if already generated
    for proj in db.get('projects', []):
        if proj.get('quoteId') == quote_id:
            proj.setdefault('files', []).append(doc_entry)
            proj['lastUpdated'] = datetime.now().strftime("%Y-%m-%d")

    save_db(db)
    return jsonify({"success": True, "document": doc_entry}), 200

@app.route('/api/documents/<filename>', methods=['GET'])
def api_download_document_alias(filename):
    return send_from_directory(DOCUMENTS_UPLOAD_FOLDER, secure_filename(filename))


# -------------------------------------------------------------
# ADMIN PROJECT ASSIGNMENT MANAGEMENT & ENGINEERING HANDOVER
# -------------------------------------------------------------
@app.route('/api/admin/pending-assignments', methods=['GET'])
def api_admin_pending_assignments():
    """Returns accepted projects awaiting engineering assignment"""
    db = load_db()
    projects = db.get('projects', [])
    pending = [p for p in projects if p.get('assignmentStatus') == 'pending_assignment' or not p.get('assignedDevId')]
    return jsonify(pending)

@app.route('/api/admin/developers-availability', methods=['GET'])
def api_admin_developers_availability():
    """Lists developers with their active project counts and availability"""
    db = load_db()
    users = db.get('users', [])
    projects = db.get('projects', [])

    devs = [u for u in users if u.get('role') == 'developer' and u.get('status') == 'active']
    res = []
    for d in devs:
        active_count = len([p for p in projects if p.get('assignedDevId') == d['id'] and p.get('status') not in ['Project Completed', 'Completed']])
        res.append({
            "id": d["id"],
            "name": d.get("name", d.get("username", "Developer")),
            "email": d.get("email", ""),
            "assignedProjectsCount": active_count,
            "availability": "Available" if active_count < 2 else "Busy"
        })
    return jsonify(res)

@app.route('/api/projects/<proj_id>/assign', methods=['POST'])
def api_project_assign_developer(proj_id):
    """
    Administrator assigns or reassigns project to engineering personnel.
    """
    db = load_db()
    projects = db.get('projects', [])
    proj = next((p for p in projects if p['id'] == proj_id), None)
    if not proj:
        return jsonify({"success": False, "message": "Project not found"}), 404

    payload = request.get_json() or {}
    dev_id = payload.get('developerId')
    expected_end = payload.get('expectedEndDate', '')
    start_date = payload.get('startDate', datetime.now().strftime("%Y-%m-%d"))

    users = db.get('users', [])
    dev = next((u for u in users if u['id'] == dev_id and u.get('role') == 'developer'), None)
    if not dev:
        return jsonify({"success": False, "message": "Invalid developer selected"}), 400

    admin_name = request.headers.get('X-User-Name') or 'Administrator'

    proj['assignedDevId'] = dev['id']
    proj['assignedDevName'] = dev.get('name', dev.get('username'))
    proj['assignedDevEmail'] = dev.get('email', '')
    proj['startDate'] = start_date
    proj['expectedEndDate'] = expected_end
    proj['assignmentStatus'] = 'assigned'
    proj['status'] = 'Assigned'
    proj['workDescription'] = f"Allocated to engineering: {proj['assignedDevName']}. Ready for sprint kickoff."
    proj['lastUpdated'] = datetime.now().strftime("%Y-%m-%d")

    proj.setdefault('assignmentHistory', []).append({
        "developerId": dev['id'],
        "developerName": proj['assignedDevName'],
        "assignedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "assignedBy": admin_name
    })

    save_db(db)
    return jsonify({"success": True, "project": proj})


# -------------------------------------------------------------
# PROJECTS API (DEVELOPER & REVIEW WORKFLOW)
# -------------------------------------------------------------
@app.route('/api/projects', methods=['GET', 'POST'])
def api_projects():
    db = load_db()
    role = request.headers.get('X-User-Role', '')
    if request.method == 'GET':
        projects = db.get('projects', [])
        # PRIVACY MASKING: Marketing team cannot see developer name
        if role.startswith('marketing'):
            masked = []
            for p in projects:
                p_copy = dict(p)
                if p_copy.get('assignedDevId'):
                    p_copy['assignedDevName'] = "Engineering Team Assigned"
                    p_copy.pop('assignedDevEmail', None)
                    p_copy['assignmentHistory'] = []
                masked.append(p_copy)
            return jsonify(masked)
        return jsonify(projects)

    payload = request.get_json() or {}
    new_project = {
        "id": f"proj-{uuid.uuid4().hex[:6]}",
        "quoteId": payload.get('quoteId', ''),
        "quoteNumber": payload.get('quoteNumber', 'AIV-PROJ'),
        "clientName": payload.get('clientName', ''),
        "projectName": payload.get('projectName', ''),
        "categoryName": payload.get('categoryName', ''),
        "referenceUrl": payload.get('referenceUrl', ''),
        "requirements": payload.get('requirements', []),
        "commExecutiveName": payload.get('commExecutiveName', ''),
        "docCoordinatorName": payload.get('docCoordinatorName', ''),
        "assignedMarketing": payload.get('assignedMarketing', []),
        "assignedDevId": payload.get('assignedDevId', ''),
        "assignedDevName": payload.get('assignedDevName', 'Unassigned'),
        "assignedDevEmail": payload.get('assignedDevEmail', ''),
        "startDate": payload.get('startDate', datetime.now().strftime("%Y-%m-%d")),
        "expectedEndDate": payload.get('expectedEndDate', ''),
        "assignmentStatus": "assigned" if payload.get('assignedDevId') else "pending_assignment",
        "assignmentHistory": [],
        "status": payload.get('status', 'Assigned'),
        "progress": int(payload.get('progress') or 0),
        "workDescription": payload.get('workDescription', 'Allocated to engineering team.'),
        "remarks": payload.get('remarks', ''),
        "testingUrl": "",
        "finalUrl": "",
        "testingStatus": "Pending",
        "finalApprovalStatus": "Not Submitted",
        "zipFiles": [],
        "requirementsFiles": payload.get('requirementsFiles', []),
        "changeRequests": [],
        "payment": payload.get('payment', {}),
        "lastUpdated": datetime.now().strftime("%Y-%m-%d")
    }

    db.setdefault('projects', []).insert(0, new_project)
    save_db(db)
    return jsonify({"success": True, "project": new_project})

@app.route('/api/projects/<proj_id>/progress', methods=['PUT'])
def api_project_progress(proj_id):
    db = load_db()
    projects = db.get('projects', [])
    proj = next((p for p in projects if p['id'] == proj_id), None)
    if not proj:
        return jsonify({"success": False, "message": "Project not found"}), 404

    payload = request.get_json() or {}
    if 'status' in payload: proj['status'] = payload['status']
    if 'progress' in payload: proj['progress'] = int(payload['progress'])
    if 'workDescription' in payload: proj['workDescription'] = payload['workDescription']
    if 'remarks' in payload: proj['remarks'] = payload['remarks']

    proj['lastUpdated'] = datetime.now().strftime("%Y-%m-%d")
    save_db(db)
    return jsonify({"success": True, "project": proj})

@app.route('/api/projects/<proj_id>/testing-submission', methods=['PUT'])
def api_project_testing_submission(proj_id):
    db = load_db()
    projects = db.get('projects', [])
    proj = next((p for p in projects if p['id'] == proj_id), None)
    if not proj:
        return jsonify({"success": False, "message": "Project not found"}), 404

    payload = request.get_json() or {}
    url = payload.get('testingUrl', '').strip()
    if not url:
        return jsonify({"success": False, "message": "Testing Website URL is required"}), 400

    proj['testingUrl'] = url
    proj['testingDescription'] = payload.get('testingDescription', '').strip()
    proj['testingDate'] = payload.get('submissionDate', datetime.now().strftime("%Y-%m-%d"))
    proj['testingStatus'] = 'Testing Website Submitted'
    proj['status'] = 'Testing Website Submitted'
    proj['lastUpdated'] = datetime.now().strftime("%Y-%m-%d")

    save_db(db)
    return jsonify({"success": True, "project": proj})

@app.route('/api/projects/<proj_id>/final-submission', methods=['PUT'])
def api_project_final_submission(proj_id):
    db = load_db()
    projects = db.get('projects', [])
    proj = next((p for p in projects if p['id'] == proj_id), None)
    if not proj:
        return jsonify({"success": False, "message": "Project not found"}), 404

    payload = request.get_json() or {}
    url = payload.get('finalUrl', '').strip()
    if not url:
        return jsonify({"success": False, "message": "Final Website URL is required"}), 400

    proj['finalUrl'] = url
    proj['finalDescription'] = payload.get('finalDescription', '').strip()
    proj['finalDate'] = payload.get('submissionDate', datetime.now().strftime("%Y-%m-%d"))
    proj['finalApprovalStatus'] = 'Final Website Submitted'
    proj['status'] = 'Final Website Submitted'
    proj['lastUpdated'] = datetime.now().strftime("%Y-%m-%d")

    save_db(db)
    return jsonify({"success": True, "project": proj})

@app.route('/api/projects/<proj_id>/request-changes', methods=['POST'])
def api_project_admin_request_changes(proj_id):
    db = load_db()
    projects = db.get('projects', [])
    proj = next((p for p in projects if p['id'] == proj_id), None)
    if not proj:
        return jsonify({"success": False, "message": "Project not found"}), 404

    payload = request.get_json() or {}
    desc = payload.get('changeDescription', '').strip()
    if not desc:
        return jsonify({"success": False, "message": "Change description is required"}), 400

    new_cr = {
        "id": f"cr-{uuid.uuid4().hex[:6]}",
        "title": payload.get('title') or "Admin Review Revisions",
        "desc": desc,
        "priority": payload.get('priority', 'High'),
        "requestedBy": "Administrator Review",
        "recordedBy": request.headers.get('X-User-Name', 'Administrator'),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "Pending"
    }

    proj.setdefault('changeRequests', []).insert(0, new_cr)
    proj['status'] = 'Changes Requested'
    proj['finalApprovalStatus'] = f"Revisions Requested: {desc}"
    proj['lastUpdated'] = datetime.now().strftime("%Y-%m-%d")

    save_db(db)
    return jsonify({"success": True, "project": proj, "changeRequest": new_cr})

@app.route('/api/projects/<proj_id>/approve-website', methods=['POST'])
def api_project_admin_approve_website(proj_id):
    db = load_db()
    projects = db.get('projects', [])
    proj = next((p for p in projects if p['id'] == proj_id), None)
    if not proj:
        return jsonify({"success": False, "message": "Project not found"}), 404

    payload = request.get_json() or {}
    proj['status'] = 'Approved'
    proj['finalApprovalStatus'] = 'Approved by Administrator'
    proj['remarks'] = payload.get('remarks', 'Production build approved. Proceeding to payment verification.')

    payment = proj.setdefault('payment', {})
    if payment.get('status') not in ['Payment Verified', 'Verification Pending', 'Payment Proof Uploaded']:
        payment['status'] = 'Payment Pending'

    proj['lastUpdated'] = datetime.now().strftime("%Y-%m-%d")
    save_db(db)
    return jsonify({"success": True, "project": proj})


# -------------------------------------------------------------
# CHANGE REQUESTS & DOCX DOCUMENT UPLOAD (Max 500 KB)
# -------------------------------------------------------------
@app.route('/api/projects/<proj_id>/change-requests', methods=['GET', 'POST'])
def api_change_requests(proj_id):
    db = load_db()
    projects = db.get('projects', [])
    proj = next((p for p in projects if p['id'] == proj_id), None)
    if not proj:
        return jsonify({"success": False, "message": "Project not found"}), 404

    if request.method == 'GET':
        return jsonify(proj.get('changeRequests', []))

    payload = request.get_json(silent=True) or {}
    title = (request.form.get('title') or payload.get('title') or '').strip()
    if not title:
        return jsonify({"success": False, "message": "Change Request Title is required"}), 400

    desc = (request.form.get('desc') or request.form.get('description') or payload.get('desc') or payload.get('description') or '').strip()
    priority = request.form.get('priority') or payload.get('priority') or 'Medium'
    requested_by = request.form.get('requestedBy') or payload.get('requestedBy') or proj.get('clientName', 'Client')
    recorded_by = request.form.get('recordedBy') or request.headers.get('X-User-Name', 'Documentation Coordinator')

    doc_filename = ""
    doc_size = 0
    doc_url = ""

    # Document upload supporting Microsoft Word (.docx), .pdf, .zip <= 500 KB
    doc_file = request.files.get('file') or request.files.get('document')
    if doc_file and doc_file.filename:
        orig = doc_file.filename
        ext = os.path.splitext(orig)[1].lower()
        if ext not in ['.docx', '.pdf', '.zip', '.png', '.jpg', '.jpeg']:
            return jsonify({"success": False, "message": "Invalid file format. Supported: .docx, .pdf, .zip, .png, .jpg"}), 400

        file_bytes = doc_file.read()
        if len(file_bytes) > MAX_DOCUMENT_SIZE:
            return jsonify({"success": False, "message": "Document exceeds maximum allowed size of 500 KB"}), 400

        clean_doc = f"cr_{proj_id}_{uuid.uuid4().hex[:6]}_{secure_filename(orig)}"
        save_path = os.path.join(CHANGE_REQ_UPLOAD_FOLDER, clean_doc)
        with open(save_path, 'wb') as f:
            f.write(file_bytes)

        doc_filename = orig
        doc_size = round(len(file_bytes) / 1024, 1)
        doc_url = f"/uploads/change_requests/{clean_doc}"

    new_cr = {
        "id": f"cr-{uuid.uuid4().hex[:6]}",
        "title": title,
        "desc": desc,
        "priority": priority,
        "requestedBy": requested_by,
        "recordedBy": recorded_by,
        "documentFilename": doc_filename,
        "documentSizeKb": doc_size,
        "documentUrl": doc_url,
        "file": {
            "originalName": doc_filename,
            "filename": doc_filename,
            "sizeKb": doc_size,
            "url": doc_url
        } if doc_filename else None,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "Pending"
    }

    proj.setdefault('changeRequests', []).insert(0, new_cr)
    proj['status'] = 'Changes Requested'
    proj['lastUpdated'] = datetime.now().strftime("%Y-%m-%d")
    save_db(db)
    return jsonify({"success": True, "changeRequest": new_cr}), 201

@app.route('/api/projects/<proj_id>/change-requests/<cr_id>', methods=['PUT'])
def api_update_change_request(proj_id, cr_id):
    db = load_db()
    projects = db.get('projects', [])
    proj = next((p for p in projects if p['id'] == proj_id), None)
    if not proj:
        return jsonify({"success": False, "message": "Project not found"}), 404

    crs = proj.get('changeRequests', [])
    cr = next((c for c in crs if c['id'] == cr_id), None)
    if not cr:
        return jsonify({"success": False, "message": "Change request not found"}), 404

    payload = request.get_json() or {}
    if 'status' in payload:
        cr['status'] = payload['status']

    proj['lastUpdated'] = datetime.now().strftime("%Y-%m-%d")
    save_db(db)
    return jsonify({"success": True, "changeRequest": cr})


# -------------------------------------------------------------
# REQUIREMENTS FILE UPLOADS (.docx, .pdf, .zip <= 500 KB)
# -------------------------------------------------------------
@app.route('/api/projects/<proj_id>/uploads', methods=['POST'])
def api_upload_project_requirements(proj_id):
    db = load_db()
    projects = db.get('projects', [])
    proj = next((p for p in projects if p['id'] == proj_id), None)
    if not proj:
        return jsonify({"success": False, "message": "Project not found"}), 404

    current_files = proj.setdefault('zipFiles', [])
    if len(current_files) >= 5:
        return jsonify({"success": False, "message": "Upload limit reached. Maximum 5 requirement files per project."}), 400

    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file uploaded"}), 400

    file = request.files['file']
    if not file or not file.filename:
        return jsonify({"success": False, "message": "Empty file received"}), 400

    orig_name = file.filename
    ext = os.path.splitext(orig_name)[1].lower()
    if ext not in ['.docx', '.pdf', '.zip', '.png', '.jpg', '.jpeg']:
        return jsonify({"success": False, "message": "Invalid file format. Supported: .docx, .pdf, .zip, .png, .jpg"}), 400

    file_bytes = file.read()
    if len(file_bytes) > MAX_DOCUMENT_SIZE:
        return jsonify({"success": False, "message": f"File exceeds maximum allowed size of 500 KB (Size: {round(len(file_bytes)/1024, 1)} KB)"}), 400

    clean_name = f"{proj_id}_{uuid.uuid4().hex[:6]}_{secure_filename(orig_name)}"
    save_path = os.path.join(DOCUMENTS_UPLOAD_FOLDER, clean_name)
    with open(save_path, 'wb') as f:
        f.write(file_bytes)

    uploaded_by = request.form.get('uploadedBy') or request.headers.get('X-User-Name', 'Documentation Coordinator')
    new_entry = {
        "id": f"doc-{uuid.uuid4().hex[:6]}",
        "filename": clean_name,
        "originalName": orig_name,
        "sizeKb": round(len(file_bytes) / 1024, 1),
        "uploadedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "uploadedBy": uploaded_by
    }

    current_files.append(new_entry)
    proj['lastUpdated'] = datetime.now().strftime("%Y-%m-%d")
    save_db(db)
    return jsonify({"success": True, "file": new_entry})

@app.route('/api/projects/<proj_id>/files/<filename>', methods=['GET'])
def api_download_project_file(proj_id, filename):
    safe_name = secure_filename(filename)
    return send_from_directory(DOCUMENTS_UPLOAD_FOLDER, safe_name, as_attachment=True)


# -------------------------------------------------------------
# PAYMENT DETAILS & VERIFICATION (UPI, PhonePe, Bank Transfer)
# -------------------------------------------------------------
@app.route('/api/projects/<proj_id>/payment', methods=['POST'])
def api_project_save_payment(proj_id):
    db = load_db()
    projects = db.get('projects', [])
    proj = next((p for p in projects if p['id'] == proj_id), None)
    if not proj:
        return jsonify({"success": False, "message": "Project not found"}), 404

    payload = request.get_json() or {}
    payment = proj.setdefault('payment', {})

    if 'amountPaid' in payload: payment['amountPaid'] = float(payload['amountPaid'])
    if 'method' in payload: payment['method'] = payload['method']
    if 'date' in payload: payment['date'] = payload['date']
    if 'refNumber' in payload: payment['refNumber'] = payload['refNumber'].strip()
    if 'notes' in payload: payment['notes'] = payload['notes'].strip()
    if 'status' in payload: payment['status'] = payload['status']

    proj['lastUpdated'] = datetime.now().strftime("%Y-%m-%d")
    save_db(db)
    return jsonify({"success": True, "payment": payment, "project": proj})

@app.route('/api/projects/<proj_id>/payment-proof', methods=['POST'])
def api_project_upload_payment_proof(proj_id):
    """
    Customer uploads payment screenshot proof.
    Supported payment methods: UPI, PhonePe, Bank Transfer.
    File formats: JPG, JPEG, PNG, PDF.
    """
    db = load_db()
    projects = db.get('projects', [])
    proj = next((p for p in projects if p['id'] == proj_id), None)
    if not proj:
        return jsonify({"success": False, "message": "Project not found"}), 404

    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No payment proof file attached"}), 400

    file = request.files['file']
    if not file or not file.filename:
        return jsonify({"success": False, "message": "Empty file received"}), 400

    orig_name = file.filename
    ext = os.path.splitext(orig_name)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.pdf']:
        return jsonify({"success": False, "message": "Invalid format. Only JPG, JPEG, PNG, and PDF files are accepted."}), 400

    file_bytes = file.read()
    if len(file_bytes) > MAX_PAYMENT_SIZE:
        return jsonify({"success": False, "message": "Payment proof file exceeds 5 MB limit."}), 400

    clean_name = f"pay_{proj_id}_{uuid.uuid4().hex[:6]}_{secure_filename(orig_name)}"
    save_path = os.path.join(PAYMENT_UPLOAD_FOLDER, clean_name)
    with open(save_path, 'wb') as f:
        f.write(file_bytes)

    uploader = request.form.get('uploadedBy') or request.headers.get('X-User-Name') or 'Customer / Marketing'
    payment = proj.setdefault('payment', {})
    payment['screenshotFilename'] = clean_name
    payment['screenshotUrl'] = f"/uploads/payments/{clean_name}"
    payment['uploadedBy'] = uploader
    payment['uploadedAt'] = datetime.now().strftime("%Y-%m-%d %H:%M")
    payment['status'] = 'Payment Proof Uploaded'

    if request.form.get('amountPaid'):
        try: payment['amountPaid'] = float(request.form.get('amountPaid'))
        except ValueError: pass
    if request.form.get('method'): payment['method'] = request.form.get('method')
    if request.form.get('refNumber'): payment['refNumber'] = request.form.get('refNumber')
    if request.form.get('notes'): payment['notes'] = request.form.get('notes')

    proj['lastUpdated'] = datetime.now().strftime("%Y-%m-%d")
    save_db(db)
    return jsonify({"success": True, "payment": payment, "project": proj})

@app.route('/api/projects/<proj_id>/verify-payment', methods=['POST'])
def api_project_verify_payment(proj_id):
    """
    Administrator verifies transaction details and approves/rejects payment.
    Do NOT automatically mark payments as successful just because a screenshot is uploaded.
    """
    db = load_db()
    projects = db.get('projects', [])
    proj = next((p for p in projects if p['id'] == proj_id), None)
    if not proj:
        return jsonify({"success": False, "message": "Project not found"}), 404

    payload = request.get_json() or {}
    decision = payload.get('decision', 'Verified')
    notes = payload.get('notes', '').strip()
    admin_name = request.headers.get('X-User-Name') or 'Laxminivas Morishetty'

    payment = proj.setdefault('payment', {})

    if decision == 'Verified':
        payment['status'] = 'Payment Verified'
        payment['verifiedBy'] = admin_name
        payment['verifiedAt'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        if notes:
            payment['notes'] = f"{payment.get('notes', '')}\n[Verified]: {notes}".strip()
        proj['status'] = 'Payment Verified'
    else:
        payment['status'] = 'Payment Rejected'
        payment['rejectionReason'] = notes
        payment['notes'] = f"{payment.get('notes', '')}\n[Rejected]: {notes}".strip()
        proj['status'] = 'Approved'

    proj['lastUpdated'] = datetime.now().strftime("%Y-%m-%d")
    save_db(db)
    return jsonify({"success": True, "payment": payment, "project": proj})

@app.route('/api/projects/<proj_id>/signoff-document', methods=['POST'])
def api_project_upload_signoff_document(proj_id):
    """Upload final sign-off document (.pdf, .docx <= 500 KB) after payment verification"""
    db = load_db()
    projects = db.get('projects', [])
    proj = next((p for p in projects if p['id'] == proj_id), None)
    if not proj:
        return jsonify({"success": False, "message": "Project not found"}), 404

    payment = proj.setdefault('payment', {})
    verified_by = request.form.get('verifiedBy') or request.headers.get('X-User-Name')
    if verified_by and payment.get('status') != 'Payment Verified':
        payment['status'] = 'Payment Verified'
        payment['verifiedBy'] = verified_by
        payment['verifiedAt'] = datetime.now().strftime("%Y-%m-%d %H:%M")
    elif payment.get('status') != 'Payment Verified':
        return jsonify({"success": False, "message": "Sign-off document upload requires verified payment."}), 400

    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No document uploaded"}), 400

    file = request.files['file']
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.pdf', '.docx']:
        return jsonify({"success": False, "message": "Only PDF and Word (.docx) documents are supported for final sign-off."}), 400

    file_bytes = file.read()
    if len(file_bytes) > MAX_DOCUMENT_SIZE:
        return jsonify({"success": False, "message": "Sign-off document exceeds 500 KB limit."}), 400

    clean_name = f"signoff_{proj_id}_{uuid.uuid4().hex[:6]}_{secure_filename(file.filename)}"
    save_path = os.path.join(SIGNOFF_UPLOAD_FOLDER, clean_name)
    with open(save_path, 'wb') as f:
        f.write(file_bytes)

    proj['signoffDocument'] = {
        "filename": clean_name,
        "originalName": file.filename,
        "url": f"/uploads/signoffs/{clean_name}",
        "uploadedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "uploadedBy": request.headers.get('X-User-Name', 'Administrator')
    }
    proj['lastUpdated'] = datetime.now().strftime("%Y-%m-%d")
    save_db(db)
    return jsonify({"success": True, "signoffDocument": proj['signoffDocument']})

@app.route('/api/projects/<proj_id>/sign-off', methods=['POST'])
def api_project_admin_sign_off(proj_id):
    """
    CRITICAL WORKFLOW CHECK:
    Admin completes final sign-off. ONLY allowed after full payment verification!
    """
    db = load_db()
    projects = db.get('projects', [])
    proj = next((p for p in projects if p['id'] == proj_id), None)
    if not proj:
        return jsonify({"success": False, "message": "Project not found"}), 404

    payment = proj.get('payment', {})
    if payment.get('status') != 'Payment Verified':
        return jsonify({
            "success": False,
            "message": f"Cannot sign off project completion. Payment status is currently '{payment.get('status')}'. Final sign-off strictly requires 'Payment Verified'."
        }), 400

    admin_name = request.headers.get('X-User-Name') or 'Laxminivas Morishetty'
    today_str = datetime.now().strftime("%Y-%m-%d")

    proj['status'] = 'Project Completed'
    proj['progress'] = 100
    proj['completionDate'] = today_str
    proj['signedOffBy'] = admin_name
    proj['signedOffAt'] = datetime.now().strftime("%Y-%m-%d %H:%M")
    proj['lastUpdated'] = today_str

    save_db(db)
    return jsonify({"success": True, "project": proj})


# -------------------------------------------------------------
# DASHBOARD STATS API (Total Categories = 7, Dynamic Totals)
# -------------------------------------------------------------
@app.route('/api/stats', methods=['GET'])
def api_stats():
    db = load_db()
    cats = db.get('categories', [])
    users = db.get('users', [])
    quotes = db.get('quotations', [])
    projs = db.get('projects', [])

    marketing_count = len([u for u in users if u.get('role') == 'marketing' or 'marketing' in u.get('role', '')])
    accepted_quotes = len([q for q in quotes if q.get('status') == 'Accepted'])
    rejected_quotes = len([q for q in quotes if q.get('status') == 'Rejected'])
    active_projs = len([p for p in projs if p.get('status') not in ['Project Completed', 'Completed']])
    completed_projs = len([p for p in projs if p.get('status') in ['Project Completed', 'Completed']])

    total_comm_inr = sum(
        q.get('commissionAmountINR', q.get('commissionAmount', 0)) if (q.get('currency') == 'INR' or q.get('commissionAmountINR')) else 0
        for q in quotes
    )
    total_comm_usd = sum(
        q.get('commissionAmountUSD', q.get('commissionAmount', 0)) if (q.get('currency') == 'USD' or q.get('commissionAmountUSD')) else 0
        for q in quotes
    )

    pending_assignments = len([p for p in projs if p.get('assignmentStatus') == 'pending_assignment' or not p.get('assignedDevId')])
    payment_pending_count = len([p for p in projs if p.get('payment', {}).get('status') != 'Payment Verified'])

    return jsonify({
        "totalCategories": len(cats),  # Preserved 7 categories
        "totalMarketingExecutives": marketing_count,
        "totalQuotations": len(quotes),
        "acceptedQuotations": accepted_quotes,
        "rejectedQuotations": rejected_quotes,
        "activeProjects": active_projs,
        "completedProjects": completed_projs,
        "totalCommissionINR": round(total_comm_inr),
        "totalCommissionUSD": round(total_comm_usd),
        "pendingAssignmentsCount": pending_assignments,
        "paymentPendingCount": payment_pending_count
    })


# -------------------------------------------------------------
# DATABASE MANAGEMENT & STORAGE OPTIMIZATION API (Enterprise)
# -------------------------------------------------------------
def require_admin_auth():
    """Restricts database management strictly to Administrators or Root Admin (supports multiple admin emails)"""
    role = (request.headers.get('X-User-Role') or '').strip().lower()
    user_email = (request.headers.get('X-User-Email') or request.headers.get('X-User-Name') or '').strip().lower()

    if role in ('admin', 'administrator') or user_email == ROOT_ADMIN_EMAIL.lower() or user_email in ADMIN_EMAILS:
        return True

    if user_email:
        db = load_db()
        matched = next((u for u in db.get('users', []) if u.get('email', '').lower() == user_email and u.get('status') == 'active'), None)
        if matched and matched.get('role') == 'admin':
            return True

    if request.remote_addr in ('127.0.0.1', 'localhost', '::1') and not role:
        return True
    return False

@app.route('/api/database/stats', methods=['GET'])
def api_database_stats():
    """Returns real-time storage metrics, shard files, health, and capacity stats"""
    stats = db_manager.get_storage_stats()
    return jsonify(stats)

@app.route('/api/database/rotate', methods=['POST'])
def api_database_rotate():
    """Manually or programmatically triggers controlled rotation to next sequential shard"""
    if not require_admin_auth():
        return jsonify({"success": False, "message": "Unauthorized: Administrator access required"}), 403

    payload = request.get_json(silent=True) or {}
    module = payload.get('module')
    if not module or module not in MODULES or module == 'backups':
        return jsonify({"success": False, "message": f"Invalid module. Supported: {', '.join([m for m in MODULES if m != 'backups'])}"}), 400

    reason = payload.get('reason', 'Administrative manual rotation trigger')
    new_shard = db_manager.rotate_shard(module, reason=reason)
    return jsonify({
        "success": True,
        "message": f"Successfully rotated {module} shard. New active shard: {new_shard['shard_id']}",
        "newShard": new_shard,
        "stats": db_manager.get_storage_stats()
    })

@app.route('/api/database/integrity-check', methods=['POST'])
def api_database_integrity_check():
    """Runs comprehensive PRAGMA integrity_check + HMAC verification on all shard files"""
    if not require_admin_auth():
        return jsonify({"success": False, "message": "Unauthorized: Administrator access required"}), 403

    report = db_manager.run_full_integrity_check()
    return jsonify({
        "success": True,
        "report": report
    })

@app.route('/api/database/optimize', methods=['POST'])
def api_database_optimize():
    """Runs VACUUM, ANALYZE and REINDEX across all databases to reclaim storage"""
    if not require_admin_auth():
        return jsonify({"success": False, "message": "Unauthorized: Administrator access required"}), 403

    result = db_manager.optimize_databases()
    return jsonify({
        "success": True,
        "message": f"Successfully optimized {len(result['optimizedFiles'])} database files.",
        "details": result,
        "stats": db_manager.get_storage_stats()
    })

@app.route('/api/database/backup', methods=['POST'])
def api_database_create_backup():
    """Creates a timestamped, compressed backup in /database/backups/"""
    if not require_admin_auth():
        return jsonify({"success": False, "message": "Unauthorized: Administrator access required"}), 403

    payload = request.get_json(silent=True) or {}
    name = payload.get('backupName')
    backup = db_manager.create_backup(name)
    return jsonify({
        "success": True,
        "message": f"Database backup {backup['filename']} created successfully.",
        "backup": backup
    })

@app.route('/api/database/backups', methods=['GET'])
def api_database_list_backups():
    """Lists existing backup archives in /database/backups/"""
    backups = db_manager.list_backups()
    return jsonify(backups)

@app.route('/api/database/backups/<filename>', methods=['GET'])
def api_database_download_backup(filename):
    """Downloads a backup archive"""
    safe_name = secure_filename(filename)
    backup_dir = os.path.join(db_manager.db_root, 'backups')
    return send_from_directory(backup_dir, safe_name, as_attachment=True)

@app.route('/api/database/audit-logs', methods=['GET'])
def api_database_audit_logs():
    """Retrieves recent audit logs from master catalog"""
    limit = int(request.args.get('limit', 100))
    logs = db_manager.get_audit_logs(limit=limit)
    return jsonify(logs)

@app.route('/api/database/simulate-growth', methods=['POST'])
def api_database_simulate_growth():
    """
    Simulates high-volume record additions to demonstrate
    real-time storage tracking, capacity meters, and sequential shard rotation.
    """
    if not require_admin_auth():
        return jsonify({"success": False, "message": "Unauthorized: Administrator access required"}), 403

    payload = request.get_json(silent=True) or {}
    module = payload.get('module', 'customers')
    count = min(int(payload.get('count', 25)), 200)

    for i in range(count):
        rec_id = f"sim-{uuid.uuid4().hex[:8]}"
        payload_data = {
            "id": rec_id,
            "name": f"Enterprise Client {i+1}",
            "type": "Simulation Record",
            "metadata": "High capacity simulated transactional workload data " * 5,
            "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        db_manager.insert_record(module, rec_id, payload_data, key_field=payload_data['name'], status="Simulated")

    stats = db_manager.get_storage_stats()
    return jsonify({
        "success": True,
        "message": f"Successfully injected {count} simulated transactional records into {module}.",
        "stats": stats
    })


if __name__ == '__main__':
    print(f"Starting {COMPANY_NAME} Operational Portal on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
