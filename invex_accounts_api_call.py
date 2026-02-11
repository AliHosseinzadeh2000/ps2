import binascii
import json
import requests
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.serialization import load_der_private_key
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes


def sign_data(private_key_hex, data_dict):
    """
    Sign the input data using RSA private key
    
    Args:
        private_key_hex: Your secret key in hex format
        data_dict: Dictionary containing the data to sign (including expire_at)
    
    Returns:
        Signature as hex string
    """
    # Convert data dict to JSON string (default formatting with spaces)
    message = json.dumps(data_dict)
    
    print(f"Data being signed: {message}")
    
    # Convert hex private key to bytes
    byte_private_key = binascii.unhexlify(private_key_hex)
    
    # Load the RSA private key
    rsa_private_key = load_der_private_key(byte_private_key, password=None)
    
    # Sign the message
    signature = rsa_private_key.sign(
        message.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    return signature.hex()


def get_account_balance(api_key, private_key_hex, currency="USDT"):
    """
    Get account balance for a specific currency
    
    Args:
        api_key: Your API key (public key)
        private_key_hex: Your secret key in hex format
        currency: The currency you want to check (default: USDT)
    
    Returns:
        Response from the API
    """
    # Set up the base URL
    base_url = "https://api.invex.ir/trading/v1/accounts"
    
    # Create expire_at timestamp (30 minutes from now)
    expire_at = (datetime.now() + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    
    # Prepare data to sign
    data_to_sign = {
        "currency": currency,
        "expire_at": expire_at
    }
    
    # Sign the data
    signature = sign_data(private_key_hex, data_to_sign)
    
    # Set up headers
    headers = {
        "X-API-Key-Invex": api_key
    }
    
    # Set up query parameters
    params = {
        "currency": currency,
        "expire_at": expire_at,
        "signature": signature
    }
    
    # Make the request
    try:
        response = requests.get(base_url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return None


if __name__ == "__main__":
    # TODO: Replace these with your actual credentials
    API_KEY = "your_api_key_here"
    PRIVATE_KEY_HEX = "your_private_key_hex_here"
    
    # Currency to check (e.g., "USDT", "BTC", "IRR", etc.)
    CURRENCY = "USDT"
    
    print(f"Fetching account balance for {CURRENCY}...")
    result = get_account_balance(API_KEY, PRIVATE_KEY_HEX, CURRENCY)
    
    if result:
        print("\nAccount Information:")
        print(json.dumps(result, indent=2))
        print(f"\nCurrency: {result.get('currency')}")
        print(f"Available: {result.get('available')}")
        print(f"Blocked: {result.get('blocked')}")
        print(f"Total: {result.get('total')}")
    else:
        print("Failed to retrieve account information")
