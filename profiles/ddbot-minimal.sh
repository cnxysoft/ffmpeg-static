#!/usr/bin/env bash
# Candidate profile. Run from an FFmpeg source tree and pass target/compiler flags.
# Example: bash /path/to/ffmpeg-static/profiles/ddbot-minimal.sh --prefix="$PWD/build"
set -euo pipefail

exec ./configure \
  --disable-autodetect --disable-everything --enable-small \
  --enable-static --disable-shared \
  --disable-programs --disable-doc --disable-debug \
  --disable-avdevice --disable-swresample --disable-postproc \
  --enable-avcodec --enable-avformat --enable-avfilter --enable-swscale \
  --enable-protocol=http,https,tls,tcp,file,httpproxy,crypto \
  --enable-demuxer=mov,hls,mpegts,aac,mp3 \
  --enable-muxer=mp4,gif \
  --enable-decoder=h264,aac,mp3 --enable-encoder=gif \
  --enable-parser=h264,aac,mpegaudio \
  --enable-bsf=aac_adtstoasc,extract_extradata \
  --enable-filter=buffer,buffersink,palettegen,paletteuse,fps,split,format,scale \
  --enable-version3 --enable-openssl \
  "$@"
