# Optional compute, never required

## 1 The problem

A viewer can avoid baking a new layer after every camera driver edit by requesting cached sensor computations. That is a performance and interaction option; it cannot be a dependency for exchanging the built thing.

## 2 The data as it arrives

The inputs are the existing core and CCTV schemas. Camera drivers already identify device placement, sensor optics and pose. The plugin adds no driver, identity or geometry vocabulary.

## 3 The model in USD

`execAecoCctv` registers six computations on the existing camera and sensor APIs. OpenExec owns scheduling, caching and invalidation. Returned matrices and point vectors are consumed by an application; this plugin authors no geometry. Baked Camera and guide Mesh layers remain the vanilla fallback.

## 4 Workflow

Build with the processing toolchain's usd-dev and matching Python. Keep the execution system and request alive, compute, copy values before edits, and schedule subsequent computation after invalidation. The [native reference](native-compute.md) explains frame restrictions and consumer lifetimes.

## 5 Validation

The unchanged native gate has 21 claims covering registration, dependency metadata, six computations, before/after parity, baked parity, invalidation, sector topology, orphan sensors and vanilla composition. The test suite includes incomplete, duplicate, corrupted and non-finite result refusals. Missing native artifacts produce 21 NOT RUN rows, each with a reason. The summary includes their count; JSON keeps them distinct from PASS and FAIL. The source gate separately executes core validators and checks the exact pins.

## 6 The example on the demo data centre

As a schema-free library, this repository uses the CCTV lobby and an orphan-sensor fixture for focused numeric parity. The CCTV repository owns the full facility workflow and baked renders. Native consumers may evaluate its sensors without changing the published facility.

## 7 Trade-offs and alternatives

Baking is simpler for exchange and works in every USD viewer. On-demand computation supports interactive consumers but requires an OpenExec-enabled USD build and application code. Stock viewers do not draw sectors merely because this plugin is installed. Lighting, compression and recognition performance remain outside these geometric computations.

## 8 Out of scope and open questions

No viewer adapter, live video, study-wide occlusion engine or new schema is supplied. Matrix-only ancestor restrictions, supported transform operations and default density choices remain documented in the native reference.

## 9 Status

Version 0.2.3 uses MIT and public names under `github.com/criad-com`, with toolchain 0.3.8. Train aeco-0.7.0 pins for core 0.9.2 and CCTV 0.5.2 are unchanged. Native computation source is unchanged. Current verification is in the [README](../README.md#status); [v0.2.1 migration acceptance](migration.md) remains historical.
