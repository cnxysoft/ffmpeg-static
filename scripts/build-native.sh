#!/usr/bin/env bash
# Build a candidate in a new directory. Production releases use build.yml.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
source "$repo/versions.env"
if [[ $# != 1 || -e $1 ]]; then
  echo "Usage: bash scripts/build-native.sh <new-build-directory>" >&2
  exit 2
fi
mkdir -p "$1"
work=$(cd "$1" && pwd)
if [[ $work == *' '* ]]; then
  echo "OpenSSL builds require a path without spaces: $work" >&2
  exit 2
fi
cc=${CC:-cc}
make=${MAKE:-make}
python=${PYTHON:-python3}
jobs=${JOBS:-4}
prefix="$work/package"
ssl_prefix="$work/openssl-install"
ff_flags=()
ff_cpu_flags=""
ff_section_flags="-ffunction-sections -fdata-sections"
link_flags=(-lm -lpthread)
ssl_flags=()
runner=()
if [[ -n ${TARGET_RUNNER:-} ]]; then runner=("$TARGET_RUNNER"); fi
case "$(uname -s):$(uname -m)" in
  Linux:x86_64) triplet=linux-amd64; ssl_target=linux-x86_64 ;;
  Linux:aarch64|Linux:arm64) triplet=linux-arm64; ssl_target=linux-aarch64 ;;
  Darwin:x86_64) triplet=darwin-amd64; ssl_target=darwin64-x86_64-cc ;;
  Darwin:arm64) triplet=darwin-arm64; ssl_target=darwin64-arm64-cc ;;
  MINGW*:x86_64|MSYS*:x86_64)
    triplet=windows-amd64; ssl_target=mingw64
    ;;
  MINGW*:i686|MSYS*:i686) triplet=windows-386; ssl_target=mingw ;;
  MINGW*:aarch64|MSYS*:aarch64|MINGW*:arm64|MSYS*:arm64)
    triplet=windows-arm64; ssl_target=ddbot-mingw-arm64 ;;
  *) echo "Unsupported native host; cross builds need separate validation" >&2; exit 2 ;;
esac
triplet=${TARGET:-$triplet}
case "$triplet" in
  linux-386)
    ssl_target=linux-x86
    cc=${CC:-i686-linux-gnu-gcc}
    ff_flags+=(--target-os=linux --arch=x86_32 --enable-cross-compile --cross-prefix=i686-linux-gnu- --pkg-config=pkg-config)
    ;;
  linux-arm)
    ssl_target=linux-armv4
    cc=${CC:-arm-linux-gnueabihf-gcc}
    ff_flags+=(--target-os=linux --arch=arm --cpu=armv7-a --enable-cross-compile --cross-prefix=arm-linux-gnueabihf- --pkg-config=pkg-config)
    ff_cpu_flags="-mfpu=vfpv3-d16"
    if [[ -z ${TARGET_RUNNER:-} ]]; then echo "ARM cross validation requires TARGET_RUNNER" >&2; exit 2; fi
    ;;
  windows-amd64) ssl_target=mingw64; cc=${CC:-gcc}; ff_flags+=(--arch=x86_64) ;;
  windows-386) ssl_target=mingw; cc=${CC:-gcc}; ff_flags+=(--arch=x86_32) ;;
  windows-arm64)
    ssl_target=ddbot-mingw-arm64; cc=${CC:-clang}
    ff_flags+=(--arch=aarch64)
    # OpenSSL 3.5 has no GNU Windows ARM target. Use its Windows C backend;
    # FFmpeg's AArch64 assembly remains enabled and is validated separately.
    ssl_flags+=(no-asm)
    ;;
  linux-amd64|linux-arm64|darwin-amd64|darwin-arm64) ;;
  *) echo "Unsupported target: $triplet" >&2; exit 2 ;;
esac
case "$triplet" in
  linux-*) link_flags+=(-ldl) ;;
  darwin-*) link_flags+=(-framework CoreFoundation -framework Security) ;;
  windows-*)
    # -fdata-sections makes MinGW zero FFT tables file-backed (~17 MB).
    ff_section_flags="-ffunction-sections"
    ff_flags+=(--target-os=mingw32)
    link_flags+=(-static -lws2_32 -lwinmm -lole32 -lshlwapi -lbcrypt -lcrypt32 -lgdi32 -lkernel32 -luser32 -ladvapi32)
    ssl_prefix=$(cygpath -m "$ssl_prefix")
    ;;
esac
# A host label must not silently contain a cross compiler's output.
machine=$("$cc" -dumpmachine)
case "$triplet:$machine" in
  linux-amd64:x86_64*linux*|linux-386:i686*linux*|linux-arm:arm*linux*gnueabihf*|linux-arm64:aarch64*linux*|linux-arm64:arm64*linux*|darwin-amd64:x86_64*darwin*|darwin-arm64:arm64*darwin*|windows-amd64:x86_64*mingw*|windows-386:i686*mingw*|windows-arm64:aarch64*windows*gnu*|windows-arm64:aarch64*mingw*) ;;
  *) echo "Compiler target $machine does not match $triplet" >&2; exit 2 ;;
esac
for tool in "$make" "$python" curl tar perl pkg-config; do
  command -v "$tool" >/dev/null
done
perl -MExtUtils::MakeMaker -MIPC::Cmd -MPod::Usage -e1
fetch() {
  local url=$1 name=$2 expected=$3
  if [[ -n ${SOURCE_CACHE:-} && -f $SOURCE_CACHE/$name ]]; then
    cp "$SOURCE_CACHE/$name" "$work/$name"
  else
    curl --fail --location --retry 3 --output "$work/$name" "$url"
  fi
  "$python" "$repo/scripts/package.py" verify "$work/$name" "$expected"
}
fetch "https://ffmpeg.org/releases/ffmpeg-$FFMPEG_VERSION.tar.xz" "ffmpeg-$FFMPEG_VERSION.tar.xz" "$FFMPEG_SHA256"
fetch "https://github.com/openssl/openssl/releases/download/openssl-$OPENSSL_VERSION/openssl-$OPENSSL_VERSION.tar.gz" "openssl-$OPENSSL_VERSION.tar.gz" "$OPENSSL_SHA256"
tar -xf "$work/ffmpeg-$FFMPEG_VERSION.tar.xz" -C "$work"
tar -xf "$work/openssl-$OPENSSL_VERSION.tar.gz" -C "$work"
cp "$repo/profiles/openssl-windows-arm.conf" "$work/openssl-$OPENSSL_VERSION/Configurations/99-ddbot.conf"
export CC="$cc"
(
  cd "$work/openssl-$OPENSSL_VERSION"
  bash "$repo/profiles/openssl-minimal.sh" "$ssl_target" \
    --prefix="$ssl_prefix" --libdir=lib -Os -ffunction-sections -fdata-sections ${ssl_flags[@]+"${ssl_flags[@]}"}
  "$make" -j"$jobs"
  "$make" install_sw
)
# Isolate dependency discovery from the host, even if it has x264/OpenSSL installed.
export PKG_CONFIG_PATH=
export PKG_CONFIG_LIBDIR="$ssl_prefix/lib/pkgconfig"
(
  cd "$work/ffmpeg-$FFMPEG_VERSION"
  bash "$repo/profiles/ddbot-minimal.sh" --prefix="$prefix" --cc="$cc" \
    --pkg-config-flags=--static ${ff_flags[@]+"${ff_flags[@]}"} \
    --extra-cflags="$ff_cpu_flags -I$ssl_prefix/include $ff_section_flags" \
    --extra-ldflags="-L$ssl_prefix/lib"
  "$make" -j"$jobs"
  "$make" install
)
mkdir -p "$prefix/include" "$prefix/lib" "$prefix/build-info" "$prefix/licenses"
cp -R "$ssl_prefix/include/openssl" "$prefix/include/"
cp "$ssl_prefix/lib/libssl.a" "$ssl_prefix/lib/libcrypto.a" "$prefix/lib/"
cp "$repo/versions.env" "$repo/profiles/"*.sh "$prefix/build-info/"
cp "$repo/profiles/openssl-windows-arm.conf" "$prefix/build-info/"
cp "$work/ffmpeg-$FFMPEG_VERSION/ffbuild/config.mak" "$prefix/build-info/ffmpeg-config.mak"
cp "$work/ffmpeg-$FFMPEG_VERSION/config.h" "$prefix/build-info/ffmpeg-config.h"
cp "$work/openssl-$OPENSSL_VERSION/configdata.pm" "$prefix/build-info/openssl-configdata.pm"
cp "$work/ffmpeg-$FFMPEG_VERSION/"COPYING* "$prefix/licenses/"
cp "$work/ffmpeg-$FFMPEG_VERSION/LICENSE.md" "$prefix/licenses/FFmpeg-LICENSE.md"
cp "$work/openssl-$OPENSSL_VERSION/LICENSE.txt" "$prefix/licenses/OpenSSL-LICENSE.txt"
"$cc" --version > "$prefix/build-info/compiler.txt"
case "$triplet" in
  *-amd64|*-386) nasm -v > "$prefix/build-info/assembler.txt" ;;
  *) printf 'Compiler assembler; target=%s\n' "$machine" > "$prefix/build-info/assembler.txt" ;;
esac
printf 'Target: %s\nHost: %s\nRunner: %s\n' "$triplet" "$(uname -sm)" "${TARGET_RUNNER:-direct}" > "$prefix/build-info/execution.txt"
"$cc" -std=c11 -Wall -Wextra -Werror -Os -I"$prefix/include" \
  "$repo/tests/capabilities.c" -L"$prefix/lib" \
  -lavfilter -lavformat -lavcodec -lswscale -lavutil -lssl -lcrypto \
  "${link_flags[@]}" -o "$work/capabilities"
${runner[@]+"${runner[@]}"} "$work/capabilities" | tee "$prefix/build-info/capabilities.txt"
# Check the actual linked versions, then exercise TLS/proxy/HLS before packaging.
"$python" "$repo/scripts/package.py" check-versions "$prefix/build-info/capabilities.txt" "$repo/versions.env"
"$python" "$repo/tests/smoke.py" "$work/capabilities" | tee "$prefix/build-info/smoke.txt"
"$python" "$repo/scripts/package.py" pack "$prefix" "$triplet" "$work/ffmpeg-$triplet-candidate.zip"
# Consumers must be able to relocate the archive and link using its .pc files.
cp -R "$prefix" "$work/relocated"
export PKG_CONFIG_LIBDIR="$work/relocated/lib/pkgconfig"
dependency_output=$(pkg-config --static --cflags --libs libavfilter libavformat libavcodec libswscale libavutil openssl)
read -r -a dependency_flags <<< "$dependency_output"
static_flag=()
if [[ $triplet == windows-* ]]; then static_flag+=(-static); fi
"$cc" -std=c11 -Wall -Wextra -Werror -Os "$repo/tests/capabilities.c" \
  "${dependency_flags[@]}" ${static_flag[@]+"${static_flag[@]}"} -o "$work/relocated-capabilities"
${runner[@]+"${runner[@]}"} "$work/relocated-capabilities"
echo "Candidate validated: $work/ffmpeg-$triplet-candidate.zip"
