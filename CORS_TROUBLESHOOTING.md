# CORS Troubleshooting Guide

## Issue: OPTIONS requests returning 400 Bad Request

If you're seeing repeated `OPTIONS /api/gallery-images HTTP/1.1 400 Bad Request` errors, this is likely a CORS preflight issue.

## Common Causes

### 1. Frontend served from `file://` protocol
**Problem**: Opening HTML files directly in the browser (`file:///path/to/file.html`) doesn't work with CORS.

**Solution**: Serve your frontend from an HTTP server:

#### Option A: VS Code Live Server
1. Install "Live Server" extension in VS Code
2. Right-click on `frontend/index.html`
3. Select "Open with Live Server"
4. Frontend will be served at `http://127.0.0.1:5500` (or similar)

#### Option B: Python HTTP Server
```bash
cd frontend
python -m http.server 5500
# Or for Python 3:
python3 -m http.server 5500
```
Then open: `http://localhost:5500`

#### Option C: Node.js http-server
```bash
npx http-server frontend -p 5500
```

### 2. Origin not in allowed list
**Problem**: The frontend origin isn't in the `CORS_ORIGINS` list.

**Solution**: Check your frontend's origin and add it to `backend/app/config.py`:
```python
CORS_ORIGINS: List[str] = [
    "http://localhost:5500",  # Add your frontend port here
    "http://127.0.0.1:5500",
    # ... other origins
]
```

### 3. Missing or invalid Origin header
**Problem**: Browser isn't sending Origin header correctly.

**Solution**: Check browser console for CORS errors and verify the frontend is making requests correctly.

## Testing CORS

### Test with curl:
```bash
# Test OPTIONS preflight
curl -X OPTIONS http://127.0.0.1:8000/api/gallery-images \
  -H "Origin: http://localhost:5500" \
  -H "Access-Control-Request-Method: GET" \
  -v

# Should return 200 OK with CORS headers
```

### Test actual request:
```bash
curl -X GET http://127.0.0.1:8000/api/gallery-images \
  -H "Origin: http://localhost:5500" \
  -v
```

## Current CORS Configuration

The backend is configured to allow:
- `http://localhost:3000`
- `http://localhost:5500`
- `http://localhost:8000`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5500`
- `http://127.0.0.1:8000`
- `http://localhost`
- `http://127.0.0.1`
- `https://*.github.io` (for production)

## Debugging Steps

1. **Check frontend origin**: Open browser DevTools → Network tab → See what Origin header is sent
2. **Check backend logs**: Look for CORS-related log messages
3. **Verify frontend is served from HTTP**: Not `file://` protocol
4. **Test with Postman/curl**: Bypass browser CORS to test if API works

## Quick Fix for Development

If you need to allow all origins during development (NOT recommended for production):

```python
# In backend/app/main.py, temporarily change:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (development only!)
    # ... rest of config
)
```

**Remember**: Never use `allow_origins=["*"]` in production!

