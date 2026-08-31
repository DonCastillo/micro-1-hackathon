> **A removed branch. Four separate group checks, merged - it recovered a second blocker the single pass missed, but cost 2.5x and lost more precision than it gained recall.**
>
> Source: `runs/20260831-062911_iter2/jd_04.json`

---

# Trajectory: jd_04

5 steps, 20.084s, $0.0135

## 1. check_legal

_13.463s · 1037 in / 185 out_

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

# Data Engineer
Los Angeles, CA (hybrid, two days per week in office)

## About Fernwood Health
Fernwood builds clinical decision support for outpatient practices. The data team turns
messy EHR exports into something clinicians can act on.

Applicants must qualify as a U.S. Person as defined by ITAR (22 CFR 120.15).

## What you'll do
- Build and maintain ingestion pipelines from partner health systems
- Model clinical data into analytics-ready tables
- Own data quality checks and the alerting around them
- Work with clinical informaticists to validate transformations

## Requirements
- 4+ years in data engineering
- Strong SQL and Python
- Experience with a modern orchestration tool such as Airflow, Dagster, or Prefect
- Care about data quality and lineage
- This is a W2 contract position; corp-to-corp and third-party candidates will not be considered.

## Nice to have
- Experience with healthcare data formats such as HL7 or FHIR
- dbt experience
- Familiarity with columnar warehouses

## Benefits
- Health, dental, and vision coverage
- Three weeks of paid time off, increasing with tenure
- Professional development budget
- Commuter benefits

## Equal opportunity
Fernwood Health is an equal opportunity employer. We consider all qualified applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, or veteran status.

Check this posting for legal disqualifiers only. Ignore every other kind of
problem — other checks cover those.

The legal conditions, and which part of my background decides each one:

- work_authorization (legal): Role does not offer visa sponsorship. Decided by the profile field `work_auth`.
- citizenship_required (legal): Employment restricted to U.S. citizens or ITAR-defined U.S. Persons. Decided by the profile field `citizenship`.
- security_clearance (legal): An active government security clearance is required at time of application. Decided by the profile field `clearance`.
- professional_licensure (legal): A named professional license is required (regulated / safety-critical work). Decided by the profile field `licenses`.

A condition only disqualifies me if the posting makes it a firm requirement and
my background fails it. A preference is not a requirement.

End your answer with one line exactly:

BLOCKERS: comma-separated ids from the list above, or NONE
```

**Output**

```
BLOCKERS: citizenship_required
```

## 2. check_logistics

_1.933s · 1090 in / 88 out_

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

# Data Engineer
Los Angeles, CA (hybrid, two days per week in office)

## About Fernwood Health
Fernwood builds clinical decision support for outpatient practices. The data team turns
messy EHR exports into something clinicians can act on.

Applicants must qualify as a U.S. Person as defined by ITAR (22 CFR 120.15).

## What you'll do
- Build and maintain ingestion pipelines from partner health systems
- Model clinical data into analytics-ready tables
- Own data quality checks and the alerting around them
- Work with clinical informaticists to validate transformations

## Requirements
- 4+ years in data engineering
- Strong SQL and Python
- Experience with a modern orchestration tool such as Airflow, Dagster, or Prefect
- Care about data quality and lineage
- This is a W2 contract position; corp-to-corp and third-party candidates will not be considered.

## Nice to have
- Experience with healthcare data formats such as HL7 or FHIR
- dbt experience
- Familiarity with columnar warehouses

## Benefits
- Health, dental, and vision coverage
- Three weeks of paid time off, increasing with tenure
- Professional development budget
- Commuter benefits

## Equal opportunity
Fernwood Health is an equal opportunity employer. We consider all qualified applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, or veteran status.

Check this posting for logistics disqualifiers only. Ignore every other kind of
problem — other checks cover those.

The logistics conditions, and which part of my background decides each one:

- onsite_location (logistics): Role requires working on-site in a specific location. Decided by the profile field `location`.
- relocation_required (logistics): Relocation is a condition of employment. Decided by the profile field `willing_to_relocate`.
- timezone_overlap (logistics): Requires sustained working-hours overlap with a specific time zone. Decided by the profile field `timezone`.
- travel_percentage (logistics): Required travel exceeds what the candidate accepts. Decided by the profile field `max_travel_pct`.
- shift_oncall (logistics): Requires overnight, weekend, or non-standard shift coverage. Decided by the profile field `accepts_night_shift`.

A condition only disqualifies me if the posting makes it a firm requirement and
my background fails it. A preference is not a requirement.

End your answer with one line exactly:

BLOCKERS: comma-separated ids from the list above, or NONE
```

**Output**

```
Location: Los Angeles, CA hybrid (2 days/week) — matches candidate's LA location, no relocation needed. No timezone conflict, no unusual travel requirement, no shift/on-call requirement mentioned.

BLOCKERS: NONE
```

## 3. check_credentials

_1.694s · 999 in / 72 out_

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

# Data Engineer
Los Angeles, CA (hybrid, two days per week in office)

## About Fernwood Health
Fernwood builds clinical decision support for outpatient practices. The data team turns
messy EHR exports into something clinicians can act on.

Applicants must qualify as a U.S. Person as defined by ITAR (22 CFR 120.15).

## What you'll do
- Build and maintain ingestion pipelines from partner health systems
- Model clinical data into analytics-ready tables
- Own data quality checks and the alerting around them
- Work with clinical informaticists to validate transformations

## Requirements
- 4+ years in data engineering
- Strong SQL and Python
- Experience with a modern orchestration tool such as Airflow, Dagster, or Prefect
- Care about data quality and lineage
- This is a W2 contract position; corp-to-corp and third-party candidates will not be considered.

## Nice to have
- Experience with healthcare data formats such as HL7 or FHIR
- dbt experience
- Familiarity with columnar warehouses

## Benefits
- Health, dental, and vision coverage
- Three weeks of paid time off, increasing with tenure
- Professional development budget
- Commuter benefits

## Equal opportunity
Fernwood Health is an equal opportunity employer. We consider all qualified applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, or veteran status.

Check this posting for credentials disqualifiers only. Ignore every other kind of
problem — other checks cover those.

The credentials conditions, and which part of my background decides each one:

- degree_required (credentials): A minimum formal degree level is mandatory, with no experience substitution. Decided by the profile field `degree`.
- certification_required (credentials): A named professional certification must be active at time of hire. Decided by the profile field `certifications`.
- years_of_experience (credentials): A hard minimum years-of-experience floor, stated as required rather than preferred. Decided by the profile field `years_experience`.

A condition only disqualifies me if the posting makes it a firm requirement and
my background fails it. A preference is not a requirement.

End your answer with one line exactly:

BLOCKERS: comma-separated ids from the list above, or NONE
```

**Output**

```
Degree required: not specified — no disqualifier. Certification required: none listed — no disqualifier. Years of experience: requires 4+, candidate has 6 — meets requirement.

BLOCKERS: NONE
```

## 4. check_terms

_2.992s · 952 in / 194 out_

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

# Data Engineer
Los Angeles, CA (hybrid, two days per week in office)

## About Fernwood Health
Fernwood builds clinical decision support for outpatient practices. The data team turns
messy EHR exports into something clinicians can act on.

Applicants must qualify as a U.S. Person as defined by ITAR (22 CFR 120.15).

## What you'll do
- Build and maintain ingestion pipelines from partner health systems
- Model clinical data into analytics-ready tables
- Own data quality checks and the alerting around them
- Work with clinical informaticists to validate transformations

## Requirements
- 4+ years in data engineering
- Strong SQL and Python
- Experience with a modern orchestration tool such as Airflow, Dagster, or Prefect
- Care about data quality and lineage
- This is a W2 contract position; corp-to-corp and third-party candidates will not be considered.

## Nice to have
- Experience with healthcare data formats such as HL7 or FHIR
- dbt experience
- Familiarity with columnar warehouses

## Benefits
- Health, dental, and vision coverage
- Three weeks of paid time off, increasing with tenure
- Professional development budget
- Commuter benefits

## Equal opportunity
Fernwood Health is an equal opportunity employer. We consider all qualified applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, or veteran status.

Check this posting for terms disqualifiers only. Ignore every other kind of
problem — other checks cover those.

The terms conditions, and which part of my background decides each one:

- employment_type (terms): Engagement model excludes the candidate's acceptable arrangements. Decided by the profile field `employment_types`.
- compensation_floor (terms): The top of the posted salary band falls below the candidate's minimum. Decided by the profile field `comp_floor`.

A condition only disqualifies me if the posting makes it a firm requirement and
my background fails it. A preference is not a requirement.

End your answer with one line exactly:

BLOCKERS: comma-separated ids from the list above, or NONE
```

**Output**

```
The posting states "This is a W2 contract position" as a firm requirement, but the candidate's profile only lists "Full-time employee" as an acceptable employment type. This is a disqualifying mismatch.

No salary information is provided in the posting, so the compensation_floor condition cannot be evaluated as a disqualifier.

BLOCKERS: employment_type
```

## 5. merge _(event)_

merged 4 group checks -> ['citizenship_required', 'employment_type']

## Result

```json
{
  "verdict": "SKIP",
  "blockers": [
    {
      "type": "citizenship_required",
      "evidence": ""
    },
    {
      "type": "employment_type",
      "evidence": ""
    }
  ],
  "caveats": []
}
```
