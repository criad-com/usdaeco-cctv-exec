"""Snapshot authored values and world transforms in a fresh USD process."""
import json
import sys

import parity  # configures the explicitly selected usd-dev Python bindings
from pxr import Tf, Usd, UsdGeom

stage = Usd.Stage.Open(sys.argv[1])
fallbacks = stage.GetMetadata("fallbackPrimTypes") or {}
snapshot = {}
for prim in stage.Traverse():
    if prim.GetTypeName().startswith("Aeco") and prim.GetTypeName() not in fallbacks:
        raise ValueError("missing fallbackPrimTypes for " + prim.GetTypeName())
    snapshot[str(prim.GetPath())] = {
        "attributes": {a.GetName(): repr(a.Get()) for a in prim.GetAuthoredAttributes()},
        "world": repr(UsdGeom.XformCache().GetLocalToWorldTransform(prim)),
    }
print(json.dumps({"schema": bool(Tf.Type.FindByName("UsdAecoCctvSensorAPI")),
                  "snapshot": snapshot}, sort_keys=True))
