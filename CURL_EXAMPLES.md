# CURL Examples for Exchange API Requests

## Invex - Place Order

Based on Invex API documentation and error messages, here's what the request should look like:

```bash
# Invex requires:
# 1. expire_at in the request body (ISO format datetime string, timezone-naive)
# 2. signature in the request body (hex-encoded RSA-PSS signature)
# 3. Signature in headers (X-API-Sign) - might be required too
# 4. API key in headers (X-API-Key-Invex)
# 5. expire_at in headers (X-API-Expire-At)

# Step 1: Create the body data (sorted keys, no spaces)
BODY='{"expire_at":"2024-12-09T01:15:00","price":"1262390","quantity":"0.00007920","side":"SELLER","symbol":"USDT_IRR","type":"LIMIT"}'

# Step 2: Generate signature from body (RSA-PSS SHA256)
# Signature is generated from the exact JSON string above

# Step 3: Add signature to body
BODY_WITH_SIG='{"expire_at":"2024-12-09T01:15:00","price":"1262390","quantity":"0.00007920","side":"SELLER","signature":"GENERATED_SIGNATURE_HEX","symbol":"USDT_IRR","type":"LIMIT"}'

curl -X POST https://api.invex.ir/trading/v1/orders \
  -H "Content-Type: application/json" \
  -H "X-API-Key-Invex: YOUR_API_KEY" \
  -H "X-API-Sign: GENERATED_SIGNATURE_HEX" \
  -H "X-API-Expire-At: 2024-12-09T01:15:00" \
  -d "$BODY_WITH_SIG"
```

**Note**: 
- The signature is generated from the JSON body WITHOUT the signature field (sorted keys, no spaces) using RSA-PSS with SHA256
- Then the signature is added to the body
- Both body and headers should include the signature

## Wallex - Place Order

Based on Wallex API documentation (https://developers.wallex.ir/spot/createorder):

```bash
# Wallex requires:
# 1. x-api-key header (lowercase)
# 2. All values as strings in JSON body
# 3. No signature needed for POST /v1/account/orders

curl -X POST https://api.wallex.ir/v1/account/orders \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "symbol": "USDTTMN",
    "side": "BUY",
    "type": "LIMIT",
    "quantity": "0.00007920",
    "price": "125890"
  }'
```

**Note**: 
- Symbol format: The symbol `USDTTMN` might not be valid. Common Wallex symbols:
  - `BTCUSDT`, `ETHUSDT` (USDT pairs)
  - `BTCTMN`, `ETHTMN` (TMN/Toman pairs)
  - For USDT/TMN pairs, it might be `USDTTMN` or the pair might not exist
  - Check Wallex trading pairs list to verify available symbols
- All numeric values must be strings
- Quantity and price should be in decimal format (not scientific notation like `7.917e-05`)
- The error "اطلاعات وارد شده اشتباه‌است" (The entered information is incorrect) usually means:
  - Invalid symbol
  - Invalid quantity/price format
  - Missing required fields

## Testing with Python httpx equivalent

The code should make requests equivalent to these curl commands.

