#!/usr/bin/env python3
"""
Create test users for Contract AI System
"""
import requests
import json

BASE_URL = "http://localhost:8000"

# Test users with different roles
TEST_USERS = [
    {
        "email": "demo@example.com",
        "name": "Demo User",
        "password": "DemoPass123!",
        "role": "demo",
        "subscription_tier": "demo"
    },
    {
        "email": "user@example.com",
        "name": "Regular User",
        "password": "UserPass123!",
        "role": "junior_lawyer",
        "subscription_tier": "basic"
    },
    {
        "email": "lawyer@example.com",
        "name": "Lawyer Pro",
        "password": "LawyerPass123!",
        "role": "lawyer",
        "subscription_tier": "pro"
    },
    {
        "email": "senior@example.com",
        "name": "Senior Lawyer",
        "password": "SeniorPass123!",
        "role": "senior_lawyer",
        "subscription_tier": "pro"
    },
    {
        "email": "admin@example.com",
        "name": "System Admin",
        "password": "AdminPass123!",
        "role": "admin",
        "subscription_tier": "enterprise"
    }
]

def create_user(user_data):
    """Create a single user"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/register",
            json=user_data,
            timeout=5
        )
        
        if response.status_code == 201:
            print(f"✅ Created: {user_data['email']} ({user_data['role']})")
            return True
        elif response.status_code == 400 and "already exists" in response.text.lower():
            print(f"ℹ️  Already exists: {user_data['email']}")
            return False
        else:
            print(f"❌ Failed: {user_data['email']} - {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Error: Backend is not running. Start it first with: uvicorn src.main:app --host 0.0.0.0 --port 8000")
        return False
    except Exception as e:
        print(f"❌ Error creating {user_data['email']}: {e}")
        return False

def main():
    print("=" * 60)
    print("🔧 Creating Test Users for Contract AI System")
    print("=" * 60)
    print()
    
    # Check if backend is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        if response.status_code != 200:
            print("❌ Backend is not healthy. Please check the server.")
            return
    except:
        print("❌ Backend is not running!")
        print("   Start it with: cd /Users/andrew/Desktop/Contract-AI-System- && source venv/bin/activate && uvicorn src.main:app --host 0.0.0.0 --port 8000")
        return
    
    print("✅ Backend is running\n")
    
    # Create users
    created = 0
    for user in TEST_USERS:
        if create_user(user):
            created += 1
    
    print()
    print("=" * 60)
    print(f"✅ Created {created} new users")
    print("=" * 60)
    print()
    print("📋 Test Credentials:")
    print()
    for user in TEST_USERS:
        print(f"   {user['role'].upper():15} | {user['email']:25} | {user['password']}")
    print()
    print("🌐 URLs:")
    print(f"   Backend API:  {BASE_URL}/api/docs")
    print(f"   Frontend UI:  http://localhost:3000")
    print()

if __name__ == "__main__":
    main()
