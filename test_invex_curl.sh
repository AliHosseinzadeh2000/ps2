#!/bin/bash
# Test Invex API with exact curl command
# This script shows you how to manually test the Invex API

# Set your API credentials here
INVEX_API_KEY="64k9kb0zfwo36sqavv8ha1vb0dc7f22111fag5e2bhqrlsfgo75uoeskmrtvd8z5"
INVEX_API_SECRET="308204be020100300d06092a864886f70d0101010500048204a8308204a40201000282010100a91c27958196b971d6c32aa0628d1b8939e4fd3c62656eae50242e70d01c4b0dfde2f2ce24fde1383e659428a314b52450b9513fa6bc6799bff910797910d8e84b4898adcf72d3e296984f1f062175ca9b1020cecf99ac714b32d01e3f7050275447637c20b69a8160de4982f91a8d24100f37b9989c5d1593369b75f19466d951f0b0dc6a0e6a01aaa90df49070da29864953e4b60adc55141807bdcb62e349d875021a59abf12ac367f8cc85b140ec8d310de7d91b282ee926e241179ea7add3eea86bc00be7d0a55e52a25a9359109eb9ef37e0989780767ce998735f911c17511ad794cac169a5cae62e5cf3b65992b18e50af11fb753a8e5e13833d3f7502030100010282010011bb4fc43ba509f74f8941c634e72e50b67715fd77a4c294f8f6be3eda77690043d380d99023e5b25fca875d367254a704e6d587dacc0d01e050f58303287ad1ea98e7576c35d255432c9fb9354b9b5dfde1d44ad3163e3057edf14806a75864335053f45f3abe5b1c04dac8e6a53bd0e0f53386dca36298414a1bc5636a07d98c67742820916adeda25aa844fece5424327da7dd3292953d3858b8de7717d30f722d7057051dcf5861b5ce9fafde7f255a4977fe755dceb56528b5d4c9f85fd7a52468669d0f15357376adcb26c583cf34d5989e9ddd0194018ddf3f8c77d9a62dd6a5b71fe8c39a4abc1446f968c6a8e641047294c66cfe501d310822c81d902818100dd8ccc29b8945faf717ee7e9c4e868b1503e633eb317e19723865e66f9517a04c028110eacaed991b9923a1755a3f873540e574229be99b8f0f7f8c5e9e47ac1bbdd522d5abe2351d99bc92a886bd790b0160935f0115bbfd1f2db6fe0d75bc4dff3447079f2e7b7a630a66ee6e09884fa81c78e1d9f59b6df6e7ec52109affd02818100c367e2f6732af3d1ad8476fa2c30a358c59d804183645cc4559b478ca24ff968401f7c623b61766e98289d9aa835a1a68c729244d4b07d51084f2f86431bbae80a5487b82368281ed8c5434e244776b8eb824f8507d0181b7f75381a68400d428f65513998686f26b0eaa79ad890c1617ca464c8739157f5da3c78ab1bf2fad902818100d35c6eae62dc9288b3136a36d8570d021456e0a1c1844800c3b07e41691bb4f7f146883762c110e9f88b2b86757a901d9e946be4c024894d29feb84440466c628552b90271eeb18d75b82cebb9e8806815c580160828d74a2206ba187afd9a1c31b74894b192ee4383762861e73b5fe68582e89989632bd8ce42010919e2bf15028180298414f08f9f7c95fbebbceb822003548507e58c05c279032dbd04029929acafbd8ff2f95bec6521322acef160f3a418a296650542bb0ca4fec2f431ee6821d9d2f80aadd0b7fc6e315817e8ae4490b0d138aa7475287d36ba69c935b31888b8af86b32f2d7662c731a7695cb8ce6887b1d7aba1fb0bd24865c99b499f728c6102818100d1ce5b81b65141a2fd7a42ee228810486174bf4fca0c225db6031977e82bec36afa7f169d85c58e6e989790724d85338391146d69f02ed1dcc50ecb87d779a7fd94bffe0a663aa1df0b3e052d7b8208bc01e14b49ffc53d10f060373221de2bd3deb15114227460626248413c3ec00eaced6e6f5909a5900c97ed24502ef53d4"

# Or load from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep INVEX | xargs)
fi

# Base URL
BASE_URL="https://api.invex.ir/trading/v1"
ENDPOINT="/orders"
FULL_URL="${BASE_URL}${ENDPOINT}"

# Generate expire_at (60 seconds from now, ISO format without timezone)
EXPIRE_AT=$(python3 -c "from datetime import datetime; print(datetime.fromtimestamp($(date +%s) + 60).isoformat())")

# Request payload (BEFORE adding signature)
# Note: Keys must be sorted alphabetically for signature generation
PAYLOAD='{
  "expire_at": "'"$EXPIRE_AT"'",
  "price": "1270400.0",
  "quantity": "0.00007888",
  "side": "SELLER",
  "symbol": "USDT_IRR",
  "type": "LIMIT"
}'

echo "=" 
echo "INVEX API TEST"
echo "=" 
echo ""
echo "URL: $FULL_URL"
echo "Method: POST"
echo ""
echo "Payload (for signature generation):"
echo "$PAYLOAD" | python3 -m json.tool
echo ""
echo "NOTE: To generate the signature, you need to:"
echo "1. Sort the JSON keys alphabetically"
echo "2. Remove all spaces (compact JSON)"
echo "3. Sign with RSA-PSS SHA256"
echo "4. Add signature to both body and X-API-Sign header"
echo ""
echo "Use generate_invex_curl.py to generate the exact curl command:"
echo "  python3 generate_invex_curl.py $INVEX_API_KEY $INVEX_API_SECRET"
echo ""









