"""Reject accidental shared FFmpeg/OpenSSL dependencies in Linux consumers."""

import re
import subprocess
import sys

report = subprocess.check_output(["ldd", sys.argv[1]], text=True)
if "not found" in report:
    raise SystemExit("Missing consumer dependency:\n" + report)
if re.search(r"\blib(?:avcodec|avformat|avfilter|avutil|swscale|ssl|crypto|x264)[-.]", report):
    raise SystemExit("Expected static FFmpeg/OpenSSL, found shared dependency:\n" + report)
versions = subprocess.check_output(["readelf", "--version-info", sys.argv[1]], text=True)
requirements = {tuple(map(int, version.split("."))) for version in re.findall(r"\bGLIBC_(\d+(?:\.\d+)+)", versions)}
if requirements:
    print("Highest required glibc symbol version: " + ".".join(map(str, max(requirements))))
print("PASS consumer links FFmpeg and OpenSSL statically")
