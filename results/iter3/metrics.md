### Iteration 3 (evidence)

| Metric | Value | Basis |
|---|---|---|
| **Detection F1** | **0.865** | 16 TP, 3 FP, 2 FN |
| Recall | 0.889 | 16/18 blockers found |
| Precision | 0.842 | 16/19 claims correct |
| Clean-posting false alarms | 0.0% | 0/8 clean postings flagged |
| Decision accuracy | 100.0% | over 24 postings |
| Evidence found | 100.0% | of 16 true positives |
| Evidence correct | 100.0% | of 16 true positives |
| Hallucinated quotes | 0.0% | of 19 claims |
| Missing evidence | 0.0% | of 19 claims |
| Parse failures | 0.0% | of 24 postings |
| Cost per task | $0.0104 | $0.25 total, 105,428 in / 3,759 out |

### Diagnostics

_Sorted worst first: the top row is the next thing to fix._

| Phrasing style | Recall | Found |
|---|---|---|
| title_body_conflict | 50% | 1/2 |
| footer | 75% | 3/4 |
| explicit | 100% | 5/5 |
| indirect | 100% | 5/5 |
| scoped_negation | 100% | 2/2 |

| Bucket | Recall | Found |
|---|---|---|
| contradiction | 75% | 3/4 |
| multi | 75% | 3/4 |
| injected | 100% | 10/10 |

| Blocker type | Recall | Found |
|---|---|---|
| onsite_location | 50% | 1/2 |
| professional_licensure | 50% | 1/2 |
| citizenship_required | 100% | 3/3 |
| compensation_floor | 100% | 1/1 |
| employment_type | 100% | 2/2 |
| relocation_required | 100% | 2/2 |
| security_clearance | 100% | 1/1 |
| shift_oncall | 100% | 1/1 |
| travel_percentage | 100% | 1/1 |
| work_authorization | 100% | 2/2 |
| years_of_experience | 100% | 1/1 |
