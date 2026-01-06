"""
Database connection diagnostic script.
Run this to test and diagnose database connection issues.

Usage:
    uv run python test_db_connection.py
"""
import asyncio
import socket
from urllib.parse import urlparse
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")


def test_dns_resolution(hostname: str) -> tuple[bool, str]:
    """Test DNS resolution for a hostname."""
    try:
        # Try IPv4
        try:
            ipv4 = socket.gethostbyname(hostname)
            return True, f"IPv4: {ipv4}"
        except socket.gaierror:
            pass
        
        # Try IPv6
        try:
            addrinfo = socket.getaddrinfo(hostname, None, socket.AF_INET6)
            ipv6 = addrinfo[0][4][0]
            return True, f"IPv6: {ipv6} (IPv4 not available)"
        except (socket.gaierror, IndexError):
            return False, "DNS resolution failed - cannot resolve hostname"
    except Exception as e:
        return False, f"DNS resolution error: {str(e)}"


async def test_database_connection():
    """Test database connection with detailed diagnostics."""
    print("=" * 60)
    print("Database Connection Diagnostic Tool")
    print("=" * 60)
    print()
    
    if not DATABASE_URL:
        print("[ERROR] DATABASE_URL environment variable is not set")
        print()
        print("Please set DATABASE_URL in your .env file:")
        print("  DATABASE_URL=postgresql+asyncpg://postgres:password@host:5432/postgres")
        return
    
    print("[OK] DATABASE_URL is set")
    print()
    
    # Parse URL
    try:
        parsed = urlparse(DATABASE_URL)
        print(f"URL Components:")
        print(f"  Scheme: {parsed.scheme}")
        print(f"  Hostname: {parsed.hostname}")
        print(f"  Port: {parsed.port or 5432}")
        print(f"  Database: {parsed.path or '/postgres'}")
        print(f"  Username: {parsed.username or 'not set'}")
        print()
    except Exception as e:
        print(f"❌ ERROR: Failed to parse DATABASE_URL: {str(e)}")
        return
    
    # Test DNS resolution
    if parsed.hostname:
        print("Testing DNS resolution...")
        dns_ok, dns_msg = test_dns_resolution(parsed.hostname)
        if dns_ok:
            print(f"[OK] {dns_msg}")
        else:
            print(f"[ERROR] {dns_msg}")
            print()
            print("Troubleshooting:")
            print("  1. Check your internet connection")
            print("  2. Verify the hostname is correct")
            print("  3. Check if your firewall is blocking DNS queries")
            print("  4. Try using a different DNS server (e.g., 8.8.8.8)")
        print()
    
    # Test actual database connection
    print("Testing database connection...")
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        
        engine = create_async_engine(DATABASE_URL)
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1 as test"))
            test_value = result.scalar()
            print(f"[OK] Database connection successful! Test query returned: {test_value}")
            print()
            print("Your database connection is working correctly!")
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"[ERROR] Database connection failed ({error_type})")
        print(f"   Error: {error_msg}")
        print()
        print("Common issues and solutions:")
        print()
        
        if "getaddrinfo failed" in error_msg or "11001" in error_msg:
            print("  DNS Resolution Error:")
            print("    - Check your internet connection")
            print("    - Verify the hostname in DATABASE_URL is correct")
            print("    - Try pinging the hostname: ping <hostname>")
            print("    - Check if IPv6 is required (some Supabase instances use IPv6)")
        elif "connection refused" in error_msg.lower():
            print("  Connection Refused:")
            print("    - Verify the port number is correct (usually 5432)")
            print("    - Check if the database server is running")
            print("    - Check firewall settings")
        elif "timeout" in error_msg.lower():
            print("  Connection Timeout:")
            print("    - Check your network connection")
            print("    - Verify firewall is not blocking the connection")
            print("    - Check if VPN is required")
        elif "authentication" in error_msg.lower() or "password" in error_msg.lower():
            print("  Authentication Error:")
            print("    - Verify username and password in DATABASE_URL")
            print("    - Check if password needs URL encoding")
            print("    - Verify database user has required permissions")
        else:
            print("  Unknown Error:")
            print("    - Check the error message above for details")
            print("    - Verify DATABASE_URL format is correct")
            print("    - Ensure asyncpg is installed: uv add asyncpg")
    
    print()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_database_connection())

