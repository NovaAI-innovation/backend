# Debugging CORS 400 Errors

## Enhanced Logging Added

I've added detailed logging to help identify the exact cause of the 400 error on OPTIONS requests. The logs will now show:

1. **All request headers** for OPTIONS requests
2. **Origin header** value
3. **Access-Control-Request-Method** header
4. **Access-Control-Request-Headers** header
5. **CORS response headers** sent back
6. **Any validation errors** with full details

## How to Debug

### Step 1: Restart Your Server

Restart your FastAPI server to pick up the new logging:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

### Step 2: Make a Request from Your Frontend

When you make a request from your frontend, watch the server logs. You should now see detailed information like:

```
OPTIONS preflight request to /api/gallery-images
  Origin: http://localhost:5500
  Access-Control-Request-Method: GET
  Access-Control-Request-Headers: Content-Type
  All headers: {...}
```

### Step 3: Check for Validation Errors

If there's a validation error, you'll see:

```
Validation error on OPTIONS /api/gallery-images:
  Origin: http://localhost:5500
  Headers: {...}
  Errors: [detailed error list]
```

### Step 4: Test with curl

Test the OPTIONS request directly to see what's happening:

```bash
# Test OPTIONS preflight
curl -X OPTIONS http://127.0.0.1:8000/api/gallery-images \
  -H "Origin: http://localhost:5500" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -v

# Check the response - should be 200 OK, not 400
```

### Step 5: Check Browser Console

Open your browser's Developer Tools (F12) and check:
1. **Console tab** - Look for CORS errors
2. **Network tab** - Click on the failed OPTIONS request
3. **Headers tab** - See what headers were sent
4. **Response tab** - See the error message

## Common Causes of 400 on OPTIONS

### 1. Missing Required Headers
**Symptom**: Validation error about missing headers
**Fix**: Ensure browser sends proper preflight headers

### 2. Invalid Origin
**Symptom**: Origin not in allowed list
**Fix**: Add origin to `CORS_ORIGINS` in `app/config.py`

### 3. File Protocol
**Symptom**: Origin is `null` or missing
**Fix**: Serve frontend from HTTP server, not `file://`

### 4. Route Handler Issue
**Symptom**: Route doesn't exist or has validation requirements
**Fix**: Check if route handler exists and accepts OPTIONS

## What to Look For in Logs

When you see the 400 error, check the logs for:

1. **What origin is being sent?**
   - If it's `null` or missing → Frontend is using `file://` protocol
   - If it's not in the allowed list → Add it to `CORS_ORIGINS`

2. **What validation errors are shown?**
   - These will tell you exactly what's wrong with the request

3. **What headers are present?**
   - Missing `Access-Control-Request-Method`?
   - Invalid header values?

4. **Is the explicit OPTIONS handler being called?**
   - If you see "Explicit OPTIONS handler called" → Handler is working
   - If not → Request might be failing before reaching the handler

## Quick Test Script

Run the test script to diagnose:

```bash
cd backend
uv run python test_cors.py
```

This will test various origins and show you what works and what doesn't.

## Next Steps

1. **Restart your server** with the new logging
2. **Make a request** from your frontend
3. **Check the server logs** - they'll tell you exactly what's wrong
4. **Share the log output** if you need help interpreting it

The enhanced logging will pinpoint the exact cause of the 400 error!

