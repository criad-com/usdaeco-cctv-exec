{
  description = "execAecoCctv: OpenExec computations for the codeless usdAecoCctv sensor schema";

  inputs = {
    aeco-toolchain.url = "github:criad-com/aeco-toolchain?ref=v0.4.0";
    toolchain.url = "github:criad-com/usdaeco-toolchain?ref=v0.3.10";
    toolchain.inputs.aeco-toolchain.follows = "aeco-toolchain";
    nixpkgs.follows = "aeco-toolchain/nixpkgs";
    usdaeco-cctv.url = "github:criad-com/usdaeco-cctv?ref=v0.5.5";
    usdaeco-cctv.flake = false;
    usdaeco-core.url = "github:criad-com/usdaeco-core?ref=v0.9.4";
    usdaeco-core.flake = false;
  };

  outputs = { self, nixpkgs, aeco-toolchain, toolchain, usdaeco-cctv, usdaeco-core }:
    let
      eachSystem = nixpkgs.lib.genAttrs [ "aarch64-darwin" "x86_64-linux" ];
      forSystem = system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          inherit (pkgs) lib;
          usd-dev = aeco-toolchain.packages.${system}.usd-dev;
          # The interpreter usd-dev's bindings were compiled for; numpy lets
          # the parity check use the library's own reference modules.
          python = pkgs.python314;
          pythonEnv = python.withPackages (ps: [ ps.numpy ps.pytest ]);
          corePlugin = "${usdaeco-core}/usdAeco";
          cctvPlugin = "${usdaeco-cctv}/usdAecoCctv";

          execAecoCctv = pkgs.stdenv.mkDerivation {
            pname = "execAecoCctv";
            version = (builtins.fromJSON (builtins.readFile (self + "/library.json"))).version;
            src = self;
            nativeBuildInputs = [ pkgs.cmake pkgs.ninja ];
            buildInputs = [ usd-dev python ]
              ++ lib.optionals pkgs.stdenv.hostPlatform.isDarwin [ pkgs.apple-sdk_15 ];
            cmakeFlags = [
              "-Dpxr_DIR=${usd-dev}"
              "-DPython3_ROOT_DIR=${python}"
              "-DPython3_FIND_STRATEGY=LOCATION"
            ];
            meta = {
              description = "OpenExec plugin: Tier A sensor computations on the codeless usdAecoCctv schema";
              mainProgram = "execcctv";
            };
          };

          # Everything check.py and the consumer need to find the three plugins.
          environment = ''
            export TOOLCHAIN_DIR=${toolchain}
            export AECO_CORE_ROOT=${usdaeco-core}
            export PXR_PLUGINPATH_NAME=${corePlugin}:${cctvPlugin}
            export CORE_PLUGIN_DIR=${corePlugin}
            export CCTV_PLUGIN_DIR=${cctvPlugin}
            export CCTV_ROOT=${usdaeco-cctv}
            export EXEC_PLUGIN_DIR=${execAecoCctv}/plugin/usd/execAecoCctv
            export EXEC_CONSUMER=${execAecoCctv}/bin/execcctv
            unset PYTHONPATH
            export USD_DEV=${usd-dev}
            export PYTHONDONTWRITEBYTECODE=1
          '';
        in { inherit pkgs usd-dev python pythonEnv execAecoCctv environment; };
    in {
      packages = eachSystem (system: let p = forSystem system; in {
        default = p.execAecoCctv;
        execAecoCctv = p.execAecoCctv;
      });

      checks = eachSystem (system: let p = forSystem system; in {
        # Builds the plugin, evaluates the six computations on the library's
        # worked example and checks parity, invalidation,
        # the manifest and hygiene: no failed or unexecuted rows are accepted.
        exec = p.pkgs.runCommand "execAecoCctv-check" {
          nativeBuildInputs = [ p.pythonEnv ];
        } ''
          ${p.environment}
          mkdir -p "$out"
          set -o pipefail
          env -u PYTHONPATH PYTHONPATH=${usdaeco-core}:${self} python ${self}/check.py --native --out "$TMPDIR/artifacts" --report "$out/check.json" \
            | tee "$out/check.log"
          grep -Eq '^[0-9]+ checks, 0 failed, 0 not run$' "$out/check.log"
          env -u PYTHONPATH python -m pytest -q -p no:cacheprovider ${self}/testenv \
            | tee "$out/pytest.log"
        '';
      });

      devShells = eachSystem (system: let p = forSystem system; in {
        default = p.pkgs.mkShell {
          packages = [ p.pkgs.cmake p.pkgs.ninja p.usd-dev p.pythonEnv ];
          shellHook = ''
            ${p.environment}
            export USD_DEV=${p.usd-dev}
            export pxr_DIR=${p.usd-dev}
            unset EXEC_PLUGIN_DIR EXEC_CONSUMER
            export PYTHON=python3
            echo 'execAecoCctv dev shell: ./build.sh then follow the README native check command'
          '';
        };
      });
    };
}
