### Iteration 1 (definitions)

| Metric | Value | Basis |
|---|---|---|
| **Detection F1** | **0.914** | 16 TP, 1 FP, 2 FN |
| Recall | 0.889 | 16/18 blockers found |
| Precision | 0.941 | 16/17 claims correct |
| Clean-posting false alarms | 0.0% | 0/8 clean postings flagged |
| Decision accuracy | 100.0% | over 24 postings |
| Evidence found | 0.0% | of 16 true positives |
| Evidence correct | 0.0% | of 16 true positives |
| Hallucinated quotes | 0.0% | of 17 claims |
| Missing evidence | 100.0% | of 17 claims |
| Parse failures | 0.0% | of 24 postings |
| Cost per task | $0.0050 | $0.12 total, 35,369 in / 4,845 out |

### Diagnostics

_Sorted worst first: the top row is the next thing to fix._

| Phrasing style | Recall | Found |
|---|---|---|
| footer | 75% | 3/4 |
| explicit | 80% | 4/5 |
| indirect | 100% | 5/5 |
| scoped_negation | 100% | 2/2 |
| title_body_conflict | 100% | 2/2 |

| Bucket | Recall | Found |
|---|---|---|
| multi | 50% | 2/4 |
| contradiction | 100% | 4/4 |
| injected | 100% | 10/10 |

| Blocker type | Recall | Found |
|---|---|---|
| employment_type | 50% | 1/2 |
| professional_licensure | 50% | 1/2 |
| citizenship_required | 100% | 3/3 |
| compensation_floor | 100% | 1/1 |
| onsite_location | 100% | 2/2 |
| relocation_required | 100% | 2/2 |
| security_clearance | 100% | 1/1 |
| shift_oncall | 100% | 1/1 |
| travel_percentage | 100% | 1/1 |
| work_authorization | 100% | 2/2 |
| years_of_experience | 100% | 1/1 |
