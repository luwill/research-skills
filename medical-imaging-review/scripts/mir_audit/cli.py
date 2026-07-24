"""Argument parsing, safe report writing, and the main() entry point.

Part of the mir_audit package (split from the original audit_manuscript.py).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

from pathlib import Path

from .constants import *  # noqa: F401,F403
from .model import *  # noqa: F401,F403
from .profile import *  # noqa: F401,F403
from .report import *  # noqa: F401,F403
from .core import *  # noqa: F401,F403


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit a medical-imaging review manuscript.")
    parser.add_argument("manuscript", type=Path)
    parser.add_argument("--route", choices=SUPPORTED_ROUTES, default="auto")
    parser.add_argument("--profile", type=Path, help="Optional JSON audit/style profile.")
    parser.add_argument("--project-dir", type=Path, help="Review project directory for artifact and human-gate checks.")
    parser.add_argument("--output", type=Path, help="Write a Markdown audit report to this path.")
    parser.add_argument("--json", action="store_true", help="Emit stable JSON to stdout.")
    parser.add_argument("--fail-on", choices=("none",) + SEVERITIES, default="critical")
    return parser


def validate_output_path(output: Path, project_dir: Path | None) -> None:
    if output.is_symlink():
        raise AuditInputError("audit output must not be a symlink")
    if project_dir is None:
        return
    if project_dir.is_symlink():
        raise AuditInputError("--project-dir must not be a symlink")
    root = project_dir / "review_outputs"
    if root.is_symlink():
        raise AuditInputError("<project_dir>/review_outputs must not be a symlink")
    try:
        output.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise AuditInputError(
            "with --project-dir, --output must be inside <project_dir>/review_outputs"
        ) from exc
    current = output.parent
    while current != root.parent and current != current.parent:
        if current.exists() and current.is_symlink():
            raise AuditInputError("audit output parent must not contain symlinks")
        if current == root:
            break
        current = current.parent


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".audit-report-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
    finally:
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink()
            except FileNotFoundError:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.json and args.output:
        parser.error("--json and --output are mutually exclusive")
    try:
        text = args.manuscript.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"error: cannot read manuscript {args.manuscript}: {exc}", file=sys.stderr)
        return 2
    try:
        overrides = load_profile(args.profile)
        result = audit_text(
            text,
            file_label=str(args.manuscript),
            requested_route=args.route,
            profile_overrides=overrides,
            profile_path=args.profile,
            project_dir=args.project_dir,
            manuscript_path=args.manuscript,
            fail_on=args.fail_on,
        )
    except AuditInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n" if args.json else render_markdown(result)
    if args.output:
        try:
            validate_output_path(args.output, args.project_dir)
            atomic_write_text(args.output, rendered)
        except (AuditInputError, OSError) as exc:
            print(f"error: cannot write report {args.output}: {exc}", file=sys.stderr)
            return 2
    else:
        print(rendered, end="")
    return 1 if result["gate_status"] == "fail" else 0
