### Baseline (run 1)

| Metric | Value | Basis |
|---|---|---|
| **Detection F1** | **0.789** | 15 TP, 5 FP, 3 FN |
| Recall | 0.833 | 15/18 blockers found |
| Precision | 0.750 | 15/20 claims correct |
| Clean-posting false alarms | 0.0% | 0/8 clean postings flagged |
| Decision accuracy | 100.0% | over 24 postings |
| Evidence found | 0.0% | of 15 true positives |
| Evidence correct | 0.0% | of 15 true positives |
| Hallucinated quotes | 0.0% | of 20 claims |
| Missing evidence | 100.0% | of 20 claims |
| Parse failures | 0.0% | of 24 postings |
| Cost per task | $0.0051 | $0.12 total, 20,657 in / 8,018 out |

### Diagnostics

_Sorted worst first: the top row is the next thing to fix._

| Phrasing style | Recall | Found |
|---|---|---|
| title_body_conflict | 50% | 1/2 |
| footer | 75% | 3/4 |
| indirect | 80% | 4/5 |
| explicit | 100% | 5/5 |
| scoped_negation | 100% | 2/2 |

| Bucket | Recall | Found |
|---|---|---|
| multi | 50% | 2/4 |
| contradiction | 75% | 3/4 |
| injected | 100% | 10/10 |

| Blocker type | Recall | Found |
|---|---|---|
| onsite_location | 50% | 1/2 |
| professional_licensure | 50% | 1/2 |
| citizenship_required | 67% | 2/3 |
| compensation_floor | 100% | 1/1 |
| employment_type | 100% | 2/2 |
| relocation_required | 100% | 2/2 |
| security_clearance | 100% | 1/1 |
| shift_oncall | 100% | 1/1 |
| travel_percentage | 100% | 1/1 |
| work_authorization | 100% | 2/2 |
| years_of_experience | 100% | 1/1 |
