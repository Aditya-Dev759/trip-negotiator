# Development Progress Summary

This file previously described a "Phase 1/2/2.5" snapshot from very early
development, before the agents had real logic, before the Terraform
described an architecture that matched the actual code, and before any of
the negotiation/UI features existed. It's been rewritten to reflect current
reality instead of a stale roadmap.

## What's actually implemented and working (verified locally)

- Full multi-agent negotiation loop: Itinerary -> Budget -> Logistics ->
  Booking -> Supervisor, bounded at 3 rounds, force-finalizing with
  unresolved objections surfaced (not hidden) if the cap is hit.
- Every agent's reasoning is grounded in live web search (`ddgs`, with a
  SearxNG opt-in and DuckDuckGo-scrape last resort) rather than raw LLM
  priors: destination highlights, weather, per-interest highlights, a
  "best time to visit / practical essentials / etiquette / safety"
  destination guide, flight/lodging cost estimates, and travel advisories
  that are explicitly fact-checked against today's date so a resolved,
  years-old warning doesn't get presented as current.
- Every agent verdict carries its live sources; the finalized itinerary
  carries a destination photo gallery.
- Traveler age tailors itinerary pacing/intensity without overriding their
  explicitly selected interests; origin/destination are picked from a real
  geocoded location-autocomplete instead of free-typed strings; a live
  exchange rate is shown when origin/destination resolve to different
  countries.
- FastAPI backend (`api/main.py`), Mangum-wrapped for Lambda, with a
  documented dual orchestration path: Step Functions in AWS,
  in-process `BackgroundTasks` locally -- one codebase, not two.
- Next.js frontend (glassmorphism redesign, framer-motion interactions) for
  the trip form, live negotiation stream, finalized itinerary, and trip
  history.
- pytest suite covering the negotiation state machine and dynamic-data
  fetch/fallback logic; `tsc --noEmit` clean on the frontend.

## What's implemented in code/IaC but NOT yet verified against real AWS

- Terraform for the full stack: ECR + container-image Lambdas (api + 4
  agents, arm64), a plain-zip Lambda (supervisor), Step Functions, API
  Gateway (proxied to the api Lambda), DynamoDB (PITR + encryption
  explicit), S3 (x2, with lifecycle rules), CloudFront, Cognito (user pool
  + JWT authorizer, off by default), CloudWatch alarms + SNS, AWS Budgets.
  Every `.tf` file has been checked for structural correctness (balanced
  braces, consistent resource references) but **no `terraform apply` has
  been run against real AWS from this environment** -- there are no AWS
  credentials configured here. This needs to happen on your machine/Learner
  Lab account before it can be called done.
- The GitHub Actions CI/CD pipeline (`.github/workflows/deploy.yml`) is
  written and appears correct, but has never executed even once: this repo
  has no `git remote` configured, so nothing has been pushed to GitHub yet.

## Known gaps / explicitly deferred

- Cognito auth enforcement is off by default (`enable_auth = false`) --
  the frontend has no login flow yet, so turning it on would break the
  current UI. This is the single largest deferred item.
- IAM relies on the shared Learner Lab `LabRole` everywhere, not
  per-function least-privilege roles (a Learner Lab constraint).
- AWS Budgets may not deploy at all under LabRole (Budgets is commonly
  blocked in Learner Lab IAM policies) -- documented in `infra/budgets.tf`.
- No load/performance testing has been done.
- The Final Report PDF (`docs/TripNegotiator_Final_Report.pdf`) is a first
  draft assembled from this repo's actual state -- review it, fill in the
  AI-assisted-coding percentage honestly, and correct anything that doesn't
  match your own understanding before submitting.

## Immediate next steps (in priority order)

1. `terraform apply` for real (see README's "Deployment to AWS" bootstrap
   order -- ECR first, then build/push the image, then the rest) and fix
   whatever `terraform validate`/`plan` surfaces that this review couldn't
   catch without a real AWS session.
2. Create a GitHub repo, push, add the AWS secrets, confirm one green CI
   run.
3. Decide whether to implement the Cognito login flow in the frontend
   before the report is due, or keep `enable_auth = false` and lean on the
   documented tradeoff writeup in the README/report.
4. Fill in the AI-assisted-coding percentage in the README and report.
5. Rehearse the demo script in the README against the real deployed stack.
