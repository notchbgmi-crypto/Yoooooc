# -*- coding: utf-8 -*-
import subprocess
import sys
import os

# ✅ Termux/Android DNS fix: dnspython (pulled in by pymongo/telethon/etc.) crashes when it
# tries to read /etc/resolv.conf, which doesn't exist AND isn't writable on Termux (real
# Android root, not the Termux prefix). Two layers of fix:
#   1. In-process patch: protects THIS run of the host bot immediately.
#   2. sitecustomize.py dropped into site-packages: protects every FUTURE process that uses
#      this same Python interpreter — including every uploaded/child script — since Python
#      auto-loads sitecustomize.py at interpreter startup, before any user code runs.
def _patch_dns_resolver_inprocess():
    try:
        import dns.resolver as _dns_resolver
        r = _dns_resolver.Resolver(configure=False)
        r.nameservers = ['8.8.8.8', '1.1.1.1']
        _dns_resolver.default_resolver = r
    except Exception:
        pass  # dnspython not installed yet — nothing to patch

def _install_dns_patch_sitecustomize():
    marker = "# __upload_bot_dns_patch__"
    patch_code = (
        f"\n{marker}\n"
        "try:\n"
        "    import dns.resolver as _ub_dns_resolver\n"
        "    _ub_resolver = _ub_dns_resolver.Resolver(configure=False)\n"
        "    _ub_resolver.nameservers = ['8.8.8.8', '1.1.1.1']\n"
        "    _ub_dns_resolver.default_resolver = _ub_resolver\n"
        "except Exception:\n"
        "    pass\n"
    )
    try:
        import site
        site_dirs = []
        if hasattr(site, 'getsitepackages'):
            try: site_dirs.extend(site.getsitepackages())
            except Exception: pass
        if hasattr(site, 'getusersitepackages'):
            try: site_dirs.append(site.getusersitepackages())
            except Exception: pass
        if not site_dirs:
            import sysconfig
            site_dirs = [sysconfig.get_paths().get('purelib')]

        for d in site_dirs:
            if not d or not os.path.isdir(d):
                continue
            target = os.path.join(d, 'sitecustomize.py')
            try:
                existing = ""
                if os.path.exists(target):
                    with open(target, 'r', encoding='utf-8') as f:
                        existing = f.read()
                if marker not in existing:
                    with open(target, 'a', encoding='utf-8') as f:
                        f.write(patch_code)
                    print(f"🛠️ Installed DNS resolver patch via {target} (Termux/Android fix).")
                return  # one writable site-packages dir is enough
            except Exception:
                continue  # this dir wasn't writable, try the next one
    except Exception as e:
        print(f"⚠️ Could not install sitecustomize DNS patch: {e}")

def _ensure_resolv_conf():
    # Best-effort fallback for environments where /etc IS writable (e.g. a rooted device
    # or a normal Linux VPS). Silently skipped on stock Termux, where this will fail.
    resolv_path = '/etc/resolv.conf'
    try:
        if not os.path.exists(resolv_path):
            os.makedirs(os.path.dirname(resolv_path), exist_ok=True)
            with open(resolv_path, 'w', encoding='utf-8') as f:
                f.write("nameserver 8.8.8.8\nnameserver 1.1.1.1\n")
            print("🛠️ Created missing /etc/resolv.conf (DNS fix).")
    except Exception:
        pass  # expected on Termux — the sitecustomize patch above covers this case instead

_patch_dns_resolver_inprocess()
_install_dns_patch_sitecustomize()
_ensure_resolv_conf()

# ✅ Auto-install missing modules
def auto_install(pip_name, import_name=None):
    import_name = import_name or pip_name
    try:
        __import__(import_name)
    except ModuleNotFoundError:
        print(f"📦 Installing missing package: {pip_name} ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
        print(f"✅ Installed: {pip_name}")

# Auto-install required modules
for pip_name, import_name in [
    ("telebot", "telebot"),
    ("psutil", "psutil"),
    ("requests", "requests"),
    ("flask", "flask"),
    ("qrcode[pil]", "qrcode"),
    ("Pillow", "PIL"),
    ("imaplib2", "imaplib2"),
    ("dnspython", "dns"),
]:
    auto_install(pip_name, import_name)

# Re-apply the DNS patch now that dnspython is guaranteed to be installed
_patch_dns_resolver_inprocess()

# --- After auto-install, import all modules safely ---
import telebot
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import json
import logging
import signal
import threading
import re
import atexit
import requests
from flask import Flask
from threading import Thread
import qrcode
from PIL import Image
import imaplib2
import io
import uuid

app = Flask('')

@app.route('/')
def home():
    return "Kya aap karan bhaiya ko. jante ho "

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    print("Flask Keep-Alive server started.")

# Bot Configuration
# On Render, set these in the dashboard under Environment (Settings → Environment Variables)
# instead of relying on the hardcoded fallbacks below — especially if this code lives in a
# public/shared git repo.
TOKEN = os.environ.get('BOT_TOKEN', '8970164628:AAElFQh1RmU6wucyRz1_Ad3iMfVz-HYRmHI')
BACKUP_BOT_TOKEN = os.environ.get('BACKUP_BOT_TOKEN', '8716243906:AAE4WfHHYQ4CGt2l9_9UsM4vsYWQjPtyWmI')
OWNER_ID = int(os.environ.get('OWNER_ID', '8954667761'))
ADMIN_ID = int(os.environ.get('ADMIN_ID', '8373276191'))
YOUR_USERNAME = os.environ.get('YOUR_USERNAME', '@karanBhaiyaa')
UPDATE_CHANNEL = os.environ.get('UPDATE_CHANNEL', 'https://t.me/karanBhaiyaaa')

# --- KaranPay Configuration ---
KARANPAY_KEY_1 = os.environ.get('KARANPAY_KEY_1', "guru131e012b5141689b9135317fb6fa7f")
KARANPAY_KEY_2 = os.environ.get('KARANPAY_KEY_2', "guru1eff587f747b3df8c7a355570f90ce")
KARANPAY_CREATE_URL = os.environ.get('KARANPAY_CREATE_URL', "https://gurupaygateway.com/api/create-order")
KARANPAY_STATUS_URL = os.environ.get('KARANPAY_STATUS_URL', "https://gurupaygateway.com/api/check-status")

# BASE_DIR defaults to a Render Persistent Disk mount if DATA_DIR is set (recommended — Render's
# regular filesystem is ephemeral and wipes on every deploy/restart, which would delete the
# SQLite DB and every user's uploaded bot files). Set DATA_DIR to your disk's mount path,
# e.g. /var/data, in Render → your service → Disks.
BASE_DIR = os.environ.get('DATA_DIR', os.path.abspath(os.path.dirname(__file__)))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')

FREE_USER_LIMIT = 10
SUBSCRIBED_USER_LIMIT = 15  # Fallback only; paid users now use their plan's bot_limit (see get_user_upload_limit)
ADMIN_LIMIT = 999
OWNER_LIMIT = float('inf')
FREE_TIER_TIMEOUT_MINUTES = 10

os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

bot = telebot.TeleBot(TOKEN)
backup_bot = telebot.TeleBot(BACKUP_BOT_TOKEN)

bot_scripts = {}
user_subscriptions = {}
user_files = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
bot_locked = False

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

COMMAND_BUTTONS_LAYOUT_USER_SPEC = [
    ["💎 Plans"],
    ["📤 Upload File", "📂 Check Files"],
    ["⚡ Bot Speed", "👤 Profile"],
    ["🛠️ Help"]
]
ADMIN_COMMAND_BUTTONS_LAYOUT_USER_SPEC = [
    ["💎 Plans"],
    ["📤 Upload File", "📂 Check Files"],
    ["⚡ Bot Speed", "👤 Profile"],
    ["🛠️ Help"],
    ["💳 Subscriptions", "🔒 Lock Bot"],
    ["📢 Broadcast", "🟢 Running All Code"],
    ["👑 Admin Panel", "📞 Contact Owner"]
]

def init_db():
    logger.info(f"Initializing database at: {DATABASE_PATH}")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
                     (user_id INTEGER PRIMARY KEY, expiry TEXT, bot_limit INTEGER DEFAULT 1, plan_name TEXT DEFAULT 'Premium')''')
        # Handle migration for existing DB
        try:
            c.execute('ALTER TABLE subscriptions ADD COLUMN bot_limit INTEGER DEFAULT 1')
        except sqlite3.OperationalError:
            pass
        try:
            c.execute('ALTER TABLE subscriptions ADD COLUMN plan_name TEXT DEFAULT "Premium"')
        except sqlite3.OperationalError:
            pass
        c.execute('''CREATE TABLE IF NOT EXISTS user_files
                     (user_id INTEGER, file_name TEXT, file_type TEXT,
                      PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_users
                     (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins
                     (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS running_scripts
                     (script_key TEXT PRIMARY KEY, pid INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS bot_settings
                     (key TEXT PRIMARY KEY, value TEXT)''')
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
        if ADMIN_ID != OWNER_ID:
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}", exc_info=True)

def get_bot_setting(key):
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT value FROM bot_settings WHERE key = ?', (key,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"Error getting setting {key}: {e}")
        return None

def set_bot_setting(key, value):
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)', (key, str(value)))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error setting {key}: {e}")

def load_data():
    logger.info("Loading data from database...")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id, expiry, bot_limit, plan_name FROM subscriptions')
        for user_id, expiry, bot_limit, plan_name in c.fetchall():
            try:
                user_subscriptions[user_id] = {'expiry': datetime.fromisoformat(expiry), 'bot_limit': bot_limit or 1, 'plan_name': plan_name or 'Premium'}
            except ValueError:
                logger.warning(f"⚠️ Invalid expiry date format for user {user_id}: {expiry}. Skipping.")
        c.execute('SELECT user_id, file_name, file_type FROM user_files')
        for user_id, file_name, file_type in c.fetchall():
            if user_id not in user_files:
                user_files[user_id] = []
            user_files[user_id].append((file_name, file_type))
        c.execute('SELECT user_id FROM active_users')
        active_users.update(user_id for (user_id,) in c.fetchall())
        c.execute('SELECT user_id FROM admins')
        admin_ids.update(user_id for (user_id,) in c.fetchall())
        conn.close()
        logger.info(f"Data loaded: {len(active_users)} users, {len(user_subscriptions)} subscriptions, {len(admin_ids)} admins.")
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}", exc_info=True)

init_db()
load_data()

def get_user_folder(user_id):
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def get_user_upload_limit(user_id):
    if user_id == OWNER_ID: return OWNER_LIMIT
    if user_id in admin_ids: return ADMIN_LIMIT
    if user_id in user_subscriptions and user_subscriptions[user_id]['expiry'] > datetime.now():
        # Paid users' upload limit now strictly matches their plan's bot (run) limit.
        return user_subscriptions[user_id].get('bot_limit', 1)
    return FREE_USER_LIMIT

def get_user_run_limit(user_id):
    if user_id == OWNER_ID: return OWNER_LIMIT
    if user_id in admin_ids: return ADMIN_LIMIT
    if user_id in user_subscriptions and user_subscriptions[user_id]['expiry'] > datetime.now():
        return user_subscriptions[user_id].get('bot_limit', 1)
    return 1 # Free users get 1 bot limit

def get_user_plan_name(user_id):
    if user_id == OWNER_ID: return "Owner"
    if user_id in admin_ids: return "Admin"
    if user_id in user_subscriptions and user_subscriptions[user_id]['expiry'] > datetime.now():
        return user_subscriptions[user_id].get('plan_name', 'Premium')
    return "Free"

def get_user_file_count(user_id):
    return len(user_files.get(user_id, []))

def is_bot_running(script_owner_id, file_name):
    script_key = f"{script_owner_id}_{file_name}"
    
    # 1. First check in-memory dictionary
    script_info = bot_scripts.get(script_key)
    if script_info and script_info.get('process'):
        try:
            proc = psutil.Process(script_info['process'].pid)
            is_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            if not is_running:
                logger.warning(f"Process {script_info['process'].pid} for {script_key} found in memory but not running/zombie. Cleaning up.")
                if 'log_file' in script_info and hasattr(script_info['log_file'], 'close') and not script_info['log_file'].closed:
                    try: script_info['log_file'].close()
                    except Exception: pass
                if script_key in bot_scripts: del bot_scripts[script_key]
                remove_pid_from_db(script_key)
            return is_running
        except psutil.NoSuchProcess:
            logger.warning(f"Process for {script_key} not found (NoSuchProcess). Cleaning up.")
            if 'log_file' in script_info and hasattr(script_info['log_file'], 'close') and not script_info['log_file'].closed:
                try: script_info['log_file'].close()
                except Exception: pass
            if script_key in bot_scripts: del bot_scripts[script_key]
            remove_pid_from_db(script_key)
            return False
        except Exception as e:
            logger.error(f"Error checking process status for {script_key}: {e}", exc_info=True)
            return False
            
    # 2. If not in memory, check Database (fallback for restart)
    saved_pid = get_pid_from_db(script_key)
    if saved_pid:
        try:
            proc = psutil.Process(saved_pid)
            is_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            if not is_running:
                remove_pid_from_db(script_key)
            return is_running
        except psutil.NoSuchProcess:
            remove_pid_from_db(script_key)
            return False
        except Exception as e:
            logger.error(f"Error checking DB pid status for {script_key}: {e}", exc_info=True)
            return False
            
    return False

def kill_process_tree(process_info):
    pid = None
    log_file_closed = False
    script_key = process_info.get('script_key', 'N/A')
    try:
        if 'log_file' in process_info and hasattr(process_info['log_file'], 'close') and not process_info['log_file'].closed:
            try:
                process_info['log_file'].close()
                log_file_closed = True
                logger.info(f"Closed log file for {script_key} (PID: {process_info.get('process', {}).get('pid', 'N/A')})")
            except Exception as log_e:
                logger.error(f"Error closing log file during kill for {script_key}: {log_e}")
        process = process_info.get('process')
        if process and hasattr(process, 'pid'):
            pid = process.pid
        else:
            pid = get_pid_from_db(script_key)
            
        if pid:
            try:
                parent = psutil.Process(pid)
                children = parent.children(recursive=True)
                logger.info(f"Attempting to kill process tree for {script_key} (PID: {pid}, Children: {[c.pid for c in children]})")
                for child in children:
                    try:
                        child.terminate()
                        logger.info(f"Terminated child process {child.pid} for {script_key}")
                    except psutil.NoSuchProcess:
                        logger.warning(f"Child process {child.pid} for {script_key} already gone.")
                    except Exception as e:
                        logger.error(f"Error terminating child {child.pid} for {script_key}: {e}. Trying kill...")
                        try: child.kill(); logger.info(f"Killed child process {child.pid} for {script_key}")
                        except Exception as e2: logger.error(f"Failed to kill child {child.pid} for {script_key}: {e2}")
                gone, alive = psutil.wait_procs(children, timeout=1)
                for p in alive:
                    logger.warning(f"Child process {p.pid} for {script_key} still alive. Killing.")
                    try: p.kill()
                    except Exception as e: logger.error(f"Failed to kill child {p.pid} for {script_key} after wait: {e}")
                try:
                    parent.terminate()
                    logger.info(f"Terminated parent process {pid} for {script_key}")
                    try: parent.wait(timeout=1)
                    except psutil.TimeoutExpired:
                        logger.warning(f"Parent process {pid} for {script_key} did not terminate. Killing.")
                        parent.kill()
                        logger.info(f"Killed parent process {pid} for {script_key}")
                except psutil.NoSuchProcess:
                    logger.warning(f"Parent process {pid} for {script_key} already gone.")
                except Exception as e:
                    logger.error(f"Error terminating parent {pid} for {script_key}: {e}. Trying kill...")
                    try: parent.kill(); logger.info(f"Killed parent process {pid} for {script_key}")
                    except Exception as e2: logger.error(f"Failed to kill parent {pid} for {script_key}: {e2}")
            except psutil.NoSuchProcess:
                logger.warning(f"Process {pid or 'N/A'} for {script_key} not found during kill. Already terminated?")
        else: logger.error(f"Process PID is None for {script_key}.")
        if not pid and log_file_closed: logger.warning(f"Process object missing for {script_key}, but log file closed.")
        elif not pid: logger.error(f"Process object missing for {script_key}, and no log file. Cannot kill.")
    except Exception as e:
        logger.error(f"❌ Unexpected error killing process tree for PID {pid or 'N/A'} ({script_key}): {e}", exc_info=True)

TELEGRAM_MODULES = {
    'telebot': 'pyTelegramBotAPI',
    'telegram': 'python-telegram-bot',
    'python_telegram_bot': 'python-telegram-bot',
    'aiogram': 'aiogram',
    'pyrogram': 'pyrogram',
    'telethon': 'telethon',
    'telethon.sync': 'telethon',
    'telepot': 'telepot',
    'pytg': 'pytg',
    'tgcrypto': 'tgcrypto',
    'requests': 'requests',
    'bs4': 'beautifulsoup4',
    'aiohttp': 'aiohttp',
    'asyncio': 'asyncio',
    'flask': 'Flask',
    'telegram_upload': 'telegram-upload',
    'telegram_send': 'telegram-send',
    'telegram_text': 'telegram-text',
    'mtproto': 'telegram-mtproto',
    'tl': 'telethon',
    'telegram_utils': 'telegram-utils',
    'telegram_logger': 'telegram-logger',
    'telegram_handlers': 'python-telegram-handlers',
    'telegram_redis': 'telegram-redis',
    'telegram_sqlalchemy': 'telegram-sqlalchemy',
    'telegram_payment': 'telegram-payment',
    'telegram_shop': 'telegram-shop-sdk',
    'pytest_telegram': 'pytest-telegram',
    'telegram_debug': 'telegram-debug',
    'telegram_scraper': 'telegram-scraper',
    'telegram_analytics': 'telegram-analytics',
    'telegram_nlp': 'telegram-nlp-toolkit',
    'telegram_ai': 'telegram-ai',
    'telegram_api': 'telegram-api-client',
    'telegram_web': 'telegram-web-integration',
    'telegram_games': 'telegram-games',
    'telegram_quiz': 'telegram-quiz-bot',
    'telegram_ffmpeg': 'telegram-ffmpeg',
    'telegram_media': 'telegram-media-utils',
    'telegram_2fa': 'telegram-twofa',
    'telegram_crypto': 'telegram-crypto-bot',
    'telegram_i18n': 'telegram-i18n',
    'telegram_translate': 'telegram-translate',
    'bs4': 'beautifulsoup4',
    'requests': 'requests',
    'pillow': 'Pillow',
    'cv2': 'opencv-python',
    'yaml': 'PyYAML',
    'dotenv': 'python-dotenv',
    'dateutil': 'python-dateutil',
    'pandas': 'pandas',
    'numpy': 'numpy',
    'flask': 'Flask',
    'django': 'Django',
    'sqlalchemy': 'SQLAlchemy',
    'pymongo': 'pymongo',
    'bson': 'pymongo',
    'certifi': 'certifi',
    'qrcode': 'qrcode[pil]',
    'cloudscraper': 'cloudscraper',
    'asyncio': None,
    'json': None,
    'datetime': None,
    'os': None,
    'sys': None,
    're': None,
    'time': None,
    'math': None,
    'random': None,
    'logging': None,
    'threading': None,
    'subprocess': None,
    'zipfile': None,
    'tempfile': None,
    'shutil': None,
    'sqlite3': None,
    'psutil': 'psutil',
    'atexit': None
}

DB_LOCK = threading.Lock()

def save_user_file(user_id, file_name, file_type='py'):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name, file_type) VALUES (?, ?, ?)',
                      (user_id, file_name, file_type))
            conn.commit()
            if user_id not in user_files: user_files[user_id] = []
            user_files[user_id] = [(fn, ft) for fn, ft in user_files[user_id] if fn != file_name]
            user_files[user_id].append((file_name, file_type))
            logger.info(f"Saved file '{file_name}' ({file_type}) for user {user_id}")
        except sqlite3.Error as e: logger.error(f"❌ SQLite error saving file for user {user_id}, {file_name}: {e}")
        except Exception as e: logger.error(f"❌ Unexpected error saving file for {user_id}, {file_name}: {e}", exc_info=True)
        finally: conn.close()

def remove_user_file_db(user_id, file_name):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
            conn.commit()
            if user_id in user_files:
                user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
                if not user_files[user_id]: del user_files[user_id]
            logger.info(f"Removed file '{file_name}' for user {user_id} from DB")
        except sqlite3.Error as e: logger.error(f"❌ SQLite error removing file for {user_id}, {file_name}: {e}")
        except Exception as e: logger.error(f"❌ Unexpected error removing file for {user_id}, {file_name}: {e}", exc_info=True)
        finally: conn.close()

def add_active_user(user_id):
    active_users.add(user_id)
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
            conn.commit()
            logger.info(f"Added/Confirmed active user {user_id} in DB")
        except sqlite3.Error as e: logger.error(f"❌ SQLite error adding active user {user_id}: {e}")
        except Exception as e: logger.error(f"❌ Unexpected error adding active user {user_id}: {e}", exc_info=True)
        finally: conn.close()

def has_ever_purchased(user_id):
    """Returns True if this user already has (or has ever had) a subscription row,
    i.e. this would NOT be their first purchase."""
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('SELECT 1 FROM subscriptions WHERE user_id = ?', (user_id,))
            return c.fetchone() is not None
        except Exception as e:
            logger.error(f"❌ Error checking purchase history for {user_id}: {e}")
            return False  # Fail open toward giving the discount rather than blocking it
        finally:
            conn.close()

def save_subscription(user_id, expiry, bot_limit=1, plan_name="Premium"):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            expiry_str = expiry.isoformat()
            c.execute('INSERT OR REPLACE INTO subscriptions (user_id, expiry, bot_limit, plan_name) VALUES (?, ?, ?, ?)', (user_id, expiry_str, bot_limit, plan_name))
            conn.commit()
            user_subscriptions[user_id] = {'expiry': expiry, 'bot_limit': bot_limit, 'plan_name': plan_name}
            logger.info(f"Saved subscription for {user_id}, expiry {expiry_str}")
        except sqlite3.Error as e: logger.error(f"❌ SQLite error saving subscription for {user_id}: {e}")
        except Exception as e: logger.error(f"❌ Unexpected error saving subscription for {user_id}: {e}", exc_info=True)
        finally: conn.close()

def remove_subscription_db(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM subscriptions WHERE user_id = ?', (user_id,))
            conn.commit()
            if user_id in user_subscriptions: del user_subscriptions[user_id]
            logger.info(f"Removed subscription for {user_id} from DB")
        except sqlite3.Error as e: logger.error(f"❌ SQLite error removing subscription for {user_id}: {e}")
        except Exception as e: logger.error(f"❌ Unexpected error removing subscription for {user_id}: {e}", exc_info=True)
        finally: conn.close()

def add_admin_db(admin_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (admin_id,))
            conn.commit()
            admin_ids.add(admin_id)
            logger.info(f"Added admin {admin_id} to DB")
        except sqlite3.Error as e: logger.error(f"❌ SQLite error adding admin {admin_id}: {e}")
        except Exception as e: logger.error(f"❌ Unexpected error adding admin {admin_id}: {e}", exc_info=True)
        finally: conn.close()

def remove_admin_db(admin_id):
    if admin_id == OWNER_ID:
        logger.warning("Attempted to remove OWNER_ID from admins.")
        return False
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        removed = False
        try:
            c.execute('SELECT 1 FROM admins WHERE user_id = ?', (admin_id,))
            if c.fetchone():
                c.execute('DELETE FROM admins WHERE user_id = ?', (admin_id,))
                conn.commit()
                removed = c.rowcount > 0
                if removed: admin_ids.discard(admin_id); logger.info(f"Removed admin {admin_id} from DB")
                else: logger.warning(f"Admin {admin_id} found but delete affected 0 rows.")
            else:
                logger.warning(f"Admin {admin_id} not found in DB.")
                admin_ids.discard(admin_id)
            return removed
        except sqlite3.Error as e: logger.error(f"❌ SQLite error removing admin {admin_id}: {e}"); return False
        except Exception as e: logger.error(f"❌ Unexpected error removing admin {admin_id}: {e}", exc_info=True); return False
        finally: conn.close()

def save_pid_to_db(script_key, pid):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR REPLACE INTO running_scripts (script_key, pid) VALUES (?, ?)', (script_key, pid))
            conn.commit()
        except Exception as e: logger.error(f"Error saving PID to DB: {e}")
        finally: conn.close()

def remove_pid_from_db(script_key):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM running_scripts WHERE script_key = ?', (script_key,))
            conn.commit()
        except Exception as e: logger.error(f"Error removing PID from DB: {e}")
        finally: conn.close()

def get_pid_from_db(script_key):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('SELECT pid FROM running_scripts WHERE script_key = ?', (script_key,))
            row = c.fetchone()
            return row[0] if row else None
        except Exception as e: logger.error(f"Error getting PID from DB: {e}"); return None
        finally: conn.close()

def create_main_menu_inline(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton('📢 Updates Channel', url=UPDATE_CHANNEL),
        types.InlineKeyboardButton('📤 Upload File', callback_data='upload'),
        types.InlineKeyboardButton('📂 Check Files', callback_data='check_files'),
        types.InlineKeyboardButton('⚡ Bot Speed', callback_data='speed'),
        types.InlineKeyboardButton('📞 Contact Owner', url=f'https://t.me/{YOUR_USERNAME.replace("@", "")}')
    ]
    if user_id in admin_ids:
        admin_buttons = [
            types.InlineKeyboardButton('💳 Subscriptions', callback_data='subscription'),
            types.InlineKeyboardButton('📊 Statistics', callback_data='stats'),
            types.InlineKeyboardButton('🔒 Lock Bot' if not bot_locked else '🔓 Unlock Bot',
                                     callback_data='lock_bot' if not bot_locked else 'unlock_bot'),
            types.InlineKeyboardButton('📢 Broadcast', callback_data='broadcast'),
            types.InlineKeyboardButton('👑 Admin Panel', callback_data='admin_panel'),
            types.InlineKeyboardButton('🟢 Run All User Scripts', callback_data='run_all_scripts')
        ]
        markup.add(buttons[0])
        markup.add(buttons[1], buttons[2])
        markup.add(buttons[3], admin_buttons[0])
        markup.add(admin_buttons[1], admin_buttons[3])
        markup.add(admin_buttons[2], admin_buttons[5])
        markup.add(admin_buttons[4])
        markup.add(buttons[4])
    else:
        markup.add(buttons[0])
        markup.add(buttons[1], buttons[2])
        markup.add(buttons[3])
        markup.add(types.InlineKeyboardButton('📊 Statistics', callback_data='stats'))
        markup.add(buttons[4])
    return markup

def create_reply_keyboard_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    layout_to_use = ADMIN_COMMAND_BUTTONS_LAYOUT_USER_SPEC if user_id in admin_ids else COMMAND_BUTTONS_LAYOUT_USER_SPEC
    for row_buttons_text in layout_to_use:
        markup.add(*[types.KeyboardButton(text) for text in row_buttons_text])
    return markup

def create_control_buttons(script_owner_id, file_name, is_running=True):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if is_running:
        markup.row(
            types.InlineKeyboardButton("🔴 Stop", callback_data=f'stop_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("🔄 Restart", callback_data=f'restart_{script_owner_id}_{file_name}')
        )
        markup.row(
            types.InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("📜 Logs", callback_data=f'logs_{script_owner_id}_{file_name}')
        )
    else:
        markup.row(
            types.InlineKeyboardButton("🟢 Start", callback_data=f'start_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_{script_owner_id}_{file_name}')
        )
        markup.row(
            types.InlineKeyboardButton("📜 View Logs", callback_data=f'logs_{script_owner_id}_{file_name}')
        )
        if file_name.endswith('.py') or file_name.endswith('.js'):
            markup.row(
                types.InlineKeyboardButton("📝 Edit Code", callback_data=f'editcode_{script_owner_id}_{file_name}')
            )
    markup.add(types.InlineKeyboardButton("🔙 Back to Files", callback_data='check_files'))
    return markup

def create_admin_panel():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton('➕ Add Admin', callback_data='add_admin'),
        types.InlineKeyboardButton('➖ Remove Admin', callback_data='remove_admin')
    )
    markup.row(types.InlineKeyboardButton('📋 List Admins', callback_data='list_admins'))
    markup.row(types.InlineKeyboardButton('🕵️ User Files Browser', callback_data='admin_spy_users'))
    markup.row(types.InlineKeyboardButton('📹 Set Welcome Video', callback_data='admin_set_welcome_video'))
    markup.row(
        types.InlineKeyboardButton('💾 Set Backup Channel', callback_data='set_backup_channel'),
        types.InlineKeyboardButton('🛠️ Set Support Link', callback_data='set_support_link')
    )
    markup.row(types.InlineKeyboardButton('💎 Edit Plans', callback_data='edit_plans_init'))
    markup.row(types.InlineKeyboardButton('🔙 Back to Main', callback_data='back_to_main'))
    return markup

def create_subscription_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton('➕ Add Subscription', callback_data='add_subscription'),
        types.InlineKeyboardButton('➖ Remove Subscription', callback_data='remove_subscription')
    )
    markup.row(types.InlineKeyboardButton('🔍 Check Subscription', callback_data='check_subscription'))
    markup.row(types.InlineKeyboardButton('🔙 Back to Main', callback_data='back_to_main'))
    return markup

def attempt_install_pip(module_name, message):
    package_name = TELEGRAM_MODULES.get(module_name.lower(), module_name)
    if package_name is None:
        logger.info(f"Module '{module_name}' is core. Skipping pip install.")
        return False
    try:
        bot.reply_to(message, f"🐍 Module `{module_name}` not found. Installing `{package_name}`...", parse_mode='Markdown')
        command = [sys.executable, '-m', 'pip', 'install', package_name]
        logger.info(f"Running install: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, check=False, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            logger.info(f"Installed {package_name}. Output:\n{result.stdout}")
            bot.reply_to(message, f"✅ Package `{package_name}` (for `{module_name}`) installed.", parse_mode='Markdown')
            return True
        else:
            error_msg = f"❌ Failed to install `{package_name}` for `{module_name}`.\nLog:\n```\n{result.stderr or result.stdout}\n```"
            logger.error(error_msg)
            if len(error_msg) > 4000: error_msg = error_msg[:4000] + "\n... (Log truncated)"
            bot.reply_to(message, error_msg, parse_mode='Markdown')
            return False
    except Exception as e:
        error_msg = f"❌ Error installing `{package_name}`: {str(e)}"
        logger.error(error_msg, exc_info=True)
        bot.reply_to(message, error_msg)
        return False

def attempt_install_npm(module_name, user_folder, message):
    try:
        bot.reply_to(message, f"🟠 Node package `{module_name}` not found. Installing locally...", parse_mode='Markdown')
        command = ['npm', 'install', module_name]
        logger.info(f"Running npm install: {' '.join(command)} in {user_folder}")
        result = subprocess.run(command, capture_output=True, text=True, check=False, cwd=user_folder, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            logger.info(f"Installed {module_name}. Output:\n{result.stdout}")
            bot.reply_to(message, f"✅ Node package `{module_name}` installed locally.", parse_mode='Markdown')
            return True
        else:
            error_msg = f"❌ Failed to install Node package `{module_name}`.\nLog:\n```\n{result.stderr or result.stdout}\n```"
            logger.error(error_msg)
            if len(error_msg) > 4000: error_msg = error_msg[:4000] + "\n... (Log truncated)"
            bot.reply_to(message, error_msg, parse_mode='Markdown')
            return False
    except FileNotFoundError:
        error_msg = "❌ Error: 'npm' not found. Ensure Node.js/npm are installed and in PATH."
        logger.error(error_msg)
        bot.reply_to(message, error_msg)
        return False
    except Exception as e:
        error_msg = f"❌ Error installing Node package `{module_name}`: {str(e)}"
        logger.error(error_msg, exc_info=True)
        bot.reply_to(message, error_msg)
        return False

def kill_free_tier_script(script_key, chat_id):
    if script_key in bot_scripts:
        logger.info(f"Free tier time limit reached for {script_key}. Killing.")
        kill_process_tree(bot_scripts[script_key])
        del bot_scripts[script_key]
        remove_pid_from_db(script_key)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💎 Buy Premium", callback_data="buy_premium"))
        try: bot.send_message(chat_id, f"⚠️ **Your free bot has stopped after {FREE_TIER_TIMEOUT_MINUTES} minutes.**\nPlease change your plan to keep it running 24/7!", parse_mode="Markdown", reply_markup=markup)
        except: pass

def run_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt=1):
    max_attempts = 2
    if attempt > max_attempts:
        bot.reply_to(message_obj_for_reply, f"❌ Failed to run '{file_name}' after {max_attempts} attempts. Check logs.")
        return
    script_key = f"{script_owner_id}_{file_name}"
    logger.info(f"Attempt {attempt} to run Python script: {script_path} (Key: {script_key}) for user {script_owner_id}")
    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj_for_reply, f"❌ Error: Script '{file_name}' not found at '{script_path}'!")
            logger.error(f"Script not found: {script_path} for user {script_owner_id}")
            if script_owner_id in user_files:
                user_files[script_owner_id] = [f for f in user_files.get(script_owner_id, []) if f[0] != file_name]
            remove_user_file_db(script_owner_id, file_name)
            return
        if attempt == 1:
            check_command = [sys.executable, script_path]
            logger.info(f"Running Python pre-check: {' '.join(check_command)}")
            check_proc = None
            try:
                check_proc = subprocess.Popen(check_command, cwd=user_folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
                stdout, stderr = check_proc.communicate(timeout=5)
                return_code = check_proc.returncode
                logger.info(f"Python Pre-check early. RC: {return_code}. Stderr: {stderr[:200]}...")
                if return_code != 0 and stderr:
                    match_py = re.search(r"ModuleNotFoundError: No module named '(.+?)'", stderr)
                    if match_py:
                        module_name = match_py.group(1).strip().strip("'\"")
                        logger.info(f"Detected missing Python module: {module_name}")
                        if attempt_install_pip(module_name, message_obj_for_reply):
                            logger.info(f"Install OK for {module_name}. Retrying run_script...")
                            bot.reply_to(message_obj_for_reply, f"🔄 Install successful. Retrying '{file_name}'...")
                            time.sleep(2)
                            threading.Thread(target=run_script, args=(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt + 1)).start()
                            return
                        else:
                            bot.reply_to(message_obj_for_reply, f"❌ Install failed. Cannot run '{file_name}'.")
                            return
                    else:
                        error_summary = stderr[:500]
                        bot.reply_to(message_obj_for_reply, f"❌ Error in script pre-check for '{file_name}':\n```\n{error_summary}\n```\nFix the script.", parse_mode='Markdown')
                        return
            except subprocess.TimeoutExpired:
                logger.info("Python Pre-check timed out (>5s), imports likely OK. Killing check process.")
                if check_proc and check_proc.poll() is None: check_proc.kill(); check_proc.communicate()
                logger.info("Python Check process killed. Proceeding to long run.")
            except FileNotFoundError:
                logger.error(f"Python interpreter not found: {sys.executable}")
                bot.reply_to(message_obj_for_reply, f"❌ Error: Python interpreter '{sys.executable}' not found.")
                return
            except Exception as e:
                logger.error(f"Error in Python pre-check for {script_key}: {e}", exc_info=True)
                bot.reply_to(message_obj_for_reply, f"❌ Unexpected error in script pre-check for '{file_name}': {e}")
                return
            finally:
                if check_proc and check_proc.poll() is None:
                    logger.warning(f"Python Check process {check_proc.pid} still running. Killing.")
                    check_proc.kill(); check_proc.communicate()
        logger.info(f"Starting long-running Python process for {script_key}")
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = None; process = None
        try: log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"Failed to open log file '{log_file_path}' for {script_key}: {e}", exc_info=True)
            bot.reply_to(message_obj_for_reply, f"❌ Failed to open log file '{log_file_path}': {e}")
            return
        try:
            startupinfo = None; creationflags = 0
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            process = subprocess.Popen(
                [sys.executable, script_path], cwd=user_folder, stdout=log_file, stderr=log_file,
                stdin=subprocess.PIPE, startupinfo=startupinfo, creationflags=creationflags,
                encoding='utf-8', errors='ignore'
            )
            logger.info(f"Started Python process {process.pid} for {script_key}")
            bot_scripts[script_key] = {
                'process': process, 'log_file': log_file, 'file_name': file_name,
                'chat_id': message_obj_for_reply.chat.id,
                'script_owner_id': script_owner_id,
                'start_time': datetime.now(), 'user_folder': user_folder, 'type': 'py', 'script_key': script_key
            }
            save_pid_to_db(script_key, process.pid)
            
            is_premium = script_owner_id in admin_ids or (script_owner_id in user_subscriptions and user_subscriptions[script_owner_id].get('expiry', datetime.min) > datetime.now())
            if not is_premium:
                threading.Timer(FREE_TIER_TIMEOUT_MINUTES * 60, kill_free_tier_script, args=[script_key, message_obj_for_reply.chat.id]).start()
                bot.reply_to(message_obj_for_reply, f"✅ Python script '{file_name}' started! (PID: {process.pid})\n⚠️ *Free Tier:* This script will auto-stop after {FREE_TIER_TIMEOUT_MINUTES} minutes. To run 24/7, please Buy Premium.", parse_mode="Markdown")
            else:
                bot.reply_to(message_obj_for_reply, f"✅ Python script '{file_name}' started! (PID: {process.pid}) (Premium 24/7)")
            
        except FileNotFoundError:
            logger.error(f"Python interpreter {sys.executable} not found for long run {script_key}")
            bot.reply_to(message_obj_for_reply, f"❌ Error: Python interpreter '{sys.executable}' not found.")
            if log_file and not log_file.closed: log_file.close()
            if script_key in bot_scripts: del bot_scripts[script_key]
        except Exception as e:
            if log_file and not log_file.closed: log_file.close()
            error_msg = f"❌ Error starting Python script '{file_name}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            bot.reply_to(message_obj_for_reply, error_msg)
            if process and process.poll() is None:
                logger.warning(f"Killing potentially started Python process {process.pid} for {script_key}")
                kill_process_tree({'process': process, 'log_file': log_file, 'script_key': script_key})
            if script_key in bot_scripts: del bot_scripts[script_key]
    except Exception as e:
        error_msg = f"❌ Unexpected error running Python script '{file_name}': {str(e)}"
        logger.error(error_msg, exc_info=True)
        bot.reply_to(message_obj_for_reply, error_msg)
        if script_key in bot_scripts:
            logger.warning(f"Cleaning up {script_key} due to error in run_script.")
            kill_process_tree(bot_scripts[script_key])
            del bot_scripts[script_key]

def run_js_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt=1):
    max_attempts = 2
    if attempt > max_attempts:
        bot.reply_to(message_obj_for_reply, f"❌ Failed to run '{file_name}' after {max_attempts} attempts. Check logs.")
        return
    script_key = f"{script_owner_id}_{file_name}"
    logger.info(f"Attempt {attempt} to run JS script: {script_path} (Key: {script_key}) for user {script_owner_id}")
    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj_for_reply, f"❌ Error: Script '{file_name}' not found at '{script_path}'!")
            logger.error(f"JS Script not found: {script_path} for user {script_owner_id}")
            if script_owner_id in user_files:
                user_files[script_owner_id] = [f for f in user_files.get(script_owner_id, []) if f[0] != file_name]
            remove_user_file_db(script_owner_id, file_name)
            return
        if attempt == 1:
            check_command = ['node', script_path]
            logger.info(f"Running JS pre-check: {' '.join(check_command)}")
            check_proc = None
            try:
                check_proc = subprocess.Popen(check_command, cwd=user_folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
                stdout, stderr = check_proc.communicate(timeout=5)
                return_code = check_proc.returncode
                logger.info(f"JS Pre-check early. RC: {return_code}. Stderr: {stderr[:200]}...")
                if return_code != 0 and stderr:
                    match_js = re.search(r"Cannot find module '(.+?)'", stderr)
                    if match_js:
                        module_name = match_js.group(1).strip().strip("'\"")
                        if not module_name.startswith('.') and not module_name.startswith('/'):
                            logger.info(f"Detected missing Node module: {module_name}")
                            if attempt_install_npm(module_name, user_folder, message_obj_for_reply):
                                logger.info(f"NPM Install OK for {module_name}. Retrying run_js_script...")
                                bot.reply_to(message_obj_for_reply, f"🔄 NPM Install successful. Retrying '{file_name}'...")
                                time.sleep(2)
                                threading.Thread(target=run_js_script, args=(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt + 1)).start()
                                return
                            else:
                                bot.reply_to(message_obj_for_reply, f"❌ NPM Install failed. Cannot run '{file_name}'.")
                                return
                        else: logger.info(f"Skipping npm install for relative/core: {module_name}")
                    error_summary = stderr[:500]
                    bot.reply_to(message_obj_for_reply, f"❌ Error in JS script pre-check for '{file_name}':\n```\n{error_summary}\n```\nFix script or install manually.", parse_mode='Markdown')
                    return
            except subprocess.TimeoutExpired:
                logger.info("JS Pre-check timed out (>5s), imports likely OK. Killing check process.")
                if check_proc and check_proc.poll() is None: check_proc.kill(); check_proc.communicate()
                logger.info("JS Check process killed. Proceeding to long run.")
            except FileNotFoundError:
                error_msg = "❌ Error: 'node' not found. Ensure Node.js is installed for JS files."
                logger.error(error_msg)
                bot.reply_to(message_obj_for_reply, error_msg)
                return
            except Exception as e:
                logger.error(f"Error in JS pre-check for {script_key}: {e}", exc_info=True)
                bot.reply_to(message_obj_for_reply, f"❌ Unexpected error in JS pre-check for '{file_name}': {e}")
                return
            finally:
                if check_proc and check_proc.poll() is None:
                    logger.warning(f"JS Check process {check_proc.pid} still running. Killing.")
                    check_proc.kill(); check_proc.communicate()
        logger.info(f"Starting long-running JS process for {script_key}")
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = None; process = None
        try: log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"Failed to open log file '{log_file_path}' for JS script {script_key}: {e}", exc_info=True)
            bot.reply_to(message_obj_for_reply, f"❌ Failed to open log file '{log_file_path}': {e}")
            return
        try:
            startupinfo = None; creationflags = 0
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            process = subprocess.Popen(
                ['node', script_path], cwd=user_folder, stdout=log_file, stderr=log_file,
                stdin=subprocess.PIPE, startupinfo=startupinfo, creationflags=creationflags,
                encoding='utf-8', errors='ignore'
            )
            logger.info(f"Started JS process {process.pid} for {script_key}")
            bot_scripts[script_key] = {
                'process': process, 'log_file': log_file, 'file_name': file_name,
                'chat_id': message_obj_for_reply.chat.id,
                'script_owner_id': script_owner_id,
                'start_time': datetime.now(), 'user_folder': user_folder, 'type': 'js', 'script_key': script_key
            }
            save_pid_to_db(script_key, process.pid)
            
            is_premium = script_owner_id in admin_ids or (script_owner_id in user_subscriptions and user_subscriptions[script_owner_id].get('expiry', datetime.min) > datetime.now())
            if not is_premium:
                threading.Timer(FREE_TIER_TIMEOUT_MINUTES * 60, kill_free_tier_script, args=[script_key, message_obj_for_reply.chat.id]).start()
                bot.reply_to(message_obj_for_reply, f"✅ JS script '{file_name}' started! (PID: {process.pid})\n⚠️ *Free Tier:* This script will auto-stop after {FREE_TIER_TIMEOUT_MINUTES} minutes. To run 24/7, please Buy Premium.", parse_mode="Markdown")
            else:
                bot.reply_to(message_obj_for_reply, f"✅ JS script '{file_name}' started! (PID: {process.pid}) (Premium 24/7)")
        except FileNotFoundError:
            error_msg = "❌ Error: 'node' not found for long run. Ensure Node.js is installed."
            logger.error(error_msg)
            if log_file and not log_file.closed: log_file.close()
            bot.reply_to(message_obj_for_reply, error_msg)
            if script_key in bot_scripts: del bot_scripts[script_key]
        except Exception as e:
            if log_file and not log_file.closed: log_file.close()
            error_msg = f"❌ Error starting JS script '{file_name}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            bot.reply_to(message_obj_for_reply, error_msg)
            if process and process.poll() is None:
                logger.warning(f"Killing potentially started JS process {process.pid} for {script_key}")
                kill_process_tree({'process': process, 'log_file': log_file, 'script_key': script_key})
            if script_key in bot_scripts: del bot_scripts[script_key]
    except Exception as e:
        error_msg = f"❌ Unexpected error running JS script '{file_name}': {str(e)}"
        logger.error(error_msg, exc_info=True)
        bot.reply_to(message_obj_for_reply, error_msg)
        if script_key in bot_scripts:
            logger.warning(f"Cleaning up {script_key} due to error in run_js_script.")
            kill_process_tree(bot_scripts[script_key])
            del bot_scripts[script_key]

def handle_zip_file(downloaded_file_content, file_name_zip, message):
    user_id = message.from_user.id
    user_folder = get_user_folder(user_id)
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp(prefix=f"user_{user_id}_zip_")
        logger.info(f"Temp dir for zip: {temp_dir}")
        zip_path = os.path.join(temp_dir, file_name_zip)
        with open(zip_path, 'wb') as new_file: new_file.write(downloaded_file_content)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.infolist():
                member_path = os.path.abspath(os.path.join(temp_dir, member.filename))
                if not member_path.startswith(os.path.abspath(temp_dir)):
                    raise zipfile.BadZipFile(f"Zip has unsafe path: {member.filename}")
            zip_ref.extractall(temp_dir)
            logger.info(f"Extracted zip to {temp_dir}")
        extracted_items = os.listdir(temp_dir)
        py_files = [f for f in extracted_items if f.endswith('.py')]
        js_files = [f for f in extracted_items if f.endswith('.js')]
        req_file = 'requirements.txt' if 'requirements.txt' in extracted_items else None
        pkg_json = 'package.json' if 'package.json' in extracted_items else None
        if req_file:
            req_path = os.path.join(temp_dir, req_file)
            logger.info(f"requirements.txt found, installing: {req_path}")
            bot.reply_to(message, f"🔄 Installing Python deps from `{req_file}`...")
            try:
                command = [sys.executable, '-m', 'pip', 'install', '-r', req_path]
                result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8', errors='ignore')
                logger.info(f"pip install from requirements.txt OK. Output:\n{result.stdout}")
                bot.reply_to(message, f"✅ Python deps from `{req_file}` installed.")
            except subprocess.CalledProcessError as e:
                error_msg = f"❌ Failed to install Python deps from `{req_file}`.\nLog:\n```\n{e.stderr or e.stdout}\n```"
                logger.error(error_msg)
                if len(error_msg) > 4000: error_msg = error_msg[:4000] + "\n... (Log truncated)"
                bot.reply_to(message, error_msg, parse_mode='Markdown'); return
            except Exception as e:
                error_msg = f"❌ Unexpected error installing Python deps: {e}"
                logger.error(error_msg, exc_info=True); bot.reply_to(message, error_msg); return
        if pkg_json:
            logger.info(f"package.json found, npm install in: {temp_dir}")
            bot.reply_to(message, f"🔄 Installing Node deps from `{pkg_json}`...")
            try:
                command = ['npm', 'install']
                result = subprocess.run(command, capture_output=True, text=True, check=True, cwd=temp_dir, encoding='utf-8', errors='ignore')
                logger.info(f"npm install OK. Output:\n{result.stdout}")
                bot.reply_to(message, f"✅ Node deps from `{pkg_json}` installed.")
            except FileNotFoundError:
                bot.reply_to(message, "❌ 'npm' not found. Cannot install Node deps."); return
            except subprocess.CalledProcessError as e:
                error_msg = f"❌ Failed to install Node deps from `{pkg_json}`.\nLog:\n```\n{e.stderr or e.stdout}\n```"
                logger.error(error_msg)
                if len(error_msg) > 4000: error_msg = error_msg[:4000] + "\n... (Log truncated)"
                bot.reply_to(message, error_msg, parse_mode='Markdown'); return
            except Exception as e:
                error_msg = f"❌ Unexpected error installing Node deps: {e}"
                logger.error(error_msg, exc_info=True); bot.reply_to(message, error_msg); return
        main_script_name = None; file_type = None
        preferred_py = ['main.py', 'bot.py', 'app.py']; preferred_js = ['index.js', 'main.js', 'bot.js', 'app.js']
        for p in preferred_py:
            if p in py_files: main_script_name = p; file_type = 'py'; break
        if not main_script_name:
            for p in preferred_js:
                if p in js_files: main_script_name = p; file_type = 'js'; break
        if not main_script_name:
            if py_files: main_script_name = py_files[0]; file_type = 'py'
            elif js_files: main_script_name = js_files[0]; file_type = 'js'
        if not main_script_name:
            bot.reply_to(message, "❌ No `.py` or `.js` script found in archive!"); return
        logger.info(f"Moving extracted files from {temp_dir} to {user_folder}")
        moved_count = 0
        for item_name in os.listdir(temp_dir):
            src_path = os.path.join(temp_dir, item_name)
            dest_path = os.path.join(user_folder, item_name)
            if os.path.isdir(dest_path): shutil.rmtree(dest_path)
            elif os.path.exists(dest_path): os.remove(dest_path)
            shutil.move(src_path, dest_path); moved_count +=1
        logger.info(f"Moved {moved_count} items to {user_folder}")
        save_user_file(user_id, main_script_name, file_type)
        logger.info(f"Saved main script '{main_script_name}' ({file_type}) for {user_id} from zip.")
        main_script_path = os.path.join(user_folder, main_script_name)
        bot.reply_to(message, f"✅ Files extracted. Starting main script: `{main_script_name}`...", parse_mode='Markdown')
        if file_type == 'py':
            threading.Thread(target=run_script, args=(main_script_path, user_id, user_folder, main_script_name, message)).start()
        elif file_type == 'js':
            threading.Thread(target=run_js_script, args=(main_script_path, user_id, user_folder, main_script_name, message)).start()
    except zipfile.BadZipFile as e:
        logger.error(f"Bad zip file from {user_id}: {e}")
        bot.reply_to(message, f"❌ Error: Invalid/corrupted ZIP. {e}")
    except Exception as e:
        logger.error(f"❌ Error processing zip for {user_id}: {e}", exc_info=True)
        bot.reply_to(message, f"❌ Error processing zip: {str(e)}")
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try: shutil.rmtree(temp_dir); logger.info(f"Cleaned temp dir: {temp_dir}")
            except Exception as e: logger.error(f"Failed to clean temp dir {temp_dir}: {e}", exc_info=True)

def handle_js_file(file_path, script_owner_id, user_folder, file_name, message):
    try:
        save_user_file(script_owner_id, file_name, 'js')
        threading.Thread(target=run_js_script, args=(file_path, script_owner_id, user_folder, file_name, message)).start()
    except Exception as e:
        logger.error(f"❌ Error processing JS file {file_name} for {script_owner_id}: {e}", exc_info=True)
        bot.reply_to(message, f"❌ Error processing JS file: {str(e)}")

def handle_py_file(file_path, script_owner_id, user_folder, file_name, message):
    try:
        save_user_file(script_owner_id, file_name, 'py')
        threading.Thread(target=run_script, args=(file_path, script_owner_id, user_folder, file_name, message)).start()
    except Exception as e:
        logger.error(f"❌ Error processing Python file {file_name} for {script_owner_id}: {e}", exc_info=True)
        bot.reply_to(message, f"❌ Error processing Python file: {str(e)}")

def _logic_send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_name = message.from_user.first_name
    user_username = message.from_user.username
    logger.info(f"Welcome request from user_id: {user_id}, username: @{user_username}")
    if bot_locked and user_id not in admin_ids:
        bot.send_message(chat_id, "⚠️ Bot locked by admin. Try later.")
        return
    user_bio = "Could not fetch bio"
    try: user_bio = bot.get_chat(user_id).bio or "No bio"
    except Exception: pass
    if user_id not in active_users:
        add_active_user(user_id)
        try:
            owner_notification = (f"🎉 New user!\n👤 Name: {user_name}\n✳️ User: @{user_username or 'N/A'}\n"
                                  f"🆔 ID: `{user_id}`\n📝 Bio: {user_bio}")
            bot.send_message(OWNER_ID, owner_notification, parse_mode='Markdown')
        except Exception as e: logger.error(f"⚠️ Failed to notify owner about new user {user_id}: {e}")
    file_limit = get_user_upload_limit(user_id)
    current_files = get_user_file_count(user_id)
    limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
    expiry_info = ""
    if user_id == OWNER_ID: user_status = "👑 Owner"
    elif user_id in admin_ids: user_status = "🛡️ Admin"
    elif user_id in user_subscriptions:
        expiry_date = user_subscriptions[user_id].get('expiry')
        if expiry_date and expiry_date > datetime.now():
            plan_name = get_user_plan_name(user_id)
            user_status = f"⭐ {plan_name}"; days_left = (expiry_date - datetime.now()).days
            expiry_info = f"\n⏳ Subscription expires in: {days_left} days"
        else: user_status = "🆓 Free User (Expired Sub)"; remove_subscription_db(user_id)
    else: user_status = "🆓 Free User"
    
    welcome_msg_text = f"""<blockquote><b>〽️ Welcome, {user_name}!</b></blockquote>
🆔 <b>Your User ID:</b> <code>{user_id}</code>
✳️ <b>Username:</b> @{user_username or 'Not set'}
🔰 <b>Your Plan:</b> {user_status}{expiry_info}
📁 <b>Files Uploaded:</b> {current_files} / {limit_str}

🤖 Host & run Python (<code>.py</code>) or JS (<code>.js</code>) scripts.
Upload single scripts or <code>.zip</code> archives.

👇 Use buttons or type commands."""
    
    main_reply_markup = create_reply_keyboard_main_menu(user_id)
    try:
        welcome_video_id = get_bot_setting("welcome_video_id")
        if welcome_video_id:
            bot.send_video(chat_id, welcome_video_id, caption=welcome_msg_text, reply_markup=main_reply_markup, parse_mode='HTML')
        else:
            bot.send_message(chat_id, welcome_msg_text, reply_markup=main_reply_markup, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error sending welcome to {user_id}: {e}", exc_info=True)
        try: bot.send_message(chat_id, welcome_msg_text, reply_markup=main_reply_markup, parse_mode='HTML')
        except Exception as fallback_e: logger.error(f"Fallback send_message failed for {user_id}: {fallback_e}")

def _logic_profile_cmd(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    if user_id == OWNER_ID: user_status = "👑 Owner"
    elif user_id in admin_ids: user_status = "🛡️ Admin"
    elif user_id in user_subscriptions:
        expiry_date = user_subscriptions[user_id].get('expiry')
        if expiry_date and expiry_date > datetime.now():
            plan_name = get_user_plan_name(user_id)
            user_status = f"⭐ {plan_name}"
        else: user_status = "🆓 Free User (Expired Sub)"
    else: user_status = "🆓 Free User"

    run_limit = get_user_run_limit(user_id)
    running_bots = []
    for key, info in list(bot_scripts.items()):
        if int(key.split('_')[0]) == user_id and is_bot_running(user_id, info['file_name']):
            uptime = datetime.now() - info['start_time']
            uptime_str = str(uptime).split('.')[0] # Remove microseconds
            running_bots.append(f"• `{info['file_name']}` (Uptime: {uptime_str})")
            
    running_count = len(running_bots)
    running_text = "\n".join(running_bots) if running_bots else "No bots running"
    
    profile_msg = f"""<blockquote><b>👤 {user_name}'s Profile</b></blockquote>
🆔 <b>User ID:</b> <code>{user_id}</code>
🔰 <b>Your Plan:</b> {user_status}

🟢 <b>Running Bots:</b> {running_count} / {run_limit}
{running_text}
"""
    bot.send_message(user_id, profile_msg, parse_mode='HTML')

def _logic_upload_file(message):
    user_id = message.from_user.id
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, "⚠️ Bot locked by admin, cannot accept files.")
        return
    file_limit = get_user_upload_limit(user_id)
    current_files = get_user_file_count(user_id)
    if current_files >= file_limit:
        limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
        bot.reply_to(message, f"⚠️ File limit ({current_files}/{limit_str}) reached. Delete files first.")
        return
    bot.reply_to(message, "📤 Send your Python (`.py`), JS (`.js`), or ZIP (`.zip`) file.")

def _logic_check_files(message):
    user_id = message.from_user.id
    user_files_list = user_files.get(user_id, [])
    if not user_files_list:
        bot.reply_to(message, "📂 Your files:\n\n(No files uploaded yet)")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for file_name, file_type in sorted(user_files_list):
        is_running = is_bot_running(user_id, file_name)
        status_icon = "🟢 Running" if is_running else "🔴 Stopped"
        btn_text = f"{file_name} ({file_type}) - {status_icon}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f'file_{user_id}_{file_name}'))
    bot.reply_to(message, "📂 Your files:\nClick to manage.", reply_markup=markup, parse_mode='Markdown')

def _logic_bot_speed(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    start_time_ping = time.time()
    wait_msg = bot.reply_to(message, "🏃 Testing speed...")
    try:
        bot.send_chat_action(chat_id, 'typing')
        response_time = round((time.time() - start_time_ping) * 1000, 2)
        status = "🔓 Unlocked" if not bot_locked else "🔒 Locked"
        if user_id == OWNER_ID: user_level = "👑 Owner"
        elif user_id in admin_ids: user_level = "🛡️ Admin"
        elif user_id in user_subscriptions and user_subscriptions[user_id].get('expiry', datetime.min) > datetime.now(): user_level = "⭐ Premium"
        else: user_level = "🆓 Free User"
        speed_msg = (f"⚡ Bot Speed & Status:\n\n⏱️ API Response Time: {response_time} ms\n"
                     f"🚦 Bot Status: {status}\n"
                     f"👤 Your Level: {user_level}")
        bot.edit_message_text(speed_msg, chat_id, wait_msg.message_id)
    except Exception as e:
        logger.error(f"Error during speed test (cmd): {e}", exc_info=True)
        bot.edit_message_text("❌ Error during speed test.", chat_id, wait_msg.message_id)

def _logic_contact_owner(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📞 Contact Owner', url=f'https://t.me/{YOUR_USERNAME.replace("@", "")}'))
    bot.reply_to(message, "Click to contact Owner:", reply_markup=markup)

def _logic_support(message):
    support_link = get_bot_setting("support_link")
    if not support_link:
        bot.reply_to(message, "🛠️ Support link not set by admin yet.")
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('🛠️ Contact Support', url=support_link))
    bot.reply_to(message, "Click to contact Support:", reply_markup=markup)

def get_plan_details():
    return {
        "5": {"price": int(get_bot_setting("plan_5_price") or 59), "limit": int(get_bot_setting("plan_5_limit") or 1)},
        "10": {"price": int(get_bot_setting("plan_10_price") or 80), "limit": int(get_bot_setting("plan_10_limit") or 1)},
        "15": {"price": int(get_bot_setting("plan_15_price") or 130), "limit": int(get_bot_setting("plan_15_limit") or 2)},
        "30": {"price": int(get_bot_setting("plan_30_price") or 250), "limit": int(get_bot_setting("plan_30_limit") or 3)},
    }

FIRST_TIME_DISCOUNT_PERCENT = 70

def apply_first_time_discount(price):
    discounted = price * (100 - FIRST_TIME_DISCOUNT_PERCENT) / 100
    # Round to nearest rupee, minimum ₹1
    return max(1, round(discounted))

def _logic_plans(message):
    user_id = message.from_user.id
    plans = get_plan_details()
    is_first_time = not has_ever_purchased(user_id)

    if is_first_time:
        for p in plans.values():
            p["original_price"] = p["price"]
            p["price"] = apply_first_time_discount(p["price"])
        header = (
            "💎 **Select a Premium Plan:**\n\n"
            f"🎉 **70% Trust Discount Applied!** _(First purchase only)_\n\n"
        )
        lines = []
        for label, days in [("🟢 **5 Days**", "5"), ("🟡 **10 Days**", "10"), ("🟠 **15 Days**", "15"), ("🔴 **30 Days**", "30")]:
            p = plans[days]
            bots_word = "Bot" if p["limit"] == 1 else "Bots"
            lines.append(f"{label} - ~~₹{p['original_price']}~~ ➡️ **₹{p['price']}** (Host {p['limit']} {bots_word})")
        text = header + "\n".join(lines) + "\n\n_Select your plan below:_"
    else:
        text = (
            "💎 **Select a Premium Plan:**\n\n"
            f"🟢 **5 Days** - ₹{plans['5']['price']} (Host {plans['5']['limit']} Bot)\n"
            f"🟡 **10 Days** - ₹{plans['10']['price']} (Host {plans['10']['limit']} Bot)\n"
            f"🟠 **15 Days** - ₹{plans['15']['price']} (Host {plans['15']['limit']} Bots)\n"
            f"🔴 **30 Days** - ₹{plans['30']['price']} (Host {plans['30']['limit']} Bots)\n\n"
            "_Select your plan below:_"
        )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"🟢 5 Days - ₹{plans['5']['price']}", callback_data="buy_plan_5"),
        types.InlineKeyboardButton(f"🟡 10 Days - ₹{plans['10']['price']}", callback_data="buy_plan_10"),
        types.InlineKeyboardButton(f"🟠 15 Days - ₹{plans['15']['price']}", callback_data="buy_plan_15"),
        types.InlineKeyboardButton(f"🔴 30 Days - ₹{plans['30']['price']}", callback_data="buy_plan_30")
    )
    bot.reply_to(message, text, reply_markup=markup, parse_mode="Markdown")

def _logic_subscriptions_panel(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    bot.reply_to(message, "💳 Subscription Management\nUse inline buttons from /start or admin command menu.", reply_markup=create_subscription_menu())



def _logic_broadcast_init(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    msg = bot.reply_to(message, "📢 Send message to broadcast to all active users.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_broadcast_message)

def _logic_toggle_lock_bot(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    global bot_locked
    bot_locked = not bot_locked
    status = "locked" if bot_locked else "unlocked"
    logger.warning(f"Bot {status} by Admin {message.from_user.id} via command/button.")
    bot.reply_to(message, f"🔒 Bot has been {status}.")

def _logic_admin_panel(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    msg = f"<blockquote><b>👑 Admin Panel</b></blockquote>\nManage admins and bot settings.\nUse inline buttons below."
    bot.reply_to(message, msg, reply_markup=create_admin_panel(), parse_mode='HTML')

def _logic_run_all_scripts(message_or_call):
    if isinstance(message_or_call, telebot.types.Message):
        admin_user_id = message_or_call.from_user.id
        admin_chat_id = message_or_call.chat.id
        reply_func = lambda text, **kwargs: bot.reply_to(message_or_call, text, **kwargs)
        admin_message_obj_for_script_runner = message_or_call
    elif isinstance(message_or_call, telebot.types.CallbackQuery):
        admin_user_id = message_or_call.from_user.id
        admin_chat_id = message_or_call.message.chat.id
        bot.answer_callback_query(message_or_call.id)
        reply_func = lambda text, **kwargs: bot.send_message(admin_chat_id, text, **kwargs)
        admin_message_obj_for_script_runner = message_or_call.message
    else:
        logger.error("Invalid argument for _logic_run_all_scripts")
        return
    if admin_user_id not in admin_ids:
        reply_func("⚠️ Admin permissions required.")
        return
    reply_func("⏳ Starting process to run all user scripts. This may take a while...")
    logger.info(f"Admin {admin_user_id} initiated 'run all scripts' from chat {admin_chat_id}.")
    started_count = 0; attempted_users = 0; skipped_files = 0; error_files_details = []
    all_user_files_snapshot = dict(user_files)
    for target_user_id, files_for_user in all_user_files_snapshot.items():
        if not files_for_user: continue
        attempted_users += 1
        logger.info(f"Processing scripts for user {target_user_id}...")
        user_folder = get_user_folder(target_user_id)
        for file_name, file_type in files_for_user:
            if not is_bot_running(target_user_id, file_name):
                file_path = os.path.join(user_folder, file_name)
                if os.path.exists(file_path):
                    logger.info(f"Admin {admin_user_id} attempting to start '{file_name}' ({file_type}) for user {target_user_id}.")
                    try:
                        if file_type == 'py':
                            threading.Thread(target=run_script, args=(file_path, target_user_id, user_folder, file_name, admin_message_obj_for_script_runner)).start()
                            started_count += 1
                        elif file_type == 'js':
                            threading.Thread(target=run_js_script, args=(file_path, target_user_id, user_folder, file_name, admin_message_obj_for_script_runner)).start()
                            started_count += 1
                        else:
                            logger.warning(f"Unknown file type '{file_type}' for {file_name} (user {target_user_id}). Skipping.")
                            error_files_details.append(f"`{file_name}` (User {target_user_id}) - Unknown type")
                            skipped_files += 1
                        time.sleep(0.7)
                    except Exception as e:
                        logger.error(f"Error queueing start for '{file_name}' (user {target_user_id}): {e}")
                        error_files_details.append(f"`{file_name}` (User {target_user_id}) - Start error")
                        skipped_files += 1
                else:
                    logger.warning(f"File '{file_name}' for user {target_user_id} not found at '{file_path}'. Skipping.")
                    error_files_details.append(f"`{file_name}` (User {target_user_id}) - File not found")
                    skipped_files += 1
    summary_msg = (f"✅ All Users' Scripts - Processing Complete:\n\n"
                   f"▶️ Attempted to start: {started_count} scripts.\n"
                   f"👥 Users processed: {attempted_users}.\n")
    if skipped_files > 0:
        summary_msg += f"⚠️ Skipped/Error files: {skipped_files}\n"
        if error_files_details:
            summary_msg += "Details (first 5):\n" + "\n".join([f"  - {err}" for err in error_files_details[:5]])
            if len(error_files_details) > 5: summary_msg += "\n  ... and more (check logs)."
    reply_func(summary_msg, parse_mode='Markdown')
    logger.info(f"Run all scripts finished. Admin: {admin_user_id}. Started: {started_count}. Skipped/Errors: {skipped_files}")

@bot.message_handler(commands=['start', 'help'])
def command_send_welcome(message): _logic_send_welcome(message)

BUTTON_TEXT_TO_LOGIC = {
    "🛠️ Help": _logic_support,
    "🛠️ Support": _logic_support,
    "📤 Upload File": _logic_upload_file,
    "📂 Check Files": _logic_check_files,
    "⚡ Bot Speed": _logic_bot_speed,
    "📞 Contact Owner": _logic_contact_owner,
    "💎 Plans": _logic_plans,
    "👤 Profile": _logic_profile_cmd,
    "💳 Subscriptions": _logic_subscriptions_panel,
    "📢 Broadcast": _logic_broadcast_init,
    "🔒 Lock Bot": _logic_toggle_lock_bot,
    "🟢 Running All Code": _logic_run_all_scripts,
    "👑 Admin Panel": _logic_admin_panel,
}

@bot.message_handler(func=lambda message: message.text in BUTTON_TEXT_TO_LOGIC)
def handle_button_text(message):
    logic_func = BUTTON_TEXT_TO_LOGIC.get(message.text)
    if logic_func: logic_func(message)
    else: logger.warning(f"Button text '{message.text}' matched but no logic func.")

@bot.message_handler(commands=['updateschannel'])
def command_updates_channel(message): _logic_updates_channel(message)
@bot.message_handler(commands=['uploadfile'])
def command_upload_file(message): _logic_upload_file(message)
@bot.message_handler(commands=['checkfiles'])
def command_check_files(message): _logic_check_files(message)
@bot.message_handler(commands=['botspeed'])
def command_bot_speed(message): _logic_bot_speed(message)
@bot.message_handler(commands=['contactowner'])
def command_contact_owner(message): _logic_contact_owner(message)
@bot.message_handler(commands=['subscriptions'])
def command_subscriptions(message): _logic_subscriptions_panel(message)
@bot.message_handler(commands=['statistics'])
def command_statistics(message): _logic_statistics(message)
@bot.message_handler(commands=['broadcast'])
def command_broadcast(message): _logic_broadcast_init(message)
@bot.message_handler(commands=['lockbot'])
def command_lock_bot(message): _logic_toggle_lock_bot(message)
@bot.message_handler(commands=['adminpanel'])
def command_admin_panel(message): _logic_admin_panel(message)
@bot.message_handler(commands=['runningallcode'])
def command_run_all_code(message): _logic_run_all_scripts(message)

@bot.message_handler(commands=['ping'])
def ping(message):
    start_ping_time = time.time()
    msg = bot.reply_to(message, "Pong!")
    latency = round((time.time() - start_ping_time) * 1000, 2)
    bot.edit_message_text(f"Pong! Latency: {latency} ms", message.chat.id, msg.message_id)

@bot.message_handler(content_types=['document'])
def handle_file_upload_doc(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    doc = message.document
    logger.info(f"Doc from {user_id}: {doc.file_name} ({doc.mime_type}), Size: {doc.file_size}")
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, "⚠️ Bot locked, cannot accept files.")
        return
    file_limit = get_user_upload_limit(user_id)
    current_files = get_user_file_count(user_id)
    if current_files >= file_limit:
        limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
        bot.reply_to(message, f"⚠️ File limit ({current_files}/{limit_str}) reached. Delete files via /checkfiles.")
        return
    file_name = doc.file_name
    if not file_name: bot.reply_to(message, "⚠️ No file name. Ensure file has a name."); return
    file_ext = os.path.splitext(file_name)[1].lower()
    if file_ext not in ['.py', '.js', '.zip']:
        bot.reply_to(message, "⚠️ Unsupported type! Only `.py`, `.js`, `.zip` allowed.")
        return
    max_file_size = 20 * 1024 * 1024
    if doc.file_size > max_file_size:
        bot.reply_to(message, f"⚠️ File too large (Max: {max_file_size // 1024 // 1024} MB)."); return
    try:
        try:
            bot.forward_message(OWNER_ID, chat_id, message.message_id)
            bot.send_message(OWNER_ID, f"⬆️ File '{file_name}' from {message.from_user.first_name} (`{user_id}`)", parse_mode='Markdown')
        except Exception as e: logger.error(f"Failed to forward uploaded file to OWNER_ID {OWNER_ID}: {e}")
        download_wait_msg = bot.reply_to(message, f"⏳ Downloading `{file_name}`...")
        file_info_tg_doc = bot.get_file(doc.file_id)
        downloaded_file_content = bot.download_file(file_info_tg_doc.file_path)
        bot.edit_message_text(f"✅ Downloaded `{file_name}`. Processing...", chat_id, download_wait_msg.message_id)
        logger.info(f"Downloaded {file_name} for user {user_id}")
        user_folder = get_user_folder(user_id)
        if file_ext == '.zip':
            handle_zip_file(downloaded_file_content, file_name, message)
        else:
            file_path = os.path.join(user_folder, file_name)
            with open(file_path, 'wb') as f: f.write(downloaded_file_content)
            logger.info(f"Saved single file to {file_path}")
            if file_ext == '.js': handle_js_file(file_path, user_id, user_folder, file_name, message)
            elif file_ext == '.py': handle_py_file(file_path, user_id, user_folder, file_name, message)
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Telegram API Error handling file for {user_id}: {e}", exc_info=True)
        if "file is too big" in str(e).lower():
            bot.reply_to(message, f"❌ Telegram API Error: File too large to download (~20MB limit).")
        else: bot.reply_to(message, f"❌ Telegram API Error: {str(e)}. Try later.")
    except Exception as e:
        logger.error(f"❌ General error handling file for {user_id}: {e}", exc_info=True)
        bot.reply_to(message, f"❌ Unexpected error: {str(e)}")

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data
    logger.info(f"Callback: User={user_id}, Data='{data}'")
    if bot_locked and user_id not in admin_ids and data not in ['back_to_main', 'speed', 'stats']:
        bot.answer_callback_query(call.id, "⚠️ Bot locked by admin.", show_alert=True)
        return
    try:
        if data == 'upload': upload_callback(call)
        elif data == 'check_files': check_files_callback(call)
        elif data.startswith('file_'): file_control_callback(call)
        elif data.startswith('start_'): start_bot_callback(call)
        elif data.startswith('stop_'): stop_bot_callback(call)
        elif data.startswith('restart_'): restart_bot_callback(call)
        elif data.startswith('delete_'): delete_bot_callback(call)
        elif data.startswith('logs_'): logs_bot_callback(call)
        elif data.startswith('editcode_'): edit_code_callback(call)
        elif data == 'speed': speed_callback(call)
        elif data == 'back_to_main': back_to_main_callback(call)
        elif data.startswith('confirm_broadcast_'): handle_confirm_broadcast(call)
        elif data == 'cancel_broadcast': handle_cancel_broadcast(call)
        elif data == 'subscription': admin_required_callback(call, subscription_management_callback)
        elif data == 'lock_bot': admin_required_callback(call, lock_bot_callback)
        elif data == 'unlock_bot': admin_required_callback(call, unlock_bot_callback)
        elif data == 'run_all_scripts': admin_required_callback(call, run_all_scripts_callback)
        elif data == 'broadcast': admin_required_callback(call, broadcast_init_callback)
        elif data == 'admin_panel': admin_required_callback(call, admin_panel_callback)
        elif data == 'add_admin': owner_required_callback(call, add_admin_init_callback)
        elif data == 'remove_admin': owner_required_callback(call, remove_admin_init_callback)
        elif data == 'list_admins': admin_required_callback(call, list_admins_callback)
        elif data == 'add_subscription': admin_required_callback(call, add_subscription_init_callback)
        elif data == 'remove_subscription': admin_required_callback(call, remove_subscription_init_callback)
        elif data == 'check_subscription': admin_required_callback(call, check_subscription_init_callback)
        elif data == 'admin_spy_users': admin_required_callback(call, admin_spy_users_callback)
        elif data == 'admin_set_welcome_video': admin_required_callback(call, admin_set_welcome_video_init_callback)
        elif data == 'set_backup_channel': admin_required_callback(call, set_backup_channel_init_callback)
        elif data == 'set_support_link': admin_required_callback(call, set_support_link_init_callback)
        elif data == 'edit_plans_init': admin_required_callback(call, edit_plans_init_callback)
        elif data.startswith('edit_plan_price_') or data.startswith('edit_plan_limit_'): admin_required_callback(call, handle_plan_edit_prompt)
        elif data.startswith('edit_plan_'): admin_required_callback(call, edit_plan_callback)
        elif data == 'buy_premium': show_plans_callback(call)
        elif data.startswith('buy_plan_'): buy_plan_callback(call)
        elif data.startswith('gateway_'): gateway_callback(call)
        elif data.startswith('verifypay_'): verify_payment_callback(call)
        elif data.startswith('check_payment_status_'): check_payment_status_callback(call)
        elif data.startswith('admin_spy_'): admin_required_callback(call, admin_spy_user_files_callback)
        elif data.startswith('admin_proj_'): admin_required_callback(call, admin_spy_proj_callback)
        elif data.startswith('admin_start_'): call.data = data.replace('admin_', '', 1); admin_required_callback(call, start_bot_callback)
        elif data.startswith('admin_stop_'): call.data = data.replace('admin_', '', 1); admin_required_callback(call, stop_bot_callback)
        elif data.startswith('admin_restart_'): call.data = data.replace('admin_', '', 1); admin_required_callback(call, restart_bot_callback)
        elif data.startswith('admin_del_'): call.data = data.replace('admin_del_', 'delete_', 1); admin_required_callback(call, delete_bot_callback)
        elif data.startswith('admin_logs_'): call.data = data.replace('admin_', '', 1); admin_required_callback(call, logs_bot_callback)
        elif data.startswith('admin_dl_'): admin_required_callback(call, admin_dl_file_callback)
        elif data.startswith('admin_zipproj_'): admin_required_callback(call, admin_zipproj_callback)
        elif data.startswith('admin_zip_'): admin_required_callback(call, admin_zip_folder_callback)
        else:
            bot.answer_callback_query(call.id, "Unknown action.")
            logger.warning(f"Unhandled callback data: {data} from user {user_id}")
    except Exception as e:
        logger.error(f"Error handling callback '{data}' for {user_id}: {e}", exc_info=True)
        try: bot.answer_callback_query(call.id, "Error processing request.", show_alert=True)
        except Exception as e_ans: logger.error(f"Failed to answer callback after error: {e_ans}")

def admin_required_callback(call, func_to_run):
    if call.from_user.id not in admin_ids:
        bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
        return
    func_to_run(call)

def owner_required_callback(call, func_to_run):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "⚠️ Owner permissions required.", show_alert=True)
        return
    func_to_run(call)

def upload_callback(call):
    user_id = call.from_user.id
    file_limit = get_user_upload_limit(user_id)
    current_files = get_user_file_count(user_id)
    if current_files >= file_limit:
        limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
        bot.answer_callback_query(call.id, f"⚠️ File limit ({current_files}/{limit_str}) reached.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "📤 Send your Python (`.py`), JS (`.js`), or ZIP (`.zip`) file.")

def check_files_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    user_files_list = user_files.get(user_id, [])
    if not user_files_list:
        bot.answer_callback_query(call.id, "⚠️ No files uploaded.", show_alert=True)
        try:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Back to Main", callback_data='back_to_main'))
            bot.edit_message_text("📂 Your files:\n\n(No files uploaded)", chat_id, call.message.message_id, reply_markup=markup)
        except Exception as e: logger.error(f"Error editing msg for empty file list: {e}")
        return
    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for file_name, file_type in sorted(user_files_list):
        is_running = is_bot_running(user_id, file_name)
        status_icon = "🟢 Running" if is_running else "🔴 Stopped"
        btn_text = f"{file_name} ({file_type}) - {status_icon}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f'file_{user_id}_{file_name}'))
    markup.add(types.InlineKeyboardButton("🔙 Back to Main", callback_data='back_to_main'))
    try:
        bot.edit_message_text("📂 Your files:\nClick to manage.", chat_id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" in str(e): logger.warning("Msg not modified (files).")
        else: logger.error(f"Error editing msg for file list: {e}")
    except Exception as e: logger.error(f"Unexpected error editing msg for file list: {e}", exc_info=True)

def file_control_callback(call):
    try:
        _, script_owner_id_str, file_name = call.data.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        requesting_user_id = call.from_user.id
        if not (requesting_user_id == script_owner_id or requesting_user_id in admin_ids):
            logger.warning(f"User {requesting_user_id} tried to access file '{file_name}' of user {script_owner_id} without permission.")
            bot.answer_callback_query(call.id, "⚠️ You can only manage your own files.", show_alert=True)
            check_files_callback(call)
            return
        user_files_list = user_files.get(script_owner_id, [])
        if not any(f[0] == file_name for f in user_files_list):
            logger.warning(f"File '{file_name}' not found for user {script_owner_id} during control.")
            bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True)
            check_files_callback(call)
            return
        bot.answer_callback_query(call.id)
        is_running = is_bot_running(script_owner_id, file_name)
        status_text = '🟢 Running' if is_running else '🔴 Stopped'
        file_type = next((f[1] for f in user_files_list if f[0] == file_name), '?')
        try:
            beautiful_text = f"""<blockquote><b>⚙️ File Control Center</b></blockquote>
👤 <b>Owner:</b> <code>{script_owner_id}</code>
📄 <b>File:</b> <code>{file_name}</code>
💻 <b>Type:</b> <code>{file_type.upper()}</code>
{status_text}"""
            bot.edit_message_text(
                beautiful_text,
                call.message.chat.id, call.message.message_id,
                reply_markup=create_control_buttons(script_owner_id, file_name, is_running),
                parse_mode='HTML'
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e): logger.warning(f"Msg not modified (controls for {file_name})")
            else: raise
    except (ValueError, IndexError) as ve:
        logger.error(f"Error parsing file control callback: {ve}. Data: '{call.data}'")
        bot.answer_callback_query(call.id, "Error: Invalid action data.", show_alert=True)
    except Exception as e:
        logger.error(f"Error in file_control_callback for data '{call.data}': {e}", exc_info=True)
        bot.answer_callback_query(call.id, "An error occurred.", show_alert=True)

def start_bot_callback(call):
    try:
        _, script_owner_id_str, file_name = call.data.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        requesting_user_id = call.from_user.id
        chat_id_for_reply = call.message.chat.id
        logger.info(f"Start request: Requester={requesting_user_id}, Owner={script_owner_id}, File='{file_name}'")
        if not (requesting_user_id == script_owner_id or requesting_user_id in admin_ids):
            bot.answer_callback_query(call.id, "⚠️ Permission denied to start this script.", show_alert=True); return
        user_files_list = user_files.get(script_owner_id, [])
        file_info = next((f for f in user_files_list if f[0] == file_name), None)
        if not file_info:
            bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True); check_files_callback(call); return
        file_type = file_info[1]
        user_folder = get_user_folder(script_owner_id)
        file_path = os.path.join(user_folder, file_name)
        if not os.path.exists(file_path):
            bot.answer_callback_query(call.id, f"⚠️ Error: File `{file_name}` missing! Re-upload.", show_alert=True)
            remove_user_file_db(script_owner_id, file_name); check_files_callback(call); return
        if is_bot_running(script_owner_id, file_name):
            bot.answer_callback_query(call.id, f"⚠️ Script '{file_name}' already running.", show_alert=True)
            try: bot.edit_message_reply_markup(chat_id_for_reply, call.message.message_id, reply_markup=create_control_buttons(script_owner_id, file_name, True))
            except Exception as e: logger.error(f"Error updating buttons (already running): {e}")
            return
            
        # Check running limits
        run_limit = get_user_run_limit(script_owner_id)
        running_count = sum(1 for key, info in list(bot_scripts.items()) 
                            if int(key.split('_')[0]) == script_owner_id and is_bot_running(script_owner_id, info['file_name']))
        if running_count >= run_limit and script_owner_id not in admin_ids:
            bot.answer_callback_query(call.id, f"⚠️ Limit Reached! You can only host {run_limit} bot(s) at a time on your current plan.", show_alert=True)
            return

        bot.answer_callback_query(call.id, f"⏳ Attempting to start {file_name} for user {script_owner_id}...")
        if file_type == 'py':
            threading.Thread(target=run_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()
        elif file_type == 'js':
            threading.Thread(target=run_js_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()
        else:
            bot.send_message(chat_id_for_reply, f"❌ Error: Unknown file type '{file_type}' for '{file_name}'."); return
        time.sleep(1.5)
        is_now_running = is_bot_running(script_owner_id, file_name)
        status_text = '🟢 Running' if is_now_running else '🟡 Starting (or failed, check logs/replies)'
        try:
            beautiful_text = f"""<blockquote><b>⚙️ File Control Center</b></blockquote>
👤 <b>Owner:</b> <code>{script_owner_id}</code>
📄 <b>File:</b> <code>{file_name}</code>
💻 <b>Type:</b> <code>{file_type.upper()}</code>
{status_text}"""
            bot.edit_message_text(
                beautiful_text,
                chat_id_for_reply, call.message.message_id,
                reply_markup=create_control_buttons(script_owner_id, file_name, is_now_running), parse_mode='HTML'
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e): logger.warning(f"Msg not modified after starting {file_name}")
            else: raise
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing start callback '{call.data}': {e}")
        bot.answer_callback_query(call.id, "Error: Invalid start command.", show_alert=True)
    except Exception as e:
        logger.error(f"Error in start_bot_callback for '{call.data}': {e}", exc_info=True)
        bot.answer_callback_query(call.id, "Error starting script.", show_alert=True)
        try:
            _, script_owner_id_err_str, file_name_err = call.data.split('_', 2)
            script_owner_id_err = int(script_owner_id_err_str)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=create_control_buttons(script_owner_id_err, file_name_err, False))
        except Exception as e_btn: logger.error(f"Failed to update buttons after start error: {e_btn}")

def stop_bot_callback(call):
    try:
        _, script_owner_id_str, file_name = call.data.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        requesting_user_id = call.from_user.id
        chat_id_for_reply = call.message.chat.id
        logger.info(f"Stop request: Requester={requesting_user_id}, Owner={script_owner_id}, File='{file_name}'")
        if not (requesting_user_id == script_owner_id or requesting_user_id in admin_ids):
            bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True); return
        user_files_list = user_files.get(script_owner_id, [])
        file_info = next((f for f in user_files_list if f[0] == file_name), None)
        if not file_info:
            bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True); check_files_callback(call); return
        file_type = file_info[1]
        script_key = f"{script_owner_id}_{file_name}"
        if not is_bot_running(script_owner_id, file_name):
            bot.answer_callback_query(call.id, f"⚠️ Script '{file_name}' already stopped.", show_alert=True)
            try:
                beautiful_text_stopped = f"""<blockquote><b>⚙️ File Control Center</b></blockquote>
👤 <b>Owner:</b> <code>{script_owner_id}</code>
📄 <b>File:</b> <code>{file_name}</code>
💻 <b>Type:</b> <code>{file_type.upper()}</code>
🔴 Stopped"""
                bot.edit_message_text(
                    beautiful_text_stopped,
                    chat_id_for_reply, call.message.message_id,
                    reply_markup=create_control_buttons(script_owner_id, file_name, False), parse_mode='HTML')
            except Exception as e: logger.error(f"Error updating buttons (already stopped): {e}")
            return
        bot.answer_callback_query(call.id, f"⏳ Stopping {file_name} for user {script_owner_id}...")
        process_info = bot_scripts.get(script_key) or {'script_key': script_key}
        if process_info:
            kill_process_tree(process_info)
            if script_key in bot_scripts: del bot_scripts[script_key]; logger.info(f"Removed {script_key} from running after stop.")
            remove_pid_from_db(script_key)
        else: logger.warning(f"Script {script_key} running by psutil but not in bot_scripts dict.")
        try:
            beautiful_text_stopped = f"""<blockquote><b>⚙️ File Control Center</b></blockquote>
👤 <b>Owner:</b> <code>{script_owner_id}</code>
📄 <b>File:</b> <code>{file_name}</code>
💻 <b>Type:</b> <code>{file_type.upper()}</code>
🔴 Stopped"""
            bot.edit_message_text(
                beautiful_text_stopped,
                chat_id_for_reply, call.message.message_id,
                reply_markup=create_control_buttons(script_owner_id, file_name, False), parse_mode='HTML'
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e): logger.warning(f"Msg not modified after stopping {file_name}")
            else: raise
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing stop callback '{call.data}': {e}")
        bot.answer_callback_query(call.id, "Error: Invalid stop command.", show_alert=True)
    except Exception as e:
        logger.error(f"Error in stop_bot_callback for '{call.data}': {e}", exc_info=True)
        bot.answer_callback_query(call.id, "Error stopping script.", show_alert=True)

def restart_bot_callback(call):
    try:
        _, script_owner_id_str, file_name = call.data.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        requesting_user_id = call.from_user.id
        chat_id_for_reply = call.message.chat.id
        logger.info(f"Restart: Requester={requesting_user_id}, Owner={script_owner_id}, File='{file_name}'")
        if not (requesting_user_id == script_owner_id or requesting_user_id in admin_ids):
            bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True); return
        user_files_list = user_files.get(script_owner_id, [])
        file_info = next((f for f in user_files_list if f[0] == file_name), None)
        if not file_info:
            bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True); check_files_callback(call); return
        file_type = file_info[1]; user_folder = get_user_folder(script_owner_id)
        file_path = os.path.join(user_folder, file_name); script_key = f"{script_owner_id}_{file_name}"
        if not os.path.exists(file_path):
            bot.answer_callback_query(call.id, f"⚠️ Error: File `{file_name}` missing! Re-upload.", show_alert=True)
            remove_user_file_db(script_owner_id, file_name)
            if script_key in bot_scripts: del bot_scripts[script_key]
            check_files_callback(call); return
        bot.answer_callback_query(call.id, f"⏳ Restarting {file_name} for user {script_owner_id}...")
        if is_bot_running(script_owner_id, file_name):
            logger.info(f"Restart: Stopping existing {script_key}...")
            process_info = bot_scripts.get(script_key) or {'script_key': script_key}
            if process_info: kill_process_tree(process_info)
            if script_key in bot_scripts: del bot_scripts[script_key]
            remove_pid_from_db(script_key)
            time.sleep(1.5)
        logger.info(f"Restart: Starting script {script_key}...")
        if file_type == 'py':
            threading.Thread(target=run_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()
        elif file_type == 'js':
            threading.Thread(target=run_js_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()
        else:
            bot.send_message(chat_id_for_reply, f"❌ Unknown type '{file_type}' for '{file_name}'."); return
        time.sleep(1.5)
        is_now_running = is_bot_running(script_owner_id, file_name)
        status_text = '🟢 Running' if is_now_running else '🟡 Starting (or failed)'
        try:
            bot.edit_message_text(
                f"⚙️ Controls for: `{file_name}` ({file_type}) of User `{script_owner_id}`\nStatus: {status_text}",
                chat_id_for_reply, call.message.message_id,
                reply_markup=create_control_buttons(script_owner_id, file_name, is_now_running), parse_mode='Markdown'
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e): logger.warning(f"Msg not modified (restart {file_name})")
            else: raise
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing restart callback '{call.data}': {e}")
        bot.answer_callback_query(call.id, "Error: Invalid restart command.", show_alert=True)
    except Exception as e:
        logger.error(f"Error in restart_bot_callback for '{call.data}': {e}", exc_info=True)
        bot.answer_callback_query(call.id, "Error restarting.", show_alert=True)
        try:
            _, script_owner_id_err_str, file_name_err = call.data.split('_', 2)
            script_owner_id_err = int(script_owner_id_err_str)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=create_control_buttons(script_owner_id_err, file_name_err, False))
        except Exception as e_btn: logger.error(f"Failed to update buttons after restart error: {e_btn}")

def delete_bot_callback(call):
    try:
        _, script_owner_id_str, file_name = call.data.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        requesting_user_id = call.from_user.id
        chat_id_for_reply = call.message.chat.id
        logger.info(f"Delete: Requester={requesting_user_id}, Owner={script_owner_id}, File='{file_name}'")
        if not (requesting_user_id == script_owner_id or requesting_user_id in admin_ids):
            bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True); return
        user_files_list = user_files.get(script_owner_id, [])
        if not any(f[0] == file_name for f in user_files_list):
            bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True); check_files_callback(call); return
        bot.answer_callback_query(call.id, f"🗑️ Deleting {file_name} for user {script_owner_id}...")
        script_key = f"{script_owner_id}_{file_name}"
        if is_bot_running(script_owner_id, file_name):
            logger.info(f"Delete: Stopping {script_key}...")
            process_info = bot_scripts.get(script_key) or {'script_key': script_key}
            if process_info: kill_process_tree(process_info)
            if script_key in bot_scripts: del bot_scripts[script_key]
            remove_pid_from_db(script_key)
            time.sleep(0.5)
        user_folder = get_user_folder(script_owner_id)
        file_path = os.path.join(user_folder, file_name)
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        deleted_disk = []
        if os.path.exists(file_path):
            try: os.remove(file_path); deleted_disk.append(file_name); logger.info(f"Deleted file: {file_path}")
            except OSError as e: logger.error(f"Error deleting {file_path}: {e}")
        if os.path.exists(log_path):
            try: os.remove(log_path); deleted_disk.append(os.path.basename(log_path)); logger.info(f"Deleted log: {log_path}")
            except OSError as e: logger.error(f"Error deleting log {log_path}: {e}")
        remove_user_file_db(script_owner_id, file_name)
        deleted_str = ", ".join(f"`{f}`" for f in deleted_disk) if deleted_disk else "associated files"
        try:
            bot.edit_message_text(
                f"🗑️ Record `{file_name}` (User `{script_owner_id}`) and {deleted_str} deleted!",
                chat_id_for_reply, call.message.message_id, reply_markup=None, parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error editing msg after delete: {e}")
            bot.send_message(chat_id_for_reply, f"🗑️ Record `{file_name}` deleted.", parse_mode='Markdown')
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing delete callback '{call.data}': {e}")
        bot.answer_callback_query(call.id, "Error: Invalid delete command.", show_alert=True)
    except Exception as e:
        logger.error(f"Error in delete_bot_callback for '{call.data}': {e}", exc_info=True)
        bot.answer_callback_query(call.id, "Error deleting.", show_alert=True)

def logs_bot_callback(call):
    try:
        _, script_owner_id_str, file_name = call.data.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        requesting_user_id = call.from_user.id
        chat_id_for_reply = call.message.chat.id
        logger.info(f"Logs: Requester={requesting_user_id}, Owner={script_owner_id}, File='{file_name}'")
        if not (requesting_user_id == script_owner_id or requesting_user_id in admin_ids):
            bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True); return
        user_files_list = user_files.get(script_owner_id, [])
        if not any(f[0] == file_name for f in user_files_list):
            bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True); check_files_callback(call); return
        user_folder = get_user_folder(script_owner_id)
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        if not os.path.exists(log_path):
            bot.answer_callback_query(call.id, f"⚠️ No logs for '{file_name}'.", show_alert=True); return
        bot.answer_callback_query(call.id)
        try:
            log_content = ""; file_size = os.path.getsize(log_path)
            max_log_kb = 100; max_tg_msg = 4096
            if file_size == 0: log_content = "(Log empty)"
            elif file_size > max_log_kb * 1024:
                with open(log_path, 'rb') as f: f.seek(-max_log_kb * 1024, os.SEEK_END); log_bytes = f.read()
                log_content = log_bytes.decode('utf-8', errors='ignore')
                log_content = f"(Last {max_log_kb} KB)\n...\n" + log_content
            else:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f: log_content = f.read()
            if len(log_content) > max_tg_msg:
                log_content = log_content[-max_tg_msg:]
                first_nl = log_content.find('\n')
                if first_nl != -1: log_content = "...\n" + log_content[first_nl+1:]
                else: log_content = "...\n" + log_content
            if not log_content.strip(): log_content = "(No visible content)"
            bot.send_message(chat_id_for_reply, f"📜 Logs for `{file_name}` (User `{script_owner_id}`):\n```\n{log_content}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error reading/sending log {log_path}: {e}", exc_info=True)
            bot.send_message(chat_id_for_reply, f"⚠️ Error reading log file: {e}")
    except ValueError:
        bot.answer_callback_query(call.id, "Error: Invalid logs command.", show_alert=True)
    except Exception as e:
        logger.error(f"Error in logs_bot_callback for '{call.data}': {e}", exc_info=True)
        bot.answer_callback_query(call.id, "Error viewing logs.", show_alert=True)

def edit_code_callback(call):
    try:
        _, script_owner_id_str, file_name = call.data.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        requesting_user_id = call.from_user.id
        chat_id_for_reply = call.message.chat.id
        if not (requesting_user_id == script_owner_id or requesting_user_id in admin_ids):
            bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True); return
        user_files_list = user_files.get(script_owner_id, [])
        if not any(f[0] == file_name for f in user_files_list):
            bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True); return
        
        user_folder = get_user_folder(script_owner_id)
        file_path = os.path.join(user_folder, file_name)
        if not os.path.exists(file_path):
            bot.answer_callback_query(call.id, f"⚠️ File '{file_name}' not found on disk.", show_alert=True); return
            
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            code_content = f.read()
            
        bot.answer_callback_query(call.id)
        
        if len(code_content) > 3500:
            bot.send_message(chat_id_for_reply, f"⚠️ File `{file_name}` is too large to edit via Telegram message (Limit: 4096 chars).\nPlease download, edit, and re-upload.", parse_mode='Markdown')
            return
            
        msg_text = f"📝 *Live Editor:* `{file_name}`\n\nSend the complete new code to replace the file. Type `/cancel` to abort.\n\nCurrent Code:\n```\n{code_content}\n```"
        msg = bot.send_message(chat_id_for_reply, msg_text, parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_edit_code, script_owner_id, file_name, file_path)
        
    except Exception as e:
        logger.error(f"Error in edit_code_callback: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "Error starting editor.", show_alert=True)

def process_edit_code(message, script_owner_id, file_name, file_path):
    if message.text == '/cancel':
        bot.reply_to(message, "❌ Cancelled code editing.")
        return
    
    new_code = message.text
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_code)
        
        markup = create_control_buttons(script_owner_id, file_name, is_running=False)
        bot.reply_to(message, f"✅ File `{file_name}` updated successfully!\n\n👇 Manage your bot:", reply_markup=markup)
        
    except Exception as e:
        logger.error(f"Error saving edited code for {file_name}: {e}", exc_info=True)
        bot.reply_to(message, f"❌ Failed to save file: {e}")


def speed_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    start_cb_ping_time = time.time()
    try:
        bot.edit_message_text("🏃 Testing speed...", chat_id, call.message.message_id)
        bot.send_chat_action(chat_id, 'typing')
        response_time = round((time.time() - start_cb_ping_time) * 1000, 2)
        status = "🔓 Unlocked" if not bot_locked else "🔒 Locked"
        if user_id == OWNER_ID:
            user_level = "👑 Owner"
        elif user_id in admin_ids:
            user_level = "🛡️ Admin"
        elif user_id in user_subscriptions and user_subscriptions[user_id].get('expiry', datetime.min) > datetime.now():
            user_level = "⭐ Premium"
        else:
            user_level = "🆓 Free User"
        speed_msg = (f"⚡ Bot Speed & Status:\n\n⏱️ API Response Time: {response_time} ms\n"
                     f"🚦 Bot Status: {status}\n"
                     f"👤 Your Level: {user_level}")
        bot.answer_callback_query(call.id)  # <-- YAHAN FIX KAR DIYA
        bot.edit_message_text(speed_msg, chat_id, call.message.message_id)
    except Exception as e:
        logger.error(f"Error in speed_callback: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "Error checking speed.", show_alert=True)

def back_to_main_callback(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text("🔙 Returning to main menu...", call.message.chat.id, call.message.message_id)
    _logic_send_welcome(call.message)

def stats_callback(call):
    _logic_statistics(call.message)

def lock_bot_callback(call):
    global bot_locked
    bot_locked = True
    bot.answer_callback_query(call.id, "🔒 Bot locked.", show_alert=True)
    _logic_send_welcome(call.message)

def unlock_bot_callback(call):
    global bot_locked
    bot_locked = False
    bot.answer_callback_query(call.id, "🔓 Bot unlocked.", show_alert=True)
    _logic_send_welcome(call.message)

def run_all_scripts_callback(call):
    _logic_run_all_scripts(call)

def broadcast_init_callback(call):
    _logic_broadcast_init(call.message)

def admin_panel_callback(call):
    _logic_admin_panel(call.message)

def add_admin_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "➕ Send User ID to add as admin:")
    bot.register_next_step_handler(msg, process_add_admin)

def remove_admin_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "➖ Send User ID to remove from admin:")
    bot.register_next_step_handler(msg, process_remove_admin)

def list_admins_callback(call):
    bot.answer_callback_query(call.id)
    admin_list = "\n".join([f"`{admin_id}`" for admin_id in admin_ids])
    bot.send_message(call.message.chat.id, f"📋 List of Admins:\n{admin_list}", parse_mode='Markdown')

def admin_set_welcome_video_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📹 Please send the Video you want to set as the Welcome message.\n\nType /cancel to abort.")
    bot.register_next_step_handler(msg, process_set_welcome_video)

def process_set_welcome_video(message):
    if message.text == '/cancel':
        bot.reply_to(message, "❌ Cancelled setting welcome video.")
        return
    if not message.video:
        bot.reply_to(message, "❌ Invalid format. Please send a Video file. Try again from Admin Panel.")
        return
    try:
        video_id = message.video.file_id
        set_bot_setting("welcome_video_id", video_id)
        bot.reply_to(message, "✅ Welcome Video has been updated successfully!")
    except Exception as e:
        bot.reply_to(message, f"❌ Error saving video: {e}")

def add_subscription_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "➕ Send User ID and days (e.g., `123456789 30`):")
    bot.register_next_step_handler(msg, process_add_subscription)

def remove_subscription_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "➖ Send User ID to remove subscription:")
    bot.register_next_step_handler(msg, process_remove_subscription)

def check_subscription_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "🔍 Send User ID to check subscription:")
    bot.register_next_step_handler(msg, process_check_subscription)

def subscription_management_callback(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "💳 Subscription Management", reply_markup=create_subscription_menu())

def process_add_admin(message):
    try:
        admin_id = int(message.text.strip())
        if admin_id == OWNER_ID:
            bot.reply_to(message, "⚠️ Owner is already admin.")
            return
        add_admin_db(admin_id)
        bot.reply_to(message, f"✅ User `{admin_id}` added as admin!", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, "❌ Invalid User ID. Please send a number.")

def process_remove_admin(message):
    try:
        admin_id = int(message.text.strip())
        if admin_id == OWNER_ID:
            bot.reply_to(message, "⚠️ Cannot remove Owner from admin.")
            return
        if remove_admin_db(admin_id):
            bot.reply_to(message, f"✅ User `{admin_id}` removed from admin.", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"⚠️ User `{admin_id}` not found in admin list.", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, "❌ Invalid User ID. Please send a number.")

def process_add_subscription(message):
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            bot.reply_to(message, "❌ Please send: `user_id days` (e.g., `123456789 30`)")
            return
        user_id = int(parts[0])
        days = int(parts[1])
        if days <= 0:
            bot.reply_to(message, "❌ Days must be positive.")
            return
        expiry = datetime.now() + timedelta(days=days)
        save_subscription(user_id, expiry)
        bot.reply_to(message, f"✅ Subscription added for user `{user_id}` until `{expiry.strftime('%Y-%m-%d %H:%M:%S')}`", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, "❌ Invalid input. Please send: `user_id days`")

def process_remove_subscription(message):
    try:
        user_id = int(message.text.strip())
        remove_subscription_db(user_id)
        bot.reply_to(message, f"✅ Subscription removed for user `{user_id}`", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, "❌ Invalid User ID. Please send a number.")

def process_check_subscription(message):
    try:
        user_id = int(message.text.strip())
        if user_id in user_subscriptions:
            expiry = user_subscriptions[user_id]['expiry']
            if expiry > datetime.now():
                days_left = (expiry - datetime.now()).days
                bot.reply_to(message, f"✅ User `{user_id}` has subscription until `{expiry.strftime('%Y-%m-%d %H:%M:%S')}` ({days_left} days left)", parse_mode='Markdown')
            else:
                bot.reply_to(message, f"⚠️ User `{user_id}` has expired subscription.", parse_mode='Markdown')
                remove_subscription_db(user_id)
        else:
            bot.reply_to(message, f"⚠️ User `{user_id}` has no subscription.", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, "❌ Invalid User ID. Please send a number.")

def process_broadcast_message(message):
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "❌ Broadcast cancelled.")
        return
    bot.reply_to(message, f"📢 Broadcasting message to {len(active_users)} users...")
    sent_count = 0
    failed_count = 0
    for user_id in active_users:
        try:
            bot.send_message(user_id, message.text)
            sent_count += 1
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to broadcast to {user_id}: {e}")
            failed_count += 1
    bot.reply_to(message, f"✅ Broadcast completed!\nSent: {sent_count}\nFailed: {failed_count}")

def handle_confirm_broadcast(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "📢 Send broadcast message or /cancel")
    bot.register_next_step_handler(call.message, process_broadcast_message)

def handle_cancel_broadcast(call):
    bot.answer_callback_query(call.id, "Broadcast cancelled.")
    bot.delete_message(call.message.chat.id, call.message.message_id)

def set_backup_channel_init_callback(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "Send the Backup Channel ID (e.g., -100123456789) or /cancel")
    bot.register_next_step_handler(call.message, process_set_backup_channel)

def process_set_backup_channel(message):
    if message.text == '/cancel':
        bot.reply_to(message, "Cancelled.")
        return
    set_bot_setting("backup_channel_id", message.text.strip())
    bot.reply_to(message, f"✅ Backup channel set to: {message.text.strip()}")

def set_support_link_init_callback(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "Send the new Support Link URL or /cancel")
    bot.register_next_step_handler(call.message, process_set_support_link)

def process_set_support_link(message):
    if message.text == '/cancel':
        bot.reply_to(message, "Cancelled.")
        return
    set_bot_setting("support_link", message.text.strip())
    bot.reply_to(message, f"✅ Support link set to: {message.text.strip()}")

def edit_plans_init_callback(call):
    plans = get_plan_details()
    markup = types.InlineKeyboardMarkup(row_width=1)
    for p_days, p_info in plans.items():
        markup.add(types.InlineKeyboardButton(f"{p_days} Days - ₹{p_info['price']} (Limit {p_info['limit']})", callback_data=f"edit_plan_{p_days}"))
    markup.add(types.InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel"))
    bot.edit_message_text("💎 **Edit Premium Plans**\n\nSelect a plan to edit:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

def edit_plan_callback(call):
    plan_days = call.data.split('_')[-1]
    plans = get_plan_details()
    p_info = plans.get(plan_days)
    if not p_info: return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton(f"💵 Edit Price (₹{p_info['price']})", callback_data=f"edit_plan_price_{plan_days}"),
        types.InlineKeyboardButton(f"🤖 Edit Limit ({p_info['limit']})", callback_data=f"edit_plan_limit_{plan_days}")
    )
    markup.add(types.InlineKeyboardButton("🔙 Back to Plans", callback_data="edit_plans_init"))
    bot.edit_message_text(f"💎 **Edit {plan_days} Days Plan**\n\nChoose what to change:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

def handle_plan_edit_prompt(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split('_')
    edit_type = parts[2] # 'price' or 'limit'
    plan_days = parts[3]
    
    msg_text = f"Send the new {edit_type.title()} for the {plan_days} Days Plan (numbers only).\nType /cancel to abort."
    msg = bot.send_message(call.message.chat.id, msg_text)
    
    if edit_type == 'price':
        bot.register_next_step_handler(msg, process_edit_plan_price, plan_days)
    else:
        bot.register_next_step_handler(msg, process_edit_plan_limit, plan_days)

def process_edit_plan_price(message, plan_days):
    if message.text == '/cancel':
        bot.reply_to(message, "Cancelled.")
        return
    if not message.text.isdigit():
        bot.reply_to(message, "❌ Invalid amount. Must be a number.")
        return
    set_bot_setting(f"plan_{plan_days}_price", message.text.strip())
    bot.reply_to(message, f"✅ Updated {plan_days} Days Plan Price to ₹{message.text.strip()}")

def process_edit_plan_limit(message, plan_days):
    if message.text == '/cancel':
        bot.reply_to(message, "Cancelled.")
        return
    if not message.text.isdigit():
        bot.reply_to(message, "❌ Invalid limit. Must be a number.")
        return
    set_bot_setting(f"plan_{plan_days}_limit", message.text.strip())
    bot.reply_to(message, f"✅ Updated {plan_days} Days Plan Bot Limit to {message.text.strip()}")

def show_plans_callback(call):
    bot.answer_callback_query(call.id)
    _logic_plans(call.message)

def buy_plan_callback(call):
    plan_days = call.data.split('_')[-1]
    plans = get_plan_details()
    
    if plan_days not in plans: return
    
    user_id = call.from_user.id
    amount = plans[plan_days]["price"]
    bot_limit = plans[plan_days]["limit"]

    is_first_time = not has_ever_purchased(user_id)
    discount_note = ""
    if is_first_time:
        original_amount = amount
        amount = apply_first_time_discount(amount)
        discount_note = f"\n🎉 **70% Trust Discount applied:** ~~₹{original_amount}~~ ➡️ **₹{amount}**"

    text = (
        f"💎 **You selected {plan_days} Days Plan (₹{amount})**"
        f"{discount_note}\n\n"
        "Please select a Payment Gateway:\n"
        "_(If one fails, try the other)_"
    )
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Gateway 1", callback_data=f"gateway_1_{plan_days}_{amount}_{bot_limit}"),
        types.InlineKeyboardButton("Gateway 2", callback_data=f"gateway_2_{plan_days}_{amount}_{bot_limit}")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

def gateway_callback(call):
    parts = call.data.split('_')
    gateway = parts[1]
    plan_days = int(parts[2])
    amount = float(parts[3])
    bot_limit = int(parts[4])
    user_id = call.from_user.id
    
    order_id = f"G{gateway}{uuid.uuid4().hex[:10]}"
    bot.answer_callback_query(call.id, "⏳ Generating Payment Link...", show_alert=False)
    
    key = KARANPAY_KEY_1 if gateway == "1" else KARANPAY_KEY_2
    
    try:
        payload = {
            "amount": f"{amount:.2f}",
            "order_id": order_id,
            "customer_name": call.from_user.first_name,
            "callback_url": f"https://t.me/yourbot"
        }
        headers = {
            "X-Guru-Key": key,
            "Content-Type": "application/json"
        }
        res = requests.post(KARANPAY_CREATE_URL, json=payload, headers=headers, timeout=15).json()
        
        if res.get("status") == "success":
            payment_url = res.get("data", {}).get("payment_url") or res.get("payment_url")
            if not payment_url:
                bot.send_message(user_id, "❌ Error: Could not generate Payment URL.")
                return
                
            upi_url = payment_url
            try:
                html_resp = requests.get(payment_url, timeout=10).text
                matches = re.findall(r'upi://pay\?[^\"\'<>]+', html_resp)
                if matches:
                    upi_url = matches[0].replace("&amp;", "&")
            except Exception as ex:
                logger.error(f"Failed to extract UPI intent: {ex}")
            
            # Generate QR
            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(upi_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            bio = io.BytesIO()
            img.save(bio, 'PNG')
            bio.seek(0)
            
            caption = (
                f"💎 **Buy Premium - {plan_days} Days**\n\n"
                f"💰 **Amount:** ₹{amount:.0f}\n\n"
                "📸 **Scan this QR code with any UPI app to pay.**\n"
                "⏳ _Please wait here... The bot is automatically checking your payment._\n"
                "_Already paid? Tap the button below to check instantly._"
            )
            verify_markup = types.InlineKeyboardMarkup()
            verify_markup.add(types.InlineKeyboardButton(
                "✅ Verify Payment",
                callback_data=f"verifypay_{gateway}_{order_id}_{plan_days}_{bot_limit}"
            ))
            bot.delete_message(call.message.chat.id, call.message.message_id)
            qr_msg = bot.send_photo(user_id, bio, caption=caption, parse_mode="Markdown", reply_markup=verify_markup)
            
            # Start auto-checking payment
            plan_name_map = {5: "Basic", 10: "Normal", 15: "Pro", 30: "Ultra Pro"}
            plan_name = plan_name_map.get(plan_days, "Premium")
            threading.Timer(10, auto_check_payment, args=(user_id, gateway, order_id, plan_days, bot_limit, plan_name, call.message.chat.id, qr_msg.message_id, 30)).start()
        else:
            bot.send_message(user_id, f"❌ Error from Payment Gateway: {res.get('message', 'Unknown Error')}")
    except Exception as e:
        logger.error(f"Error in buy premium: {e}")
        bot.send_message(user_id, "❌ An error occurred while generating payment link.")

def check_payment_status(gateway, order_id):
    """Single status check against the gateway. Returns True if paid, False otherwise."""
    key = KARANPAY_KEY_1 if gateway == "1" else KARANPAY_KEY_2
    headers = {"X-Guru-Key": key, "Content-Type": "application/json"}
    res = requests.post(KARANPAY_STATUS_URL, json={"order_id": order_id}, headers=headers, timeout=10).json()
    return res.get("status") == "success" and res.get("data", {}).get("payment_status") == "success"

def activate_paid_plan(user_id, plan_days, bot_limit, plan_name, chat_id, message_id):
    expiry = datetime.now() + timedelta(days=plan_days)
    save_subscription(user_id, expiry, bot_limit=bot_limit, plan_name=plan_name)
    try:
        bot.edit_message_caption(
            f"✅ **Payment Successful!**\n\nYour {plan_days}-day Premium has been activated!\nYou can now host up to {bot_limit} Bot(s).",
            chat_id, message_id, parse_mode="Markdown", reply_markup=None
        )
        bot.send_message(chat_id, f"🎉 Congratulations! Your **{plan_name}** ({plan_days} Days) Plan is now active.")
    except Exception: pass

def auto_check_payment(user_id, gateway, order_id, plan_days, bot_limit, plan_name, chat_id, message_id, checks_left=30):
    if checks_left <= 0:
        try: bot.edit_message_caption("❌ Payment not received within 5 minutes. Order expired.", chat_id, message_id, reply_markup=None)
        except Exception: pass
        return

    try:
        if check_payment_status(gateway, order_id):
            activate_paid_plan(user_id, plan_days, bot_limit, plan_name, chat_id, message_id)
            return
    except Exception as e:
        logger.error(f"Auto-check payment error for {order_id}: {e}")
        
    # Schedule next check
    threading.Timer(10, auto_check_payment, args=(user_id, gateway, order_id, plan_days, bot_limit, plan_name, chat_id, message_id, checks_left - 1)).start()

def verify_payment_callback(call):
    """Handles the '✅ Verify Payment' button - forces an instant check."""
    parts = call.data.split('_', 4)
    # verifypay_{gateway}_{order_id}_{plan_days}_{bot_limit}
    gateway = parts[1]
    order_id = parts[2]
    plan_days = int(parts[3])
    bot_limit = int(parts[4])
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    bot.answer_callback_query(call.id, "🔎 Checking payment status...", show_alert=False)

    try:
        if check_payment_status(gateway, order_id):
            plan_name_map = {5: "Basic", 10: "Normal", 15: "Pro", 30: "Ultra Pro"}
            plan_name = plan_name_map.get(plan_days, "Premium")
            activate_paid_plan(user_id, plan_days, bot_limit, plan_name, chat_id, message_id)
        else:
            bot.answer_callback_query(call.id, "⏳ Payment not detected yet. We'll keep checking automatically — try again in a moment.", show_alert=True)
    except Exception as e:
        logger.error(f"Manual verify payment error for {order_id}: {e}")
        bot.answer_callback_query(call.id, "❌ Could not reach the payment gateway. Please try again shortly.", show_alert=True)

# --- Owner Spy Features ---
def admin_spy_users_callback(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    users = list(user_files.keys())
    if not users:
        bot.answer_callback_query(call.id, "No users have uploaded files.")
        return
    for uid in users:
        num_files = len(user_files.get(uid, []))
        try:
            chat = bot.get_chat(uid)
            name_display = f"@{chat.username}" if chat.username else chat.first_name
        except:
            name_display = str(uid)
        markup.add(types.InlineKeyboardButton(f"{name_display} ({num_files} bots)", callback_data=f"admin_spy_{uid}"))
    markup.add(types.InlineKeyboardButton('🔙 Back', callback_data='admin_panel'))
    bot.edit_message_text("🕵️ Select a user to spy on:", call.message.chat.id, call.message.message_id, reply_markup=markup)

def admin_spy_user_files_callback(call):
    try:
        uid = int(call.data.split('_')[2])
    except:
        bot.answer_callback_query(call.id, "Error getting UID")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    user_folder = get_user_folder(uid)
    if not os.path.exists(user_folder):
        bot.answer_callback_query(call.id, "User folder not found.")
        return
        
    try:
        chat = bot.get_chat(uid)
        name_display = f"@{chat.username}" if chat.username else chat.first_name
    except:
        name_display = str(uid)
        
    files = os.listdir(user_folder)
    main_scripts = [f for f in files if f.endswith(('.py', '.js'))]
    
    if not main_scripts:
        markup.add(types.InlineKeyboardButton('📦 Download All User Files as ZIP', callback_data=f'admin_zip_{uid}'))
        markup.add(types.InlineKeyboardButton('🔙 Back to Users', callback_data='admin_spy_users'))
        bot.edit_message_text(f"🕵️ No main scripts found for {name_display}.", call.message.chat.id, call.message.message_id, reply_markup=markup)
        return
        
    for fname in main_scripts:
        markup.add(types.InlineKeyboardButton(f"🤖 {fname} Data", callback_data=f"admin_proj_{uid}_{fname}"))
            
    markup.add(types.InlineKeyboardButton('📦 Download ALL User Files', callback_data=f'admin_zip_{uid}'))
    markup.add(types.InlineKeyboardButton('🔙 Back to Users', callback_data='admin_spy_users'))
    bot.edit_message_text(f"🕵️ Scripts for {name_display}:\nSelect a script to view its data/logs.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

def admin_spy_proj_callback(call):
    parts = call.data.split('_', 3)
    uid = int(parts[2])
    fname = parts[3]
    fname_base = os.path.splitext(fname)[0]
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    user_folder = get_user_folder(uid)
    
    if not os.path.exists(user_folder):
        bot.answer_callback_query(call.id, "Folder not found.")
        return
        
    is_running = is_bot_running(uid, fname)
    status_icon = "🟢 Running" if is_running else "🔴 Stopped"
    
    # Control Buttons
    if is_running:
        markup.add(
            types.InlineKeyboardButton('🔴 Stop', callback_data=f'admin_stop_{uid}_{fname}'),
            types.InlineKeyboardButton('🔄 Restart', callback_data=f'admin_restart_{uid}_{fname}')
        )
    else:
        markup.add(
            types.InlineKeyboardButton('🟢 Start', callback_data=f'admin_start_{uid}_{fname}')
        )
    markup.add(
        types.InlineKeyboardButton('📜 Logs', callback_data=f'admin_logs_{uid}_{fname}'),
        types.InlineKeyboardButton('🗑️ Delete', callback_data=f'admin_del_{uid}_{fname}')
    )
        
    files = os.listdir(user_folder)
    proj_files = [f for f in files if f.startswith(fname_base)]
    
    markup.add(types.InlineKeyboardButton('📦 Download Project as ZIP', callback_data=f'admin_zipproj_{uid}_{fname_base}'))
    
    for p_fname in proj_files:
        if os.path.isfile(os.path.join(user_folder, p_fname)):
            markup.add(types.InlineKeyboardButton(f"📄 {p_fname}", callback_data=f"admin_dl_{uid}_{p_fname}"))
            
    markup.add(types.InlineKeyboardButton('🔙 Back to Scripts', callback_data=f'admin_spy_{uid}'))
    bot.edit_message_text(f"🕵️ **Admin Control for:** `{fname}`\nOwner: `{uid}`\nStatus: {status_icon}\n\nProject Files:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

def admin_dl_file_callback(call):
    parts = call.data.split('_', 3)
    if len(parts) < 4: return
    uid, fname = parts[2], parts[3]
    file_path = os.path.join(get_user_folder(uid), fname)
    if os.path.exists(file_path):
        bot.answer_callback_query(call.id, f"Sending {fname}...")
        try:
            with open(file_path, 'rb') as f:
                bot.send_document(call.message.chat.id, f, caption=f"File: {fname} from User {uid}")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"Error sending file: {e}")
    else:
        bot.answer_callback_query(call.id, "File not found.", show_alert=True)

def admin_zip_folder_callback(call):
    uid = call.data.split('_')[2]
    user_folder = get_user_folder(uid)
    if not os.path.exists(user_folder):
        bot.answer_callback_query(call.id, "Folder not found.", show_alert=True)
        return
    
    bot.answer_callback_query(call.id, "Zipping folder...")
    zip_path = os.path.join(UPLOAD_BOTS_DIR, f"user_{uid}_backup.zip")
    try:
        import shutil
        shutil.make_archive(zip_path.replace('.zip', ''), 'zip', user_folder)
        with open(zip_path, 'rb') as f:
            bot.send_document(call.message.chat.id, f, caption=f"📦 Full Backup for User {uid}")
        os.remove(zip_path)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Error zipping: {e}")

def admin_zipproj_callback(call):
    parts = call.data.split('_', 3)
    uid = parts[2]
    fname_base = parts[3]
    user_folder = get_user_folder(uid)
    
    if not os.path.exists(user_folder):
        bot.answer_callback_query(call.id, "Folder not found.", show_alert=True)
        return
        
    bot.answer_callback_query(call.id, "Zipping project files...")
    zip_path = os.path.join(UPLOAD_BOTS_DIR, f"proj_{uid}_{fname_base}.zip")
    
    try:
        files = os.listdir(user_folder)
        proj_files = [f for f in files if f.startswith(fname_base)]
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for fname in proj_files:
                file_path = os.path.join(user_folder, fname)
                if os.path.isfile(file_path):
                    zipf.write(file_path, arcname=fname)
                    
        with open(zip_path, 'rb') as f:
            bot.send_document(call.message.chat.id, f, caption=f"📦 Project Backup: `{fname_base}`\nUser: {uid}", parse_mode='Markdown')
        os.remove(zip_path)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Error zipping project: {e}")

def auto_telegram_backup_thread():
    while True:
        time.sleep(600) # 10 minutes
        try:
            logger.info("Starting auto Telegram backup via Backup Bot...")
            zip_path = os.path.join(BASE_DIR, f"backup_{int(time.time())}.zip")
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                if os.path.exists(IROTECH_DIR):
                    for root, _, files in os.walk(IROTECH_DIR):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, BASE_DIR)
                            zipf.write(file_path, arcname=arcname)
                        
            active_count = len(active_users)
            caption = f"💾 **Auto Backup via Backup Bot!**\n\n🕒 **Time:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n👥 **Active Users:** `{active_count}`\n\n_Contains all user scripts and DB._"
            
            with open(zip_path, 'rb') as f:
                backup_bot.send_document(OWNER_ID, f, caption=caption, parse_mode='Markdown')
                
            os.remove(zip_path)
            logger.info("Auto Telegram backup sent via backup_bot.")
        except Exception as e:
            logger.error(f"Error in auto_telegram_backup_thread: {e}")

def auto_resume_scripts():
    logger.info("Auto-resuming previously running scripts from database...")
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT script_key FROM running_scripts')
        rows = c.fetchall()
        conn.close()
        
    for row in rows:
        script_key = row[0]
        try:
            user_id_str, file_name = script_key.split('_', 1)
            user_id = int(user_id_str)
            user_folder = get_user_folder(user_id)
            file_path = os.path.join(user_folder, file_name)
            
            if not os.path.exists(file_path):
                logger.warning(f"Cannot auto-resume {script_key}: file not found.")
                remove_pid_from_db(script_key)
                continue
                
            logger.info(f"Auto-resuming: {script_key}")
            # Mock a message object so the reply doesn't fail, we'll just log
            class MockChat: id = OWNER_ID
            class MockMessage: chat = MockChat(); from_user = MockChat()
            mock_message = MockMessage()
            
            if file_name.endswith('.py'):
                threading.Thread(target=run_script, args=(file_path, user_id, user_folder, file_name, mock_message)).start()
            elif file_name.endswith('.js'):
                threading.Thread(target=run_js_script, args=(file_path, user_id, user_folder, file_name, mock_message)).start()
        except Exception as e:
            logger.error(f"Failed to auto-resume {script_key}: {e}")

# --- Main ---
if __name__ == "__main__":
    keep_alive()
    init_db()
    load_data()
    
    # Auto-resume scripts
    auto_resume_scripts()
    
    # Start background threads
    threading.Thread(target=auto_telegram_backup_thread, daemon=True).start()
    
    print("🤖 Bot started. Polling...")
    while True:
        try:
            bot.infinity_polling()
        except Exception as e:
            logger.error(f"Bot polling error: {e}", exc_info=True)
            time.sleep(5)
