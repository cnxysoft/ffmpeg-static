"""Verify consumer dependencies: system libraries only, with a Linux glibc ceiling."""

import argparse
import os
import re
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("binary")
parser.add_argument("--max-glibc", help="reject symbol requirements above this glibc version")
args = parser.parse_args()

if sys.platform == "darwin":
    report = subprocess.check_output(["otool", "-L", args.binary], text=True)
    print(report)
    for line in report.splitlines()[1:]:
        dependency = line.strip().split(" (", 1)[0]
        if not dependency.startswith(("/usr/lib/", "/System/Library/")):
            raise SystemExit("Unexpected non-system macOS dependency: " + dependency)
    print(subprocess.check_output(["otool", "-l", args.binary], text=True))
    print("PASS consumer links FFmpeg and OpenSSL statically; macOS system dependencies only")
    raise SystemExit(0)
if os.name == "nt":
    if shutil.which("llvm-readobj"):
        report = subprocess.check_output(["llvm-readobj", "--coff-imports", args.binary], text=True)
        names = re.findall(r"^\s*Name: (.+)$", report, re.M)
    else:
        report = subprocess.check_output(["objdump", "-p", args.binary], text=True)
        names = re.findall(r"DLL Name:\s*(\S+)", report)
    if not names:
        raise SystemExit("Cannot inspect PE imports")
    print("DLL imports: " + ", ".join(names))
    if any(re.search(r"libav|libswscale|libssl|libcrypto|libwinpthread|libgcc|libstdc|libc\+\+|msys-|cygwin", name, re.I) for name in names):
        raise SystemExit("Unexpected FFmpeg/OpenSSL/compiler runtime DLL")
    print("PASS consumer links FFmpeg, OpenSSL and compiler runtimes statically")
    raise SystemExit(0)

if os.environ.get("TARGET_RUNNER"):
    # Host ldd cannot inspect an ARM executable. Resolve through its target loader.
    loader = os.path.join(os.environ.get("QEMU_LD_PREFIX", "/usr/arm-linux-gnueabihf"), "lib/ld-linux-armhf.so.3")
    command = [os.environ["TARGET_RUNNER"], loader, "--list", args.binary]
else:
    command = ["ldd", args.binary]
report = subprocess.check_output(command, text=True)
print(report)
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
