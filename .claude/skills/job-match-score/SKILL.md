---
name: job-match-score
description: Compares a user's CV/resume or profile against a specific job description and produces a match score with supporting analysis. Use when the user provides (or references) both a CV/profile and a job description and asks things like "how well do I match this job", "score my fit for this role", "am I qualified for this posting", or "job match score". Requires both a CV/profile and a job description — if either is missing, ask for it before scoring.
---

# Job Match Score

Compares a candidate's CV/profile against a specific job description and produces an honest, explained match score. This is an analysis skill, not a CV-editing skill — for rewriting or tailoring the CV itself, defer to the CV Agent.

## Inputs required

Both of the following, before scoring:

1. **The candidate's CV/profile** — a resume file, pasted CV text, or a summary of their skills/experience.
2. **The job description** — pasted text, a file, or a URL (fetch it with WebFetch if only a URL is given).

If either is missing, ask the user for it rather than guessing or scoring on partial information.

## How to score

Read both documents in full before scoring. Build the score from concrete, checkable overlap — not vibes.

1. **Extract job requirements.** Separate them into: must-haves (explicitly required skills, years of experience, certifications, domain knowledge, location/work-authorization constraints) and nice-to-haves (preferred but not required).
2. **Extract candidate evidence.** For each requirement, look for direct evidence in the CV/profile — a matching skill, a project, a role, a quantified result. Do not count a requirement as met unless the CV actually supports it.
3. **Weight must-haves heavily.** A candidate missing several must-haves should score noticeably lower than one missing only nice-to-haves, even if their overall experience looks impressive. Recency and depth matter too — a skill used for one week three jobs ago counts for less than one used recently and repeatedly.
4. **Score out of 100** as a holistic judgment grounded in that evidence, not a mechanical percentage of keywords matched. Reserve 90+ for a candidate who clearly meets nearly every must-have and several nice-to-haves; reserve sub-40 for a candidate missing multiple must-haves or in the wrong domain/seniority entirely.

## Hard constraints

- **Never invent experience, skills, results, or qualifications.** Only use what's actually stated or clearly implied in the CV/profile. If something is ambiguous (e.g. "familiar with X" — unclear how deep), say so rather than assuming the best case.
- **Be honest, not encouraging.** The point of this skill is a candid signal, not a pep talk. A weak match should read as a weak match.
- **Keep the explanation short and easy to understand.** No jargon, no padding, no restating the entire job description back at the user. Bullet points over paragraphs wherever possible.
- Suggested improvements must be things the candidate could actually do or already has evidence for surfacing better (e.g. "highlight your X project, which is relevant but not mentioned prominently") — not fabricated skills to add.

## Output format

Always respond in exactly this structure, with these five headers in this order:

```
Match Score: <N>/100

Strong Matches:
- <requirement the candidate clearly meets, with a one-line reason>
- ...

Possible Gaps:
- <missing or weak requirement, with a one-line reason>
- ...

Why This Score:
<2-4 sentences on the overall reasoning: which factors pulled the score up, which pulled it down>

Recommendation:
- <one or two honest, actionable next steps -- apply as-is / tailor CV first / build missing skill X / likely not a fit, etc>
```

Keep each bullet to one line where possible. If there are no meaningful gaps, say so explicitly under "Possible Gaps" rather than omitting the section.
