### Iteration 4 (verification)

| Metric | Value | Basis |
|---|---|---|
| **Detection F1** | **0.909** | 15 TP, 0 FP, 3 FN |
| Recall | 0.833 | 15/18 blockers found |
| Precision | 1.000 | 15/15 claims correct |
| Clean-posting false alarms | 0.0% | 0/8 clean postings flagged |
| Decision accuracy | 91.7% | over 24 postings |
| Evidence found | 100.0% | of 15 true positives |
| Evidence correct | 100.0% | of 15 true positives |
| Hallucinated quotes | 0.0% | of 15 claims |
| Missing evidence | 0.0% | of 15 claims |
| Parse failures | 0.0% | of 24 postings |
| Cost per task | $0.0047 | $0.11 total, 41,901 in / 2,881 out |

### Diagnostics

_Sorted worst first: the top row is the next thing to fix._

| Phrasing style | Recall | Found |
|---|---|---|
| scoped_negation | 50% | 1/2 |
| footer | 75% | 3/4 |
| explicit | 80% | 4/5 |
| indirect | 100% | 5/5 |
| title_body_conflict | 100% | 2/2 |

| Bucket | Recall | Found |
|---|---|---|
| contradiction | 75% | 3/4 |
| multi | 75% | 3/4 |
| injected | 90% | 9/10 |

| Blocker type | Recall | Found |
|---|---|---|
| compensation_floor | 0% | 0/1 |
| security_clearance | 0% | 0/1 |
| professional_licensure | 50% | 1/2 |
| citizenship_required | 100% | 3/3 |
| employment_type | 100% | 2/2 |
| onsite_location | 100% | 2/2 |
| relocation_required | 100% | 2/2 |
| shift_oncall | 100% | 1/1 |
| travel_percentage | 100% | 1/1 |
| work_authorization | 100% | 2/2 |
| years_of_experience | 100% | 1/1 |
