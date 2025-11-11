#!/usr/bin/env python3
"""
Secret Key Generator for JWT Authentication
Run this script to generate a secure SECRET_KEY for your .env file
"""

import secrets
import string

def generate_secret_key(length=64):
    """Generate a cryptographically secure secret key"""
    # Use letters, digits, and safe symbols
    alphabet = string.ascii_letters + string.digits + '-_'
    secret_key = ''.join(secrets.choice(alphabet) for _ in range(length))
    return secret_key

def generate_multiple_keys(count=3, length=64):
    """Generate multiple secret keys to choose from"""
    print("🔐 Secure SECRET_KEY Generator")
    print("=" * 50)
    print(f"Generated {count} secure keys ({length} characters each):")
    print()
    
    for i in range(count):
        key = generate_secret_key(length)
        print(f"Option {i+1}:")
        print(f"SECRET_KEY={key}")
        print()
    
    print("Instructions:")
    print("1. Copy one of the keys above")
    print("2. Add it to your .env file in the chatbot_backend directory")
    print("3. Make sure to keep this key secret and secure!")
    print("4. Never commit the .env file to version control")

if __name__ == "__main__":
    generate_multiple_keys()
