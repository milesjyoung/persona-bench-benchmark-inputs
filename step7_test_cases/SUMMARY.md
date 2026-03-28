# Step 7: Evaluation Test Cases — Summary

## Results

**Total test cases: 75** (all with Successful Response + Evidence)

### By Type
| Type | Count | Description |
|------|-------|-------------|
| Type 1: Simple Fact-Check | 1 | Single-source retrieval (calendar lookup) |
| Type 2: Cross-Log Fact-Check | 3 | Cross-reference messenger ↔ calendar or multiple messenger sessions |
| Type 3: Dynamic Preference Tracking | 1 | Temporal dietary change tracking (BP/sodium progression Jan→Mar) |
| Type 4: Reasoning | 70 | Multi-source reasoning across apps and chat sessions |

### By Category (Type 4 breakdown)
| Category | Count | Examples |
|----------|-------|---------|
| Social | 13 | Relationship ranking, communication styles, inside jokes |
| Family | 12 | Nonna's health tracking, Tony's engagement, family dynamics |
| Scheduling | 12 | Sunday patterns, work shift analysis, run transitions |
| Preference | 11 | Restaurant criteria, cooking repertoire, coffee spots |
| Health | 10 | BP timeline, shellfish avoidance, family health patterns |
| Career | 7 | Promotion timeline, Kaylee lessons, Sun Prairie info containment |
| Religion | 5 | Lent observance, Mass attendance rate, Easter planning |
| Financial | 5 | Budget evidence, diner savings, half-marathon affordability |

### Deduplication
All 75 test cases have unique IDs (TC-001 through TC-075) and unique evidence chains.
No two cases require the exact same reasoning path.

### Evidence Sources Used
- **Messenger logs:** All 5 conversations (CONV-001 through CONV-005) referenced
- **Calendar entries:** 30+ of 47 entries referenced across test cases
- **Cross-app references:** 45+ test cases require both messenger and calendar data

### Key Test Case Highlights

**TC-005 (Type 3):** Tracks Mary's dietary shift from unmonitored eating → doctor visit (Jan 22) → sodium reduction + meal prep (Feb 12) → improved BP numbers (Mar 12). Requires reasoning across 3 conversations and 1 calendar entry.

**TC-007 (Type 4):** Reconstructs full career promotion timeline from 4 conversations + 2 calendar entries spanning Jan 14 to Mar 18.

**TC-003 (Type 2):** Cross-references ServSafe mentions across Jess, Dana, and Tony conversations + calendar to verify information consistency.

**TC-009 (Type 4):** Connects shellfish avoidance behavior across Mom, Nonna, and Tony conversations spanning 3 months.
