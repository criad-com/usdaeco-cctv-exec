# usdaeco-cctv-exec — optional compute for camera drivers

## Use case

OpenExec evaluates CCTV sensor computations on demand and invalidates affected outputs after driver edits. It is optional compute, never required to compose baked USD. See the [use case](docs/usecase.md) and [native computation reference](docs/native-compute.md).

## The schema on an index card

| Item | Contract |
|---|---|
| Schema classes or properties | None |
| Native plugin | `execAecoCctv` |
| Inputs | Existing `UsdAecoCctvCameraAPI` and `UsdAecoCctvSensorAPI` drivers |
| Results | Width, field of view, sensor frame, plane/arc target range, sector points |

## The example

This library has no example directory or result to publish. The native consumer evaluates the CCTV [lobby](https://github.com/criad-com/usdaeco-cctv/blob/v0.5.5/examples/lobby.usda) before and after a pan edit. It checks eight sensor records against both the Python computation and baked derived layers. [Current v0.2.4 acceptance](docs/public-pins.md) records the native rebuild and provenance comparison. [Previous release evidence](docs/release-acceptance.json) records 21/21 native checks and 8/8 baked records at v0.1.3; this is historical evidence, not a current native pass.

## Build and check

Use source sibling checkouts at the exact tags in [dependencies.json](dependencies.json) and the interpreter matching your USD runtime. Set `AECO_PYTHON` to an existing Python executable with USD 26.8, NumPy and pytest for source checks; setuptools and an installed package are unnecessary.

```sh
export PYTHONDONTWRITEBYTECODE=1
export TOOLCHAIN_DIR="$PWD/../usdaeco-toolchain"
export AECO_CORE_ROOT="$PWD/../usdaeco-core"
export CCTV_ROOT="$PWD/../usdaeco-cctv"
export CORE_PLUGIN_DIR="$AECO_CORE_ROOT/usdAeco"
export CCTV_PLUGIN_DIR="$CCTV_ROOT/usdAecoCctv"
env -u PYTHONPATH PYTHONPATH="$AECO_CORE_ROOT:$PWD" "$AECO_PYTHON" check.py --report artifacts/check.json
env -u PYTHONPATH "$AECO_PYTHON" -m pytest -q
nix flake check
```

The gate prints `N checks, M failed, K not run`. `N` includes every row;
PASS, FAIL and NOT RUN are disjoint. When the usd-dev consumer or installed
plugin descriptor is missing, all **21 native gate rows** are NOT RUN, each
with its reason. They include baked parity and the native suite's own metadata
and hygiene checks. Source structure, links, exact dependency versions and all
eight core validators still run independently. The JSON report uses
`status: "NOT RUN"` and `ok: null`; historical evidence never supplies a PASS.
Pytest reports the actual count and reason for deselected native cases.

The source gate can exit zero with NOT RUN rows: this proves only the executed
checks. Core validator import/registration failures always fail the gate.
`--native` additionally fails if native artifacts are unavailable; the Nix
check requires `0 failed, 0 not run`.

To run the native rows, enter the flake's default **nix devShell** and use its
matching USD development interpreter:

```sh
nix develop
env -u PYTHONPATH ./build.sh
env -u PYTHONPATH PYTHONPATH="$AECO_CORE_ROOT:$PWD" "$PYTHON" check.py --native --report artifacts/check.json
env -u PYTHONPATH "$PYTHON" -m pytest -q
```

For local source mappings, supply `--override-input aeco-toolchain
"path:$PROCESSING_TOOLCHAIN_SOURCE"`, `--override-input toolchain
path:../usdaeco-toolchain`, `--override-input usdaeco-core path:../usdaeco-core`, `--override-input usdaeco-cctv path:../usdaeco-cctv`
and `--override-input toolchain/core
"git+file://$PWD/../usdaeco-core?ref=refs/tags/v0.9.2"` (the toolchain test fixture) to `nix develop` or
`nix flake check`. Keep any private registry and deployment lockfiles outside
the published tree. No package installation is needed for source tests.

## Family

Requires `usdAeco >=0.9.2,<1.0` and `usdAecoCctv >=0.5.2,<0.6`. [Exact pins](dependencies.json) select core v0.9.4, CCTV v0.5.5, usdaeco-toolchain v0.3.10 and aeco-toolchain v0.4.0. All four family inputs use public release tags. Revisions record the tested source checkouts; public inputs resolve by tag. [Family board](https://github.com/criad-com/usdaeco-board).

## Layout

`src/` contains native computations; `resources/` supplies their plugin descriptor. `testenv/` retains the C++ consumer, vanilla probe and parity regressions. `check.py` runs the 29 family structure rules and includes all 21 claims from `tools_native_check.py` in one report. This schema-free library has no schema directory, validators plugin or mandatory data-centre example.

## Status

Version **0.2.4**: **54 checks, 0 failed, 0 not run; 24 pytest cases passed** after a local native rebuild. Structure checks use toolchain v0.3.10, including S05 release-tag and version checks. All eight core validators execute with zero findings. The regenerated lobby layer differs from CCTV v0.5.2 only in 13 version stamps; geometry and all other opinions are byte-identical. The single offline Nix attempt evaluated the package, check and dev shell, then stopped at an uncached build dependency with local jobs disabled; the full Nix closure remains **not proven**. [Current acceptance, reproduction commands and deviations](docs/public-pins.md). The native computations are unchanged. A stock viewer does not automatically request these computations; a viewer integration remains outside this release.

## Licence

[MIT](LICENSE). Copyright (c) 2026 Criad.

Runtime dependencies retain their licences: OpenUSD (Apache-2.0-style TOST)
and NumPy (BSD-3-Clause, Python parity reference). Third-party code is not vendored.
