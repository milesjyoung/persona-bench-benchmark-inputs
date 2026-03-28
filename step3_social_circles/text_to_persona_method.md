# Text-to-Persona Method Usage

## Professor's Requirement
> "Use both methods of text to Persona and Persona-to-Persona."

## How Both PersonaHub Methods Are Used in Our Pipeline

PersonaHub (Tencent AI Lab, 2024) defines two core methods for persona generation:

### Method 1: Text-to-Persona (Used in Steps 1→2)

**Definition (from paper):** Given a text, derive the persona of someone who would have written or said it.

**Our usage:** The NVIDIA Nemotron-Personas-USA dataset provides narrative text fields
(professional_persona, sports_persona, arts_persona, etc.) that describe Mary Alberti.
In Step 2, we apply Text-to-Persona by:

1. **Input text:** NVIDIA's 10 narrative fields describing Mary's behaviors, interests, and background
2. **Persona derivation:** The Stanford interview prompt takes this text and derives a RICHER
   persona — surfacing implicit traits (anxiety when routine is disrupted), hidden facts
   (borderline hypertension, shellfish sensitivity), social relationships (Dana, Jess, Nonna),
   and financial constraints ($150/month leisure limit) that are not in the original text but
   are consistent with the persona described by it.
3. **Output:** A fully enriched persona (interview_output.json) with 12 Q&A pairs and
   an extracted profile covering interests, health, religion, finances, personality, routines,
   and conflicts.

**Why this is Text-to-Persona:** We start with TEXT (NVIDIA narrative descriptions) and derive
a PERSONA (enriched interview profile). The LLM reads what kind of person this text describes
and generates a consistent, detailed persona from it.

**Prompt mapping:**
```
PersonaHub Text-to-Persona:  "Given this text, who is the persona that wrote/said it?"
Our Step 2 adaptation:       "Given these NVIDIA narrative descriptions, conduct an interview
                              as this persona and derive their enriched profile."
```

### Method 2: Persona-to-Persona (Used in Step 3)

**Definition (from paper):** Given an existing persona, derive new personas through
interpersonal relationships ("Who is in close relationship with this persona?").

**Our usage (Miles' adaptation):** Starting from Mary's enriched persona (Step 2 output),
we generate her 5 closest social circle members:

1. **Input persona:** Mary Alberti's full enriched profile
2. **Relationship derivation:** The LLM generates 5 new personas (Lucia, Dana, Jess,
   Nonna, Tony) specifically from Mary's life context — each with demographics,
   personality, communication style, shared activities, and recent conversation topics.
3. **Output:** social_circle_output.json with 5 fully characterized circle members.

**Why this is Persona-to-Persona:** We start with a PERSONA (Mary) and derive NEW PERSONAS
(her social circle) through interpersonal relationships. The generated people are coherent
with the seed persona by construction.

**Prompt mapping:**
```
PersonaHub Persona-to-Persona:  "Who is in close relationship with this persona?"
Our Step 3 adaptation:          "Given Mary's enriched persona and interview transcript,
                                 identify her 5 closest people and generate their profiles."
```

## Summary

| PersonaHub Method | Our Pipeline Step | Input → Output |
|---|---|---|
| **Text-to-Persona** | Step 1 → Step 2 | NVIDIA narrative text → Enriched persona via interview |
| **Persona-to-Persona** | Step 2 → Step 3 | Mary's persona → 5 social circle personas |

Both methods from the PersonaHub paper are used sequentially: Text-to-Persona creates the
seed persona, and Persona-to-Persona expands her social world.

## References
- PersonaHub: "Scaling Synthetic Data Creation with 1,000,000,000 Personas" (Tencent AI Lab, 2024)
- Section 3.1: Text-to-Persona method
- Section 3.2: Persona-to-Persona method
- Miles' adaptation notes (Meeting 3/12/26)
