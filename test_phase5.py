#!/usr/bin/env python3
"""
Phase 5 API Testing Script
Test all Phase 5 endpoints locally or on Render
"""

import requests
import json
import os
from datetime import datetime

BASE_URL = os.getenv('API_URL', 'http://localhost:10000')
TEST_TOKEN = os.getenv('TEST_TOKEN', '')

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def log_test(name, status, response=None):
    """Log test result"""
    icon = f"{Colors.GREEN}✓{Colors.END}" if status else f"{Colors.RED}✗{Colors.END}"
    print(f"{icon} {name}")
    if response and not status:
        print(f"  {Colors.RED}Error: {response}{Colors.END}")

def test_health_check():
    """Test health check endpoint"""
    print(f"\n{Colors.BLUE}=== HEALTH CHECK ==={Colors.END}")
    try:
        r = requests.get(f"{BASE_URL}/")
        log_test("Health check", r.status_code == 200, r.text if r.status_code != 200 else None)
    except Exception as e:
        log_test("Health check", False, str(e))

def test_user_endpoints():
    """Test user management endpoints"""
    print(f"\n{Colors.BLUE}=== USER ENDPOINTS ==={Colors.END}")

    if not TEST_TOKEN:
        print(f"{Colors.YELLOW}⚠ Skipping user tests (no TEST_TOKEN set){Colors.END}")
        return

    headers = {'Authorization': f'Bearer {TEST_TOKEN}'}
    test_email = f"test_{datetime.now().timestamp()}@example.com"

    # Test create user (this would need a real Firebase token)
    print(f"{Colors.YELLOW}Note: User creation requires valid Firebase token{Colors.END}")

def test_stripe_endpoints():
    """Test Stripe endpoints"""
    print(f"\n{Colors.BLUE}=== STRIPE ENDPOINTS ==={Colors.END}")

    if not TEST_TOKEN:
        print(f"{Colors.YELLOW}⚠ Skipping Stripe tests (no TEST_TOKEN){Colors.END}")
        return

    headers = {
        'Authorization': f'Bearer {TEST_TOKEN}',
        'Content-Type': 'application/json'
    }

    # Test get current subscription
    try:
        r = requests.get(f"{BASE_URL}/api/v1/subscriptions/current", headers=headers)
        log_test("Get current subscription", r.status_code in [200, 401, 403])
    except Exception as e:
        log_test("Get current subscription", False, str(e))

def test_public_endpoints():
    """Test public endpoints (no auth required)"""
    print(f"\n{Colors.BLUE}=== PUBLIC ENDPOINTS ==={Colors.END}")

    # Test check referral code
    try:
        r = requests.get(f"{BASE_URL}/api/v1/referrals/check-code?code=TESTCODE123")
        log_test("Check referral code", r.status_code in [200, 400])
        if r.status_code == 200:
            print(f"  Response: {json.dumps(r.json(), indent=2)}")
    except Exception as e:
        log_test("Check referral code", False, str(e))

def test_endpoints_exist():
    """Test that all endpoints exist (404 means not found)"""
    print(f"\n{Colors.BLUE}=== ENDPOINT AVAILABILITY ==={Colors.END}")

    endpoints = [
        ('POST', '/api/v1/users'),
        ('GET', '/api/v1/users/test-uid'),
        ('PUT', '/api/v1/users/test-uid'),
        ('GET', '/api/v1/users/test-uid/referral-stats'),
        ('DELETE', '/api/v1/users/test-uid'),
        ('POST', '/api/v1/subscriptions/checkout'),
        ('GET', '/api/v1/subscriptions/current'),
        ('POST', '/api/v1/subscriptions/cancel'),
        ('POST', '/api/v1/groups'),
        ('GET', '/api/v1/groups/test-group'),
        ('POST', '/api/v1/groups/test-group/members'),
        ('DELETE', '/api/v1/groups/test-group/members/test-user'),
        ('POST', '/api/v1/deals/test-deal/gift'),
        ('GET', '/api/v1/gifts/received'),
        ('POST', '/api/v1/referrals/activate'),
        ('GET', '/api/v1/referrals/check-code'),
        ('POST', '/webhooks/stripe'),
    ]

    for method, endpoint in endpoints:
        try:
            if method == 'GET':
                r = requests.get(f"{BASE_URL}{endpoint}", timeout=2)
            elif method == 'POST':
                r = requests.post(f"{BASE_URL}{endpoint}", json={}, timeout=2)
            elif method == 'PUT':
                r = requests.put(f"{BASE_URL}{endpoint}", json={}, timeout=2)
            elif method == 'DELETE':
                r = requests.delete(f"{BASE_URL}{endpoint}", timeout=2)

            # 401/403 means endpoint exists but auth failed (good!)
            # 400 means endpoint exists but bad request (good!)
            # 404 means endpoint doesn't exist (bad!)
            exists = r.status_code != 404
            log_test(f"{method} {endpoint}", exists, f"Status: {r.status_code}")
        except requests.exceptions.ConnectError:
            log_test(f"{method} {endpoint}", False, "Connection refused")
        except Exception as e:
            log_test(f"{method} {endpoint}", False, str(e))

def main():
    """Run all tests"""
    print(f"{Colors.BLUE}{'='*50}")
    print(f"DealHunter Phase 5 - API Test Suite")
    print(f"API URL: {BASE_URL}")
    print(f"{'='*50}{Colors.END}")

    test_health_check()
    test_endpoints_exist()
    test_public_endpoints()
    test_user_endpoints()
    test_stripe_endpoints()

    print(f"\n{Colors.BLUE}{'='*50}")
    print(f"Testing complete!")
    print(f"{'='*50}{Colors.END}\n")

if __name__ == '__main__':
    main()
