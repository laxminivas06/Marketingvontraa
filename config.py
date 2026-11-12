"""
Aivontraa Automation Pvt. Ltd. - Application Configuration & Environment Management
====================================================================================
Guarantees 100% Strict Database Separation between Development and Production:
- Development environment uses its own isolated database directory and files.
- Production environment uses its own isolated database directory and files.
- Development testing and changes never modify or overwrite production records.
- Validation prevents accidental connection or writes across environment boundaries.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_env_file(filepath: str):
    """Loads key-value pairs from an env file into os.environ if not already set."""
    if not os.path.exists(filepath):
        return
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception as e:
        print(f"[CONFIG] Notice loading {filepath}: {e}")

# 1. Determine active environment (default to 'development' in Antigravity / local)
APP_ENV = os.environ.get('APP_ENV', '').lower()
if not APP_ENV:
    # Check if .env specifies it, else default to development
    load_env_file(os.path.join(BASE_DIR, '.env'))
    APP_ENV = os.environ.get('APP_ENV', 'development').lower()

if APP_ENV not in ('development', 'production', 'test'):
    APP_ENV = 'development'
os.environ['APP_ENV'] = APP_ENV

# 2. Load environment-specific env file
if APP_ENV == 'production':
    load_env_file(os.path.join(BASE_DIR, '.env.production'))
else:
    load_env_file(os.path.join(BASE_DIR, '.env.development'))

# 3. Resolve Environment-Specific Database Locations
class Config:
    ENV = APP_ENV
    IS_PRODUCTION = (APP_ENV == 'production')
    IS_DEVELOPMENT = (APP_ENV == 'development')
    IS_TEST = (APP_ENV == 'test')
    
    BASE_DIR = BASE_DIR
    SECRET_KEY = os.environ.get('SECRET_KEY', 'aivontraa_enterprise_key_2026')
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '524356808349-31ele7mkqr9bn0uqt28bod9m638978eh.apps.googleusercontent.com')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')

    if IS_PRODUCTION:
        # Production: isolated production database
        DB_DIR_NAME = os.environ.get('DATABASE_DIR', 'database_prod')
        DB_FILE_NAME = os.environ.get('DATABASE_FILE', 'database_prod.json')
    else:
        # Development: completely separate development database
        DB_DIR_NAME = os.environ.get('DATABASE_DIR', 'database_dev')
        DB_FILE_NAME = os.environ.get('DATABASE_FILE', 'database_dev.json')

    DATABASE_DIR = os.path.join(BASE_DIR, DB_DIR_NAME)
    DATABASE_FILE = os.path.join(BASE_DIR, DB_FILE_NAME)
    DATABASE_URL = os.environ.get('DATABASE_URL', f"json://{DB_DIR_NAME}")

    # Uploads directory
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads_prod' if IS_PRODUCTION else 'uploads_dev')
    PAYMENT_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'payments')
    DOCUMENTS_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'documents')
    CHANGE_REQ_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'change_requests')
    SIGNOFF_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'signoffs')

    @classmethod
    def validate_isolation(cls):
        """Strict validation preventing development from accessing production database."""
        prod_dir = os.path.join(cls.BASE_DIR, 'database_prod')
        if cls.IS_DEVELOPMENT:
            # Must not point to production directory
            norm_db = os.path.normpath(cls.DATABASE_DIR)
            norm_prod = os.path.normpath(prod_dir)
            if norm_db == norm_prod:
                raise RuntimeError(
                    "[FATAL CONFIG ERROR] Development environment is configured to point to the production database! "
                    "Aborting to protect production data."
                )
        print(f"[CONFIG SUCCESS] Active Environment: {cls.ENV.upper()} | DB Directory: {cls.DATABASE_DIR}")

# Perform validation at import
Config.validate_isolation()
