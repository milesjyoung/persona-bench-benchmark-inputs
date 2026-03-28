# Step 4: Messenger Logs

## What I Did

Professor referenced these papers for synthesizing conversations:
- **SimsChat** ("Crafting Customisable Characters with LLMs")
- **PICLe** ("Persona In-Context Learning")
- **SPP** ("Solo Performance Prompting" — multi-persona self-collaboration)
- **Sequential-NIAH** ("Needle-In-A-Haystack" — inserting hidden facts in long context)

Professor specifically asked: do we need "real temporal order needles" and "real
logical order needles" in addition to synthetic temporal needles? I used Claude to
research Sequential-NIAH and found there are 3 needle types we should use.

The process is two phases: generate short conversation snippets with embedded
preferences, then merge them into a long history with filler.

## Three Needle Types (from Sequential-NIAH)

| Type | What It Is | Mary Example |
|---|---|---|
| **Synthetic temporal** | Facts with dates in order | Feb 3 "doc appointment" → Feb 5 "low-sodium recipes?" → Feb 20 "numbers better!" |
| **Real temporal** | Cause → effect chain | Applied for supervisor → interview Thursday → still waiting |
| **Real logical** | Behavior pattern → inference | "not Red Lobster" + "pasta salad at fish fry" + "shrimp smell" = shellfish allergy |

## Snippet Generation Prompt

```
SYSTEM:

Generate text message snippets between Mary Alberti and one circle member.
Each snippet: 2-6 turns. IMPLICITLY reveal 1-2 preferences — never stated directly.

MARY'S PERSONA: {from Step 2}
PARTNER: {from Step 3}
FACTS TO EMBED: {preferences and hidden facts}

RULES:

1. IMPLICIT ONLY
   GOOD: "Can we skip Red Lobster? Last time I had a bad reaction"
   BAD:  "I can't go because I'm allergic to shellfish"

2. VOICE
   - Mary: casual, "lol", "omg", Midwestern
   - Partner: their own voice from mini-profile
   - Texts with mom ≠ texts with best friend

3. FEEL REAL
   - Small talk, emoji, topic changes, planning logistics
   - Not every message carries a needle

4. NEEDLE CHAINS
   Each hidden fact: 2-3 messages across DIFFERENT conversations.

   Temporal chain (hypertension):
     Feb 3, to Mom: "doc wants me to watch my salt"
     Feb 10, to Jess: "know any good low-sodium recipes?"
     Feb 22, to Mom: "numbers are better!"

   Logical chain (shellfish):
     To Jess: "can we not do seafood for girls night?"
     To Mom: "I'll bring pasta salad to the fish fry"
     To Danny: "shrimp smell made me weird lol"

Generate 3-5 snippets per circle member.

OUTPUT:
{
  "snippets": [
    {
      "date": "2026-01-XX",
      "embedded_facts": ["..."],
      "needle_type": "synthetic_temporal | real_temporal | real_logical",
      "messages": [
        {"sender": "Mary", "text": "...", "time": "HH:MM"},
        {"sender": "Partner", "text": "...", "time": "HH:MM"}
      ]
    }
  ]
}
```

## Merging into Long History

1. Sort all snippets chronologically
2. Add filler messages between them (logistics, memes, "running tomorrow?")
3. Filler buries the needles — like real text history
4. One long array per relationship

## Verification Prompt

```
SYSTEM:

Verify messenger logs against persona (Step 2) and circles (Step 3).

1. PERSONA: Voice matches? Hidden facts NEVER stated directly?
2. RELATIONSHIP: Tone matches closeness? Activities match Step 3?
3. TEMPORAL: Needle chains in order? No contradictions across conversations?
4. NEEDLE INTEGRITY: Each fact has 2-3 refs? Inferable but never stated?
5. NATURALNESS: Feels real? Enough filler? Both sides feel like people?

OUTPUT: {verdict per check, fixes if needed}
```
