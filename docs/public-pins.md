# Release 0.2.4 acceptance

All four family inputs now name public release tags: aeco-toolchain v0.4.0,
usdaeco-toolchain v0.3.10, core v0.9.4 and CCTV v0.5.5. Exact tested revisions
are recorded in [dependencies.json](../dependencies.json). Both schema pins
remain inside the existing requirement ranges. C++ computations are unchanged.

[Numeric receipt](public-pin-acceptance.json) records this release's measurements.
Earlier acceptance files retain their original pins and are historical fixtures.

| Acceptance | Measured result |
|---|---:|
| Family release-tag inputs / resolved source revisions | 4 / 4 |
| Gate after native rebuild | 54 checks, 0 failed, 0 not run |
| Source smoke before native build | 54 checks, 0 failed, 21 not run |
| Structure rules, including S05 | 29, 0 failed |
| Core validators on the CCTV input | 8 executed, 0 findings |
| Native suite | 21 claims passed |
| Pytest | 24 passed |
| Lobby records / baked parity records | 8 / 8 |
| Orphan records | 8 |
| Maximum world-point deviation | 7.105427357601002e-15 m |
| Maximum baked float32 point deviation | 8.445743162610597e-7 m |
| Vanilla composition with authored-value and transform parity | 2 stages |
| Regenerated lobby layer | 514,563 bytes, identical to CCTV v0.5.5 |
| Changes from the CCTV v0.5.2 lobby derivation | 13 version stamps only |
| Nix attempts / completed checks | 1 / 0 |

S01–S05 and S25–S26 apply to this schema-free library. The other structure
rows explicitly report not applicable; they do not prove publication or rendering.

## Reproduce the native build

Follow the [README source setup](../README.md#build-and-check) with the exact
tagged checkouts. In the Nix dev shell, use its documented build command.
An existing compatible usd-dev installation also supports the documented
standalone build:

```sh
export USD_DEV="$USD_DEV_PREFIX"
env -u PYTHONPATH ./build.sh
unset USD_DEV
env -u PYTHONPATH PYTHONPATH="$AECO_CORE_ROOT:$PWD" "$AECO_PYTHON" check.py --native --report artifacts/check.json
env -u PYTHONPATH "$AECO_PYTHON" -m pytest -q
```

The measured build used OpenUSD dev `47154dc7b5e28df623745495a7a508b69535ba24`
on macOS ARM64, linked to Python 3.14.6. The parity reference and core validators
used USD 26.8. No package installation was needed. The rebuilt installed plugin
metadata matches version 0.2.4, tier and requirement ranges from `library.json`.

## Provenance comparison

The native plugin authors no USD. This library has no publication runner, result
bundle or render. CCTV owns those deliverables. Re-run its documented derivation
on a disposable copy of the pinned lobby:

```sh
mkdir -p artifacts/provenance
cp "$CCTV_ROOT/examples/lobby.usda" artifacts/provenance/lobby.usda
export PXR_PLUGINPATH_NAME="$CORE_PLUGIN_DIR:$CCTV_PLUGIN_DIR"
env -u PYTHONPATH "$AECO_PYTHON" "$CCTV_ROOT/tools/aeco-cctv" derive artifacts/provenance/lobby.usda -o artifacts/provenance/lobby.derived.usda
cmp artifacts/provenance/lobby.derived.usda "$CCTV_ROOT/examples/lobby.derived.usda"
```

The regenerated layer is byte-identical to the pinned v0.5.5 layer. Replacing
exactly 13 `usdAecoCctv derive 0.5.2` stamps with `usdAecoCctv derive 0.5.5`
in the v0.5.2 layer produces those same bytes. Geometry, samples, transforms and
all other opinions are therefore byte-identical. The input lobby, local orphan
fixture, C++ computation source and consumer source are unchanged; the receipt
records hashes. No dependency checkout was modified.

The [CCTV changelog](https://github.com/criad-com/usdaeco-cctv/blob/v0.5.5/CHANGELOG.md)
records the v0.5.5 lobby version-stamp refresh. The
[core changelog](https://github.com/criad-com/usdaeco-core/blob/v0.9.4/CHANGELOG.md)
records unchanged schema and result files. The processing toolchain retains
the same OpenUSD and nixpkgs revisions. No computation behavior change was found.

## Deviations

- The single `nix flake check --offline --no-write-lock-file` attempt used
  exact local overrides for all four direct inputs and the toolchain's core
  v0.9.2 test fixture. Package, check and dev-shell evaluation succeeded.
  It exited 1 after 12.236 seconds when an uncached `add-flags.sh` dependency
  required a builder with local jobs disabled (`--max-jobs 0`), no substituters
  and no remote builders. The full Nix closure is **not proven**; no retry ran.
- Public tag availability comes from the supplied release inventory. This run
  verified the four tagged source revisions; online public resolution remains
  for release review. Native acceptance covers macOS ARM64 only.
- Publication and render checks are not applicable to this library. The fresh
  lobby derivation and two-stage vanilla composition check above establish the
  measured scope; no new render is claimed.
