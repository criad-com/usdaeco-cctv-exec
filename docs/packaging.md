# Historical release 0.1.3 acceptance

These measurements apply only to **CCTV v0.4.8**, **core v0.8.4** and the
OpenUSD development revision recorded in [release-acceptance.json](release-acceptance.json).
They do not describe the current dependency pins. See [current acceptance](migration.md)
for v0.2.1 and the [README](../README.md#build-and-check) for current commands.
The repository is now licensed under [MIT](../LICENSE).

Both codeless dependency plugins were rebuilt with USD 26.8; their six
committed resources remained byte-identical. The C++ plugin and consumer
were rebuilt against OpenUSD dev `47154dc` and Python 3.14.6 on macOS ARM64.
CMake reads the project version from `library.json`. C++ computation source
was unchanged. The numeric evidence records the runtime, dependency refs,
resource hashes and parity measurements for that release.

| Historical acceptance | Result |
|---|---:|
| Native gate | 21 checks, 0 failed |
| Native pytest | 15 passed in 5.10 s |
| Lobby sensor records, before/after | 8/8 |
| Maximum world-point error | 7.105427357601002e-15 m |
| Maximum baked float32 point error | 8.445743162610597e-7 m |
| Other lobby computation deviations | 0 |
| Orphan sensor records, before/after | 8/8 |
| Maximum orphan deviation | 1.9539925233402755e-14 |
| Point / other tolerances | 1e-6 m / 1e-9 |
| Vanilla composition | 2/2 stages; identical authored values and transforms |
| Rebuilt dependency resource sets | 2/2 equal to the committed releases |
| Repository text sweep | 19 files, 0 violations |
| Nix flake checks attempted / passed | 1 / 0 |

## Historical Nix boundary

The single offline Nix attempt used exact source overrides with no lock
writes, substituters or remote builders, and zero local jobs. Package,
check and development-shell evaluation succeeded, then the attempt exited
1 after 17.938 seconds because a new derivation required a builder. That
Nix build remained **not proven**. The native build/check/pytest above used
an already installed development closure and were recorded separately.

These historical numbers never replace a current NOT RUN row. Current
reports preserve every unexecuted claim with its reason and count.
