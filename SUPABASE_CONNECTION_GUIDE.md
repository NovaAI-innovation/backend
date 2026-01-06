# Supabase Database Connection Guide

## Current DATABASE_URL Format

Your current connection string format is correct:
```
postgresql+asyncpg://postgres:PASSWORD@db.PROJECT_ID.supabase.co:5432/postgres
```

## How to Get Your Correct Connection String from Supabase

### Step 1: Access Supabase Dashboard
1. Go to https://supabase.com/dashboard
2. Log in to your account
3. Select your project (project ID: `jfeklugiwfuapxkkpeyo`)

### Step 2: Get Database Connection String
1. In your Supabase project dashboard, go to **Settings** → **Database**
2. Scroll down to **Connection string** section
3. Select **URI** tab (not Session mode)
4. Copy the connection string

### Step 3: Convert to Async Format
The Supabase connection string will look like:
```
postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

**For asyncpg (SQLAlchemy async), you need to change it to:**
```
postgresql+asyncpg://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

### Step 4: Verify Connection String Components

Your connection string should have:
- ✅ **Scheme**: `postgresql+asyncpg://` (for async operations)
- ✅ **Username**: `postgres` or `postgres.[PROJECT-REF]`
- ✅ **Password**: Your database password
- ✅ **Hostname**: `db.PROJECT_ID.supabase.co` (direct) or `aws-0-REGION.pooler.supabase.com` (pooler)
- ✅ **Port**: `5432` (direct) or `6543` (pooler) or `5432` (transaction mode pooler)
- ✅ **Database**: `postgres`

## Connection String Options

### Option 1: Direct Connection (Current)
```
postgresql+asyncpg://postgres:PASSWORD@db.PROJECT_ID.supabase.co:5432/postgres
```
- Direct connection to database
- May have IPv6-only resolution issues on Windows

### Option 2: Connection Pooler (Recommended)
```
postgresql+asyncpg://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres
```
- Uses Supabase connection pooler
- Better for serverless/server applications
- More reliable DNS resolution

### Option 3: Transaction Mode Pooler
```
postgresql+asyncpg://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?pgbouncer=true
```
- Uses transaction mode pooling
- Port 5432 with pgbouncer parameter

## Troubleshooting DNS Issues

If you're experiencing DNS resolution errors (`getaddrinfo failed`):

1. **Check if your Supabase project is active**
   - Go to Supabase dashboard
   - Verify project status is "Active"

2. **Try using Connection Pooler URL**
   - Connection pooler URLs often have better DNS resolution
   - Get it from Settings → Database → Connection string → Transaction mode

3. **Verify your password**
   - Make sure the password in DATABASE_URL matches your Supabase database password
   - Special characters in passwords may need URL encoding

4. **Test with different DNS servers**
   ```powershell
   nslookup db.jfeklugiwfuapxkkpeyo.supabase.co 8.8.8.8
   ```

5. **Check IPv6 support**
   - Your system may need IPv6 enabled
   - Connection pooler URLs often work better with IPv4

## URL Encoding Special Characters

If your password contains special characters, you may need to URL-encode them:

| Character | Encoded |
|-----------|---------|
| `@` | `%40` |
| `#` | `%23` |
| `$` | `%24` |
| `%` | `%25` |
| `&` | `%26` |
| `+` | `%2B` |
| `=` | `%3D` |
| `?` | `%3F` |
| `/` | `%2F` |
| `:` | `%3A` |

## Testing Your Connection

After updating your `.env` file, test the connection:

```bash
cd backend
uv run python test_db_connection.py
```

Or restart your API server and check the logs:
```bash
cd backend
uv run uvicorn app.main:app --reload
```

## Current Connection String Analysis

Based on your current DATABASE_URL:
```
postgresql+asyncpg://postgres:G72kNaiqTJLCgsEZ@db.jfeklugiwfuapxkkpeyo.supabase.co:5432/postgres
```

✅ **Format**: Correct
✅ **Scheme**: `postgresql+asyncpg` (correct for async)
✅ **Hostname**: `db.jfeklugiwfuapxkkpeyo.supabase.co` (correct format)
✅ **Port**: `5432` (standard PostgreSQL port)
✅ **Database**: `postgres` (default)

⚠️ **Issue**: DNS resolution failing - hostname resolves to IPv6 only, which may cause issues on Windows

**Recommendation**: Try using the Connection Pooler URL from Supabase dashboard instead.


