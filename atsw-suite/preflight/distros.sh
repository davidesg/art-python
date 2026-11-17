#!/bin/bash
# La prueba de instalación limpia de atsw en distribuciones Linux, con podman:
# en cada imagen, Python del sistema (>= 3.10), atsw desde PyPI con las ruedas
# binarias de fue, drvarma y drvec, `pip check` y atsw-suite/preflight/pruebas.py
# (procedencia, motores C, asistentes, funcionamiento) — lo mismo que el job
# «Prueba» de preflight-atsw.yml con origen=pypi, en otras libc y otros Python.
#
#   atsw-suite/preflight/distros.sh ATSW_VERSION [imagen ...]
#
# Sin imágenes, las diez de siempre: glibc de 2.28 (AlmaLinux 8) a la última
# (Arch), y musl (Alpine). Los registros van a $DISTROS_LOG (por defecto
# ./distros-log/<imagen>.log, fuera del repositorio si se lanza desde fuera).
# Sale 1 si alguna falla. Es el paso 6 de docs/PUBLISHING.md §4: después del
# tag, como el preflight con origen=pypi. Necesita podman y red.
set -u
V=${1:?versión de atsw}; shift
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)                 # el repositorio: se monta en /w
LOG=${DISTROS_LOG:-$PWD/distros-log}
IMGS=("$@")
[ ${#IMGS[@]} -eq 0 ] && IMGS=(almalinux:8 rockylinux:9 ubuntu:22.04 ubuntu:24.04 debian:12 debian:13
  registry.opensuse.org/opensuse/leap:15.6 fedora:41 archlinux:latest alpine:3.20)
mkdir -p "$LOG"
fallos=0
prep() {   # instala un Python >= 3.10 con venv; deja su ruta en /tmp/py
  case "$1" in
    almalinux:8|rockylinux:9) echo 'dnf -y -q install python3.12 >/dev/null && echo python3.12 >/tmp/py';;
    fedora:*)       echo 'dnf -y -q install python3 >/dev/null && echo python3 >/tmp/py';;
    ubuntu:*|debian:*) echo 'apt-get -qq update && DEBIAN_FRONTEND=noninteractive apt-get -qq install -y python3 python3-venv >/dev/null && echo python3 >/tmp/py';;
    *opensuse*)     echo 'zypper -q -n install python312 >/dev/null && echo python3.12 >/tmp/py';;
    # Arch no admite instalar sin actualizar: una imagen de hace semanas choca
    # con openssl si sólo se pide python (-Sy).
    archlinux:*)    echo 'pacman -Syu --noconfirm --quiet python >/dev/null && echo python >/tmp/py';;
    alpine:*)       echo 'apk add --no-cache python3 build-base pkgconf freetype-dev libpng-dev >/dev/null && echo python3 >/tmp/py';;
  esac
}
for img in "${IMGS[@]}"; do
  log="$LOG/$(echo "$img" | tr '/:' '__').log"
  podman run --rm -v "$ROOT:/w:Z" -w /w -e PYTHONUTF8=1 -e ART_NO_VIEWER=1 -e MPLBACKEND=Agg \
    "$img" sh -c "set -e; $(prep "$img"); PY=\$(cat /tmp/py); \$PY -V; ldd --version 2>&1 | head -1 || true
      \$PY -m venv /venv; /venv/bin/pip install -q --upgrade pip
      rm -rf /tmp/wh; /venv/bin/pip download -q --no-cache-dir --no-deps -d /tmp/wh atsw==$V pyfug art-tseries drtran sima-tseries
      /venv/bin/pip download -q --no-cache-dir --no-deps --only-binary :all: -d /tmp/wh fue drvarma drvec || true
      ls /tmp/wh
      /venv/bin/pip install -q --no-cache-dir --only-binary fue,drvarma,drvec atsw==$V
      /venv/bin/pip check
      /venv/bin/python atsw-suite/preflight/pruebas.py atsw-suite/preflight/data /tmp/wh" >"$log" 2>&1
  rc=$?
  [ $rc = 0 ] || fallos=$((fallos + 1))
  printf '%-45s %s\n' "$img" "$([ $rc = 0 ] && echo OK || echo "FALLA (rc $rc)") — $(grep -m1 -E '^Python ' "$log")"
done
[ $fallos = 0 ] || { echo "$fallos imagen(es) fallaron: ver $LOG"; exit 1; }
