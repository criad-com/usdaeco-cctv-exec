"""Integration parity and regressions against false acceptance passes."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools_native_check as check
import parity


@pytest.fixture(scope="module")
def lobby(tmp_path_factory):
    d = check.defaults()
    os.environ["PXR_PLUGINPATH_NAME"] = os.pathsep.join(map(str, (d["core_plugin"], d["cctv_plugin"])))
    stage = d["cctv_root"] / "examples/lobby.usda"
    # Include every composed file layer, including the checked-in derived layer.
    from pxr import Usd
    opened = Usd.Stage.Open(str(stage))
    files = [Path(layer.realPath) for layer in opened.GetUsedLayers() if layer.realPath]
    hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    done = check.run_consumer(d["consumer"], stage,
                              [d["core_plugin"], d["cctv_plugin"], d["plugin_dir"]],
                              tmp_path_factory.mktemp("exec"))
    assert done.returncode == 0, done.stderr
    yield json.loads(done.stdout), parity.load_reference(d["cctv_root"]), stage
    assert hashes == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


@pytest.mark.parametrize("baked", [False, True])
def test_lobby_derivation_parity(lobby, baked):
    document, reference, stage = lobby
    worst, count = parity.compare(document, reference, stage, baked=baked)
    assert count == 8
    assert all(v <= parity.tolerance(k) for k, v in worst.items()), worst


def test_pan_invalidation(lobby):
    assert check.invalidation_claim(lobby[0])[0]
    assert check.topology_claim(lobby[0])[0]


@pytest.mark.parametrize("damage", ["empty", "missing", "duplicate", "missing_result"])
def test_incomplete_results_fail(lobby, damage):
    document, reference, stage = lobby
    document = deepcopy(document)
    if damage == "empty":
        document["records"] = []
    elif damage == "missing":
        document["records"].pop()
    elif damage == "duplicate":
        document["records"][-1] = document["records"][0]
    else:
        del document["records"][0]["computeFieldOfView"]
    with pytest.raises(ValueError):
        parity.compare(document, reference, stage)


@pytest.mark.parametrize("name,delta", [("computeEffectiveWidth", 1e-5),
                                       ("computeFieldOfView", 1e-5),
                                       ("computeSectorPoints", 1e-3)])
def test_corrupted_results_fail(lobby, name, delta):
    document, reference, stage = lobby
    document = deepcopy(document)
    value = document["records"][0][name]
    if name == "computeEffectiveWidth":
        document["records"][0][name] += delta
    elif name == "computeFieldOfView":
        value[0] += delta
    else:
        value[1][0] += delta
    worst, _ = parity.compare(document, reference, stage)
    assert worst[name] > parity.tolerance(name)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_results_fail(lobby, bad):
    document, reference, stage = lobby
    document = deepcopy(document)
    document["records"][0]["computeSectorPoints"][1][0] = bad
    worst, _ = parity.compare(document, reference, stage)
    assert worst["computeSectorPoints"] == float("inf")


def test_shape_mismatch_fails():
    assert parity.deviation([[1, 2]], [1, 2]) == float("inf")


def test_reversed_vertex_order_fails(lobby):
    document, reference, stage = lobby
    document = deepcopy(document)
    points = document["records"][0]["computeSectorPoints"]
    points[1:] = reversed(points[1:])
    worst, _ = parity.compare(document, reference, stage)
    assert worst["computeSectorPoints"] > parity.POINT_TOLERANCE
