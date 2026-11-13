"""Reject accidental shared FFmpeg/OpenSSL dependencies in Linux consumers."""

import argparse
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("binary")
parser.add_argument("--max-glibc", help="reject symbol requirements above this glibc version")
args = parser.parse_args()

report = subprocess.check_output(["ldd", args.binary], text=True)
if "not found" in report:
    raise SystemExit("Missing consumer dependency:\n" + report)
if re.search(r"\blib(?:avcodec|avformat|avfilter|avutil|swscale|ssl|crypto|x264)[-.]", report):
    raise SystemExit("Expected static FFmpeg/OpenSSL, found shared dependency:\n" + report)
versions = subprocess.check_output(["readelf", "--version-info", args.binary], text=True)
requirements = {tuple(map(int, version.split("."))) for version in re.findall(r"\bGLIBC_(\d+(?:\.\d+)+)", versions)}
if requirements:
    highest = max(requirements)
    print("Highest required glibc symbol version: " + ".".join(map(str, highest)))
    if args.max_glibc and highest > tuple(map(int, args.max_glibc.split("."))):
        raise SystemExit("Consumer exceeds the glibc " + args.max_glibc + " baseline")
elif args.max_glibc:
    raise SystemExit("Cannot verify the glibc baseline: no version requirements found")
print("PASS consumer links FFmpeg and OpenSSL statically")
