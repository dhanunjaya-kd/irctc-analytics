"""PNG content comparison helpers. The execution platform can append a C2PA content-credentials chunk ('caBX') to PNG files in the outputs folder; it changes the file bytes, never the pixels.
Baseline comparisons in the test suites therefore hash a PNG WITHOUT its caBX chunk. Nothing is stripped from any file: only the comparison ignores it."""
import hashlib


def png_core(b: bytes) -> bytes:
    if b[:8] != b"\x89PNG\r\n\x1a\n": return b
    out, i = [b[:8]], 8
    while i < len(b):
        ln = int.from_bytes(b[i:i + 4], "big")
        if b[i + 4:i + 8] != b"caBX": out.append(b[i:i + 12 + ln])
        i += 12 + ln
    return b"".join(out)


def content_sha256(name: str, data: bytes) -> str:
    return hashlib.sha256(png_core(data) if str(name).lower().endswith(".png") else data).hexdigest()
