{
  description = "simple hysteria control panel";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};

    env = pkgs.python3.withPackages (ps: with ps; [
      fastapi 
      uvicorn 
      httpx 
      jinja2
    ]);
  in {
    packages.${system}.default = pkgs.writeShellScriptBin "hyst-panel" ''
      export HYST_DB_PATH="''${HYST_DB_PATH:-/var/lib/hyst-panel/app.db}"
      mkdir -p "$(dirname "$HYST_DB_PATH")"
      if [ $# -eq 0 ]; then
        exec ${env}/bin/python ${self}/run.py run
      else
        exec ${env}/bin/python ${self}/run.py "$@"
      fi
    '';
  };
}
