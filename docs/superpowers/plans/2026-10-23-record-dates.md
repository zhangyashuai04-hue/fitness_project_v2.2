# Record dates implementation plan
Goal: iOS date list and daily detail, preserving weight and stored data.
Spec: ../specs/2026-10-23-record-dates-design.md
1. Add tests for unique descending training dates, exclusion of weight/hidden records, legacy dates, and date navigation with weight control identity retained.
2. Implement RecordsService.training_days using result local_date and local legacy timestamps. Reuse current daily rendering in an iOS detail view with back action; Android remains unchanged.
3. Run Python regression tests; review diff. Commit and push iOS branch, dispatch existing device-unsigned workflow, inspect build and retrieve IPA.
