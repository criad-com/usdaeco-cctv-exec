# execAecoCctv native computation reference

Optional C++ OpenExec computations for the codeless `usdAecoCctv` sensor
schema. It reads sensor drivers, evaluates optics, pose and sector points,
and recomputes after edits. It authors no USD data. The codeless library
never depends on this plugin; its Python derivation and baked layers remain
the portable interchange path.

The current dependency pins are core **v0.9.2**, CCTV **v0.5.2** and the
processing toolchain's OpenUSD dev **47154dc** build (26.11 dev, Python 3.14).
Exact refs are in [dependencies.json](../dependencies.json); supported ranges
are `usdAeco >=0.9.2,<1.0` and `usdAecoCctv >=0.5.2,<0.6`. Native execution at
these pins is **NOT RUN** without the development closure. The fresh v0.2.1
[acceptance](migration.md) includes a local native rebuild and parity run;
the older v0.1.3 evidence remains separately labelled.
This plugin supplies no schema or validation library; those belong to CCTV.

## Build and check

Follow the [README build and check commands](../README.md#build-and-check),
using the committed core and CCTV source plugins, core first to register
`aecoDerived`. The native consumer reads the CCTV checkout's
`examples/lobby.usda` and compares its values with that checkout's derivation.
Use the same exact pins in source checks and the flake devShell.

The default package installs:

```text
bin/execcctv
plugin/usd/execAecoCctv/libexecAecoCctv.dylib  # .so on Linux
plugin/usd/execAecoCctv/plugInfo.json
plugin/usd/execAecoCctv/library.json
```

The development shell supplies CMake, Ninja, a compiler, usd-dev, and its
Python 3.14 with numpy and pytest. Inside it:

```sh
env -u PYTHONPATH ./build.sh
env -u PYTHONPATH PYTHONPATH="$AECO_CORE_ROOT:$PWD" "$PYTHON" check.py --native --report artifacts/check.json
env -u PYTHONPATH python -m pytest -q
env -u PYTHONPATH python testenv/parity.py artifacts/lobby.json --baked
```

`build.sh` also works outside Nix with `USD_DEV` set to an existing usd-dev
installation; it obtains the matching Python, TBB and OpenSubdiv locations
from `pxrConfig.cmake` and propagated dependencies. The CMake targets link
OpenUSD's `python` library when present. The ordinary `usd-core` wheel has
no OpenExec and cannot compile or load this plugin.

For a native consumer run, set `PXR_PLUGINPATH_NAME` to the colon-separated
core resources, CCTV resources, and installed execution plugin directory:

```sh
PXR_PLUGINPATH_NAME="$PWD/../usdaeco-core/usdAeco:$PWD/../usdaeco-cctv/usdAecoCctv:$PWD/build/install/plugin/usd/execAecoCctv" \
  build/install/bin/execcctv ../usdaeco-cctv/examples/lobby.usda > artifacts/lobby.json
```

It prints one JSON document to stdout and stage markers to stderr, builds
one request for all sensors, edits the first sensor's pan by 15 degrees in
the session layer, and evaluates that same request again. No source layer
is saved. `check.py` separates the C++ plugin path from the Python schema
path, so the durable Python/26.8 environment can also check the C++ output.
When `USD_DEV` is set, the Python scripts explicitly add only that build's
matching Python bindings after global `PYTHONPATH` is removed. Unset
`USD_DEV` when using a different interpreter's installed `pxr`.

## Computation contract

Registration uses the **TfType name** `UsdAecoCctvSensorAPI`, while stages
apply the identifier `AecoCctvSensorAPI`. The installed `plugInfo.json`
declares `Exec.Schemas.<TfType>.allowsPluginComputations = true` and copies
`Info.aeco` from the single [manifest](../library.json).

| Sensor computation | Result | Meaning |
|---|---|---|
| `computeEffectiveWidth` | `double` | Effective sensor width in mm, interpolated from datasheet FOV endpoints at the clamped focal length; physical width if endpoints are absent |
| `computeFieldOfView` | `GfVec2d` | Horizontal and vertical angles in degrees; vertical endpoints, physical height, or pixel aspect |
| `computeSensorToWorld` | `GfMatrix4d` | Pose drivers and boresight composed with the device's placement |
| `computeTargetRange` | `double` | Metres at target density: plane for rectilinear, arc for fisheye/cylindrical |
| `computeTargetRangeArc` | `double` | Explicit arc-model alternative; zero for a head without pixels |
| `computeSectorPoints` | `std::vector<GfVec3d>` | World-space apex, then a 25 × 15 cap grid: **376 points**, v outer, u inner, identical order to `usdaeco_cctv.sectors` |

Pan 0 looks along device +X; tilt is positive **down**; roll is about the
optical axis. Gf row-vector composition is
`Rx(90) * Ry(roll) * Rx(-tilt) * Rz(pan-90) * T(offset) * deviceToWorld`.
The input stage must use metres (`metersPerUnit = 1`); offsets and design
ranges are metres, optics mm and angles degrees. No stage-unit conversion
is performed by this plugin.

For a rectilinear head, endpoint widths are `2*f*tan(hfov/2)`, interpolated
linearly over the focal range, then `hfov = 2*atan(width/(2*f))`. Plane range
is `H/(2*density*tan(hfov/2))`; arc range is `H/(density*hfov_radians)`.
Fisheye and cylindrical heads interpolate the angles and use equidistant
width `f*hfov_radians`. Radar heads use the detection dome with zero density
range. Sector radius is the explicit design range, else the default-model
target range. Cylindrical caps use cylindrical radius, as in the derivation.

These computations require valid, finite drivers; run the library's
validators first. Empty sectors are returned for degenerate radii or FOV.
The plugin does not implement the full validation contract.

## Checks and measured scope

The v0.2.1 native build uses macOS ARM64 and usd-dev `47154dc` with its
Python 3.14 linkage. Python parity and core validation use USD 26.8 in a
separate process. [Current acceptance](migration.md) records 53 gate rows and
24 pytest passes. [Historical acceptance](packaging.md) preserves v0.1.3.
See the [changelog](../CHANGELOG.md) for release changes.
The v0.1.1 Nix build/check passed with explicit input overrides; that
historical result does not establish the current locked closure.

[tools_native_check.py](../tools_native_check.py) retains **21 native-suite checks**: manifests and dependencies, six
computations on four lobby sensors before and after pan, comparison with
the actual baked derivation, exact changed-value census, sector topology,
four orphan sensors (physical optics, fisheye and radar), vanilla USD in
fresh subprocesses for both stages, links and sanitization.

[testenv/test_parity.py](../testenv/test_parity.py) has **15 pytest cases**, including
real consumer/derivation parity, source-layer byte preservation, and seeded
bad results (missing/duplicate records, changed values, nonfinite points,
wrong shapes and reversed vertex order). Reference import failures are
fatal; the tests never substitute local replicas of the derivation.

Tolerances are `1e-9` for angles, widths, ranges and matrices and `1e-6 m`
for points. On the lobby, all non-point deviations were zero, world points
agreed within `7.11e-15 m`, and the float32 baked mesh agreed within
`8.4e-7 m`. Those baked-point bounds describe this fixture, not arbitrary
large ranges or coordinates. Pan changes only the edited sensor's matrix
and points; the other four values and all other sensors remain equal.
This proves output invalidation, not a count of internal callback executions.

## OpenExec limits and deviations (2026, pinned build)

This implementation targets the installed headers at OpenUSD `47154dc`.
It provides C++ dependency-tracked evaluation, including an API to change
time. There is **no Python OpenExec API**, **no built-in baking**, and
**no Tier B coverage study** in this plugin. The Python here compares USD
values and invokes a C++ process. Obstacle collection expansion, ray
casting, occlusion, study findings, level shells, PTZ envelopes and tour
synthesis stay with the codeless library's preprocessing tools. The test
consumer evaluates default time only.

* `NamespaceAncestor` **does work** from the applied API. However, the
  pinned `execGeom` transform computation reads only `xformOp:transform`.
  An additional `computeDeviceToWorld` on `UsdAecoCctvCameraAPI` handles the
  camera element's unsuffixed matrix, translate, scale, orient, and all
  rotate orders (double/float), plus reset-stack. Higher ancestors and
  orphan parents still require matrix-only transforms. Suffixed, inverse
  and half-precision operations warn and are skipped. Use a direct Camera
  child of its device; transforms between a sensor and a more distant
  camera ancestor are outside this implementation's supported layout.
* OpenExec rejects `VtArray` callback result types. The registered
  `std::vector<GfVec3d>` preserves precision through world transforms.
  A viewer converts each point to `GfVec3f` when building a `VtVec3fArray`;
  the computation itself returns doubles. No geometry is authored here.
* Study-wide settings are not inputs to these per-sensor computations.
  A zero sensor target density means **125 px/m**, not a search for a
  study. The default-model range is plane for rectilinear heads; callers
  request `computeTargetRangeArc` explicitly for arc. No extra driver token
  was added to the codeless schema, and the sector uses the default-model
  range unless an explicit design range is authored. Parity is with stages
  using these settings; changing a study's model or default density can
  intentionally make the library's derivation differ.
* Nix advertises macOS ARM64 and Linux x86-64 outputs; the last native evidence covers
  macOS ARM64 only. The private deployment lockfile is ignored; preserve
  your local lockfile to reproduce the exact toolchain closure.

## Viewer consumption

[testenv/execcctv.cpp](../testenv/execcctv.cpp) is the working C++ consumer. Build
`ExecUsdValueKey(sensor, TfToken("computeSensorToWorld"))` and sector keys,
keep an `ExecUsdSystem` and `ExecUsdRequest` alive, then extract values from
`system.Compute(request).Get(index)`. Copy results before edits; cache views
must not outlive their request or system. Invalidation callbacks should
schedule a later redraw, never call `Compute` reentrantly. Evaluate again
after notification to renew interest in future invalidations.

The pinned `usdExecImaging` API offers a sparse computation overlay on
`UsdImagingStageSceneIndex`: `UsdExecImagingCreateStageSceneIndex()` creates
it (null when Exec is disabled); set its stage/time and call
`ApplyPendingUpdates()` to flush computed-value dirtiness. A custom
`UsdExecImagingPrimAdapterInterface` registers keys in `BuildRequest`,
supplies computed data sources in `GetPrimData`, and maps invalidated keys
to Hydra locators in `InvalidatePrimData`. This plugin does not ship that
adapter: merely registering computations does not make a stock viewer
request our names or draw sectors. The relevant interfaces are in
[usdExecImaging](https://github.com/PixarAnimationStudios/OpenUSD/tree/47154dc7b5e28df623745495a7a508b69535ba24/pxr/usdImaging/usdExecImaging).

A usdview integration sketch is a small compiled bridge with a Python UI:

1. The C++ bridge retains the stage, execution system and batch request.
2. Driver edits and time changes schedule evaluation on the viewer thread.
3. It returns matrices and point buffers to a custom scene index or draw
   overlay. The 24 × 14 grid topology comes from `sectors.sector_mesh`.
4. The overlay uses world points with an identity transform, or converts
   them back to sensor-local points before applying the sensor transform.
   This avoids applying the pose twice. Camera optics need their own data
   source mapping too; the stock xform overlay is insufficient.
5. Python supplies controls and redraw scheduling through that bridge.
   It never calls a nonexistent `pxr.ExecUsd` binding. Hide the selected
   sensor's own sector while looking through it.

That integration is a sketch, not a delivered viewer plugin. For sharing
with any USD viewer, use the codeless library's derive command and its baked
Camera/guide Mesh layers; plugin-free composition is the B7 contract.

The current native plugin was rebuilt from this tree. Core and CCTV use their
committed source plugins. Parity detaches its derived output between edit
phases as required by the output-safety contract. C++ computations are unchanged.
See [current acceptance](migration.md) for the measured checks and single Nix attempt.
