### Baseline (run 2)

| Metric | Value | Basis |
|---|---|---|
| **Detection F1** | **0.850** | 17 TP, 5 FP, 1 FN |
| Recall | 0.944 | 17/18 blockers found |
| Precision | 0.773 | 17/22 claims correct |
| Clean-posting false alarms | 0.0% | 0/8 clean postings flagged |
| Decision accuracy | 100.0% | over 24 postings |
| Evidence found | 0.0% | of 17 true positives |
| Evidence correct | 0.0% | of 17 true positives |
| Hallucinated quotes | 0.0% | of 22 claims |
| Missing evidence | 100.0% | of 22 claims |
| Parse failures | 0.0% | of 24 postings |
| Cost per task | $0.0049 | $0.12 total, 20,657 in / 7,528 out |

### Diagnostics

_Sorted worst first: the top row is the next thing to fix._

| Phrasing style | Recall | Found |
|---|---|---|
| footer | 75% | 3/4 |
| explicit | 100% | 5/5 |
| indirect | 100% | 5/5 |
| scoped_negation | 100% | 2/2 |
| title_body_conflict | 100% | 2/2 |

| Bucket | Recall | Found |
|---|---|---|
| multi | 75% | 3/4 |
| contradiction | 100% | 4/4 |
| injected | 100% | 10/10 |

| Blocker type | Recall | Found |
|---|---|---|
| professional_licensure | 50% | 1/2 |
| citizenship_required | 100% | 3/3 |
| compensation_floor | 100% | 1/1 |
| employment_type | 100% | 2/2 |
| onsite_location | 100% | 2/2 |
| relocation_required | 100% | 2/2 |
| security_clearance | 100% | 1/1 |
| shift_oncall | 100% | 1/1 |
| travel_percentage | 100% | 1/1 |
| work_authorization | 100% | 2/2 |
| years_of_experience | 100% | 1/1 |
