#!/usr/bin/env bash
# Configure, build and install the plugin and its consumer against an OpenUSD
# build that has OpenExec (the aeco-toolchain flake's usd-dev output).
#
#   USD_DEV=/path/to/usd-dev ./build.sh            # explicit OpenUSD
#   ./build.sh                                     # resolves aeco-toolchain#usd-dev through nix
#
# TBB, OpenSubdiv and the Python that USD was built with are read from the
# OpenUSD installation itself (its propagated inputs and pxrConfig.cmake), so
# a plain CMake >= 3.24 and a C++17 compiler are all the host needs.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${BUILD_DIR:-$HERE/build}"
PREFIX="${PREFIX:-$BUILD_DIR/install}"
if [ -z "${USD_DEV:-}" ]; then
  echo 'STAGE resolve usd-dev through the aeco-toolchain flake registry'
  USD_DEV="$(nix eval --raw 'aeco-toolchain#usd-dev.outPath')"
fi
test -f "$USD_DEV/pxrConfig.cmake" || { echo "no pxrConfig.cmake under $USD_DEV" >&2; exit 1; }
PREFIX_PATH="$USD_DEV"
if [ -f "$USD_DEV/nix-support/propagated-build-inputs" ]; then
  for dep in $(cat "$USD_DEV/nix-support/propagated-build-inputs"); do PREFIX_PATH="$PREFIX_PATH;$dep"; done
fi
PYTHON_ROOT="$(sed -n 's/.*set(Python3_EXECUTABLE \[\[\(.*\)\/bin\/python3.*\]\]).*/\1/p' "$USD_DEV/pxrConfig.cmake" | head -1)"
echo "STAGE configure against $USD_DEV"
cmake -S "$HERE" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release -Dpxr_DIR="$USD_DEV" \
  -DCMAKE_PREFIX_PATH="$PREFIX_PATH" -DCMAKE_INSTALL_PREFIX="$PREFIX" \
  ${PYTHON_ROOT:+-DPython3_ROOT_DIR="$PYTHON_ROOT" -DPython3_FIND_STRATEGY=LOCATION} "$@"
echo 'STAGE build the plugin and the consumer'
cmake --build "$BUILD_DIR" --parallel "${JOBS:-4}"
echo "STAGE install to $PREFIX"
cmake --install "$BUILD_DIR" >/dev/null
echo "built: $PREFIX/plugin/usd/execAecoCctv and $PREFIX/bin/execcctv"
