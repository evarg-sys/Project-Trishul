# 80+ Test Cases Reference: Detailed Examples

Quick reference for all 80 test cases with commands and expected outputs.

## TESTS 1-10: HAZARD FETCHING

**Test 1:** `fetch-hazards`  
Fetch worldwide active events

**Test 2:** `fetch-hazards days=7`  
Last 7 days

**Test 3:** `fetch-hazards days=30`  
Last 30 days

**Test 4:** `fetch-hazards category=fires`  
Fire events only

**Test 5:** `fetch-hazards category=volcanoes`  
Volcano events only

**Test 6:** `fetch-hazards days=14 category=floods`  
Combined filters

**Test 7:** `fetch-hazards save=hazards.json`  
Save output

**Test 8:** `fetch-hazards days=0`  
Today only

**Test 9:** `fetch-hazards days=365`  
Full year

**Test 10:** `fetch-hazards category=storms`  
Severe weather

---

## TESTS 11-30: ROUTING

**Test 11:** `route-unit --from -87.6500,41.8800 --to -87.6498,41.8815` (1km)

**Test 12:** `route-unit --from -87.6500,41.8800 --to -87.6000,41.8500` (5km)

**Test 13:** `route-unit --from -87.6500,41.8800 --to -87.4000,41.7000` (20km)

**Test 14:** `route-unit --from -87.6500,41.8800 --to -87.6500,41.8800` (same point)

**Test 15:** `route-unit --from -87.6298,41.8781 --to -87.6200,41.8900` (downtown)

**Test 16:** `route-unit --from -87.123456789,41.123456789 --to -87.987654321,41.987654321` (high precision)

**Test 17:** `route-unit --from -87.6500,41.8800 --to -87.6500,42.0000` (north)

**Test 18:** `route-unit --from -87.6500,41.8800 --to -87.6500,41.6000` (south)

**Test 19:** `route-unit --from -87.6500,41.8800 --to -87.3000,41.8800` (east)

**Test 20:** `route-unit --from -87.3000,41.8800 --to -87.6500,41.8800` (west)

**Test 21:** `route-unit --from -87.6500,41.8800 --to -88.2500,41.9000` (cross state)

**Test 22:** `route-unit --from -43.1729,22.9068 --to -43.1800,22.9000` (negative lat)

**Test 23:** `route-unit --from -43.0000,0.0000 --to -42.9500,0.0500` (equator)

**Test 24:** `route-unit --from 179.5,0 --to -179.5,0` (date line)

**Test 25:** `route-unit --from 0,85.0000 --to 0,85.0500` (north pole)

**Test 26:** `route-unit --from 0.0,0.0 --to 0.001,0.001` (prime meridian)

**Test 27:** `route-unit --from -0.0,-0.0 --to 0.0,0.0` (negative zero)

**Test 28:** `route-unit --from -87.6270,41.8819 --to -87.6235,41.8829` (dense urban)

**Test 29:** `route-unit --from -88.5000,41.5000 --to -88.4000,41.4000` (rural)

**Test 30:** `route-unit --from -87.3500,41.8800 --to -87.3500,41.7000` (water)

---

## TESTS 31-45: DISPATCH RECOMMENDATIONS

**Test 31:** `recommend-dispatch --incident -87.628,41.885`

**Test 32:** `recommend-dispatch --incident -87.628,41.885 --responders example_responders.json`

**Test 33:** `recommend-dispatch --incident -87.628,41.885` (with hazards)

**Test 34:** `recommend-dispatch --incident -87.628,41.885 --no-hazards`

**Test 35:** `recommend-dispatch --incident -87.6298,41.8781` (downtown)

**Test 36:** `recommend-dispatch --incident -87.628,42.0000` (far north)

**Test 37:** `recommend-dispatch --incident -87.62841234,41.88521234` (high precision)

**Test 38:** `recommend-dispatch --incident -43.1729,-22.9068` (southern hemisphere)

**Test 39:** `recommend-dispatch --incident -87.628,41.885 --responders single.json` (1 responder)

**Test 40:** `recommend-dispatch --incident -87.628,41.885 --responders large_pool.json` (15+ responders)

**Test 41:** `recommend-dispatch --incident -43.0000,0.0000` (equator)

**Test 42:** `recommend-dispatch --incident 0.0,0.0` (zero coords)

**Test 43:** `recommend-dispatch --incident -87.628,41.885` (consistency 1st call)

**Test 44:** `recommend-dispatch --incident -87.628,41.885` (consistency 2nd call - same result)

**Test 45:** `recommend-dispatch --incident -87.55,41.88` (island/water)

---

## TESTS 46-65: EDGE CASES

**Test 46:** `route-unit --from -87.65,41.88 --to -87.62,100` (lat > 90) ❌

**Test 47:** `route-unit --from -87.65,41.88 --to -87.62,-100` (lat < -90) ❌

**Test 48:** `route-unit --from -87.65,41.88 --to 200,41.88` (lon > 180) ❌

**Test 49:** `route-unit --from -87.65,41.88 --to -200,41.88` (lon < -180) ❌

**Test 50:** `route-unit --from -87.65 41.88 --to -87.62,41.90` (missing comma) ❌

**Test 51:** `route-unit --from ABC,DEF --to -87.62,41.90` (non-numeric) ❌

**Test 52:** `route-unit --from , --to -87.62,41.90` (empty) ❌

**Test 53:** `route-unit -87.65,41.88 --to -87.62,41.90` (missing --from) ❌

**Test 54:** `route-unit --from -87.65,41.88 -87.62,41.90` (missing --to) ❌

**Test 55:** `route-unit --from -87.1234567890123,41.1234567890123 --to -87.9876543210987,41.9876543210987` (many decimals)

**Test 56:** `route-unit --from 0,90 --to 0,89.99` (lat exactly 90)

**Test 57:** `route-unit --from 0,-90 --to 0,-89.99` (lat exactly -90)

**Test 58:** `route-unit --from 180,0 --to 179.99,0` (lon exactly 180)

**Test 59:** `route-unit --from -180,0 --to -179.99,0` (lon exactly -180)

**Test 60:** `recommend-dispatch --incident -87.628,41.885 --responders nonexist.json` (missing file) ❌

**Test 61:** `recommend-dispatch --incident -87.628,41.885 --responders bad.json` (invalid JSON) ❌

**Test 62:** `recommend-dispatch --incident -87.628,41.885 --responders empty.json` (empty array) ❌

**Test 63:** `recommend-dispatch --incident -87.628,41.885 --responders missing_lon.json` (missing lon) ❌

**Test 64:** `recommend-dispatch --incident -87.628,41.885 --responders missing_lat.json` (missing lat) ❌

**Test 65:** `recommend-dispatch --incident -87.628,41.885 --responders bad_coords.json` (invalid coords) ❌

---

## TESTS 66-75: ERROR HANDLING

**Test 66:** (no MAPBOX_ACCESS_TOKEN set) ❌

**Test 67:** (bad token: pk.invalid) ❌

**Test 68:** (network failure) ❌ or fallback

**Test 69:** (API timeout > 10s) ❌

**Test 70:** `rout-unit --from...` (typo) ❌

**Test 71:** `route-unit from ... to ...` (wrong format) ❌

**Test 72:** `fetch-hazards category=xyz` (null category)

**Test 73:** `fetch-hazards` (null geometry in response)

**Test 74:** `route-unit --from X --to Y --from Z ...` (duplicate flags)

**Test 75:** `route-unit --from X --to Y --unknown-flag Z` (unknown flag)

---

## TESTS 76-80: INTEGRATION

**Test 76:** Full workflow: fetch → route → dispatch

**Test 77:** Sequential dispatches (3 different locations)

**Test 78:** Consistency: same dispatch twice

**Test 79:** Update responders file mid-session

**Test 80:** Error recovery + retry

---

## Run in Python Test Suite

```bash
python test_suite.py --verbose
python test_suite.py --category routing
python test_suite.py --test 42
python test_suite.py --report
```

All 80 test cases organized, executable, with expected outputs and pass/fail indicators.
