"""
Quick script to verify DATABASE_URL format and components.
Run this to check if your connection string is correctly formatted.

Usage:
    uv run python verify_db_url.py
"""
import os
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

print("=" * 70)
print("DATABASE_URL Verification Tool")
print("=" * 70)
print()

if not DATABASE_URL:
    print("[ERROR] DATABASE_URL is not set in .env file")
    print()
    print("Please add DATABASE_URL to your .env file:")
    print("  DATABASE_URL=postgresql+asyncpg://postgres:password@host:5432/postgres")
    exit(1)

print(f"[OK] DATABASE_URL is set")
print()

# Parse the URL
try:
    parsed = urlparse(DATABASE_URL)
except Exception as e:
    print(f"[ERROR] Failed to parse DATABASE_URL: {str(e)}")
    exit(1)

# Check components
print("Connection String Components:")
print("-" * 70)

# Scheme
scheme = parsed.scheme
if scheme == "postgresql+asyncpg":
    print(f"[OK] Scheme: {scheme} (correct for async operations)")
elif scheme == "postgresql":
    print(f"[WARN] Scheme: {scheme} (should be 'postgresql+asyncpg' for async)")
    print("       Update to: postgresql+asyncpg://...")
else:
    print(f"[ERROR] Scheme: {scheme} (invalid)")
    print("       Expected: postgresql+asyncpg://")

# Username
username = parsed.username or ""
if username:
    print(f"[OK] Username: {username}")
else:
    print(f"[ERROR] Username: not found")

# Password
password = parsed.password or ""
if password:
    # Mask password for display
    masked_password = "*" * min(len(password), 8) + "..." if len(password) > 8 else "*" * len(password)
    print(f"[OK] Password: {masked_password} (length: {len(password)})")
    
    # Check for special characters that might need encoding
    special_chars = ['@', '#', '$', '%', '&', '+', '=', '?', '/', ':']
    found_special = [c for c in password if c in special_chars]
    if found_special:
        print(f"[WARN] Password contains special characters: {', '.join(found_special)}")
        print("       These may need URL encoding if connection fails")
else:
    print(f"[ERROR] Password: not found")

# Hostname
hostname = parsed.hostname or ""
if hostname:
    print(f"[OK] Hostname: {hostname}")
    
    # Check hostname format
    if hostname.endswith(".supabase.co"):
        print(f"       Format: Direct Supabase connection")
    elif "pooler.supabase.com" in hostname:
        print(f"       Format: Supabase connection pooler (recommended)")
    else:
        print(f"       Format: Custom hostname")
else:
    print(f"[ERROR] Hostname: not found")

# Port
port = parsed.port or 5432
if port == 5432:
    print(f"[OK] Port: {port} (standard PostgreSQL port)")
elif port == 6543:
    print(f"[OK] Port: {port} (Supabase connection pooler port)")
else:
    print(f"[INFO] Port: {port} (custom port)")

# Database
database = parsed.path.lstrip("/") if parsed.path else "postgres"
if database:
    print(f"[OK] Database: {database}")
else:
    print(f"[WARN] Database: not specified (defaults to 'postgres')")

# Query parameters
if parsed.query:
    print(f"[INFO] Query parameters: {parsed.query}")

print()
print("=" * 70)
print("Format Check Summary")
print("=" * 70)

issues = []
if scheme != "postgresql+asyncpg":
    issues.append("Scheme should be 'postgresql+asyncpg' for async operations")
if not username:
    issues.append("Username is missing")
if not password:
    issues.append("Password is missing")
if not hostname:
    issues.append("Hostname is missing")

if issues:
    print("[WARN] Found potential issues:")
    for issue in issues:
        print(f"  - {issue}")
    print()
    print("Recommended format:")
    print("  postgresql+asyncpg://postgres:PASSWORD@HOSTNAME:5432/postgres")
else:
    print("[OK] Connection string format looks correct!")
    print()
    print("If you're still experiencing connection issues:")
    print("  1. Verify your Supabase project is active")
    print("  2. Check your database password is correct")
    print("  3. Try using the Connection Pooler URL from Supabase dashboard")
    print("  4. See SUPABASE_CONNECTION_GUIDE.md for detailed instructions")

print()
print("=" * 70)


