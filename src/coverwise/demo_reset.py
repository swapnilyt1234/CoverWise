"""Offline, dry-run-first reset of one designated rehearsal database only."""

import argparse
import os
import sqlite3
from pathlib import Path

from coverwise.policies import ROOT

DEMO_DATABASE = ROOT / "runtime" / "demo" / "rehearsal.sqlite3"
CONFIRMATION = "CLEAR-REHEARSAL-RECORDS"
TABLES = (
    "payment_ledger",
    "payments",
    "approvals",
    "revisions",
    "applications",
    "quotes",
    "operations",
)


class ResetRefused(Exception):
    """Safe operational explanation without record data."""


def checked_path(path):
    path = Path(path).absolute()
    expected = DEMO_DATABASE.absolute()
    if path != expected or ".." in path.parts:
        raise ResetRefused(
            "Only runtime/demo/rehearsal.sqlite3 is resettable; live paths are refused."
        )
    for item in (path, *path.parents):
        if item.is_symlink() or (
            item.exists() and getattr(item.stat(), "st_file_attributes", 0) & 0x400
        ):
            raise ResetRefused("Symlinks, junctions and reparse points are refused.")
        if item == ROOT.absolute() or item == expected.parent.parent.parent:
            break
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise ResetRefused("Database must be a regular file without hard links.")
    if path.resolve() != expected:
        raise ResetRefused("Resolved database path is unsafe.")
    return path


def lease(path, *, exclusive):
    """Providers share a process-lifetime lease; reset needs exclusive access."""
    guard = path.with_suffix(path.suffix + ".lease")
    if guard.is_symlink() or (
        guard.exists()
        and (
            not guard.is_file()
            or guard.stat().st_nlink != 1
            or getattr(guard.stat(), "st_file_attributes", 0) & 0x400
        )
    ):
        raise ResetRefused("Unsafe rehearsal lease file.")
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        )
        create.restype = wintypes.HANDLE
        handle = create(
            str(guard),
            0xC0000000 if exclusive else 0x80000000,
            0 if exclusive else 1,
            None,
            4,
            0x80,
            None,
        )
        if handle == ctypes.c_void_p(-1).value:
            raise ResetRefused(
                "Rehearsal database is active or its lease is unavailable; "
                "stop the process."
            )
        flags = os.O_RDWR if exclusive else os.O_RDONLY
        return os.fdopen(
            msvcrt.open_osfhandle(handle, flags), "r+b" if exclusive else "rb"
        )
    import fcntl

    file = guard.open("a+b")
    try:
        fcntl.flock(
            file, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB
        )
    except OSError:
        file.close()
        raise ResetRefused("Rehearsal database is active; stop the process.") from None
    return file


def provider_lease(path):
    if Path(path).resolve() != DEMO_DATABASE.resolve():
        return None
    return lease(checked_path(path), exclusive=False)


def reset(path=DEMO_DATABASE, *, execute=False, confirmation=None):
    path = checked_path(path)
    if execute and confirmation != CONFIRMATION:
        raise ResetRefused("Execution requires --confirm " + CONFIRMATION)
    if not path.exists():
        return {
            "mode": "execute" if execute else "dry-run",
            "exists": False,
            "counts": {},
        }
    if not path.with_suffix(path.suffix + ".lease").is_file():
        raise ResetRefused("Rehearsal safety lease is missing; no reset attempted.")
    with lease(path, exclusive=True):
        checked_path(path)
        try:
            db = sqlite3.connect(
                path.as_uri() + "?mode=rw", uri=True, timeout=0, isolation_level=None
            )
            try:
                db.execute("PRAGMA foreign_keys=ON")
                db.execute("BEGIN EXCLUSIVE")
                tables = {
                    r[0]
                    for r in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if db.execute("PRAGMA user_version").fetchone()[
                    0
                ] != 1 or tables != set(TABLES):
                    raise ResetRefused("Unrecognized schema; no records cleared.")
                counts = {
                    name: db.execute("SELECT count(*) FROM " + name).fetchone()[0]
                    for name in TABLES
                }
                if execute:
                    for name in TABLES:
                        db.execute("DELETE FROM " + name)
                    db.commit()
                else:
                    db.rollback()
                return {
                    "mode": "execute" if execute else "dry-run",
                    "exists": True,
                    "counts": counts,
                }
            finally:
                if db.in_transaction:
                    db.rollback()
                db.close()
        except sqlite3.Error:
            raise ResetRefused(
                "Database is locked, invalid or unavailable; no reset completed."
            ) from None


def main():
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEMO_DATABASE)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args()
    try:
        result = reset(args.database, execute=args.execute, confirmation=args.confirm)
    except (ResetRefused, OSError) as exc:
        parser.exit(
            2,
            "Reset refused: "
            + (str(exc) if isinstance(exc, ResetRefused) else "filesystem unavailable")
            + "\n",
        )
    print(json.dumps(result, indent=2))
    print(
        "Counts would be cleared (dry-run) or were cleared (execute). "
        "Only rehearsal quotes, applications/revisions, approvals, "
        "payments/ledger and operations. "
        "Database/schema retained; no PDFs, configuration or identities touched."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
