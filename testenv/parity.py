#!/usr/bin/env python3
"""Parity of the execAecoCctv computations with the library's Tier A derivation.

Reads the JSON document printed by the ``execcctv`` consumer and recomputes
every value for the same stage with ``usdaeco_cctv.derive.sensor_state``.
The merged library (v0.1.0 or newer) and numpy are required. No inline
formula fallback can turn a missing reference into an acceptance pass.
With --baked it also runs the derivation into an anonymous layer and compares
its double attributes and float32 mesh points.

Run with a Python that imports ``pxr``; set ``PXR_PLUGINPATH_NAME`` to the core
and cctv resource directories (never to this plugin: its library is built for
the OpenExec USD, not necessarily for this interpreter's).

    parity.py <execcctv.json> [--cctv-root DIR] [--baked] [--json REPORT]
"""
import argparse
import importlib
import json
import math
import os
from pathlib import Path
import sys
import types

# Explicit usd-dev bindings, after callers have removed any global PYTHONPATH.
if os.environ.get("USD_DEV"):
    bindings = Path(os.environ["USD_DEV"]) / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    if not (bindings / "pxr").is_dir():
        raise RuntimeError("USD_DEV has no bindings for this Python interpreter")
    sys.path.insert(0, str(bindings))

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ANGLE_TOLERANCE = 1e-9   # degrees, also mm (widths) and m (ranges, matrices)
POINT_TOLERANCE = 1e-6   # m: what a point3f[] mesh keeps of a point within 32 m of its frame origin
SECTOR_NU, SECTOR_NV = 24, 14
COMPUTATIONS = ("computeEffectiveWidth", "computeFieldOfView", "computeSensorToWorld",
                "computeTargetRange", "computeTargetRangeArc", "computeSectorPoints")


def cctv_root(explicit=None):
    return Path(explicit or os.environ.get("CCTV_ROOT")
                or os.environ.get("AECO_CCTV_ROOT") or ROOT.parent / "usdaeco-cctv")


def load_reference(root):
    """Load the shipped derivation; import and API errors are fatal."""
    tools = str(Path(root) / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    derive = importlib.import_module("usdaeco_cctv.derive")
    return types.SimpleNamespace(
        mode="derive", derive=derive,
        density=importlib.import_module("usdaeco_cctv.density"),
        sectors=importlib.import_module("usdaeco_cctv.sectors"))


def reference_values(stage, path, reference):
    """Every computation for one sensor prim, from the drivers on the stage.

    Invalid drivers fail parity; validation belongs to the codeless library.
    """
    from pxr import Gf, UsdGeom
    prim = stage.GetPrimAtPath(path)
    if not prim:
        raise ValueError("no prim at " + path)
    derive = reference.derive
    reader = derive.Reader(stage)
    state = derive.sensor_state(derive.drivers_of(prim, reader), derive.settings_of(stage, reader))
    pixels = tuple(prim.GetAttribute("aeco:cctvSensor:pixels").Get())
    hfov, vfov = state["hfov"], state["vfov"]
    arc = reference.density.range_at_density(pixels[0], hfov, state["density"], "arc") if pixels[0] > 0 else 0.0
    matrix = state["matrix"] * UsdGeom.XformCache().GetLocalToWorldTransform(prim.GetParent())
    points = []
    if state["radius"] > 0:
        grid = reference.sectors.sector_mesh(hfov, vfov, state["radius"], projection=state["projection"])[0]
        points = [tuple(matrix.Transform(Gf.Vec3d(*map(float, p)))) for p in grid]
    return {"computeEffectiveWidth": state["effectiveWidth"],
            "computeFieldOfView": (hfov, vfov),
            "computeSensorToWorld": [list(matrix[i]) for i in range(4)],
            "computeTargetRange": state["targetRange"], "computeTargetRangeArc": arc,
            "computeSectorPoints": points}


def baked_values(stage, path):
    """What the derivation authored for one sensor (after derive() ran on the stage)."""
    from pxr import Gf, UsdGeom
    prim = stage.GetPrimAtPath(path)
    get = lambda name: prim.GetAttribute("aeco:cctvSensor:" + name).Get()
    matrix = UsdGeom.XformCache().GetLocalToWorldTransform(prim)
    sector = prim.GetChild("Sector")
    points = []
    if sector:
        points = [tuple(matrix.Transform(Gf.Vec3d(p))) for p in sector.GetAttribute("points").Get()]
    return {"computeEffectiveWidth": get("effectiveWidth"), "computeFieldOfView": (get("hfov"), get("vfov")),
            "computeSensorToWorld": [list(matrix[i]) for i in range(4)],
            "computeTargetRange": get("targetRange"), "computeSectorPoints": points}


def deviation(computed, expected):
    """Maximum absolute error; shape differences and nonfinite values fail."""
    if isinstance(expected, (int, float)):
        if not isinstance(computed, (int, float)):
            return math.inf
        if not math.isfinite(computed) or not math.isfinite(expected):
            return math.inf
        return abs(computed - expected)
    if not isinstance(computed, (list, tuple)) or len(computed) != len(expected):
        return math.inf
    return max((deviation(a, b) for a, b in zip(computed, expected)), default=0.0)


def validate_document(document, stage):
    """Require every stage sensor exactly once in both phases and all results."""
    from pxr import UsdGeom
    sensors = {str(p.GetPath()) for p in stage.Traverse()
               if p.IsA(UsdGeom.Camera) and p.HasAPI("AecoCctvSensorAPI")}
    records = document["records"]
    wanted = {(phase, path) for phase in ("before", "after") for path in sensors}
    actual = [(r["phase"], r["path"]) for r in records]
    if not sensors or len(actual) != len(wanted) or set(actual) != wanted:
        raise ValueError("records must contain every sensor once before and after the edit")
    if any(not set(COMPUTATIONS) <= r.keys() for r in records):
        raise ValueError("record is missing a computation")
    edit = document["edit"]
    if edit["path"] not in sensors or edit["attribute"] != "aeco:cctvSensor:pan":
        raise ValueError("expected a pan edit on a stage sensor")
    pan = stage.GetPrimAtPath(edit["path"]).GetAttribute(edit["attribute"]).Get()
    if edit["before"] != pan or not math.isfinite(edit["after"]) or edit["after"] == pan:
        raise ValueError("edit must change the original pan to a finite value")


def _replay_edit(stage, document):
    edit = document["edit"]
    stage.SetEditTarget(stage.GetSessionLayer())
    stage.GetPrimAtPath(edit["path"]).GetAttribute(edit["attribute"]).Set(edit["after"])


def compare(document, reference, stage_path=None, baked=False):
    """{computation: max deviation} over every record, and the record count.

    The 'after' records are checked against the stage with the consumer's edit
    replayed in a session layer, so the recomputation is verified, not only
    the invalidation. With baked=True the derivation is run on the stage and
    its authored values are the expectation instead of the state function.
    """
    from pxr import Sdf, Usd
    stage = Usd.Stage.Open(str(stage_path or document["stage"]))
    if not stage:
        raise RuntimeError("cannot open " + document["stage"])
    validate_document(document, stage)
    if baked and (reference is None or reference.mode != "derive"):
        raise RuntimeError("the baked comparison needs usdaeco_cctv.derive")
    layer = Sdf.Layer.CreateAnonymous("execAecoCctv-parity.usda") if baked else None
    worst = {name: 0.0 for name in COMPUTATIONS}
    counted = 0
    for phase in ("before", "after"):
        if phase == "after":
            _replay_edit(stage, document)
        if baked:
            # derive() composes its output; detach it before the next phase so
            # the output is never also an input to the reference computation.
            if layer.identifier in stage.GetSessionLayer().subLayerPaths:
                stage.GetSessionLayer().subLayerPaths.remove(layer.identifier)
            stats = reference.derive.derive(stage, layer)
            if stats.get("skipped"):
                raise ValueError("derivation skipped sensors: " + str(stats["skipped"]))
        for record in document["records"]:
            if record["phase"] != phase:
                continue
            expected = baked_values(stage, record["path"]) if baked else reference_values(stage, record["path"], reference)
            for name in expected:
                worst[name] = max(worst[name], deviation(record[name], expected[name]))
            counted += 1
    if baked:
        worst.pop("computeTargetRangeArc")  # the derivation bakes one model only
    return worst, counted


def tolerance(name):
    return POINT_TOLERANCE if name == "computeSectorPoints" else ANGLE_TOLERANCE


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("document", type=Path, help="JSON printed by execcctv")
    parser.add_argument("--cctv-root", type=Path, help="usdaeco-cctv checkout (its tools/ is the reference)")
    parser.add_argument("--stage", type=Path, help="override the stage path recorded in the document")
    parser.add_argument("--baked", action="store_true", help="also compare with a derived layer written by the library")
    parser.add_argument("--json", type=Path, help="write the deviations here")
    args = parser.parse_args(argv)
    document = json.loads(args.document.read_text())
    reference = load_reference(cctv_root(args.cctv_root))
    source = reference.mode
    failed, report = 0, {"reference": source}
    for baked in ((False, True) if args.baked else (False,)):
        worst, counted = compare(document, reference, args.stage, baked)
        label = "baked layer" if baked else source
        print(f"reference: {label}; {counted} sensor records compared")
        for name, value in worst.items():
            ok = value <= tolerance(name)
            failed += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {name}  max |dev| = {value:.3e} (tol {tolerance(name):g})")
        report["baked" if baked else "state"] = {"records": counted, "deviations": worst}
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
