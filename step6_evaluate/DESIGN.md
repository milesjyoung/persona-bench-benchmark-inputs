# Step 6: Evaluate Coverage (Two-Track Scoring)

## Goal

Rate how much of Mary's persona and social circles are reflected in the app logs.
Two scoring tracks: LLM judgment (qualitative) and spec compliance (quantitative).

## Track 1: LLM Judgment (qualitative, 1-5)

Can an LLM infer each preference, hidden fact, and relationship from logs alone?
This is what the Stanford paper's expert agents do — qualitative assessment.

```
SYSTEM:

Given ONLY these app logs (no persona profile, no social circles),
rate how well an LLM could reconstruct each aspect of Mary's life.

Rate 1-5:
  5 = Clearly inferable
  1 = Not present

Rate: preferences, hidden facts, relationships, expert perspectives.
```

## Track 2: Spec Compliance (deterministic PASS/FAIL)

Does the generated data conform to the concrete specs from our project —
US Census, Dunbar layers, OCEAN-behavior correlation, health prevalence.

```
SYSTEM:

Check the generated data against these specs. PASS or FAIL each.

1. DUNBAR LAYER SIZING
   S_L = BL * (0.5 + E), base: intimate=5, close=15, social=50, active=150
   Does Mary's circle size match her Extraversion?

2. US CENSUS DEMOGRAPHICS
   Mary: 28F, HS, food service, Madison WI, unmarried
   Check each against Census distribution ranges.

3. HEALTH CONDITION PREVALENCE (from PDF Table 4)
   Hypertension: 45% of adults (age-adjusted — plausible at 28?)
   Shellfish allergy: ~3.8% of adults (within prevalence?)

4. OCEAN-BEHAVIOR CORRELATION
   High C → planning, budgeting, journaling (present?)
   E level → social activity frequency (matches?)
   High N → health anxiety, rechecking (present?)

5. ALLERGEN ACCURACY (PDF Table 4)
   Shellfish=3 out of ~78 adults — Mary's allergy fits the pool?

6. SOCIAL CIRCLE DEMOGRAPHICS
   Are the 5 people demographically plausible for Madison WI?

7. ACTIVITY-PERSONALITY MATCH
   E<0.2: 4:1 alone:social. Age 45+: max 2 social. Age 18-24: highest.
   Does Mary's pattern match her age and E?

OUTPUT:
{
  "spec_compliance": {
    "check_name": {"verdict": "PASS/FAIL", "expected": "...", "actual": "..."}
  },
  "passed": N,
  "failed": N,
  "compliance_rate": "X%"
}
```

## Why Two Tracks

| | Track 1 (LLM Judgment) | Track 2 (Spec Compliance) |
|---|---|---|
| Measures | Can you infer persona from logs? | Does data match known specs? |
| Method | LLM rates 1-5 | Deterministic PASS/FAIL |
| Basis | Expert judgment | Census, PDF tables, Dunbar formula |
| Weakness | Subjective | Only checks structure |
| Strength | Catches narrative gaps | Reproducible, verifiable |
