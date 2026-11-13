"""Verify every candidate file and promote the exact nine tested ZIPs to a release."""

import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

from package import digest

TARGETS = {"linux-amd64", "linux-386", "linux-arm", "linux-arm64",
           "darwin-amd64", "darwin-arm64", "windows-amd64", "windows-386", "windows-arm64"}


def main():
    source, destination = map(Path, sys.argv[1:])
    if destination.exists():
        raise ValueError("Release destination must be new")
    versions_text = (Path(__file__).resolve().parents[1] / "versions.env").read_text(encoding="utf-8")
    versions = dict(line.split("=", 1) for line in versions_text.splitlines() if line)
    archives = sorted(source.glob("ffmpeg-*-candidate.zip"))
    actual = {path.name.removeprefix("ffmpeg-").removesuffix("-candidate.zip") for path in archives}
    if actual != TARGETS:
        raise ValueError(f"Incomplete or unexpected target set: {actual ^ TARGETS}")
    records = []
    for archive in archives:
        checksum = digest(archive)
        if archive.with_suffix(".zip.sha256").read_text().split() != [checksum, archive.name]:
            raise ValueError("Candidate ZIP checksum mismatch: " + archive.name)
        with zipfile.ZipFile(archive) as zipped:
            manifest = json.loads(zipped.read("manifest.json"))
            if set(zipped.namelist()) != set(manifest["files"]) | {"manifest.json"}:
                raise ValueError("ZIP content differs from manifest")
            for name, record in manifest["files"].items():
                import hashlib
                data = zipped.read(name)
                if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
                    raise ValueError("Candidate file checksum mismatch: " + name)
            if zipped.read("build-info/versions.env").decode() != versions_text:
                raise ValueError("Candidate source versions do not match the release")
            report = zipped.read("build-info/capabilities.txt").decode()
            if f"FFmpeg {versions['FFMPEG_VERSION']};" not in report or f"OpenSSL {versions['OPENSSL_VERSION']} " not in report or "capability-failures=0" not in report:
                raise ValueError("Candidate runtime capability/version check failed")
            if zipped.read("build-info/smoke.txt").decode().count("PASS ") != 22:
                raise ValueError("Candidate network tests incomplete")
            target = manifest["target"]
            if archive.name != f"ffmpeg-{target}-candidate.zip":
                raise ValueError("Archive target does not match its name")
            expected_bits = 32 if target.endswith(("-386", "-arm")) else 64
            if f"pointer-bits={expected_bits};" not in report:
                raise ValueError("Candidate pointer width mismatch")
            records.append(dict(target=target, name=f"ffmpeg-{target}.zip", sha256=checksum,
                                bytes=archive.stat().st_size, verified_files=len(manifest["files"])))
    destination.mkdir()
    for archive, record in zip(archives, records):
        output = destination / record["name"]
        shutil.copyfile(archive, output)
        output.with_suffix(".zip.sha256").write_text(f"{record['sha256']}  {output.name}\n", encoding="utf-8")
    (destination / "SHA256SUMS").write_text("".join(f"{r['sha256']}  {r['name']}\n" for r in records), encoding="utf-8")
    evidence = dict(commit=os.environ["GITHUB_SHA"], validated_run_id=os.environ["VALIDATED_RUN_ID"],
                    ffmpeg=versions["FFMPEG_VERSION"], openssl=versions["OPENSSL_VERSION"], assets=records)
    (destination / "release-manifest.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    Path("release-notes.md").write_text(
        f"FFmpeg {versions['FFMPEG_VERSION']} / OpenSSL {versions['OPENSSL_VERSION']}, DDBOT minimal static libraries.\n\n"
        f"Promoted without rebuilding from [nine-platform validation](https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['VALIDATED_RUN_ID']}). "
        "Each target passed 22 local media/TLS/proxy checks, relocated linking, DDBOT media regressions, root-module tests/vet and the application build.\n\n"
        "Targets: Linux amd64/386/ARMv7 hard-float/ARM64, macOS Intel/Apple Silicon, Windows amd64/386/ARM64. "
        "Linux ARM runs under QEMU; x86 32-bit targets use OS compatibility execution. "
        "Windows ARM64 uses the OpenSSL C backend; FFmpeg assembly remains enabled. "
        "Windows ARM32 is excluded because the current Go toolchain does not support that target.\n\n"
        "Includes matching headers, seven static libraries, relocatable pkg-config files, licenses and per-file hashes. "
        "No x264 or AAC encoder. DDBOT MP4 remuxing and H.264-to-GIF paths are retained. "
        "Use the matching DDBOT consumer update; older consumers need the `ffmpeg_minimal` build tag.\n\n"
        "Linux glibc symbol ceiling: 2.35. macOS deployment target: 13.0. See build-info and release-manifest.json for exact evidence.\n",
        encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
