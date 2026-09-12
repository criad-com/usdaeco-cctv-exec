# Changelog

## 0.2.4

- public re-pin: aeco-toolchain v0.4.0, usdaeco-toolchain v0.3.10, core v0.9.4 and CCTV v0.5.5. Record exact checked revisions alongside the public release tags.
- Keep the existing requirement ranges; both schema pins remain compatible.
- Rebuild the native plugin: 54 checks pass, including all 21 native claims and eight core validators; 24 pytest cases pass. The regenerated lobby differs only in 13 upstream version stamps, with byte-identical geometry and other opinions.
- Record the single offline Nix attempt as not proven: package, check and dev-shell evaluation succeeded, but an uncached dependency needed a builder while local jobs were disabled. See [acceptance](docs/public-pins.md).

## 0.2.3

- Public names → github.com/criad-com.
- Re-pin toolchain to v0.3.8 for the public-name structure checks.

## 0.2.2

- Re-pin to train aeco-0.7.0: toolchain v0.3.5, core v0.9.2 and CCTV v0.5.2; requirement ranges are unchanged.
- Declare historical acceptance pins as fixtures; native rows remain NOT RUN with reasons.

## 0.2.1

- Count every unexecuted native claim as NOT RUN with its reason in console and JSON reports; require zero NOT RUN rows in Nix.
- Verify exact dependency versions and execute the core validators on the CCTV input; use committed source plugins.
- Republish under MIT and declare the runtime dependency licences.
- Require core >=0.9.2,<1.0 and CCTV >=0.5.2,<0.6; pin toolchain v0.3.2.

## 0.2.0

- Adopt the schema-free library skeleton and family checks.
- Require core 0.9 and CCTV 0.5; preserve native computations and all 21 native claims.
- Report unavailable native execution and baked parity as NOT RUN with v0.1.3 evidence.


## 0.1.3

- Refresh tested inputs to CCTV v0.4.8 and core v0.8.4, with release tags,
  exact revisions and matching flake metadata.
- Keep the schema ranges `usdAecoCctv >=0.4.5,<0.5` and
  `usdAeco >=0.8.1,<0.9` unchanged.
- Read the CMake project version from `library.json` so native build metadata
  follows the release version.
- Rebuild the native plugin against OpenUSD dev `47154dc` and refresh
  [acceptance evidence](docs/packaging.md): 21 checks, 0 failed; 15 pytest
  cases passed; exec/Python and baked-layer parity within the existing
  `1e-9` scalar/matrix and `1e-6 m` point tolerances.
- Record the single offline Nix check separately from native acceptance.
  C++ computation source and the sensor contract are unchanged.

## 0.1.2

- Tested CCTV v0.4.5 and core v0.8.3 with compatible schema ranges and
  native parity evidence.
