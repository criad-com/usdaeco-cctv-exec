// Consumer of the execAecoCctv plugin: opens a stage, builds one request for
// the sensor computations on every sensor, prints the values as one JSON document,
// edits one sensor's pan in the session layer and recomputes the same request.
// Exit 0 only when the edit invalidated exactly the pose-dependent results.
//
// usage: execcctv <stage.usda>   (PXR_PLUGINPATH_NAME = core : cctv : this plugin)
#include "pxr/pxr.h"
#include "pxr/base/gf/matrix4d.h"
#include "pxr/base/gf/vec2d.h"
#include "pxr/base/gf/vec3d.h"
#include "pxr/base/js/json.h"
#include "pxr/base/tf/errorMark.h"
#include "pxr/base/tf/token.h"
#include "pxr/base/vt/value.h"
#include "pxr/usd/usd/prim.h"
#include "pxr/usd/usd/primRange.h"
#include "pxr/usd/usd/stage.h"
#include "pxr/usd/usdGeom/camera.h"
#include "pxr/exec/execUsd/cacheView.h"
#include "pxr/exec/execUsd/request.h"
#include "pxr/exec/execUsd/system.h"
#include "pxr/exec/execUsd/valueKey.h"
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

PXR_NAMESPACE_USING_DIRECTIVE

namespace {

const std::vector<TfToken> kComputations = {
    TfToken("computeEffectiveWidth"), TfToken("computeFieldOfView"),
    TfToken("computeSensorToWorld"), TfToken("computeTargetRange"),
    TfToken("computeTargetRangeArc"), TfToken("computeSectorPoints")};

// Which results must change when a sensor's pan changes.
bool _PoseDependent(const TfToken &name)
{
    return name == kComputations[2] || name == kComputations[5];
}

JsValue _Json(const VtValue &value)
{
    if (value.IsHolding<double>()) {
        return JsValue(value.UncheckedGet<double>());
    }
    JsArray array;
    if (value.IsHolding<GfVec2d>()) {
        const GfVec2d v = value.UncheckedGet<GfVec2d>();
        array = {JsValue(v[0]), JsValue(v[1])};
    } else if (value.IsHolding<GfMatrix4d>()) {
        const GfMatrix4d m = value.UncheckedGet<GfMatrix4d>();
        for (int i = 0; i != 4; ++i) {
            JsArray row;
            for (int j = 0; j != 4; ++j) row.emplace_back(m[i][j]);
            array.emplace_back(row);
        }
    } else if (value.IsHolding<std::vector<GfVec3d>>()) {
        for (const GfVec3d &p : value.UncheckedGet<std::vector<GfVec3d>>()) {
            array.emplace_back(JsArray{JsValue(p[0]), JsValue(p[1]), JsValue(p[2])});
        }
    } else {
        throw std::runtime_error("unexpected or empty computation result of type "
                                 + value.GetTypeName());
    }
    return JsValue(array);
}

std::vector<VtValue>
_Snapshot(ExecUsdSystem &system, const ExecUsdRequest &request,
          const std::vector<UsdPrim> &sensors, const char *phase, JsArray *records)
{
    const ExecUsdCacheView view = system.Compute(request);
    std::vector<VtValue> values;
    for (size_t s = 0; s < sensors.size(); ++s) {
        JsObject record{{"phase", JsValue(std::string(phase))},
                        {"path", JsValue(sensors[s].GetPath().GetString())}};
        for (size_t c = 0; c < kComputations.size(); ++c) {
            values.push_back(view.Get(int(s * kComputations.size() + c)));
            record[kComputations[c].GetString()] = _Json(values.back());
        }
        records->emplace_back(record);
    }
    return values;
}

} // namespace

int main(int argc, char **argv)
{
    try {
        if (argc != 2) {
            throw std::runtime_error("usage: execcctv <stage.usda>");
        }
        TfErrorMark errors;
        std::cerr << "STAGE open " << argv[1] << " and collect sensors\n";
        const UsdStageRefPtr stage = UsdStage::Open(argv[1]);
        if (!stage) {
            throw std::runtime_error("cannot open stage");
        }
        std::vector<UsdPrim> sensors;
        std::vector<ExecUsdValueKey> keys;
        for (const UsdPrim &prim : stage->Traverse()) {
            if (!prim.IsA<UsdGeomCamera>() || !prim.HasAPI(TfToken("AecoCctvSensorAPI"))) {
                continue;
            }
            sensors.push_back(prim);
            for (const TfToken &name : kComputations) {
                keys.emplace_back(prim, name);
            }
        }
        if (sensors.empty()) {
            throw std::runtime_error("no Camera prim with AecoCctvSensorAPI on the stage");
        }
        std::cerr << "STAGE build one request: " << sensors.size() << " sensors x "
                  << kComputations.size() << " computations\n";
        ExecUsdSystem system(stage);
        const ExecUsdRequest request = system.BuildRequest(std::move(keys));
        system.PrepareRequest(request);
        JsArray records;
        const std::vector<VtValue> before = _Snapshot(system, request, sensors, "before", &records);

        // The edit goes to the session layer: nothing on disk changes.
        stage->SetEditTarget(stage->GetSessionLayer());
        const UsdAttribute pan = sensors[0].GetAttribute(TfToken("aeco:cctvSensor:pan"));
        double angle = 0;
        if (!pan || !pan.Get(&angle) || !pan.Set(angle + 15)) {
            throw std::runtime_error("cannot edit aeco:cctvSensor:pan on the first sensor");
        }
        std::cerr << "STAGE recompute the same request after pan " << angle << " -> "
                  << angle + 15 << " on " << sensors[0].GetPath() << "\n";
        const std::vector<VtValue> after = _Snapshot(system, request, sensors, "after", &records);
        // One JSON document: the stage, the edit and every record.
        JsObject document{{"stage", JsValue(std::string(argv[1]))},
                          {"edit", JsObject{{"path", JsValue(sensors[0].GetPath().GetString())},
                                            {"attribute", JsValue(std::string("aeco:cctvSensor:pan"))},
                                            {"before", JsValue(angle)}, {"after", JsValue(angle + 15)}}},
                          {"records", JsValue(records)}};
        std::cout << JsWriteToString(JsValue(document)) << '\n';

        for (size_t k = 0; k < before.size(); ++k) {
            const size_t sensor = k / kComputations.size();
            const TfToken &name = kComputations[k % kComputations.size()];
            const bool expected = sensor == 0 && _PoseDependent(name);
            const bool changed = before[k] != after[k];
            if (changed != expected) {
                throw std::runtime_error(
                    "invalidation mismatch: " + sensors[sensor].GetPath().GetString() + " "
                    + name.GetString() + (changed ? " changed" : " did not change"));
            }
        }
        if (!errors.IsClean()) {
            for (const TfError &error : errors) {
                std::cerr << "USD error: " << error.GetCommentary() << '\n';
            }
            throw std::runtime_error("USD reported errors");
        }
        std::cerr << "STAGE PASS " << sensors.size() << " sensors, " << kComputations.size()
                  << " computations, pan invalidation exact\n";
        return 0;
    } catch (const std::exception &e) {
        std::cerr << "FAIL " << e.what() << '\n';
        return 1;
    }
}
