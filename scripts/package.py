"""Verify sources, reject version drift, and package relocatable candidate libraries."""

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def check_versions(report, versions_file):
    versions = dict(line.split("=", 1) for line in versions_file.read_text(encoding="utf-8").splitlines()
                    if line and not line.startswith("#"))
    text = report.read_text(encoding="utf-8")
    for component in ("FFmpeg", "OpenSSL"):
        expected = versions[f"{component.upper()}_VERSION"]
        if not re.search(rf"\b{component} {re.escape(expected)}(?:[;\s]|$)", text):
            raise ValueError(f"linked {component} does not match {expected}: {text.strip()}")
    if "capability-failures=0" not in text:
        raise ValueError("capability checks did not succeed")


def pack(prefix, triplet, archive):
    check_versions(prefix / "build-info" / "capabilities.txt", prefix / "build-info" / "versions.env")
    required = {f"lib{name}.a" for name in (
        "avcodec", "avformat", "avfilter", "avutil", "swscale", "ssl", "crypto")}
    actual = {path.name for path in (prefix / "lib").glob("*.a")}
    if actual != required:
        raise ValueError(f"unexpected static libraries: {actual ^ required}")
    # Retain only FFmpeg .pc files. OpenSSL paths are supplied by this relative .pc.
    pc_dir = prefix / "lib" / "pkgconfig"
    pc_dir.mkdir(exist_ok=True)
    for path in pc_dir.glob("*.pc"):
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"^prefix=.*$", "prefix=${pcfiledir}/../..", text, flags=re.M)
        text = re.sub(r"^exec_prefix=.*$", "exec_prefix=${prefix}", text, flags=re.M)
        text = re.sub(r"^libdir=.*$", "libdir=${prefix}/lib", text, flags=re.M)
        text = re.sub(r"^includedir=.*$", "includedir=${prefix}/include", text, flags=re.M)
        # Configuration may inline the private dependency's absolute -I/-L paths.
        text = re.sub(r"(?<!\S)-[IL](?:\"[^\"]*\"|[^\s]+)", "", text)
        # Restore the package's own relative flags after removing absolute flags.
        text = re.sub(r"^(Libs:(?:[^\n]*))$", r"\1 -L${libdir}", text, flags=re.M)
        text = re.sub(r"^(Cflags:(?:[^\n]*))$", r"\1 -I${includedir}", text, flags=re.M)
        path.write_text(text, encoding="utf-8")
    openssl_version = dict(line.split("=", 1) for line in (prefix / "build-info" / "versions.env").read_text(encoding="utf-8").splitlines())["OPENSSL_VERSION"]
    for name, libs in (("libcrypto", "-lcrypto"), ("libssl", "-lssl -lcrypto"), ("openssl", "-lssl -lcrypto")):
        # Same system dependencies as the validated final static link.
        private = {"windows": "-lws2_32 -lgdi32 -lcrypt32 -lbcrypt",
                   "linux": "-ldl -lpthread", "darwin": "-lpthread"}[triplet.split("-")[0]]
        (pc_dir / f"{name}.pc").write_text(
            f"prefix=${{pcfiledir}}/../..\nlibdir=${{prefix}}/lib\nincludedir=${{prefix}}/include\n\n"
            f"Name: {name}\nDescription: Static OpenSSL for DDBOT\nVersion: {openssl_version}\n"
            f"Libs: -L${{libdir}} {libs}\nLibs.private: {private}\nCflags: -I${{includedir}}\n", encoding="utf-8")
    files = sorted(path for path in prefix.rglob("*") if path.is_file() and path.name != "manifest.json")
    manifest = {"profile": "ddbot-minimal", "target": triplet,
                "files": {str(path.relative_to(prefix)).replace("\\", "/"):
                          {"bytes": path.stat().st_size, "sha256": digest(path)} for path in files}}
    (prefix / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
        for path in sorted(prefix.rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(prefix).as_posix())
    archive.with_suffix(archive.suffix + ".sha256").write_text(f"{digest(archive)}  {archive.name}\n", encoding="utf-8")
    print(f"{archive.name}: {archive.stat().st_size} bytes; {digest(archive)}")


if __name__ == "__main__":
    mode, *args = sys.argv[1:]
    if mode == "verify":
        if digest(Path(args[0])) != args[1]:
            raise ValueError(f"SHA-256 mismatch: {args[0]}")
    elif mode == "check-versions":
        check_versions(*map(Path, args))
    elif mode == "pack":
        pack(Path(args[0]), args[1], Path(args[2]))
    else:
        raise ValueError(f"unknown operation: {mode}")
