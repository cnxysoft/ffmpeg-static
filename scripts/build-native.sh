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
ff_section_flags="-ffunction-sections -fdata-sections"
link_flags=(-lm -lpthread)
case "$(uname -s):$(uname -m)" in
  Linux:x86_64) triplet=linux-amd64; ssl_target=linux-x86_64 ;;
  Linux:aarch64|Linux:arm64) triplet=linux-arm64; ssl_target=linux-aarch64 ;;
  Darwin:x86_64) triplet=darwin-amd64; ssl_target=darwin64-x86_64-cc ;;
  Darwin:arm64) triplet=darwin-arm64; ssl_target=darwin64-arm64-cc ;;
  MINGW*:x86_64|MSYS*:x86_64)
    triplet=windows-amd64; ssl_target=mingw64
    cc=${CC:-gcc}
    # MinGW writes zero-initialized FFT tables into file-backed .data$ sections
    # with -fdata-sections (about 17 MB). Preserve ordinary .bss storage.
    ff_section_flags="-ffunction-sections"
    ff_flags+=(--target-os=mingw32 --arch=x86_64)
    link_flags+=(-static -lws2_32 -lwinmm -lole32 -lshlwapi -lbcrypt -lcrypt32 -lgdi32 -lkernel32 -luser32 -ladvapi32)
    ssl_prefix=$(cygpath -m "$ssl_prefix")
    ;;
  *) echo "Unsupported native host; cross builds need separate validation" >&2; exit 2 ;;
esac
case "$triplet" in
  linux-*) link_flags+=(-ldl) ;;
  darwin-*) link_flags+=(-framework CoreFoundation -framework Security) ;;
esac
# A host label must not silently contain a cross compiler's output.
machine=$("$cc" -dumpmachine)
case "$triplet:$machine" in
  linux-amd64:x86_64*linux*|linux-arm64:aarch64*linux*|linux-arm64:arm64*linux*|darwin-amd64:x86_64*darwin*|darwin-arm64:arm64*darwin*|windows-amd64:x86_64*mingw*) ;;
  *) echo "Compiler target $machine does not match $triplet" >&2; exit 2 ;;
esac
for tool in "$make" "$python" curl tar perl pkg-config nasm; do
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
export CC="$cc"
(
  cd "$work/openssl-$OPENSSL_VERSION"
  bash "$repo/profiles/openssl-minimal.sh" "$ssl_target" \
    --prefix="$ssl_prefix" --libdir=lib -Os -ffunction-sections -fdata-sections
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
    --extra-cflags="-I$ssl_prefix/include $ff_section_flags" \
    --extra-ldflags="-L$ssl_prefix/lib"
  "$make" -j"$jobs"
  "$make" install
)
mkdir -p "$prefix/include" "$prefix/lib" "$prefix/build-info" "$prefix/licenses"
cp -R "$ssl_prefix/include/openssl" "$prefix/include/"
cp "$ssl_prefix/lib/libssl.a" "$ssl_prefix/lib/libcrypto.a" "$prefix/lib/"
cp "$repo/versions.env" "$repo/profiles/"*.sh "$prefix/build-info/"
cp "$work/ffmpeg-$FFMPEG_VERSION/ffbuild/config.mak" "$prefix/build-info/ffmpeg-config.mak"
cp "$work/ffmpeg-$FFMPEG_VERSION/config.h" "$prefix/build-info/ffmpeg-config.h"
cp "$work/openssl-$OPENSSL_VERSION/configdata.pm" "$prefix/build-info/openssl-configdata.pm"
cp "$work/ffmpeg-$FFMPEG_VERSION/"COPYING* "$prefix/licenses/"
cp "$work/ffmpeg-$FFMPEG_VERSION/LICENSE.md" "$prefix/licenses/FFmpeg-LICENSE.md"
cp "$work/openssl-$OPENSSL_VERSION/LICENSE.txt" "$prefix/licenses/OpenSSL-LICENSE.txt"
"$cc" --version > "$prefix/build-info/compiler.txt"
nasm -v > "$prefix/build-info/assembler.txt"
"$cc" -std=c11 -Wall -Wextra -Werror -Os -I"$prefix/include" \
  "$repo/tests/capabilities.c" -L"$prefix/lib" \
  -lavfilter -lavformat -lavcodec -lswscale -lavutil -lssl -lcrypto \
  "${link_flags[@]}" -o "$work/capabilities"
"$work/capabilities" | tee "$prefix/build-info/capabilities.txt"
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
"$work/relocated-capabilities"
echo "Candidate validated: $work/ffmpeg-$triplet-candidate.zip"
