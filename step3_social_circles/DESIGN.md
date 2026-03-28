# Step 3: Social Circles — Miles' Persona-to-Persona

## What I Did

Professor said to use Miles' approach for social circles. Miles used the **PersonaHub
paper** (Tencent AI Lab 2024, arXiv 2406.20094) — specifically the **Persona-to-Persona
generation** method: start with a seed persona, ask "who is in close relationship with
this persona?", and the LLM generates circle members grounded in that person's context.

Professor's instructions: identify 5 closest people from family, friends, colleagues.
For each: name, demographics, background, how they met, shared interests, why they're
close, and what they've discussed in texts recently.

## Generation Prompt

```
SYSTEM:

Persona-to-Persona generation (PersonaHub, 2024). Given a seed persona,
generate the 5 closest people by deriving new personas through
interpersonal relationships.

MARY'S PERSONA: {from Step 2}
INTERVIEW TRANSCRIPT: {transcript}

For each of 5 people, provide:

1. DEMOGRAPHICS: name, age, gender, occupation, location, education,
   relationship to Mary

2. BACKGROUND: how they met, years known, why they are close

3. MINI-PROFILE: personality traits, interests, how they text
   (slang? full sentences? emojis?)

4. SHARED ACTIVITIES: what they do together, how often

5. RECENT TEXT TOPICS: what they've been texting about (past 2-3 months)

CONSTRAINTS:
- At least 1 family, 1 non-work friend, 1 colleague
- All plausible for Madison, WI
- Cite interview evidence for each (e.g. "Mary said 'I talk to
  my mom almost every day'")

OUTPUT:
{
  "social_circle": [
    {
      "name": "...",
      "relationship": "...",
      "demographics": {...},
      "background": {...},
      "personality_mini_profile": {...},
      "shared_activities": [...],
      "recent_text_topics": [...],
      "evidence_from_interview": "Mary said '...'"
    }
  ]
}
```

## Expected Output

| # | Name | Relationship | Interview Evidence |
|---|------|-------------|-------------------|
| 1 | Rosa Alberti, 56 | Mother | "I talk to my mom almost every day" |
| 2 | Jessica Torres, 28 | Best friend / roommate | "My best friend since middle school is Jess" |
| 3 | Danny Kowalski, 31 | Coworker | "My coworker Danny... like a brother at work" |
| 4 | Tony Alberti, 32 | Brother | "My brother Tony... comes back for Packers games" |
| 5 | Lisa Chen, 30 | Running club friend | Madison Runners Club, sees Mary 3x/week |

## Questions from Professor

**Should parents be included?** Yes — Mary talks to her mom daily.

**How rich for Step 4?** Rich enough to generate their side of text conversations
(personality, communication style, shared context, current topics).

**Interview each circle member?** Not full interviews — the mini-profile from
Persona-to-Persona is enough for generating their text voice.

## Verify

Check that the 5 people don't contradict the persona from Step 2.
