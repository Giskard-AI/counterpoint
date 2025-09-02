Compliance process for third-party licenses

Overview
This repository uses Python with `uv` for dependency management. We maintain an inventory of direct and transitive dependencies and comply with their license obligations via a `THIRD_PARTY_NOTICES.md` file generated locally with Makefile targets.

Steps
1. Dependency inventory
   - Run `make licenses` to generate `licenses.json` (machine-readable) and `THIRD_PARTY_NOTICES.md` (human-readable with license texts).
2. License gating
   - Run `make licenses-check` to fail if packages under disallowed licenses are detected. The allowlist is a conservative set of permissive licenses and common weak copyleft.
3. Notices
   - Commit updated `THIRD_PARTY_NOTICES.md` when releasing. Ensure Apache-2.0 NOTICE content is preserved.

Local regeneration
- Requires `uv` installed locally.
- Commands:
  - make install-tools
  - make licenses
  - make licenses-check

Policy notes
- Prefer permissive licenses (MIT/BSD/Apache-2.0/ISC). Avoid GPL/AGPL in distributed artifacts unless approved.
- Apache-2.0: include NOTICE content if present. MIT/BSD/ISC: preserve full license texts.
- For MPL/EPL/LGPL: ensure obligations are understood for linking/modification scenarios.

Questions
- Contact maintainers for exceptions or legal review.
