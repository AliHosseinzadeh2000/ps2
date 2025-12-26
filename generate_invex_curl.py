#!/usr/bin/env python3
"""Generate exact curl command for Invex API request.

This script generates the exact curl command that the bot uses to call Invex API.
Use this to test the request manually and see the exact error from Invex.
"""

import json
import time
import sys
import os
from datetime import datetime
import binascii
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_der_private_key

def generate_signature(message: str, api_secret: str) -> str:
    """Generate RSA-PSS signature for Invex."""
    try:
        # Convert hex secret key to bytes
        byte_private_key = binascii.unhexlify(api_secret)
        
        # Load RSA private key from DER format
        rsa_private_key = load_der_private_key(byte_private_key, password=None)
        
        # Sign using RSA-PSS with SHA256
        signature = rsa_private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        
        return signature.hex()
    except Exception as e:
        print(f"Error generating signature: {e}", file=sys.stderr)
        raise

def generate_curl_command(
    api_key: str,
    api_secret: str,
    symbol: str = "USDT_IRR",
    side: str = "SELLER",
    order_type: str = "LIMIT",
    quantity: str = "0.00007888",
    price: str = "1270400.0"
):
    """Generate exact curl command for Invex place_order."""
    
    base_url = "https://api.invex.ir/trading/v1"
    endpoint = "/orders"
    full_url = f"{base_url}{endpoint}"
    
    # Create payload (same as bot does)
    expire_at_timestamp = int(time.time()) + 60
    expire_at_iso = datetime.fromtimestamp(expire_at_timestamp).isoformat()
    
    payload = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "quantity": quantity,
    }
    
    if order_type == "LIMIT":
        payload["price"] = price
    
    payload["expire_at"] = expire_at_iso
    
    # Create message for signing (sorted JSON string, WITHOUT signature field)
    message = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    
    # Generate signature
    signature = generate_signature(message, api_secret)
    
    # Add signature to payload
    payload["signature"] = signature
    
    # Headers
    headers = {
        "Content-Type": "application/json",
        "X-API-Key-Invex": api_key,
        "X-API-Sign": signature,
        "X-API-Expire-At": expire_at_iso,
    }
    
    # Generate curl command
    curl_headers = " ".join([f"-H '{k}: {v}'" for k, v in headers.items()])
    curl_data = json.dumps(payload, separators=(",", ":"))
    
    curl_command = f"""curl -X POST '{full_url}' \\
  {curl_headers} \\
  -d '{curl_data}'"""
    
    print("=" * 80)
    print("INVEX API REQUEST DETAILS")
    print("=" * 80)
    print(f"\nURL: {full_url}")
    print(f"\nMethod: POST")
    print(f"\nHeaders:")
    for k, v in headers.items():
        print(f"  {k}: {v}")
    print(f"\nBody (JSON):")
    print(json.dumps(payload, indent=2))
    print(f"\nMessage used for signature (sorted, no spaces):")
    print(message)
    print(f"\nSignature (hex): {signature}")
    print(f"\n" + "=" * 80)
    print("CURL COMMAND:")
    print("=" * 80)
    print(curl_command)
    print("=" * 80)
    print("\nTo test, copy the curl command above and run it in your terminal.")
    print("Make sure your INVEX_API_KEY and INVEX_API_SECRET are correct.")
    print("=" * 80)
    
    return curl_command

if __name__ == "__main__":
    # Get API credentials from environment or command line
    api_key = os.getenv("INVEX_API_KEY")
    api_secret = os.getenv("INVEX_API_SECRET")
    
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    if len(sys.argv) > 2:
        api_secret = sys.argv[2]
    
    if not api_key or not api_secret:
        print("Usage: python3 generate_invex_curl.py [API_KEY] [API_SECRET]")
        print("   OR: set INVEX_API_KEY and INVEX_API_SECRET environment variables")
        print("\nExample:")
        print("  python3 generate_invex_curl.py your_api_key your_hex_encoded_private_key")
        sys.exit(1)
    
    # Default values from the log (matching the exact request from your test)
    generate_curl_command(
        api_key=api_key,
        api_secret=api_secret,
        symbol="USDT_IRR",
        side="SELLER",
        order_type="LIMIT",
        quantity="7.887918981606556e-05",  # From your log
        price="1270400.0"  # From your log
    )
    
    print("\n" + "=" * 80)
    print("IMPORTANT NOTES:")
    print("=" * 80)
    print("1. The signature is generated from the JSON body WITHOUT the signature field")
    print("2. The JSON keys must be sorted alphabetically for signature generation")
    print("3. The signature is then added to BOTH:")
    print("   - The request body (as 'signature' field)")
    print("   - The X-API-Sign header")
    print("4. The expire_at must be in ISO format without timezone (naive datetime)")
    print("5. Make sure your INVEX_API_SECRET is the hex-encoded DER private key")
    print("=" * 80)

