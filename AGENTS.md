# Light Routines

<!-- workspace-pointer -->
## Shared workspace rules

Part of the bitosome Home Assistant workspace. Shared rules, access (SSH, ha-mcp) and processes
are in `../AGENTS.md` (the workspace entry point) and `../home-assistant-knowledge/`; they take
precedence over this file. Build, test, release and known gotchas for this repo:
[repo catalog](../home-assistant-knowledge/docs/repo-catalog.md#light-routines).

- Edit and release from this checkout; never patch production directly.
- Push, tag/release, HACS install, production changes, reloads and restarts need the owner's explicit approval.
- After a release or install, update `docs/current-state.md` and `docs/changelog.md` in the knowledge repo.

Own implementation here, not in production-only scripts. Keep room/light IDs out of source and tests. Configuration uses native Home Assistant flows; dashboard tiles use existing entity contracts. Persist run intent before light commands, serialize commands, and never run competing fades. Do not use long native transitions that cannot be cancelled. Adding/configuring the integration must not actuate lights. Test with mocked services and actual Home Assistant lifecycle; no physical test without explicit authorization. Run pytest before release. Bump manifest version, push main, release an annotated tag; keep release assets reproducible and free of caches.
