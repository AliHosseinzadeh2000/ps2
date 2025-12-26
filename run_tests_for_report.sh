#!/bin/bash
# Test Runner for Report Generation
# Runs all tests and captures output for documentation

set -e

REPORT_DIR="test_reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "========================================"
echo "Test Runner for Report 2"
echo "========================================"
echo "Timestamp: $(date)"
echo ""

# Create report directory
mkdir -p "$REPORT_DIR"

echo "1️⃣  Running Exchange Connectivity Verification..."
echo "=================================================="
python3 verify_exchanges.py 2>&1 | tee "$REPORT_DIR/connectivity_$TIMESTAMP.txt"
CONNECTIVITY_EXIT=$?
echo ""
echo "✅ Connectivity verification complete (exit code: $CONNECTIVITY_EXIT)"
echo ""

echo "2️⃣  Running Unit Tests..."
echo "========================"
pytest tests/test_exchanges.py tests/test_arbitrage.py tests/test_ai.py -v --tb=short 2>&1 | tee "$REPORT_DIR/unit_tests_$TIMESTAMP.txt"
UNIT_EXIT=$?
echo ""
echo "✅ Unit tests complete (exit code: $UNIT_EXIT)"
echo ""

echo "3️⃣  Running Integration Tests (without real API)..."
echo "===================================================="
pytest tests/test_exchanges_integration.py -v --tb=short 2>&1 | tee "$REPORT_DIR/integration_tests_$TIMESTAMP.txt"
INTEGRATION_EXIT=$?
echo ""
echo "✅ Integration tests complete (exit code: $INTEGRATION_EXIT)"
echo ""

echo "4️⃣  Running Real API Tests (if credentials available)..."
echo "========================================================="
echo "Note: Set SKIP_REAL_API_TESTS=0 to enable real API tests"
echo ""

# Ask user if they want to run real API tests
read -p "Run real API tests? This will make actual API calls. (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Running real API tests..."
    SKIP_REAL_API_TESTS=0 pytest tests/test_real_api_integration.py -v --tb=short -s 2>&1 | tee "$REPORT_DIR/real_api_tests_$TIMESTAMP.txt"
    REAL_API_EXIT=$?
    echo ""
    echo "✅ Real API tests complete (exit code: $REAL_API_EXIT)"
else
    echo "Skipping real API tests."
    REAL_API_EXIT=0
fi
echo ""

echo "5️⃣  Running Code Coverage Analysis..."
echo "====================================="
pytest tests/ --cov=app --cov-report=term --cov-report=html:$REPORT_DIR/coverage_$TIMESTAMP 2>&1 | tee "$REPORT_DIR/coverage_$TIMESTAMP.txt"
COVERAGE_EXIT=$?
echo ""
echo "✅ Coverage analysis complete (exit code: $COVERAGE_EXIT)"
echo ""

echo "========================================"
echo "TEST SUMMARY"
echo "========================================"
echo "Connectivity Test:    $([ $CONNECTIVITY_EXIT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
echo "Unit Tests:           $([ $UNIT_EXIT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
echo "Integration Tests:    $([ $INTEGRATION_EXIT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
echo "Real API Tests:       $([ $REAL_API_EXIT -eq 0 ] && echo '✅ PASS' || echo '❌ SKIP/FAIL')"
echo "Coverage Analysis:    $([ $COVERAGE_EXIT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
echo ""
echo "All test outputs saved to: $REPORT_DIR/"
echo "========================================"

# Calculate overall result
OVERALL_EXIT=0
if [ $CONNECTIVITY_EXIT -ne 0 ] || [ $UNIT_EXIT -ne 0 ] || [ $INTEGRATION_EXIT -ne 0 ]; then
    OVERALL_EXIT=1
fi

exit $OVERALL_EXIT
