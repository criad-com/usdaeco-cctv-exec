// OpenExec computations for the codeless usdAecoCctv sensor schema.
//
// Registered by TfType name (UsdAecoCctvSensorAPI, UsdAecoCctvCameraAPI) on
// schemas that have no generated C++ class. Every computation is a pure
// function of the drivers of the proposal's Tier A contract; nothing here
// authors scene description. Angles are degrees, optics millimetres, lengths
// metres, as in the schema. Gf composes with row vectors: local * parent.
#include "pxr/pxr.h"
#include "pxr/base/gf/matrix4d.h"
#include "pxr/base/gf/quatd.h"
#include "pxr/base/gf/quatf.h"
#include "pxr/base/gf/rotation.h"
#include "pxr/base/gf/vec2d.h"
#include "pxr/base/gf/vec2i.h"
#include "pxr/base/gf/vec3d.h"
#include "pxr/base/gf/vec3f.h"
#include "pxr/base/tf/diagnostic.h"
#include "pxr/base/tf/staticTokens.h"
#include "pxr/base/tf/stringUtils.h"
#include "pxr/exec/exec/registerSchema.h"
#include "pxr/exec/exec/typeRegistry.h"
#include "pxr/exec/execGeom/tokens.h"
#include "pxr/exec/vdf/context.h"
#include "pxr/exec/vdf/readIterator.h"
#include <cmath>
#include <optional>
#include <vector>

PXR_NAMESPACE_USING_DIRECTIVE

TF_DEFINE_PRIVATE_TOKENS(_tokens,
    // computations published by this plugin
    (computeEffectiveWidth)(computeFieldOfView)(computeSensorToWorld)
    (computeTargetRange)(computeTargetRangeArc)(computeSectorPoints)
    (computeDeviceToWorld)
    // sensor drivers (schema identifiers, as authored on the stage)
    ((focalLength, "aeco:cctvSensor:focalLength"))
    ((focalRange, "aeco:cctvSensor:focalRange"))
    ((hfovRange, "aeco:cctvSensor:hfovRange"))
    ((vfovRange, "aeco:cctvSensor:vfovRange"))
    ((sensorSize, "aeco:cctvSensor:sensorSize"))
    ((pixels, "aeco:cctvSensor:pixels"))
    ((offset, "aeco:cctvSensor:offset"))
    ((pan, "aeco:cctvSensor:pan"))
    ((tilt, "aeco:cctvSensor:tilt"))
    ((roll, "aeco:cctvSensor:roll"))
    ((range, "aeco:cctvSensor:range"))
    ((targetDensity, "aeco:cctvSensor:targetDensity"))
    ((projection, "aeco:cctvSensor:projection"))
    ((spectrum, "aeco:cctvSensor:spectrum"))
    (rectilinear)(fisheye)(cylindrical)(radar)
    // the camera element's placement (UsdGeomXformable vocabulary)
    (xformOpOrder)
    ((resetXformStack, "!resetXformStack!"))
    ((opTransform, "xformOp:transform"))
    ((opTranslate, "xformOp:translate"))
    ((opScale, "xformOp:scale"))
    ((opRotateX, "xformOp:rotateX"))
    ((opRotateY, "xformOp:rotateY"))
    ((opRotateZ, "xformOp:rotateZ"))
    ((opRotateXYZ, "xformOp:rotateXYZ"))
    ((opRotateXZY, "xformOp:rotateXZY"))
    ((opRotateYXZ, "xformOp:rotateYXZ"))
    ((opRotateYZX, "xformOp:rotateYZX"))
    ((opRotateZXY, "xformOp:rotateZXY"))
    ((opRotateZYX, "xformOp:rotateZYX"))
    ((opOrient, "xformOp:orient"))
    // one input name per (op, precision): exec connects only the one whose
    // value type matches the authored attribute, the other stays empty
    (translate_d)(translate_f)(scale_d)(scale_f)
    (rotateX_d)(rotateX_f)(rotateY_d)(rotateY_f)(rotateZ_d)(rotateZ_f)
    (rotateXYZ_d)(rotateXYZ_f)(rotateXZY_d)(rotateXZY_f)(rotateYXZ_d)(rotateYXZ_f)
    (rotateYZX_d)(rotateYZX_f)(rotateZXY_d)(rotateZXY_f)(rotateZYX_d)(rotateZYX_f)
    (orient_d)(orient_f));

// The sector cap grid is a value type of its own because OpenExec (dev
// 47154dc) refuses VtArray result types; std::vector<GfVec3d> is the
// registered equivalent, in double so that nothing is lost before a consumer
// rounds it into a point3f[] mesh (VtVec3fArray(v.begin(), v.end())).
TF_REGISTRY_FUNCTION(ExecTypeRegistry)
{
    ExecTypeRegistry::RegisterType(std::vector<GfVec3d>{});
}

namespace {

constexpr double kDegrees = M_PI / 180.0;
constexpr int kSectorNu = 24;
constexpr int kSectorNv = 14;
// The library's default requirement (px/m) when a sensor states none: the
// derivation takes the study's requiredDensity, which a per-sensor
// computation cannot see, and this value on a stage without a study.
constexpr double kDefaultDensity = 125.0;

// Zoom state clamped to the datasheet range; 0 = widest.
double _Focal(const VdfContext &ctx)
{
    const GfVec2d limits = ctx.GetInputValue<GfVec2d>(_tokens->focalRange);
    const double f = ctx.GetInputValue<double>(_tokens->focalLength);
    const double wanted = f == 0 ? limits[0] : f;
    return std::min(std::max(wanted, limits[0]), limits[1]);
}

// The effective sensor dimension (mm) that reproduces a datasheet FOV pair at
// focal length f: linear interpolation between the width implied at the
// minimum focal length (wide end, fov[0]) and at the maximum (telephoto end,
// fov[1]). A (0, 0) pair means "use the physical size". Invalid drivers give
// 0; validators, not exec, report them.
double _EffectiveDimension(double f, const GfVec2d &focal, const GfVec2d &fov,
                           double physical)
{
    if (fov[0] <= 0 || fov[1] <= 0) {
        return physical > 0 ? physical : 0;
    }
    const double wide = 2 * focal[0] * std::tan(fov[0] * kDegrees / 2);
    const double tele = 2 * focal[1] * std::tan(fov[1] * kDegrees / 2);
    if (focal[1] == focal[0]) {
        return wide;
    }
    return wide + (tele - wide) * (f - focal[0]) / (focal[1] - focal[0]);
}

double _FieldOfView(double size, double f)
{
    return (size > 0 && f > 0) ? 2 * std::atan(size / (2 * f)) / kDegrees : 0;
}

// The lens projection the derivation draws: a radar head with the default
// rectilinear token is drawn as a fisheye detection dome, as the library does.
TfToken _Projection(const VdfContext &ctx)
{
    const TfToken projection = ctx.GetInputValue<TfToken>(_tokens->projection);
    const TfToken spectrum = ctx.GetInputValue<TfToken>(_tokens->spectrum);
    if (spectrum == _tokens->radar && projection == _tokens->rectilinear) {
        return _tokens->fisheye;
    }
    return projection;
}

// Fisheye and cylindrical heads take their angle straight from the datasheet
// pair, interpolated over the focal range (equidistant image, arc model).
double _InterpolatedAngle(double f, const GfVec2d &focal, const GfVec2d &fov)
{
    if (focal[1] == focal[0]) {
        return fov[0];
    }
    return fov[0] + (fov[1] - fov[0]) * (f - focal[0]) / (focal[1] - focal[0]);
}

GfMatrix4d _Rotate(const GfVec3d &axis, double degrees)
{
    return GfMatrix4d(1).SetRotate(GfRotation(axis, degrees));
}

GfMatrix4d _Rotate(const GfQuatd &quat)
{
    return GfMatrix4d(1).SetRotate(GfRotation(quat));
}

// Distance (m) at which `density` px/m is met, under the plane or arc model.
double _RangeAtDensity(int pixels, double hfov, double density, bool arc)
{
    if (density <= 0 || pixels <= 0 || hfov <= 0) {
        return 0;
    }
    if (arc) {
        return pixels / (hfov * kDegrees * density);
    }
    return pixels / (2 * std::tan(hfov * kDegrees / 2) * density);
}

double _Density(const VdfContext &ctx)
{
    const double own = ctx.GetInputValue<double>(_tokens->targetDensity);
    return own > 0 ? own : kDefaultDensity;
}

// --- reading the camera element's xformOps ---------------------------------

std::optional<GfVec3d> _Vec3(const VdfContext &ctx, const TfToken &d,
                             const TfToken &f)
{
    if (const GfVec3d *v = ctx.GetInputValuePtr<GfVec3d>(d)) return *v;
    if (const GfVec3f *v = ctx.GetInputValuePtr<GfVec3f>(f)) return GfVec3d(*v);
    return std::nullopt;
}

std::optional<double> _Scalar(const VdfContext &ctx, const TfToken &d,
                              const TfToken &f)
{
    if (const double *v = ctx.GetInputValuePtr<double>(d)) return *v;
    if (const float *v = ctx.GetInputValuePtr<float>(f)) return double(*v);
    return std::nullopt;
}

std::optional<GfQuatd> _Quat(const VdfContext &ctx, const TfToken &d,
                             const TfToken &f)
{
    if (const GfQuatd *v = ctx.GetInputValuePtr<GfQuatd>(d)) return *v;
    if (const GfQuatf *v = ctx.GetInputValuePtr<GfQuatf>(f)) return GfQuatd(*v);
    return std::nullopt;
}

const GfVec3d kX(1, 0, 0), kY(0, 1, 0), kZ(0, 0, 1);

// Three-axis rotate ops: UsdGeomXformOp applies the named axes in order, so
// the row-vector matrix is R(first) * R(second) * R(third).
GfMatrix4d _RotateThree(const GfVec3d &angles, const GfVec3d &a0, int i0,
                        const GfVec3d &a1, int i1, const GfVec3d &a2, int i2)
{
    return _Rotate(a0, angles[i0]) * _Rotate(a1, angles[i1]) * _Rotate(a2, angles[i2]);
}

struct _Op {
    TfToken name;
    TfToken inputD, inputF;
};

// The matrix of one op, or nullopt when the op is not authored/supported.
std::optional<GfMatrix4d> _OpMatrix(const VdfContext &ctx, const TfToken &op)
{
    if (op == _tokens->opTransform) {
        if (const GfMatrix4d *m = ctx.GetInputValuePtr<GfMatrix4d>(_tokens->opTransform)) {
            return *m;
        }
        return std::nullopt;
    }
    if (op == _tokens->opTranslate) {
        if (auto v = _Vec3(ctx, _tokens->translate_d, _tokens->translate_f)) {
            return GfMatrix4d(1).SetTranslate(*v);
        }
        return std::nullopt;
    }
    if (op == _tokens->opScale) {
        if (auto v = _Vec3(ctx, _tokens->scale_d, _tokens->scale_f)) {
            return GfMatrix4d(1).SetScale(*v);
        }
        return std::nullopt;
    }
    if (op == _tokens->opOrient) {
        if (auto q = _Quat(ctx, _tokens->orient_d, _tokens->orient_f)) {
            return _Rotate(*q);
        }
        return std::nullopt;
    }
    struct Single { TfToken op, d, f; GfVec3d axis; };
    static const Single singles[] = {
        {_tokens->opRotateX, _tokens->rotateX_d, _tokens->rotateX_f, kX},
        {_tokens->opRotateY, _tokens->rotateY_d, _tokens->rotateY_f, kY},
        {_tokens->opRotateZ, _tokens->rotateZ_d, _tokens->rotateZ_f, kZ}};
    for (const Single &s : singles) {
        if (op == s.op) {
            if (auto a = _Scalar(ctx, s.d, s.f)) return _Rotate(s.axis, *a);
            return std::nullopt;
        }
    }
    struct Triple { TfToken op, d, f; GfVec3d a0, a1, a2; int i0, i1, i2; };
    static const Triple triples[] = {
        {_tokens->opRotateXYZ, _tokens->rotateXYZ_d, _tokens->rotateXYZ_f, kX, kY, kZ, 0, 1, 2},
        {_tokens->opRotateXZY, _tokens->rotateXZY_d, _tokens->rotateXZY_f, kX, kZ, kY, 0, 2, 1},
        {_tokens->opRotateYXZ, _tokens->rotateYXZ_d, _tokens->rotateYXZ_f, kY, kX, kZ, 1, 0, 2},
        {_tokens->opRotateYZX, _tokens->rotateYZX_d, _tokens->rotateYZX_f, kY, kZ, kX, 1, 2, 0},
        {_tokens->opRotateZXY, _tokens->rotateZXY_d, _tokens->rotateZXY_f, kZ, kX, kY, 2, 0, 1},
        {_tokens->opRotateZYX, _tokens->rotateZYX_d, _tokens->rotateZYX_f, kZ, kY, kX, 2, 1, 0}};
    for (const Triple &t : triples) {
        if (op == t.op) {
            if (auto v = _Vec3(ctx, t.d, t.f)) {
                return _RotateThree(*v, t.a0, t.i0, t.a1, t.i1, t.a2, t.i2);
            }
            return std::nullopt;
        }
    }
    return std::nullopt;
}

// The camera element's own local transform from its xformOpOrder, in the
// UsdGeomXformable vocabulary without suffixes or inversion: the listed
// order is outermost first, so the row-vector product is op_n * ... * op_1.
// Returns whether the stack was reset (ancestors ignored).
bool _LocalFromOps(const VdfContext &ctx, GfMatrix4d *local)
{
    *local = GfMatrix4d(1);
    bool reset = false;
    std::vector<TfToken> order;
    for (VdfReadIterator<TfToken> it(ctx, _tokens->xformOpOrder); !it.IsAtEnd(); ++it) {
        order.push_back(*it);
    }
    for (const TfToken &op : order) {
        if (op == _tokens->resetXformStack) {
            reset = true;
            continue;
        }
        if (const auto m = _OpMatrix(ctx, op)) {
            *local = *m * *local;
        } else {
            TF_WARN("execAecoCctv: xformOp '%s' is not supported by "
                    "computeDeviceToWorld (suffixed, inverted, half-precision "
                    "or unauthored op); it is skipped", op.GetText());
        }
    }
    return reset;
}

// The four pose drivers composed with the boresight, in the device frame:
// column notation T(offset) * Rz(pan-90) * Rx(-tilt) * Ry(roll) * Rx(90),
// which Gf's row vectors write in reverse. Pan 0 looks along device +X;
// tilt is positive DOWN; roll is about the optical axis.
GfMatrix4d _SensorToDevice(const VdfContext &ctx)
{
    return _Rotate(kX, 90)
        * _Rotate(kY, ctx.GetInputValue<double>(_tokens->roll))
        * _Rotate(kX, -ctx.GetInputValue<double>(_tokens->tilt))
        * _Rotate(kZ, ctx.GetInputValue<double>(_tokens->pan) - 90)
        * GfMatrix4d(1).SetTranslate(ctx.GetInputValue<GfVec3d>(_tokens->offset));
}

} // namespace

// ---------------------------------------------------------------------------
// The camera element: the device frame.
//
// execGeom's computeLocalToWorldTransform (dev 47154dc) reads a single
// xformOp:transform attribute and nothing else, so an element placed with
// xformOp:translate / rotateZ would evaluate to the identity. This
// computation evaluates the element's own op stack and chains to execGeom for
// the ancestors (which therefore still honour only xformOp:transform).
// ---------------------------------------------------------------------------
EXEC_REGISTER_COMPUTATIONS_FOR_SCHEMA(UsdAecoCctvCameraAPI)
{
    self.PrimComputation(_tokens->computeDeviceToWorld)
        .Callback(+[](const VdfContext &ctx) -> GfMatrix4d {
            GfMatrix4d local;
            const bool reset = _LocalFromOps(ctx, &local);
            const GfMatrix4d *parent = ctx.GetInputValuePtr<GfMatrix4d>(
                ExecGeomXformableTokens->computeLocalToWorldTransform);
            return (parent && !reset) ? local * *parent : local;
        })
        .Inputs(
            AttributeValue<TfToken>(_tokens->xformOpOrder),
            AttributeValue<GfMatrix4d>(_tokens->opTransform),
            AttributeValue<GfVec3d>(_tokens->opTranslate).InputName(_tokens->translate_d),
            AttributeValue<GfVec3f>(_tokens->opTranslate).InputName(_tokens->translate_f),
            AttributeValue<GfVec3d>(_tokens->opScale).InputName(_tokens->scale_d),
            AttributeValue<GfVec3f>(_tokens->opScale).InputName(_tokens->scale_f),
            AttributeValue<double>(_tokens->opRotateX).InputName(_tokens->rotateX_d),
            AttributeValue<float>(_tokens->opRotateX).InputName(_tokens->rotateX_f),
            AttributeValue<double>(_tokens->opRotateY).InputName(_tokens->rotateY_d),
            AttributeValue<float>(_tokens->opRotateY).InputName(_tokens->rotateY_f),
            AttributeValue<double>(_tokens->opRotateZ).InputName(_tokens->rotateZ_d),
            AttributeValue<float>(_tokens->opRotateZ).InputName(_tokens->rotateZ_f),
            AttributeValue<GfVec3d>(_tokens->opRotateXYZ).InputName(_tokens->rotateXYZ_d),
            AttributeValue<GfVec3f>(_tokens->opRotateXYZ).InputName(_tokens->rotateXYZ_f),
            AttributeValue<GfVec3d>(_tokens->opRotateXZY).InputName(_tokens->rotateXZY_d),
            AttributeValue<GfVec3f>(_tokens->opRotateXZY).InputName(_tokens->rotateXZY_f),
            AttributeValue<GfVec3d>(_tokens->opRotateYXZ).InputName(_tokens->rotateYXZ_d),
            AttributeValue<GfVec3f>(_tokens->opRotateYXZ).InputName(_tokens->rotateYXZ_f),
            AttributeValue<GfVec3d>(_tokens->opRotateYZX).InputName(_tokens->rotateYZX_d),
            AttributeValue<GfVec3f>(_tokens->opRotateYZX).InputName(_tokens->rotateYZX_f),
            AttributeValue<GfVec3d>(_tokens->opRotateZXY).InputName(_tokens->rotateZXY_d),
            AttributeValue<GfVec3f>(_tokens->opRotateZXY).InputName(_tokens->rotateZXY_f),
            AttributeValue<GfVec3d>(_tokens->opRotateZYX).InputName(_tokens->rotateZYX_d),
            AttributeValue<GfVec3f>(_tokens->opRotateZYX).InputName(_tokens->rotateZYX_f),
            AttributeValue<GfQuatd>(_tokens->opOrient).InputName(_tokens->orient_d),
            AttributeValue<GfQuatf>(_tokens->opOrient).InputName(_tokens->orient_f),
            NamespaceAncestor<GfMatrix4d>(ExecGeomXformableTokens->computeLocalToWorldTransform));
}

// ---------------------------------------------------------------------------
// The sensor: Tier A of the computation contract.
// ---------------------------------------------------------------------------
EXEC_REGISTER_COMPUTATIONS_FOR_SCHEMA(UsdAecoCctvSensorAPI)
{
    // Effective sensor width (mm) at the current focal length.
    self.PrimComputation(_tokens->computeEffectiveWidth)
        .Callback(+[](const VdfContext &ctx) -> double {
            const double f = _Focal(ctx);
            const GfVec2d focal = ctx.GetInputValue<GfVec2d>(_tokens->focalRange);
            const GfVec2d hfov = ctx.GetInputValue<GfVec2d>(_tokens->hfovRange);
            if (_Projection(ctx) != _tokens->rectilinear) {
                return f * _InterpolatedAngle(f, focal, hfov) * kDegrees;
            }
            return _EffectiveDimension(f, focal, hfov,
                                       ctx.GetInputValue<GfVec2d>(_tokens->sensorSize)[0]);
        })
        .Inputs(AttributeValue<double>(_tokens->focalLength).Required(),
                AttributeValue<GfVec2d>(_tokens->focalRange).Required(),
                AttributeValue<GfVec2d>(_tokens->hfovRange).Required(),
                AttributeValue<GfVec2d>(_tokens->sensorSize).Required(),
                AttributeValue<TfToken>(_tokens->projection).Required(),
                AttributeValue<TfToken>(_tokens->spectrum).Required());

    // (hfov, vfov) in degrees at the current focal length. The vertical
    // dimension comes from vfovRange, else the physical height, else the
    // pixel aspect applied to the effective width.
    self.PrimComputation(_tokens->computeFieldOfView)
        .Callback(+[](const VdfContext &ctx) -> GfVec2d {
            const double f = _Focal(ctx);
            const double w = ctx.GetInputValue<double>(_tokens->computeEffectiveWidth);
            const GfVec2d focal = ctx.GetInputValue<GfVec2d>(_tokens->focalRange);
            const GfVec2d vfov = ctx.GetInputValue<GfVec2d>(_tokens->vfovRange);
            const GfVec2d size = ctx.GetInputValue<GfVec2d>(_tokens->sensorSize);
            const GfVec2i px = ctx.GetInputValue<GfVec2i>(_tokens->pixels);
            if (_Projection(ctx) != _tokens->rectilinear) {
                const double hfov = _InterpolatedAngle(f, focal, ctx.GetInputValue<GfVec2d>(_tokens->hfovRange));
                const double v = (vfov[0] > 0 && vfov[1] > 0) ? _InterpolatedAngle(f, focal, vfov)
                    : (px[0] > 0 && px[1] > 0) ? hfov * px[1] / px[0] : 0;
                return GfVec2d(hfov, v);
            }
            double h;
            if (vfov[0] > 0 && vfov[1] > 0) {
                h = _EffectiveDimension(f, focal, vfov, 0);
            } else if (size[1] > 0) {
                h = size[1];
            } else {
                h = (px[0] > 0 && px[1] > 0) ? w * px[1] / px[0] : 0;
            }
            return GfVec2d(_FieldOfView(w, f), _FieldOfView(h, f));
        })
        .Inputs(Computation<double>(_tokens->computeEffectiveWidth).Required(),
                AttributeValue<double>(_tokens->focalLength).Required(),
                AttributeValue<GfVec2d>(_tokens->focalRange).Required(),
                AttributeValue<GfVec2d>(_tokens->hfovRange).Required(),
                AttributeValue<GfVec2d>(_tokens->vfovRange).Required(),
                AttributeValue<GfVec2d>(_tokens->sensorSize).Required(),
                AttributeValue<GfVec2i>(_tokens->pixels).Required(),
                AttributeValue<TfToken>(_tokens->projection).Required(),
                AttributeValue<TfToken>(_tokens->spectrum).Required());

    // Sensor frame to world: pose drivers in the device frame, then the
    // device frame of the parent camera element (computeDeviceToWorld), or
    // execGeom's local-to-world of the nearest ancestor for an orphan sensor.
    self.PrimComputation(_tokens->computeSensorToWorld)
        .Callback(+[](const VdfContext &ctx) -> GfMatrix4d {
            const GfMatrix4d *device =
                ctx.GetInputValuePtr<GfMatrix4d>(_tokens->computeDeviceToWorld);
            if (!device) {
                device = ctx.GetInputValuePtr<GfMatrix4d>(
                    ExecGeomXformableTokens->computeLocalToWorldTransform);
            }
            const GfMatrix4d local = _SensorToDevice(ctx);
            return device ? local * *device : local;
        })
        .Inputs(AttributeValue<GfVec3d>(_tokens->offset).Required(),
                AttributeValue<double>(_tokens->pan).Required(),
                AttributeValue<double>(_tokens->tilt).Required(),
                AttributeValue<double>(_tokens->roll).Required(),
                NamespaceAncestor<GfMatrix4d>(_tokens->computeDeviceToWorld),
                NamespaceAncestor<GfMatrix4d>(ExecGeomXformableTokens->computeLocalToWorldTransform));

    // Distance (m) at which the sensor's targetDensity (else the default
    // requirement) is met under the derivation's default model: plane for a
    // rectilinear head (exact for a flat target facing the camera), arc for
    // the equidistant projections. 0 for a head without pixels (radar).
    self.PrimComputation(_tokens->computeTargetRange)
        .Callback(+[](const VdfContext &ctx) -> double {
            return _RangeAtDensity(
                ctx.GetInputValue<GfVec2i>(_tokens->pixels)[0],
                ctx.GetInputValue<GfVec2d>(_tokens->computeFieldOfView)[0],
                _Density(ctx), _Projection(ctx) != _tokens->rectilinear);
        })
        .Inputs(AttributeValue<double>(_tokens->targetDensity).Required(),
                AttributeValue<GfVec2i>(_tokens->pixels).Required(),
                AttributeValue<TfToken>(_tokens->projection).Required(),
                AttributeValue<TfToken>(_tokens->spectrum).Required(),
                Computation<GfVec2d>(_tokens->computeFieldOfView).Required());

    // The same under the arc model (pixels per metre of arc, the convention
    // of the manufacturer's design tools and Revit families).
    self.PrimComputation(_tokens->computeTargetRangeArc)
        .Callback(+[](const VdfContext &ctx) -> double {
            return _RangeAtDensity(
                ctx.GetInputValue<GfVec2i>(_tokens->pixels)[0],
                ctx.GetInputValue<GfVec2d>(_tokens->computeFieldOfView)[0],
                _Density(ctx), true);
        })
        .Inputs(AttributeValue<double>(_tokens->targetDensity).Required(),
                AttributeValue<GfVec2i>(_tokens->pixels).Required(),
                Computation<GfVec2d>(_tokens->computeFieldOfView).Required());

    // The view sector in world space: apex + (nu+1)(nv+1) cap grid at the
    // design range (or the target range when range is 0), in the vertex
    // order of usdaeco_cctv.sectors.sector_mesh (v outer, u inner): the
    // frustum planes meeting the range sphere for a rectilinear head, an
    // angular dome for a fisheye, a cylinder for a cylindrical head. Empty
    // when the radius or the field of view is degenerate.
    self.PrimComputation(_tokens->computeSectorPoints)
        .Callback(+[](const VdfContext &ctx) -> std::vector<GfVec3d> {
            const GfVec2d fov = ctx.GetInputValue<GfVec2d>(_tokens->computeFieldOfView);
            const GfMatrix4d matrix = ctx.GetInputValue<GfMatrix4d>(_tokens->computeSensorToWorld);
            const double authored = ctx.GetInputValue<double>(_tokens->range);
            const double radius = authored > 0
                ? authored : ctx.GetInputValue<double>(_tokens->computeTargetRange);
            const TfToken projection = _Projection(ctx);
            const bool rectilinear = projection == _tokens->rectilinear;
            std::vector<GfVec3d> points;
            if (radius <= 0 || fov[0] <= 0 || fov[1] <= 0 || fov[1] > 180
                || fov[0] > 360 || (rectilinear && (fov[0] >= 180 || fov[1] >= 180))
                || (projection == _tokens->cylindrical && fov[1] >= 180)) {
                return points;
            }
            const double tx = std::tan(fov[0] * kDegrees / 2);
            const double ty = std::tan(fov[1] * kDegrees / 2);
            points.reserve(1 + (kSectorNu + 1) * (kSectorNv + 1));
            points.push_back(matrix.Transform(GfVec3d(0)));
            for (int j = 0; j <= kSectorNv; ++j) {
                for (int i = 0; i <= kSectorNu; ++i) {
                    const double u = -1 + 2.0 * i / kSectorNu;
                    const double v = -1 + 2.0 * j / kSectorNv;
                    GfVec3d ray;
                    if (rectilinear) {
                        ray = GfVec3d(u * tx, v * ty, -1);
                        ray *= radius / ray.GetLength();
                    } else {
                        const double a = u * fov[0] * kDegrees / 2;
                        const double b = v * fov[1] * kDegrees / 2;
                        ray = projection == _tokens->fisheye
                            ? GfVec3d(std::sin(a) * std::cos(b), std::sin(b), -std::cos(a) * std::cos(b))
                            : GfVec3d(std::sin(a), v * ty, -std::cos(a));
                        ray *= radius;
                    }
                    points.push_back(matrix.Transform(ray));
                }
            }
            return points;
        })
        .Inputs(Computation<GfVec2d>(_tokens->computeFieldOfView).Required(),
                Computation<GfMatrix4d>(_tokens->computeSensorToWorld).Required(),
                AttributeValue<double>(_tokens->range).Required(),
                AttributeValue<TfToken>(_tokens->projection).Required(),
                AttributeValue<TfToken>(_tokens->spectrum).Required(),
                Computation<double>(_tokens->computeTargetRange).Required());
}
