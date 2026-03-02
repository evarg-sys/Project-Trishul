# Input Validation Rules - Interactive Mode

## Validation Rules Reference

### Latitude Input
**Valid Range:** `-90.0` to `90.0` (degrees)

**Valid Examples:**
- `41.8781` ✓ (Chicago)
- `0` ✓ (Equator)
- `-33.9249` ✓ (Sydney)
- `51.5074` ✓ (London)

**Invalid Examples:**
- `91` ✗ (Out of range, must be ≤ 90)
- `-91` ✗ (Out of range, must be ≥ -90)
- `abc` ✗ (Not a number)
- ` ` ✗ (Empty/whitespace)

**Error Messages:**
```
[ERROR] Latitude cannot be empty. Please enter a valid number.
[ERROR] Latitude must be between -90 and 90. Got: {value}
[ERROR] Invalid input: could not convert string to float: '{value}'
```

---

### Longitude Input
**Valid Range:** `-180.0` to `180.0` (degrees)

**Valid Examples:**
- `-87.6298` ✓ (Chicago)
- `0` ✓ (Prime meridian)
- `151.2093` ✓ (Sydney)
- `-0.1278` ✓ (London)

**Invalid Examples:**
- `181` ✗ (Out of range, must be ≤ 180)
- `-181` ✗ (Out of range, must be ≥ -180)
- `xyz` ✗ (Not a number)
- ` ` ✗ (Empty/whitespace)

**Error Messages:**
```
[ERROR] Longitude cannot be empty. Please enter a valid number.
[ERROR] Longitude must be between -180 and 180. Got: {value}
[ERROR] Invalid input: could not convert string to float: '{value}'
```

---

### Radius Input
**Valid Range:** Greater than `0` (meters)
**Optional:** Press Enter for default `1000` meters
**Warning Threshold:** Greater than `50000` meters (50 km)

**Valid Examples:**
- `500` ✓ (Small area, fast)
- `1000` ✓ (Default, recommended)
- `2000` ✓ (Larger area)
- `25000` ✓ (25 km, still reasonable)
- (empty/Enter) ✓ (Uses default 1000)

**Invalid Examples:**
- `0` ✗ (Must be > 0)
- `-1000` ✗ (Must be positive)
- `abc` ✗ (Not a number)
- `100000` ⚠ (Very large, triggers warning)

**Error Messages:**
```
[ERROR] Radius must be greater than 0.
[ERROR] Invalid input: invalid literal for int() with base 10: '{value}'
[WARNING] Radius is very large (>50km). This will take longer...
```

**Large Radius Behavior:**
```
[WARNING] Radius is very large (>50km). This will take longer and may hit API limits.
Continue anyway? (y/n): 
```
- Type `y` or `yes` to continue with large radius
- Type `n` or `no` to retry with different radius

---

## Common Input Scenarios

### Scenario 1: User Enters Letter in Latitude
```
Enter Latitude (e.g., 41.8781): abc
[ERROR] Invalid input: could not convert string to float: 'abc'
Please enter valid numbers. Example:
  Latitude: 41.8781
  Longitude: -87.6298
  Radius: 1000

Enter Latitude (e.g., 41.8781): 41.8781  ← Retry
```

### Scenario 2: User Enters Out-of-Range Latitude
```
Enter Latitude (e.g., 41.8781): 100
[ERROR] Latitude must be between -90 and 90. Got: 100

Enter Latitude (e.g., 41.8781): 41.8781  ← Retry
```

### Scenario 3: User Forgets Negative Sign in Longitude
```
Enter Latitude (e.g., 41.8781): 41.8781
Enter Longitude (e.g., -87.6298): 87.6298
[ERROR] Longitude must be between -180 and 180. Got: 87.6299
[This actually wouldn't error as it's within range]
```

Actually, if user forgets the negative sign for a western location:
```
Enter Longitude (e.g., -87.6298): 87.6298  ← Without minus
[Valid - but gives completely wrong location if user intended Chicago]
```

**Solution:** Validation doesn't catch this semantic error. User should:
- Check that Western Hemisphere = negative longitude
- Check that Eastern Hemisphere = positive longitude
- Check that Northern Hemisphere = positive latitude
- Check that Southern Hemisphere = negative latitude

### Scenario 4: User Enters Very Large Radius
```
Enter Radius in meters (default 1000): 75000
[WARNING] Radius is very large (>50km). This will take longer and may hit API limits.
Continue anyway? (y/n): n
→ Allows user to enter new radius without re-entering coordinates
```

### Scenario 5: User Presses Ctrl+C
```
Enter Latitude (e.g., 41.8781): [Ctrl+C]

Exiting...
[Program terminates gracefully]
```

---

## Validation Flow Diagram

```
START
  ↓
VALID_INPUT = false
  ↓
WHILE not VALID_INPUT:
  ↓
  Try:
    ↓
    INPUT: Latitude
    ↓
    Is empty?
      YES → Print error, continue ↻
      NO ↓
    Can convert to float?
      NO → ValueError caught, print error, continue ↻
      YES → lat = float(value) ↓
    Is in range [-90, 90]?
      NO → Print error, continue ↻
      YES ↓
    INPUT: Longitude
    ↓
    [Same validation as latitude but range [-180, 180]] ↓
    INPUT: Radius (optional, default 1000)
    ↓
    If provided:
      Can convert to int?
        NO → ValueError caught, print error, continue ↻
        YES ↓
      Is > 0?
        NO → Print error, continue ↻
        YES ↓
      Is <= 50000?
        NO → Ask for confirmation ↻
        YES ↓
    VALID_INPUT = true ↓
    Break while loop ↓
  Except KeyboardInterrupt:
    → Print "Exiting...", return ↓
  ↓
PROCEED WITH ESTIMATION
  ↓
END
```

---

## Summary Table

| Input | Type | Range | Optional | Error Message |
|-------|------|-------|----------|---------------|
| Latitude | float | -90 to 90 | No | Out of range or non-numeric |
| Longitude | float | -180 to 180 | No | Out of range or non-numeric |
| Radius | int | > 0 | Yes (1000m default) | Non-numeric or ≤ 0 |

---

## Global Coordinate Reference

**Latitude:**
- North Pole: `90`
- Equator: `0`
- South Pole: `-90`
- Chicago: `41.8781`
- Sydney: `-33.9249`

**Longitude:**
- Prime Meridian (Greenwich): `0`
- Maximum East: `180` (International Date Line)
- Maximum West: `-180` (International Date Line)
- Chicago: `-87.6298`
- Sydney: `151.2093`

---

## Testing Checklist

- [ ] Valid input: `41.8781, -87.6298, 1000` → Success
- [ ] Empty latitude → Error → Retry → `41.8781` → Success
- [ ] Non-numeric latitude: `abc` → Error → Retry → `41.8781` → Success
- [ ] Out-of-range latitude: `91` → Error → Retry → `41.8781` → Success
- [ ] Out-of-range longitude: `-181` → Error → Retry → `-87.6298` → Success
- [ ] Negative radius: `-500` → Error → Retry → `1000` → Success
- [ ] Large radius: `75000` → Warning → Choose `y` → Continue
- [ ] Large radius: `75000` → Warning → Choose `n` → Retry with different radius
- [ ] No radius (press Enter) → Use default 1000 → Success
- [ ] Keyboard interrupt (Ctrl+C) → Graceful exit → "Exiting..."

---

## Tips for Users

1. **Coordinate Format:** Use decimal degrees, not degrees-minutes-seconds
   - ✓ Correct: `41.8781`
   - ✗ Wrong: `41°52'41"N`

2. **Western Hemisphere:** Remember the minus sign for longitude
   - ✓ Chicago: `-87.6298` (west is negative)
   - ✗ Chicago: `87.6298` (positive would be in Moscow)

3. **Southern Hemisphere:** Remember the minus sign for latitude
   - ✓ Sydney: `-33.9249` (south is negative)

4. **Search Radius:** Larger radius = slower but larger area coverage
   - Small (500m): Very fast, ~0.5 minute walking distance
   - Medium (1000m): Typical, ~10 minute walk
   - Large (5000m): 5 km area, noticeable API delay
   - Very Large (>50000m): May trigger API limits, slow

5. **Common Locations (Latitude, Longitude):**
   - **Chicago Center:** `41.8781,-87.6298`
   - **Lincoln Park:** `41.9212,-87.6567`
   - **Hyde Park:** `41.7943,-87.5907`
   - **Downtowntown:** `41.8827,-87.6233`
