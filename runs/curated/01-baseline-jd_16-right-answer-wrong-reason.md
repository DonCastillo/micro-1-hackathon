> **The dominant failure mode. Correct SKIP verdict, both real blockers missed, a third invented, and nothing cited so nobody could tell.**
>
> Source: `runs/20260831-030332_baseline/jd_16.json`

---

# Trajectory: jd_16

1 steps, 2.298s, $0.0033

## 1. ask

_2.296s · 888 in / 154 out_

**System**

```
You are helping someone decide which jobs are worth applying to.
```

**User**

```
Here is my background:

label: synthetic-candidate-01
role_target: Software Engineer
work_auth: requires_sponsorship
citizenship: CA
clearance: none
licenses: []
location:
  city: Los Angeles
  state: CA
  country: US
willing_to_relocate: false
timezone: America/Los_Angeles
utc_offset: -8
max_travel_pct: 25
accepts_night_shift: false
degree: Bachelor's
certifications: []
years_experience: 6
employment_types:
- Full-time employee
comp_floor: 140000

Here is a job posting:

# Platform Engineer
Remote (United States)

## About Northbeam
Northbeam runs analytics infrastructure for mid-market retailers. The platform team keeps
the paved road that our forty product engineers build on.

Applicants must qualify as a U.S. Person as defined by ITAR (22 CFR 120.15).

## What you'll do
- Maintain and extend our Kubernetes-based deployment platform
- Reduce build and deploy times across roughly sixty services
- Improve observability so teams can debug their own incidents
- Write internal tooling that product engineers actually want to use

## Requirements
- 5+ years in infrastructure, platform, or backend engineering
- Strong Kubernetes and container fundamentals
- Infrastructure as code, ideally Terraform
- One of Go, Python, or Rust

## Nice to have
- Experience running Postgres at scale
- Familiarity with OpenTelemetry
- Background in developer experience work

## Benefits
- Health, dental, and vision coverage
- Unlimited paid time off with a four-week minimum
- Learning stipend
- Home office budget

## Equal opportunity
Northbeam is an equal opportunity employer. We consider all qualified applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, or veteran status.

Licensure will be verified with the state board prior to an offer being extended.

Should I apply? If anything in this posting disqualifies me, tell me what.

End your answer with two lines exactly:

VERDICT: APPLY or SKIP
BLOCKERS: comma-separated labels from the list below, or NONE

The labels:
- certification_required
- citizenship_required
- compensation_floor
- degree_required
- employment_type
- onsite_location
- professional_licensure
- relocation_required
- security_clearance
- shift_oncall
- timezone_overlap
- travel_percentage
- work_authorization
- years_of_experience
```

**Output**

```
This posting requires applicants to qualify as a "U.S. Person" under ITAR (22 CFR 120.15), which includes U.S. citizens, permanent residents, and certain protected individuals—but excludes those requiring visa sponsorship, like yourself as a Canadian citizen needing sponsorship. This is a hard disqualifier regardless of your strong fit on skills/experience.

VERDICT: SKIP
BLOCKERS: work_authorization
```

## Result

```json
{
  "verdict": "SKIP",
  "blockers": [
    {
      "type": "work_authorization",
      "evidence": ""
    }
  ],
  "caveats": []
}
```
