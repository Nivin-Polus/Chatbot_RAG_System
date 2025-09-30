"""
Test script for user management fixes
Run this after starting the backend server to verify all fixes work correctly
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def get_auth_token(username, password):
    """Login and get JWT token"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"Login failed: {response.status_code} - {response.text}")
        return None

def test_create_user_with_collection(token):
    """Test creating a user with collection assignment"""
    print("\n=== Test 1: Create User with Collection ===")
    
    # First, get list of collections
    headers = {"Authorization": f"Bearer {token}"}
    collections_response = requests.get(f"{BASE_URL}/collections/", headers=headers)
    
    if collections_response.status_code != 200:
        print(f"Failed to get collections: {collections_response.text}")
        return False
    
    collections = collections_response.json()
    if not collections:
        print("No collections found. Create a collection first.")
        return False
    
    collection_id = collections[0]["collection_id"]
    print(f"Using collection: {collections[0]['name']} ({collection_id})")
    
    # Create user
    user_data = {
        "username": "testuser_" + str(hash(str(collections[0]['name'])))[:6],
        "password": "password123",
        "email": "testuser@example.com",
        "full_name": "Test User",
        "role": "user",
        "collection_id": collection_id
    }
    
    response = requests.post(
        f"{BASE_URL}/users/",
        json=user_data,
        headers=headers
    )
    
    if response.status_code == 200:
        user = response.json()
        print(f"✓ User created successfully: {user['username']}")
        print(f"  User ID: {user['user_id']}")
        print(f"  Collection IDs: {user.get('collection_ids', [])}")
        
        # Verify user can login
        login_token = get_auth_token(user_data['username'], user_data['password'])
        if login_token:
            print(f"✓ User can login successfully")
            return True
        else:
            print(f"✗ User cannot login")
            return False
    else:
        print(f"✗ Failed to create user: {response.status_code}")
        print(f"  Error: {response.text}")
        return False

def test_create_super_admin(token):
    """Test creating a super admin without collection"""
    print("\n=== Test 2: Create Super Admin (No Collection) ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    user_data = {
        "username": "superadmin_test",
        "password": "super123",
        "email": "superadmin@example.com",
        "full_name": "Super Admin Test",
        "role": "super_admin",
        "collection_id": ""  # Empty string should be handled
    }
    
    response = requests.post(
        f"{BASE_URL}/users/",
        json=user_data,
        headers=headers
    )
    
    if response.status_code == 200:
        user = response.json()
        print(f"✓ Super admin created successfully: {user['username']}")
        print(f"  User ID: {user['user_id']}")
        print(f"  Collection IDs: {user.get('collection_ids', [])}")
        return True
    else:
        print(f"✗ Failed to create super admin: {response.status_code}")
        print(f"  Error: {response.text}")
        return False

def test_list_users(token):
    """Test listing users and verify collection_ids are present"""
    print("\n=== Test 3: List Users ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/users/", headers=headers)
    
    if response.status_code == 200:
        users = response.json()
        print(f"✓ Found {len(users)} users")
        
        for user in users[:5]:  # Show first 5 users
            print(f"  - {user['username']} ({user['role']})")
            print(f"    Collections: {user.get('collection_ids', [])}")
        
        # Verify all users have collection_ids field
        missing_collection_ids = [u['username'] for u in users if 'collection_ids' not in u]
        if missing_collection_ids:
            print(f"✗ Users missing collection_ids: {missing_collection_ids}")
            return False
        else:
            print(f"✓ All users have collection_ids field")
            return True
    else:
        print(f"✗ Failed to list users: {response.status_code}")
        print(f"  Error: {response.text}")
        return False

def test_delete_user(token):
    """Test deleting a user (including super admin)"""
    print("\n=== Test 4: Delete User ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get list of users
    response = requests.get(f"{BASE_URL}/users/", headers=headers)
    if response.status_code != 200:
        print(f"✗ Failed to get users: {response.text}")
        return False
    
    users = response.json()
    
    # Find a test user to delete (not the current user)
    test_user = None
    for user in users:
        if user['username'].startswith('testuser_') or user['username'] == 'superadmin_test':
            test_user = user
            break
    
    if not test_user:
        print("No test user found to delete. Skipping test.")
        return True
    
    print(f"Attempting to delete user: {test_user['username']} ({test_user['role']})")
    
    response = requests.delete(
        f"{BASE_URL}/users/{test_user['user_id']}",
        headers=headers
    )
    
    if response.status_code == 204:
        print(f"✓ User deleted successfully")
        
        # Verify user is deactivated
        response = requests.get(f"{BASE_URL}/users/", headers=headers)
        if response.status_code == 200:
            users = response.json()
            deleted_user = next((u for u in users if u['user_id'] == test_user['user_id']), None)
            if deleted_user:
                print(f"✗ User still appears in active list")
                return False
            else:
                print(f"✓ User removed from active list")
                return True
    else:
        print(f"✗ Failed to delete user: {response.status_code}")
        print(f"  Error: {response.text}")
        return False

def main():
    print("=" * 60)
    print("User Management Test Suite")
    print("=" * 60)
    
    # Login as super admin
    print("\nLogging in as super admin...")
    token = get_auth_token("superadmin", "superadmin123")
    
    if not token:
        print("Failed to login. Please ensure:")
        print("1. Backend server is running")
        print("2. Super admin account exists (superadmin/superadmin123)")
        return
    
    print("✓ Login successful")
    
    # Run tests
    results = []
    results.append(("Create User with Collection", test_create_user_with_collection(token)))
    results.append(("Create Super Admin", test_create_super_admin(token)))
    results.append(("List Users", test_list_users(token)))
    results.append(("Delete User", test_delete_user(token)))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")

if __name__ == "__main__":
    main()
