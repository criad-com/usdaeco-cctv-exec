cmake_minimum_required(VERSION 3.24)
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/library.json" manifest)
string(JSON AECO_VERSION GET "${manifest}" version)
project(execAecoCctv VERSION ${AECO_VERSION} LANGUAGES CXX)

# An OpenUSD build with OpenExec: pxr_DIR points at the usd-dev output of the
# aeco-toolchain flake (pxrConfig.cmake at its root).
find_package(pxr CONFIG REQUIRED)
foreach(component exec execUsd execGeom vdf esf esfUsd ef)
  if(NOT TARGET ${component})
    message(FATAL_ERROR "the OpenUSD at pxr_DIR has no OpenExec library '${component}'")
  endif()
endforeach()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_VISIBILITY_PRESET default)
set(CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE)
set(CMAKE_BUILD_WITH_INSTALL_RPATH TRUE)

# The plugin: computations registered on the codeless cctv schemas.
add_library(execAecoCctv SHARED src/computations.cpp)
target_link_libraries(execAecoCctv PRIVATE exec execGeom vdf gf vt tf)
set_target_properties(execAecoCctv PROPERTIES PREFIX "lib")

# A consumer: evaluates the sensor computations on a stage and recomputes
# after an edit (the check script and the flake check run it).
add_executable(execcctv testenv/execcctv.cpp)
target_link_libraries(execcctv PRIVATE execUsd exec vdf usdGeom usd sdf gf vt tf js)

# The pxr headers reference Python-backed Tf/Vt symbols in a Python-enabled
# USD build.
if(TARGET python)
  target_link_libraries(execAecoCctv PRIVATE python)
  target_link_libraries(execcctv PRIVATE python)
endif()

# plugInfo.json: Info.aeco comes from library.json (the single manifest).
set(AECO_METADATA "{}")
foreach(field version tier requires)
  string(JSON value GET "${manifest}" ${field})
  if(NOT field STREQUAL "requires")
    set(value "\"${value}\"")
  endif()
  string(JSON AECO_METADATA SET "${AECO_METADATA}" ${field} "${value}")
endforeach()
string(JSON AECO_NAME GET "${manifest}" plugin)
if(NOT AECO_NAME STREQUAL "execAecoCctv")
  message(FATAL_ERROR "library.json plugin must be execAecoCctv")
endif()
set(PLUGIN_LIBRARY "lib${PROJECT_NAME}${CMAKE_SHARED_LIBRARY_SUFFIX}")
configure_file(resources/plugInfo.json.in plugInfo.json @ONLY)

install(TARGETS execAecoCctv LIBRARY DESTINATION plugin/usd/execAecoCctv)
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/plugInfo.json" DESTINATION plugin/usd/execAecoCctv)
install(FILES library.json DESTINATION plugin/usd/execAecoCctv)
install(TARGETS execcctv RUNTIME DESTINATION bin)
