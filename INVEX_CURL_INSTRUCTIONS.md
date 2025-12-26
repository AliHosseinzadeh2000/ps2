# How to Generate Exact Invex API Curl Command

## Quick Method

Run the script with your API credentials:

```bash
python3 generate_invex_curl.py YOUR_API_KEY YOUR_HEX_ENCODED_PRIVATE_KEY
```

Or set environment variables:

```bash
export INVEX_API_KEY="your_api_key"
export INVEX_API_SECRET="your_hex_encoded_private_key"
python3 generate_invex_curl.py
```

## Manual Method

If you want to create the curl manually, here's the exact format:

### 1. Request Details

- **URL**: `https://api.invex.ir/trading/v1/orders`
- **Method**: `POST`
- **Content-Type**: `application/json`

### 2. Headers Required

```
Content-Type: application/json
X-API-Key-Invex: YOUR_API_KEY
X-API-Sign: SIGNATURE_HEX_STRING
X-API-Expire-At: 2025-12-12T19:10:58  (ISO format, no timezone)
```

### 3. Body Format (BEFORE adding signature)

```json
{
  "expire_at": "2025-12-12T19:10:58",
  "price": "1270400.0",
  "quantity": "7.887918981606556e-05",
  "side": "SELLER",
  "symbol": "USDT_IRR",
  "type": "LIMIT"
}
```

### 4. Signature Generation

1. Sort JSON keys alphabetically: `expire_at`, `price`, `quantity`, `side`, `symbol`, `type`
2. Create compact JSON (no spaces): `{"expire_at":"...","price":"...","quantity":"...","side":"...","symbol":"...","type":"..."}`
3. Sign with RSA-PSS SHA256 using your private key (DER format, hex-encoded)
4. Convert signature to hex string
5. Add signature to:
   - Body: `{"signature": "hex_string", ...}`
   - Header: `X-API-Sign: hex_string`

### 5. Final Body (WITH signature)

```json
{
  "expire_at": "2025-12-12T19:10:58",
  "price": "1270400.0",
  "quantity": "7.887918981606556e-05",
  "side": "SELLER",
  "signature": "71a5d482613e5aa1089b882fdd8de7a9...",
  "symbol": "USDT_IRR",
  "type": "LIMIT"
}
```

### 6. Example Curl Command

```bash
curl -X POST 'https://api.invex.ir/trading/v1/orders' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key-Invex: YOUR_API_KEY' \
  -H 'X-API-Sign: SIGNATURE_HEX' \
  -H 'X-API-Expire-At: 2025-12-12T19:10:58' \
  -d '{"expire_at":"2025-12-12T19:10:58","price":"1270400.0","quantity":"7.887918981606556e-05","side":"SELLER","signature":"SIGNATURE_HEX","symbol":"USDT_IRR","type":"LIMIT"}'
```

## Testing

The script will output:
1. The exact URL
2. All headers with values
3. The complete JSON body
4. The message used for signature generation
5. The generated signature
6. The complete curl command ready to copy/paste

Run it and copy the curl command to test directly with Invex API.
