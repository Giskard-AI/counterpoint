Compliance process for third-party licenses

Overview
This repository uses Python with `uv` for dependency management. We maintain an inventory of direct and transitive dependencies and comply with their license obligations via a `THIRD_PARTY_NOTICES.md` file generated in CI.

Steps
1. Dependency inventory
   - CI installs dependencies from the lockfile and generates `licenses.json` (machine-readable) and `THIRD_PARTY_NOTICES.md` (human-readable with license texts).
2. License gating
   - CI fails if packages under disallowed licenses are detected. The allowlist is a conservative set of permissive licenses and common weak copyleft.
3. Notices
   - `THIRD_PARTY_NOTICES.md` is updated from CI artifacts. Ensure Apache-2.0 NOTICE content is preserved.

Local regeneration
- Requires `uv` installed locally.
- Commands:
  - uv sync --all-groups --locked
  - uvx pip-licenses --format=json --with-license-file --with-authors --with-urls > licenses.json
  - uvx pip-licenses --format=markdown --with-license-file --with-authors --with-urls > THIRD_PARTY_NOTICES.md

Policy notes
- Prefer permissive licenses (MIT/BSD/Apache-2.0/ISC). Avoid GPL/AGPL in distributed artifacts unless approved.
- Apache-2.0: include NOTICE content if present. MIT/BSD/ISC: preserve full license texts.
- For MPL/EPL/LGPL: ensure obligations are understood for linking/modification scenarios.

Questions
- Contact maintainers for exceptions or legal review.
