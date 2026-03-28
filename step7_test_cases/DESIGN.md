# Step 7: Evaluation Test Cases

## Goal
Generate daily task requests for the persona (Mary Alberti) that test whether an AI agent
can accurately find and connect fragmented data across different app logs (messenger + calendar).
Each request functions as a test case and includes a Successful Response with Evidence
referencing specific app logs.

## Focus
**Fact-Checking and Information Retrieval** rather than reasoning (for Types 1-3).
**Reasoning over cross-apps/cross-chat sessions** (for Type 4).
The goal is to see if the agent can accurately "find and connect" fragmented data across logs.

## Test Case Types

### Type 1: Simple Fact-Check (1 Case)
- Goal: Basic information retrieval from a single source
- Requirement: Solvable by referring to only one app log

### Type 2: Cross-Log Fact-Check (3 Cases)
- Goal: Connect fragmented information across multiple sources
- Requirement: Cross-reference between two or more messenger sessions OR two different apps

### Type 3: Dynamic Preference Tracking (1 Case)
- Goal: Recognize an explicit change in the persona's life
- Requirement: Identify the latest information over outdated persona data

### Type 4: Reasoning Test Cases (70 Cases)
- Goal: Reasoning over cross-apps/cross-chat sessions
- Requirement: Correctly reason over multiple sources that matter
- Objective: Agent must correctly reason over multiple sources

## Distribution Summary
| Type | Count | Focus |
|------|-------|-------|
| Type 1 | 1 | Single-source fact retrieval |
| Type 2 | 3 | Cross-log fact connection |
| Type 3 | 1 | Temporal preference change detection |
| Type 4 | 70 | Multi-source reasoning |
| **Total** | **75** | |

## Deduplication
All test cases were checked for overlap. Each tests a unique combination of:
- Different log sources (messenger session, calendar entry, or both)
- Different factual claims or reasoning chains
- Different time periods or relationships

No two test cases require the exact same evidence chain.

## Generation Prompt

```
SYSTEM:

You are generating evaluation test cases for an AI agent that has access to Mary Alberti's
messenger logs (5 conversations: Lucia/Mom, Dana, Jess, Nonna, Tony) and calendar entries
(47 entries, Jan 1 - Mar 15, 2026). The agent does NOT have access to Mary's persona
profile, interview transcript, or social circle descriptions — only the raw app logs.

For each test case, generate:
1. A natural daily task request from Mary (first person, conversational)
2. The test case type (1, 2, 3, or 4)
3. A Successful Response with specific evidence citations:
   - Messenger evidence: cite conversation partner, date, and time
   - Calendar evidence: cite date, time, and event title
4. The reasoning required (what connections must the agent make)

RULES:
- Test cases must be solvable ONLY from the app logs provided
- Evidence must reference SPECIFIC entries (dates, times, quotes)
- Each test case must be unique (no duplicate evidence chains)
- Type 1: exactly 1 app log source
- Type 2: exactly 2+ sources (cross-log)
- Type 3: must involve a temporal change in behavior/preference
- Type 4: must require reasoning across multiple sources

OUTPUT FORMAT:
{
  "test_cases": [
    {
      "id": "TC-001",
      "type": 1,
      "category": "health|career|financial|family|religion|social|scheduling|preference",
      "request": "Mary's spoken request",
      "successful_response": {
        "answer": "The correct answer",
        "evidence": [
          {"source": "messenger|calendar", "reference": "specific log entry"}
        ],
        "reasoning": "What connections were needed"
      }
    }
  ]
}
```

## Verification
Each test case was verified against the actual messenger_output.json and calendar_output.json
to ensure all cited evidence exists in the logs.
