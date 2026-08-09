"""Fail CI on high-confidence committed credential patterns."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {"backend/.env.example", "miniprogram/.env.production", "miniprogram/.env.staging", "miniprogram/.env.development"}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "database URL with password": re.compile(r"postgres(?:ql)?://[^\s:/]+:[^\s@/]+@"),
}


def main() -> None:
    files = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).splitlines()
    findings = []
    for relative in files:
        normalized = relative.replace("\\", "/")
        if normalized in EXCLUDED:
            continue
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for name, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{relative}: {name}")
    if findings:
        raise SystemExit("Potential committed secrets:\n" + "\n".join(findings))
    print(f"secret scan passed ({len(files)} release-candidate files)")


if __name__ == "__main__":
    main()
