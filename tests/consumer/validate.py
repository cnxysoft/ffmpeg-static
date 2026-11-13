"""Run DDBOT's media regression, full root-module tests, and executable build."""

import hashlib
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path


def run(command, log, cwd):
    with log.open("w", encoding="utf-8") as output:
        print("Running: " + " ".join(map(str, command)), flush=True)
        process = subprocess.Popen(list(map(str, command)), cwd=cwd, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in process.stdout:
            output.write(line)
            print(line, end="", flush=True)
        if process.wait() != 0:
            raise RuntimeError("Command failed; see " + str(log))


def check_machine(binary, goos, arch):
    data = binary.read_bytes()
    if goos == "linux":
        expected = {"386": 3, "amd64": 62, "arm": 40, "arm64": 183}[arch]
        actual = struct.unpack_from("<H", data, 18)[0]
        if data[:4] != b"\x7fELF" or actual != expected:
            raise RuntimeError("ELF machine does not match " + arch)
    elif goos == "windows":
        offset = struct.unpack_from("<I", data, 0x3C)[0]
        expected = {"386": 0x14C, "amd64": 0x8664, "arm64": 0xAA64}[arch]
        if data[offset:offset + 4] != b"PE\0\0" or struct.unpack_from("<H", data, offset + 4)[0] != expected:
            raise RuntimeError("PE machine does not match " + arch)
    elif goos == "darwin":
        expected = {"amd64": 0x1000007, "arm64": 0x100000C}[arch]
        if data[:4] != b"\xcf\xfa\xed\xfe" or struct.unpack_from("<I", data, 4)[0] != expected:
            raise RuntimeError("Mach-O CPU does not match " + arch)
    else:
        raise RuntimeError("Unsupported consumer OS: " + goos)
    return data


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    repo = Path(__file__).resolve().parents[2]
    consumer = repo / "ddbot-consumer"
    output = repo / "candidate-build"
    destination = consumer / "ffmpeg" / "ffmpeg-static"
    if destination.exists():
        raise RuntimeError("Consumer dependency directory must be absent to prevent mixed libraries")
    shutil.copytree(output / "package", destination)
    shutil.copyfile(repo / "tests/consumer/fixtures_test.go", consumer / "ffmpeg/candidate_fixtures_test.go")
    os.environ["DDBOT_FFMPEG_FIXTURES"] = str(repo / "tests/data")
    os.environ["CGO_ENABLED"] = "1"
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=consumer, text=True).strip()
    if source != os.environ["DDBOT_CONSUMER_REF"]:
        raise RuntimeError("Consumer source does not match the pinned commit")
    goos, arch = subprocess.check_output(["go", "env", "GOOS", "GOARCH"], text=True).split()
    flags = []  # Validate the consumer's actual default build, without opt-in tags.
    runner = os.environ.get("TARGET_RUNNER")
    execution = ["-exec", runner] if runner else []
    run(["go", "test", "-v", "-timeout=5m", *flags, *execution, "./ffmpeg"], output / "ddbot-tests.log", consumer)
    run(["go", "test", "-timeout=10m", *flags, *execution, "./..."], output / "ddbot-suite.log", consumer)
    run(["go", "vet", *flags, "./..."], output / "ddbot-vet.log", consumer)
    suffix = ".exe" if goos == "windows" else ""
    binary = output / f"DDBOT-candidate-{goos}-{arch}{suffix}"
    run(["go", "build", *flags, "-trimpath", "-ldflags=-s -w", "-o", binary, "./cmd"], output / "ddbot-build.log", consumer)
    data = check_machine(binary, goos, arch)
    version = subprocess.check_output(["go", "version"], text=True).strip()
    header = (f"DDBOT source: {source}\n{version}\nTarget: {goos}/{arch}\n"
              f"Execution: {runner or 'direct'}\nCC: {os.environ.get('CC', 'default')}\n"
              f"MACOSX_DEPLOYMENT_TARGET: {os.environ.get('MACOSX_DEPLOYMENT_TARGET', '')}\n"
              f"{len(data)} bytes\nPASS executable machine matches {goos}/{arch}\n")
    print(header, flush=True)
    report = output / "consumer-build-info.txt"
    report.write_text(header, encoding="utf-8")
    command = [sys.executable, repo / "tests/consumer/dependencies.py", binary]
    if goos == "linux":
        command.extend(["--max-glibc", "2.35"])
    run(command, output / "ddbot-dependencies.log", consumer)
    with report.open("a", encoding="utf-8") as stream:
        stream.write((output / "ddbot-dependencies.log").read_text(encoding="utf-8"))
    checksum = hashlib.sha256(data).hexdigest()
    binary.with_suffix(binary.suffix + ".sha256").write_text(f"{checksum}  {binary.name}\n", encoding="utf-8")
    print(f"PASS full DDBOT consumer: {binary.name}; sha256={checksum}", flush=True)


if __name__ == "__main__":
    main()
