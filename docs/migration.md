# Release 0.2.1 acceptance

This schema-free compute library is MIT. Its supported ranges are
`usdAeco >=0.9.2,<1.0` and `usdAecoCctv >=0.5.2,<0.6`; the exact checks used
core v0.9.2, CCTV v0.5.2 and toolchain v0.3.2. The C++ computation source is
unchanged. [Numeric evidence](republish-acceptance.json) records the two gate
modes separately; [v0.2.0 evidence](rebase-acceptance.json) remains historical.

## Verification

| Acceptance | Measured result |
|---|---:|
| Gate after native rebuild | 53 checks, 0 failed, 0 not run |
| Gate with explicit missing native artifact paths | 53 checks, 0 failed, 21 not run |
| Structure under toolchain v0.3.2 | 28 rules, 0 failed |
| Core validators on the CCTV input | 8 executed, 0 findings |
| Native suite | 21 claims passed |
| Pytest with rebuilt native artifacts | 24 passed |
| Pytest without native artifacts | 10 passed, 14 deselected with NOT RUN reason |
| Lobby before/after records | 8 |
| Baked parity records | 8 |
| Maximum lobby world-point deviation | 7.105427357601002e-15 m |
| Maximum baked float32 point deviation | 8.445743162610597e-7 m |
| Maximum orphan deviation across 8 records | 1.9539925233402755e-14 |
| Vanilla composition and authored-value/transform parity | 2 stages |
| Repository term violations | 0 |
| Nix attempts / successful checks | 1 / 0 |

The local CMake build used the cached OpenUSD dev revision `47154dc`, linked
to its Python 3.14.6 runtime. The consumer executes in its own process; the
Python parity reference and core validators run with USD 26.8. No package
installation was needed. The installed plugin's `Info.aeco` matches precisely
`version`, `tier` and `requires` from the manifest; licence metadata stays in
the library manifest.

## NOT RUN semantics

The shared Report counts all planned rows. NOT RUN is `ok: null` with an
explicit reason, never PASS. Missing native artifacts defer the entire 21-row
native suite, including its own metadata and hygiene checks. The 32 source
rows still execute independently. Every row left after a failed native
prerequisite remains visible as NOT RUN. `--native` fails on unavailable
artifacts; Nix requires `0 failed, 0 not run`. The regressions cover missing,
partial and non-executable installs, interrupted execution, JSON accounting,
CLI overrides and required mode, and a missing core validator import.

The [README](../README.md#build-and-check) shows how to enter the nix devShell,
build the plugin and rerun the native gate. Prior release evidence cannot
replace an unexecuted current row.

## Structure and examples

S01–S05 and S25–S26 apply. The other rules report not applicable for this
schema-free library; that does not prove schema generation or rendering.
There is no example directory, publication runner or result to publish here.
The orphan-sensor USDA is a numeric test fixture. CCTV owns the lobby and
published facility example, including its standalone result and vanilla render.
Consequently `check_example`, S27 and S28 publication proofs are inapplicable
in this repository. The existing two-stage B7 composition check remains.

## Deviations

- The single Nix attempt exited 1 during input resolution: the shared
  toolchain's nested `core` input at v0.8.4 was uncached. Offline mode, no
  substituters or remote builders, zero local jobs and denied outbound
  networking prevented a fetch. The Nix closure is **not proven**; no second
  attempt was made. This is separate from the successful local native build.
- The supplied core build-output descriptor still advertised v0.9.1. Checks
  use the committed v0.9.2 source plugin, matching the flake, and leave the
  dependency checkout untouched. The gate now rejects mismatched versions.
- Native acceptance was measured on macOS ARM64. Linux and the full nix
  devShell closure remain unproven by this run.
