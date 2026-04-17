1. Ubuntu vm with git and python (file)
2. Download https://github.com/milesjyoung/persona-bench-benchmark-inputs.git git repo
3. download openclaw (https://docs.openclaw.ai/install):
    * quickstart and set keys...you will need model with embedding provided
    * Skip pretty much everything else
    * When hatch in tui: it gives you the im awake prompt give it-- "I am {persona_name}, you are OC the helpful and down to business personal agent." Any other prompts just respond briefly (the setup prompts tend to change) 
    * Setup done!!!
4. Move generated/{persona}/..._raw_app_logs.txt content into main/memory/YYYY-MM-DD.md for current day
5. add to .openclaw/workspace/AGENTS.md:
```
## Extra Instructions
When answering questions about the user’s life, schedule, habits, relationships, or recent events, check memory for relevant messenger and calendar context first.

Treat the stored app-log memory as the primary source of truth for personal questions.
Use only information supported by retrieved memory.
Do not invent facts.
If memory is insufficient, say so briefly.

When the user includes a test case id, always return valid JSON only in exactly this shape:
{
  "test_case_id": "TC-01",
  "answer": "short natural-language answer",
  "confidence": "high|medium|low",
  "evidence": [
    {
      "source": "messenger|calendar|memory",
      "reference": "brief citation with date/time or event title"
    }
  ]
}

```
6. run python3 $PB_RUNNER \
  --questions-file $Q_FILE= \
  --output-file $O_FIL
