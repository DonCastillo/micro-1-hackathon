> **The grounding filter working. The model claimed a blocker and quoted a sentence that is not in the posting; the mechanical check dropped it. No API call.**
>
> Source: `runs/20260831-083928_final/jd_18.json`

---

# Trajectory: jd_18

2 steps, 12.951s, $0.0040

## 1. detect

_12.949s · 1598 in / 79 out_

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

# Frontend Engineer, Design Systems
Remote (United States)

## About Kettle
Kettle makes collaborative design tools. Our component library is used by every product
team in the company and by a few thousand external developers, so the work is unusually
visible.

Many roles on our team are open to candidates without a clearance. This one requires an active Secret clearance before your start date.

## What you'll do
- Build and maintain the shared React component library
- Push accessibility forward — we treat WCAG AA as a floor, not a goal
- Write the documentation and usage guidance that ships alongside components
- Partner with designers on tokens, theming, and dark mode

## Requirements
- 4+ years writing production frontend code
- Deep React and TypeScript
- Real experience with accessible interface work, including keyboard and screen reader testing
- An eye for API design at the component level

## Nice to have
- Experience with Storybook or similar documentation tooling
- Familiarity with CSS-in-JS tradeoffs
- Open source maintenance experience

## Benefits
- Health, dental, and vision coverage
- Flexible paid time off
- Annual learning budget
- Quarterly team offsites

## Equal opportunity
Kettle is an equal opportunity employer. We consider all qualified applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, or veteran status.

Should I apply? Report every condition in this posting that disqualifies me.

These are the disqualifying conditions, what each one means, and which part of
my background decides it:

- work_authorization (legal): Role does not offer visa sponsorship. Decided by the profile field `work_auth`.
- citizenship_required (legal): Employment restricted to U.S. citizens or ITAR-defined U.S. Persons. Decided by the profile field `citizenship`.
- security_clearance (legal): An active government security clearance is required at time of application. Decided by the profile field `clearance`.
- professional_licensure (legal): A named professional license is required (regulated / safety-critical work). Decided by the profile field `licenses`.
- onsite_location (logistics): Role requires working on-site in a specific location. Decided by the profile field `location`.
- relocation_required (logistics): Relocation is a condition of employment. Decided by the profile field `willing_to_relocate`.
- timezone_overlap (logistics): Requires sustained working-hours overlap with a specific time zone. Decided by the profile field `timezone`.
- travel_percentage (logistics): Required travel exceeds what the candidate accepts. Decided by the profile field `max_travel_pct`.
- shift_oncall (logistics): Requires overnight, weekend, or non-standard shift coverage. Decided by the profile field `accepts_night_shift`.
- degree_required (credentials): A minimum formal degree level is mandatory, with no experience substitution. Decided by the profile field `degree`.
- certification_required (credentials): A named professional certification must be active at time of hire. Decided by the profile field `certifications`.
- years_of_experience (credentials): A hard minimum years-of-experience floor, stated as required rather than preferred. Decided by the profile field `years_experience`.
- employment_type (terms): Engagement model excludes the candidate's acceptable arrangements. Decided by the profile field `employment_types`.
- compensation_floor (terms): The top of the posted salary band falls below the candidate's minimum. Decided by the profile field `comp_floor`.

A condition only disqualifies me if the posting makes it a firm requirement and
my background fails it. A preference is not a requirement.

For every disqualifier you report, quote the sentence from the posting that
states it. Copy that sentence exactly as it appears — do not paraphrase,
shorten, or join two sentences together. If you cannot find a sentence that
states the condition, do not report it.

Reply with only this JSON object and nothing else:

{"blockers": [{"type": "<id from the list above>", "evidence": "<exact sentence from the posting>"}]}

Use an empty list if nothing here disqualifies me.
```

**Output**

```
{"blockers": [{"type": "security_clearance", "evidence": "This one requires an active Secret clearance before your start date."}, {"type": "work_authorization", "evidence": "Role does not offer visa sponsorship."}]}
```

## 2. reject_ungrounded _(event)_

work_authorization: quoted text is not in the posting — 'Role does not offer visa sponsorship.'

## Result

```json
{
  "verdict": "SKIP",
  "blockers": [
    {
      "type": "security_clearance",
      "evidence": "This one requires an active Secret clearance before your start date."
    }
  ],
  "caveats": []
}
```
