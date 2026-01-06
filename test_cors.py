"""
Test script to diagnose CORS issues.
Run this to test OPTIONS requests and see what's happening.

Usage:
    uv run python test_cors.py
"""
import requests
import json

API_BASE_URL = "http://127.0.0.1:8000"

def test_options_request():
    """Test OPTIONS preflight request."""
    print("=" * 70)
    print("Testing OPTIONS Preflight Request")
    print("=" * 70)
    print()
    
    url = f"{API_BASE_URL}/api/gallery-images"
    
    # Test with different origins
    test_origins = [
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:3000",
        "file://",  # This won't work but let's see the error
        None,  # No origin header
    ]
    
    for origin in test_origins:
        print(f"Testing with origin: {origin}")
        print("-" * 70)
        
        headers = {
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type",
        }
        
        if origin:
            headers["Origin"] = origin
        
        try:
            response = requests.options(url, headers=headers, timeout=5)
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers:")
            for key, value in response.headers.items():
                if key.lower().startswith("access-control") or key.lower() == "content-type":
                    print(f"  {key}: {value}")
            
            if response.status_code != 200:
                print(f"Response Body: {response.text[:200]}")
            
            print()
            
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {str(e)}")
            print()
    
    print("=" * 70)
    print("Testing GET Request")
    print("=" * 70)
    print()
    
    # Test actual GET request
    try:
        response = requests.get(url, headers={"Origin": "http://localhost:5500"})
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Success! Retrieved {len(data)} gallery images")
        else:
            print(f"Error: {response.text[:200]}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {str(e)}")

if __name__ == "__main__":
    test_options_request()

