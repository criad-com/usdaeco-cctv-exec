#!/usr/bin/env python3
"""Acceptance claims for the execAecoCctv OpenExec plugin.

Runs the built consumer (``execcctv``) on the library's worked example
with the core, cctv and exec plugins registered, then
checks parity with the Python contract, the invalidation behaviour, the
manifest and the repository hygiene. Ends with
``N checks, M failed, K not run``.

    tools_native_check.py [--native] [--plugin-dir ...] [--consumer ...]
"""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
KIT = Path(os.environ.get("TOOLCHAIN_DIR", ROOT.parent / "usdaeco-toolchain"))
sys.path[:0] = [str(ROOT / "testenv"), str(KIT / "tools")]
from usdaeco_check import Report as FamilyReport
import parity  # noqa: E402

SECTOR_POINTS = 1 + (parity.SECTOR_NU + 1) * (parity.SECTOR_NV + 1)
PRIVATE = [r"\b(?:10\.\d{1,3}|192\.168)\.\d{1,3}\.\d{1,3}\b", r"[/]Volumes[/]", r"[/]Users[/]"]
SWEPT = ["README.md", "docs", "src", "testenv", "resources", "check.py", "build.sh", "flake.nix",
         "CMakeLists.txt", "library.json", "dependencies.json"]


CHECK_NAMES = (
    "manifest", "installed plugin", "exec plugin metadata", "dependency plugins",
    "consumer run", "sensors evaluated",
    *(f"lobby parity {name}" for name in parity.COMPUTATIONS),
    "lobby parity with the baked derived layer", "invalidation", "sector topology",
    "orphan consumer run", "orphan parity",
    "orphan sensors: derivation skips, exec evaluates",
    "vanilla USD [B7]", "term sweep", "links",
)


class Report(FamilyReport):
    """Adapt the native claims' (ok, detail) callbacks to the shared report."""

    def run(self, name, function, *args):
        try:
            value = function(*args)
            ok, detail = value if isinstance(value, tuple) else (value, "")
            return self.check(name, ok, detail)
        except Exception as exc:  # a failing claim never stops the others
            return self.check(name, False, f"{type(exc).__name__}: {exc}")


def read_plug_info(path):
    """plugInfo.json with the leading '#' comment lines usdGenSchema writes."""
    text = re.sub(r"^\s*#.*$", "", Path(path).read_text(), flags=re.M)
    return json.loads(text)["Plugins"][0]


def defaults():
    core_root = Path(os.environ.get("AECO_CORE_ROOT", os.environ.get("CORE_DIR", ROOT.parent / "usdaeco-core")))
    cctv_root = parity.cctv_root()
    return {
        "plugin_dir": Path(os.environ.get("EXEC_PLUGIN_DIR", ROOT / "build/install/plugin/usd/execAecoCctv")),
        "consumer": Path(os.environ.get("EXEC_CONSUMER", ROOT / "build/install/bin/execcctv")),
        "core_plugin": Path(os.environ.get("CORE_PLUGIN_DIR", core_root / "usdAeco")),
        "cctv_plugin": Path(os.environ.get("CCTV_PLUGIN_DIR", cctv_root / "usdAecoCctv")),
        "cctv_root": cctv_root,
    }


def run_consumer(consumer, stage, plugin_path, out_dir):
    env = dict(os.environ, PXR_PLUGINPATH_NAME=os.pathsep.join(map(str, plugin_path)))
    env.pop("PYTHONPATH", None)
    done = subprocess.run([str(consumer), str(stage)], env=env, capture_output=True, text=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / (Path(stage).stem + ".json")).write_text(done.stdout)
    (out_dir / (Path(stage).stem + ".log")).write_text(done.stderr)
    return done


def parity_claims(report, label, document, reference, stage):
    worst, counted = parity.compare(document, reference, stage)
    source = reference.mode if reference else "inline contract"
    for name in parity.COMPUTATIONS:
        tol = parity.tolerance(name)
        report.check(f"{label} parity {name}", worst[name] <= tol,
                     f"max |dev| {worst[name]:.3e} <= {tol:g} over {counted} records ({source})")


def baked_claim(document, reference, stage):
    """The values the library's derivation bakes into a layer agree with the computed ones."""
    if reference is None or reference.mode != "derive":
        return False, "usdaeco_cctv.derive is not importable (library checkout too old, or no numpy)"
    worst, counted = parity.compare(document, reference, stage, baked=True)
    bad = {n: f"{w:.3e}" for n, w in worst.items() if w > parity.tolerance(n)}
    detail = ", ".join(f"{n.replace('compute', '')} {w:.1e}" for n, w in worst.items())
    return not bad, f"derived layer vs exec over {counted} records: {detail}" if not bad else str(bad)


def orphan_derivation_claim(reference, stage_path, evaluated):
    """The library derives sensors of camera elements only; exec answers for any sensor prim."""
    if reference is None or reference.mode != "derive":
        return False, "usdaeco_cctv.derive is not importable (library checkout too old, or no numpy)"
    from pxr import Sdf, Usd
    stage = Usd.Stage.Open(str(stage_path))
    stats = reference.derive.derive(stage, Sdf.Layer.CreateAnonymous("execAecoCctv-orphan.usda"))
    return (stats["sensors"] == 0 and evaluated > 0,
            f"derivation wrote {stats['sensors']} sensors (no camera element), exec evaluated {evaluated}")


def invalidation_claim(document):
    before = {r["path"]: r for r in document["records"] if r["phase"] == "before"}
    after = {r["path"]: r for r in document["records"] if r["phase"] == "after"}
    edited = document["edit"]["path"]
    wrong = []
    for path, b in before.items():
        a = after[path]
        for name in parity.COMPUTATIONS:
            expected = path == edited and name in ("computeSensorToWorld", "computeSectorPoints")
            if (a[name] != b[name]) != expected:
                wrong.append(f"{path.rsplit('/', 2)[-2]}:{name}")
    return not wrong, ("edited sensor: matrix and points changed, nothing else did"
                       if not wrong else "unexpected: " + ", ".join(wrong))


def topology_claim(document):
    counts, apex_error = set(), 0.0
    for record in document["records"]:
        points = record["computeSectorPoints"]
        if not points:
            continue
        counts.add(len(points))
        translation = record["computeSensorToWorld"][3][:3]
        apex_error = max(apex_error, max(abs(p - t) for p, t in zip(points[0], translation)))
    ok = counts == {SECTOR_POINTS} and apex_error <= parity.POINT_TOLERANCE
    return ok, f"{sorted(counts)} points per sector (expect {SECTOR_POINTS}), apex at the sensor within {apex_error:.1e} m"


def term_sweep():
    hits = []
    for entry in SWEPT:
        path = ROOT / entry
        files = [p for p in path.rglob("*") if p.is_file()] if path.is_dir() else [path] if path.exists() else []
        for file in files:
            if file.suffix in (".dylib", ".so", ".pyc") or "__pycache__" in file.parts:
                continue
            text = file.read_text(errors="replace")
            for pattern in PRIVATE:
                if re.search(pattern, text):
                    hits.append(f"{file.relative_to(ROOT)}: {pattern}")
    return not hits, "no private addresses or local paths in committed text" if not hits else "; ".join(hits)


def link_check():
    broken = []
    for doc in (ROOT / "README.md", ROOT / "docs/README.md"):
        if not doc.exists():
            continue
        for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", doc.read_text()):
            if "://" in target:
                continue
            if not (doc.parent / target).exists():
                broken.append(f"{doc.relative_to(ROOT)} -> {target}")
    return not broken, "README and docs links resolve" if not broken else "; ".join(broken)


def vanilla_claim(stages, schema_plugins):
    for stage in stages:
        snapshots = []
        for plugins in (schema_plugins, []):
            env = dict(os.environ, PXR_PLUGINPATH_NAME=os.pathsep.join(map(str, plugins)))
            env.pop("PYTHONPATH", None)
            done = subprocess.run([sys.executable, str(ROOT / "testenv/vanilla.py"), str(stage)],
                                  env=env, capture_output=True, text=True, check=True)
            snapshots.append(json.loads(done.stdout))
        if not snapshots[0]["schema"] or snapshots[1]["schema"]:
            return False, "fresh subprocesses did not isolate schema registration"
        if snapshots[0]["snapshot"] != snapshots[1]["snapshot"]:
            return False, "authored values or world transforms differ on " + stage.name
    return True, f"{len(stages)} stages: complete fallbacks, identical authored values and world transforms"


def argument_parser():
    d = defaults()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plugin-dir", type=Path, default=d["plugin_dir"], help="installed execAecoCctv resource directory")
    parser.add_argument("--consumer", type=Path, default=d["consumer"], help="the built execcctv executable")
    parser.add_argument("--core-plugin", type=Path, default=d["core_plugin"])
    parser.add_argument("--cctv-plugin", type=Path, default=d["cctv_plugin"])
    parser.add_argument("--cctv-root", type=Path, default=d["cctv_root"], help="usdaeco-cctv checkout (example + reference modules)")
    parser.add_argument("--stage", type=Path, help="stage to evaluate (default: the library's examples/lobby.usda)")
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts", help="where the consumer's JSON and logs go")
    parser.add_argument("--report", type=Path, help="write the claims as JSON")
    parser.add_argument("--native", action="store_true", help="fail if native execution is unavailable")
    return parser


def unavailable_reason(options):
    """Missing native artifacts defer the gate; present but broken ones fail it."""
    get = options.get if isinstance(options, dict) else lambda key: getattr(options, key)
    missing = []
    if not get("consumer").is_file():
        missing.append("usd-dev consumer is missing")
    elif not os.access(get("consumer"), os.X_OK):
        missing.append("usd-dev consumer is not executable")
    if not (get("plugin_dir") / "plugInfo.json").is_file():
        missing.append("installed exec plugin descriptor is missing")
    return "; ".join(missing)


def run_checks(args, report):
    """Retain every planned native row, including when an earlier claim fails."""
    start = len(report.results)
    reason = unavailable_reason(args)
    if reason:
        reason += "; build in the nix devShell and run check.py --native"
        if args.native:
            report.check("required native artifacts", False, reason)
    else:
        try:
            _run_checks(args, report)
        except Exception as exc:
            report.check("native execution", False, f"{type(exc).__name__}: {exc}")
        reason = "native gate stopped after a failed prerequisite; see preceding FAIL rows"
    completed = {r.name for r in report.results[start:]}
    for name in CHECK_NAMES:
        if name not in completed:
            report.not_run(name, reason)


def write_report(path, report):
    """Keep NOT RUN distinct from FAIL and PASS in machine-readable evidence."""
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "version": json.loads((ROOT / "library.json").read_text())["version"],
            "checks": [{**asdict(r), "status": r.status} for r in report.results],
            "total": len(report.results),
            "passed": sum(r.ok is True for r in report.results),
            "failed": report.failed,
            "not_run": report.not_run_count,
        }, indent=2) + "\n")


def _run_checks(args, report):
    stage = args.stage or args.cctv_root / "examples/lobby.usda"
    schema_plugins = [args.core_plugin, args.cctv_plugin]
    os.environ["PXR_PLUGINPATH_NAME"] = os.pathsep.join(map(str, schema_plugins))
    print("== stage: native manifest and plugins", flush=True)
    manifest = json.loads((ROOT / "library.json").read_text())
    report.check("manifest", manifest.get("plugin") == "execAecoCctv" and manifest.get("tier") == "toolchain"
                 and set(manifest.get("requires", {})) == {"usdAeco", "usdAecoCctv"}
                 and re.fullmatch(r"\d+\.\d+\.\d+", manifest.get("version", "")),
                 f"execAecoCctv {manifest.get('version')} tier {manifest.get('tier')} requires {manifest.get('requires')}")

    def installed():
        info = read_plug_info(args.plugin_dir / "plugInfo.json")
        library = args.plugin_dir / info["LibraryPath"]
        expected = {k: v for k, v in manifest.items() if k in ("version", "tier", "requires")}
        return (info["Type"] == "library" and library.exists() and info["Info"]["aeco"] == expected,
                f"{library.name}, Info.aeco == library.json")
    report.run("installed plugin", installed)

    def exec_metadata():
        schemas = read_plug_info(args.plugin_dir / "plugInfo.json")["Info"]["Exec"]["Schemas"]
        wanted = {"UsdAecoCctvSensorAPI", "UsdAecoCctvCameraAPI"}
        return (wanted <= set(schemas) and all(schemas[s].get("allowsPluginComputations") is True for s in wanted),
                "Exec.Schemas declares " + ", ".join(sorted(wanted)))
    report.run("exec plugin metadata", exec_metadata)

    def dependencies():
        core = read_plug_info(args.core_plugin / "plugInfo.json")["Info"]
        cctv = read_plug_info(args.cctv_plugin / "plugInfo.json")["Info"]
        ok = (core["aeco"]["tier"] == "core" and "aecoDerived" in core.get("SdfMetadata", {})
              and cctv["aeco"]["tier"] == "kind" and {"UsdAecoCctvSensorAPI", "UsdAecoCctvCameraAPI"} <= set(cctv["Types"]))
        return ok, f"usdAeco {core['aeco']['version']} (registers aecoDerived), usdAecoCctv {cctv['aeco']['version']} (registers both types)"
    report.run("dependency plugins", dependencies)

    print("== stage: native consumer", flush=True)
    if not stage.is_file():
        report.check("stage available", False, "the library's examples/lobby.usda is required")
        return
    done = run_consumer(args.consumer, stage, schema_plugins + [args.plugin_dir], args.out)
    passed = done.returncode == 0 and "STAGE PASS" in done.stderr
    report.check("consumer run", passed, done.stderr.strip().splitlines()[-1] if done.stderr.strip() else "no output")
    if not passed:
        return
    document = json.loads(done.stdout)
    sensors = {r["path"] for r in document["records"]}
    report.check("sensors evaluated", len(sensors) >= 4 and len(document["records"]) == 2 * len(sensors),
                 f"{len(sensors)} sensors x {len(parity.COMPUTATIONS)} computations x 2 phases")

    print("== stage: parity with the Python contract", flush=True)
    reference = parity.load_reference(args.cctv_root)
    parity_claims(report, "lobby", document, reference, stage)
    report.run("lobby parity with the baked derived layer", baked_claim, document, reference, stage)
    report.run("invalidation", invalidation_claim, document)
    report.run("sector topology", topology_claim, document)

    print("== stage: orphan sensor (no camera element above it)", flush=True)
    orphan = ROOT / "testenv/orphan.usda"
    done = run_consumer(args.consumer, orphan, schema_plugins + [args.plugin_dir], args.out)
    report.check("orphan consumer run", done.returncode == 0 and "STAGE PASS" in done.stderr,
                 done.stderr.strip().splitlines()[-1] if done.stderr.strip() else "no output")
    if done.returncode == 0:
        orphan_document = json.loads(done.stdout)
        worst, counted = parity.compare(orphan_document, reference, orphan)
        bad = {n: w for n, w in worst.items() if w > parity.tolerance(n)}
        report.check("orphan parity", not bad,
                     f"execGeom ancestor frame, fisheye and radar heads: max |dev| {max(worst.values()):.3e} over {counted} records"
                     if not bad else str(bad))
        report.run("orphan sensors: derivation skips, exec evaluates", orphan_derivation_claim, reference, orphan,
                   len({r["path"] for r in orphan_document["records"]}))

    print("== stage: native hygiene", flush=True)
    report.run("vanilla USD [B7]", vanilla_claim, [stage, orphan], schema_plugins)
    report.run("term sweep", term_sweep)
    report.run("links", link_check)


def main(argv=None):
    args = argument_parser().parse_args(argv)
    report = Report()
    run_checks(args, report)
    write_report(args.report, report)
    return report.finish()


if __name__ == "__main__":
    sys.exit(main())
