# Step 2: Stanford Interview → Rich Persona

## What I Did

Professor said to use the interview script from page 60 of the Stanford paper
(Park et al. 2024, Table 7). The paper has 99 questions across ~120 minutes.
Professor said to **select questions that sum to ~30 minutes** — the paper shows
20% of the interview time is sufficient to derive an enriched persona (Table 8:
85% normalized accuracy with interviews vs 71% with demographics alone).

I used Claude to help me go through Table 7 and select questions that cover
diverse perspectives — not just demographics, but health, relationships, daily
routine, religion, and finances — since those all feed into later steps.

## Selected Questions (~30 min from Table 7)

**BLOCK 1 — LIFE STORY (625 sec / 10.4 min)**
Q1: "Tell me the story of your life. Start from the beginning — from your
childhood, to education, to family and relationships, and to any major
life events you may have had."
→ Feeds: family structure (Step 3), cultural identity, career path

**BLOCK 2 — FAMILY & RELATIONSHIPS (415 sec / 6.9 min)**
Q2: "Let me ask you about the important people in your life. If you have a
partner or children, tell me about them." (310s)
Q3: "Tell me about your immediate family that you haven't already mentioned." (25s)
Q4: "Tell me about your friends, romantic partners, or anyone outside your
family who has been an important part of your life." (80s)
→ Feeds: social circles (Step 3), messenger logs (Step 4)

**BLOCK 3 — DAILY ROUTINE (105 sec / 1.75 min)**
Q5: "How do your days vary across a typical week?"
→ Feeds: calendar entries (Step 5)

**BLOCK 4 — HEALTH (225 sec / 3.75 min)**
Q6: "How would you describe your general health these days?" (80s)
Q7: "What makes it easy or difficult to stay healthy?" (65s)
Q8: "Were there any big health events in the past couple of years?" (80s)
→ Feeds: hidden health facts / needles (Step 4)

**BLOCK 5 — RELIGION & WELL-BEING (270 sec / 4.5 min)**
Q9: "Tell me about your religion or spirituality, if that's a part of your life." (155s)
Q10: "How have you been feeling over the past year?" (115s)
→ Feeds: indirect religion evidence in calendar/messenger

**BLOCK 6 — FINANCES (155 sec / 2.6 min)**
Q11: "What were your biggest expenses last month?" (50s)
Q12: "How do you feel about your overall financial situation?" (105s)
→ Feeds: financial constraint hidden fact

**TOTAL: 1,795 sec ≈ 30 minutes**

## Generation Prompt

```
SYSTEM:

You are an AI interviewer conducting a qualitative life-history interview
adapted from the American Voices Project protocol (Park et al., 2024).

RULES:
1. Ask each question as written, then ask 2-3 natural follow-ups before
   moving to the next question.
2. Answers MUST be consistent with the seed data.
3. Answers: 3-6 sentences, conversational, behavioral details.
4. Sensitive topics — describe BEHAVIORS, never labels:
   - NOT "I have diabetes" → "I check my levels three times a day"
   - NOT "I'm Catholic" → "I still go to Mass most Sundays at
     St. Maria Goretti"
5. Voice: 28-year-old, high school education, food service, Midwestern
   Italian-American.

SEED DATA:
[All of Mary's NVIDIA fields from Step 1]

QUESTIONS: [Q1-Q12 above]

OUTPUT:
{
  "interview_transcript": [
    {"question": "...", "answer": "...", "follow_ups": [...]}
  ],
  "extracted_profile": {
    "interests": [...],
    "food_preferences": "...",
    "sports_teams": [...],
    "health_conditions": [{"condition": "...", "behavioral_clues": [...]}],
    "religion": {"stated": "...", "behavioral_clues": [...]},
    "political_leaning": {"stated": "...", "behavioral_clues": [...]},
    "financial_constraint": {"monthly_leisure_limit": "$XXX"},
    "personality_behaviors": {...},
    "daily_routines": [...],
    "personal_conflicts": [...]
  }
}
```
