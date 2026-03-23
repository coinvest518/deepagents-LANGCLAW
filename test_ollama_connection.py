#!/usr/bin/env python3
"""
Test script to diagnose Ollama connection issues.
"""

import requests
import os
import sys
import time

def test_ollama_connection():
    """Test Ollama connection with detailed diagnostics."""

    # Get Ollama URL from environment or use default
    ollama_url = os.environ.get('OLLAMA_BASE_URL', 'http://13.222.51.51:11434')

    print(f"Testing Ollama connection to: {ollama_url}")
    print("=" * 50)

    # Test 1: Basic connectivity
    print("Test 1: Basic connectivity check...")
    try:
        start_time = time.time()
        response = requests.get(f'{ollama_url}/api/tags', timeout=15)
        end_time = time.time()

        print(f"[OK] Connection successful!")
        print(f"  Status code: {response.status_code}")
        print(f"  Response time: {end_time - start_time:.2f}s")

        if response.status_code == 200:
            try:
                data = response.json()
                models = data.get("models", [])
                print(f"  Available models: {len(models)}")
                for model in models:
                    print(f"    - {model['name']}")
            except Exception as e:
                print(f"  Could not parse models: {e}")
                print(f"  Raw response: {response.text[:200]}...")
        else:
            print(f"  Error response: {response.text}")

    except requests.exceptions.ConnectionError as e:
        print(f"[FAIL] Connection failed: {e}")
        print("  This suggests the server is not accessible from this environment")
        return False
    except requests.exceptions.Timeout:
        print("[FAIL] Connection timed out - server might be slow or unreachable")
        return False
    except requests.exceptions.RequestException as e:
        print(f"[FAIL] Request failed: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")
        return False

    # Test 2: Test with trailing slash
    print("\nTest 2: Testing with trailing slash...")
    try:
        response = requests.get(f'{ollama_url.rstrip("/")}/api/tags', timeout=10)
        print(f"[OK] Trailing slash version works: {response.status_code}")
    except Exception as e:
        print(f"[FAIL] Trailing slash version failed: {e}")

    # Test 3: Test model availability
    print("\nTest 3: Testing model availability...")
    model_name = os.environ.get('OLLAMA_MODEL', 'llama3.2:1b')
    print(f"Checking if model '{model_name}' is available...")

    try:
        response = requests.get(f'{ollama_url}/api/tags', timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = [m['name'] for m in data.get('models', [])]
            if model_name in models:
                print(f"[OK] Model '{model_name}' is available")
            else:
                print(f"[FAIL] Model '{model_name}' not found")
                print(f"  Available models: {models}")
        else:
            print(f"[FAIL] Could not check models: {response.status_code}")
    except Exception as e:
        print(f"[FAIL] Model check failed: {e}")

    # Test 4: Test actual chat endpoint
    print("\nTest 4: Testing chat endpoint...")
    try:
        chat_data = {
            "model": model_name,
            "messages": [{"role": "user", "content": "Hello, are you working?"}],
            "stream": False
        }

        response = requests.post(f'{ollama_url}/api/chat', json=chat_data, timeout=30)
        print(f"[OK] Chat endpoint test: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                print(f"[OK] Chat response received")
                if 'message' in result:
                    print(f"  Response: {result['message']['content'][:100]}...")
            except Exception as e:
                print(f"  Could not parse chat response: {e}")
        else:
            print(f"  Chat error: {response.text}")

    except Exception as e:
        print(f"[FAIL] Chat endpoint test failed: {e}")

    print("\n" + "=" * 50)
    print("Connection test completed!")
    return True

if __name__ == "__main__":
    test_ollama_connection()
