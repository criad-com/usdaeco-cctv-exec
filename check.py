#!/usr/bin/env python3
"""Check source packaging and native claims: N checks, M failed, K not run."""
import importlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
KIT = Path(os.environ.get("TOOLCHAIN_DIR", ROOT.parent / "usdaeco-toolchain"))
sys.path[:0] = [str(ROOT / "tools"), str(KIT / "tools"), str(ROOT)]
from usdaeco_check import link_check
from usdaeco_check.structure import check_structure
import tools_native_check as native
from tools_native_check import Report


def dependency_versions(args):
    pins = json.loads((ROOT / "dependencies.json").read_text())["repos"]
    actual = {
        "toolchain": json.loads((KIT / "library.json").read_text())["version"],
        "usdaeco-core": native.read_plug_info(args.core_plugin / "plugInfo.json")["Info"]["aeco"]["version"],
        "usdaeco-cctv": native.read_plug_info(args.cctv_plugin / "plugInfo.json")["Info"]["aeco"]["version"],
    }
    expected = {name: pins[name]["ref"].removeprefix("v") for name in actual}
    return actual == expected, ", ".join(f"{name} {version}" for name, version in actual.items())


def core_validation(args):
    """Import and execute every declared core validator; an empty registry fails."""
    from pxr import Plug, Usd, UsdValidation
    core = Path(os.environ.get("AECO_CORE_ROOT", os.environ.get("CORE_DIR", ROOT.parent / "usdaeco-core")))
    descriptor = core / "usdAecoValidators" / "plugInfo.json"
    for path in (args.core_plugin, args.cctv_plugin, descriptor.parent):
        Plug.Registry().RegisterPlugins(str(path))
    # Import explicitly: a missing core checkout must never yield an empty pass.
    importlib.import_module("usdAecoValidators")
    declared = native.read_plug_info(descriptor)["Info"]["Validators"]
    names = sorted("usdAecoValidators:" + name for name, data in declared.items() if isinstance(data, dict))
    if not names:
        raise RuntimeError("usdAecoValidators declares no validators")
    registry = UsdValidation.ValidationRegistry()
    validators = registry.GetOrLoadValidatorsByName(names)
    if len(validators) != len(names) or not all(validators):
        raise RuntimeError("usdAecoValidators did not load every declared validator")
    stage = Usd.Stage.Open(str(args.stage or args.cctv_root / "examples/lobby.usda"))
    if not stage or stage.GetCompositionErrors():
        raise RuntimeError("CCTV input stage did not compose")
    findings = UsdValidation.ValidationContext(validators).Validate(stage)
    errors = [e for e in findings if e.GetType() == UsdValidation.ValidationErrorType.Error]
    return not errors, f"{len(validators)} core validators executed; {len(errors)} errors, {len(findings) - len(errors)} other findings"


def main(argv=None):
    args = native.argument_parser().parse_args(argv)
    report = Report()
    print("== stage: library structure", flush=True)
    for result in check_structure(ROOT):
        report.add(result)
    report.add(link_check(ROOT / "README.md"))
    report.add(link_check(ROOT / "docs"))
    print("== stage: pinned dependencies and core validation", flush=True)
    report.run("tested dependency versions", dependency_versions, args)
    report.run("core validators on CCTV input", core_validation, args)
    print("== stage: native 21-claim gate", flush=True)
    native.run_checks(args, report)
    native.write_report(args.report, report)
    return report.finish()


if __name__ == "__main__":
    raise SystemExit(main())
