# Step 5: Calendar Logs

## What I Did

Professor said to synthesize calendar entries for Mary for the past months. Key rules:
map as many preferences as possible into calendar entries, and keep it natural — no
routine tasks like "breakfast" on a calendar.

## Generation Prompt

```
SYSTEM:

Generate calendar entries for Mary Alberti, December 2025 - February 2026.

MARY'S PERSONA: {from Step 2}
SOCIAL CIRCLES: {from Step 3}

INCLUDE (things that need scheduling):
- Work shifts (variable food service — NOT 9-5)
- Social plans ("Dinner at Mom's", "Running with Jess", "Packers at Danny's")
- Appointments ("Dr. follow-up", "ServSafe study")
- Events ("Parish Fish Fry", "Badgers game", "Art walk")
- Recurring ("Mass - St. Maria Goretti", "Running club")

EXCLUDE (things real people don't calendar):
- "Breakfast", "Shower", "Drive to work"
- "Sleep", "Lunch", "Relax"

PREFERENCE MAPPING — every preference in at least 1 entry:
- Sports teams → game days
- Running → "Lake Mendota run" recurring
- Cooking → "Dinner party", "Meal prep"
- Gardening → "Garden center trip"
- Religion → "Mass" Sundays
- Health → "Dr. appointment" (no condition name)
- Career → "ServSafe study"
- Financial → "Budget review"

SOCIAL CIRCLE — each person in 2-3 entries.

NATURALNESS:
- Vary density, include cancellations
- Seasonal (no outdoor runs in January blizzards)
- Holiday entries (Christmas, New Year's, Super Bowl)

Generate 40-60 entries.

OUTPUT:
{
  "calendar_entries": [
    {
      "date": "2026-01-05",
      "time": "09:00",
      "title": "Lake Mendota Run w/ Jess & Lisa",
      "location": "Lake Mendota path",
      "people_involved": ["Jessica Torres", "Lisa Chen"],
      "preferences_reflected": ["Running"]
    }
  ]
}
```

## Verification Prompt

```
SYSTEM:

Verify calendar against persona (Step 2), circles (Step 3), messenger (Step 4).

1. PREFERENCE COVERAGE: Every preference in at least 1 entry? X/Y mapped.
2. PERSONA: Work schedule matches food service? No condition names?
3. SOCIAL CIRCLE: All 5 people appear? Activities match Step 3?
4. NATURALNESS: No "breakfast" entries? Realistic density? Seasonal?
5. CROSS-CHECK: Plans in messenger show up on calendar? No contradictions?

OUTPUT: {verdict per check}
```
