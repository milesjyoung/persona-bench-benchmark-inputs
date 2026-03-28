# Step 2b: 4-Expert Verification

## What I Did

Professor said to verify the enriched persona using the 4 expert agents from the
Stanford paper (pages 23-25): **Psychologist, Behavioral Economist, Political
Scientist, Demographer.** Each generates 5-15 observations checking for
contradictions between the interview output and the NVIDIA seed data.

I used Claude to help design a prompt where each expert has specific checks
relevant to Mary's profile — not generic.

## Verification Prompt

```
SYSTEM:

You are 4 domain experts verifying a synthetic persona for consistency
with its seed data. Find CONTRADICTIONS and IMPLAUSIBILITIES.

SEED DATA (NVIDIA): {nvidia_seed_data}
ENRICHED PERSONA (INTERVIEW): {extracted_profile}
TRANSCRIPT: {interview_transcript}

──────────────────────────────────────────────────────────
EXPERT 1: PSYCHOLOGIST

Write 5-15 observations. Check:
a) Does interview behavior match seed personality? (Seed says
   "routine-obsessed, disciplined, competitive, double-checks receipts")
b) Are all behaviors compatible with each other?
c) Is social life consistent with personality?
d) Are stressors and coping mechanisms consistent?

Format: "[OBSERVATION N]: text. [CONSISTENT/INCONSISTENT/GAP]
         Seed ref: {field} | Interview ref: {answer}"

──────────────────────────────────────────────────────────
EXPERT 2: BEHAVIORAL ECONOMIST

Check:
a) Income-expense plausibility (fast food in Madison ~$28-35k/yr.
   Rent $650, savings $200/mo, leisure $150/mo — feasible?)
b) Career path realism (crew → supervisor → manager → diner owner at 28?)
c) Financial behavior matches spending patterns?
d) Consumption patterns match income? (Napa Valley on fast food wages?)

──────────────────────────────────────────────────────────
EXPERT 3: POLITICAL SCIENTIST

Check:
a) Ideological coherence (Catholic Italian-American in Wisconsin —
   do media habits match stated leaning?)
b) Civic behavior consistent with demographics?
c) Media consumption matches political leaning?
d) Cultural-political alignment makes sense?

──────────────────────────────────────────────────────────
EXPERT 4: DEMOGRAPHER

Check:
a) Demographics all consistent? (28, HS, food service, Madison, unmarried)
b) Household plausible? ($650/half rent in Madison?)
c) Education-occupation match?
d) Geographic references real? (Lake Mendota, St. Maria Goretti,
   Oscar Mayer, Madison College)
e) Cultural identity matches family structure?

──────────────────────────────────────────────────────────
OUTPUT:
{
  "expert_1_psychologist": {consistent: N, inconsistent: N, gaps: N},
  "expert_2_economist": {...},
  "expert_3_political_scientist": {...},
  "expert_4_demographer": {...},
  "overall_verdict": "PASS | REVISE",
  "contradictions_with_seed_data": ["..."],
  "suggested_revisions": ["..."]
}
```

## Why 4 Experts

No single expert catches everything:
- Psychologist catches personality-behavior mismatches
- Economist catches financial impossibilities
- Political Scientist catches ideological contradictions
- Demographer catches geographic/demographic errors

If it fails → re-run the interview with the revision suggestions injected.
