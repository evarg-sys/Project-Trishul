# Testing Guide: How to Test All 80 Cases

## Quick Start (5 minutes)

```bash
cd ml_research/routing

# 1. Set Mapbox token (PowerShell)
$env:MAPBOX_ACCESS_TOKEN="your_token_here"

# 2. Run all tests with report
python test_suite.py --report

# Expected output:
# Category     Total  Passed  Failed  Pass Rate
# ────────────────────────────────────────────
# hazards        10      8       2     80%
# routing        20     16       4     80%
# dispatch       15     12       3     80%
# edge_cases     20      5      15     25%
# error_hdlng    10      0      10      0%
# integration     5      5       0    100%
# ────────────────────────────────────────────
# TOTAL          80     46      34     57.5%
```

## Running by Category (20 minutes)

```bash
# Hazard tests (assumes NASA EONET API available)
python test_suite.py --category hazards

# Routing tests (requires valid Mapbox token)
python test_suite.py --category routing

# Dispatch tests (combines both)
python test_suite.py --category dispatch

# Edge cases (tests boundary conditions)
python test_suite.py --category edge_cases

# Error handling (tests failures)
python test_suite.py --category error_handling

# Integration (tests full workflows)
python test_suite.py --category integration
```

## Running Individual Tests (30 minutes)

```bash
# Test 1: Fetch all hazards
python test_suite.py --test 1

# Test 15: Route downtown
python test_suite.py --test 15

# Test 42: Dispatch from zero coordinates
python test_suite.py --test 42

# Test 65: Handle directory traversal in filename
python test_suite.py --test 65
```

## Running in Interactive Mode

```bash
python test_suite.py --interactive

# Output will be:
# [Test 1/80] Fetch all active hazards
# "y" to run, "s" to skip, "q" to quit: y
# Running: fetch-hazards
# ✓ PASS: Found 50+ events
# 
# [Test 2/80] Fetch hazards (last 7 days)
# "y" to run, "s" to skip, "q" to quit: y
# ...
```

## Running in Verbose Mode (Detailed Output)

```bash
python test_suite.py --test 42 --verbose

# Output:
# [Test 42] Dispatch from zero coordinates
# Category: dispatch
# Command: recommend-dispatch --incident 0.0,0.0
# Description: Test routing from exact zero coordinates (prime meridian)
# Expected Output: Should handle gracefully
# Running command...
# Output: {"incident": "0.0,0.0", "recommendations": [...], "score": 1234}
# Result: ✓ PASS
```

## Manual CLI Testing (without test suite)

```bash
python dispatch_cli.py

# Try these commands:
ws> fetch-hazards
ws> fetch-hazards days=7 category=fires
ws> fetch-hazards save=my_hazards.json
ws> route-unit --from -87.65,41.88 --to -87.62,41.90
ws> route-unit --from 0,0 --to 1,1
ws> recommend-dispatch --incident -87.628,41.885
ws> recommend-dispatch --incident -87.628,41.885 --responders example_responders.json
ws> recommend-dispatch --incident -87.628,41.885 --no-hazards
ws> help
ws> quit
```

## Creating Test Data Files

The test suite expects these files for certain tests:

**example_responders.json** - Already created (5 responders)

**test_data_empty.json** - Empty responder list `[]`

**test_data_large_pool.json** - 15 responders (for stress testing)

**test_data_single.json** - 1 responder

**test_data_missing_lon.json** - Invalid format (for error handling)

**test_data_missing_lat.json** - Invalid format

**test_data_bad_coords.json** - Non-numeric coordinates

**test_data_bad_json.txt** - Malformed JSON

## Expected Results by Category

### Hazards (Tests 1-10): 80% Pass Rate
- Tests 1-6: ✓ PASS (API working)
- Tests 7-9: ✓ PASS (filters applied)
- Test 10: ? Depends on storm events

### Routing (Tests 11-30): 85% Pass Rate
- Tests 11-29: ✓ PASS (valid coordinates)
- Test 30: ⚠️ Water routes may be unavailable

### Dispatch (Tests 31-45): 90% Pass Rate
- Tests 31-45: ✓ PASS (all valid inputs)

### Edge Cases (Tests 46-65): 25% Pass Rate
- Tests 46-59: ❌ FAIL gracefully (expected failures)
- Tests 60-65: ❌ FAIL gracefully (error handling)

### Error Handling (Tests 66-75): 0% Pass Rate
- Tests 66-75: ❌ FAIL (demonstrating error handling)

### Integration (Tests 76-80): 100% Pass Rate
- Tests 76-80: ✓ PASS (complete workflows)

## Performance Testing

```bash
# Run with timing info
python test_suite.py --report --verbose

# Key metrics to watch:
# - Hazard fetch: < 2s
# - Single route calculation: < 1s  
# - Dispatch recommendation: < 2s (with 5 responders)
# - Test suite total: < 5 minutes for all 80
```

## Debugging Failed Tests

```bash
# If a test fails, run it with verbose to see details
python test_suite.py --test 42 --verbose

# Check specific error handling
python test_suite.py --category error_handling --verbose

# See raw output
python test_suite.py --test 15 --verbose | tee test_output.txt
```

## Continuous Testing

```bash
# For CI/CD integration
python test_suite.py --report > test_results.txt

# Exit code: 0 if pass, 1 if any unexpected failures
# Extract results with:
cat test_results.txt | grep "Pass Rate"
```

## Troubleshooting

**"Missing MAPBOX_ACCESS_TOKEN"**
```bash
$env:MAPBOX_ACCESS_TOKEN="your_token_here"
```

**"API timeout"**
- Extend timeout in test_suite.py
- Check internet connection
- Verify Mapbox token is valid

**"Empty test results"**
- Run with --verbose to see what's happening
- Check if Python imports working: `python -c "import requests; print('OK')"`

**"File not found"**
- Files should be in `ml_research/routing/`
- Run tests from: `cd ml_research/routing && python test_suite.py`

## Success Criteria

✅ **Minimum to proceed:**
- Tests 1-45: At least 80% pass
- Tests 46-75: Expected failures only
- Tests 76-80: All pass

✅ **Full success:**
- Tests 1-45: 95%+ pass
- Tests 76-80: 100% pass
- Test suite completes in < 5 minutes
