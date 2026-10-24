import os
import sqlite3

import pytest

from coverwise import demo_reset
from coverwise.sandbox import SandboxError, SandboxProvider


@pytest.fixture
def demo(tmp_path, monkeypatch):
    path = tmp_path / "runtime" / "demo" / "rehearsal.sqlite3"
    monkeypatch.setattr(demo_reset, "DEMO_DATABASE", path)
    store = SandboxProvider(path)
    with store.transaction() as db:
        db.execute(
            "INSERT INTO quotes VALUES "
            "('synthetic-reset-fixture','scope','{}','digest')"
        )
    store.close()
    return path


def count(path):
    with sqlite3.connect(path) as db:
        return db.execute("SELECT count(*) FROM quotes").fetchone()[0]


def test_dry_run_preserves_database_and_schema(demo):
    before = demo.read_bytes()
    result = demo_reset.reset(demo)
    assert result["mode"] == "dry-run" and result["counts"]["quotes"] == 1
    assert demo.read_bytes() == before and count(demo) == 1


@pytest.mark.parametrize("confirmation", [None, "yes", "wrong"])
def test_execute_requires_exact_confirmation(demo, confirmation):
    with pytest.raises(demo_reset.ResetRefused, match="--confirm"):
        demo_reset.reset(demo, execute=True, confirmation=confirmation)
    assert count(demo) == 1


def test_explicit_reset_clears_only_designated_temporary_records(demo):
    sibling = demo.parent / "keep.txt"
    sibling.write_text("synthetic sentinel", encoding="utf-8")
    result = demo_reset.reset(demo, execute=True, confirmation=demo_reset.CONFIRMATION)
    assert result["counts"]["quotes"] == 1
    assert demo.is_file() and count(demo) == 0
    with sqlite3.connect(demo) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert (
            len(list(db.execute("SELECT name FROM sqlite_master WHERE type='table'")))
            == 7
        )
    assert sibling.read_text(encoding="utf-8") == "synthetic sentinel"
    fresh = SandboxProvider(demo)
    assert fresh.counts()["quotes"] == 0
    fresh.close()


@pytest.mark.parametrize(
    "name",
    [
        "provider.sqlite3",
        "other.sqlite3",
        "rehearsal.sqlite3.backup",
        "../demo/rehearsal.sqlite3",
    ],
)
def test_unsafe_or_non_designated_paths_refused(demo, name):
    with pytest.raises(demo_reset.ResetRefused):
        demo_reset.reset(demo.parent / name)
    assert count(demo) == 1


def test_default_live_database_refused_without_opening_it(demo):
    with pytest.raises(demo_reset.ResetRefused):
        demo_reset.reset(demo_reset.ROOT / "runtime" / "provider.sqlite3")


@pytest.mark.parametrize("execute", [False, True])
def test_live_provider_lease_refuses_reset_between_requests(demo, execute):
    first, second = SandboxProvider(demo), SandboxProvider(demo)
    try:
        first.close()
        with pytest.raises(demo_reset.ResetRefused, match="active"):
            demo_reset.reset(
                demo, execute=execute, confirmation=demo_reset.CONFIRMATION
            )
        assert count(demo) == 1
    finally:
        second.close()
    assert demo_reset.reset(demo)["counts"]["quotes"] == 1
    with pytest.raises(SandboxError, match="provider_closed"):
        second.counts()


@pytest.mark.parametrize("execute", [False, True])
def test_sqlite_lock_refuses_reset(demo, execute):
    with sqlite3.connect(demo) as locked:
        locked.execute("BEGIN IMMEDIATE")
        with pytest.raises(demo_reset.ResetRefused, match="locked"):
            demo_reset.reset(
                demo, execute=execute, confirmation=demo_reset.CONFIRMATION
            )
        locked.rollback()
    assert count(demo) == 1


def test_hard_link_alias_refused(demo):
    alias = demo.parent / "external.sqlite3"
    os.link(demo, alias)
    with pytest.raises(demo_reset.ResetRefused, match="hard links"):
        demo_reset.reset(demo, execute=True, confirmation=demo_reset.CONFIRMATION)
    assert count(alias) == count(demo) == 1


def test_symlink_path_refused_before_open(demo, monkeypatch):
    # Native Windows symlink creation requires privileges; model the path flag.
    original = type(demo).is_symlink
    monkeypatch.setattr(type(demo), "is_symlink", lambda p: p == demo or original(p))
    with pytest.raises(demo_reset.ResetRefused, match="Symlinks"):
        demo_reset.reset(demo)
    assert count(demo) == 1


def test_unknown_schema_refused(demo):
    with sqlite3.connect(demo) as db:
        db.execute("PRAGMA user_version=99")
    with pytest.raises(demo_reset.ResetRefused, match="schema"):
        demo_reset.reset(demo, execute=True, confirmation=demo_reset.CONFIRMATION)
    assert count(demo) == 1


def test_unmarked_database_refused_without_creating_a_lease(demo):
    guard = demo.with_suffix(demo.suffix + ".lease")
    guard.unlink()
    with pytest.raises(demo_reset.ResetRefused, match="lease is missing"):
        demo_reset.reset(demo, execute=True, confirmation=demo_reset.CONFIRMATION)
    assert not guard.exists() and count(demo) == 1


def test_missing_demo_database_does_not_create_records_or_directories(
    tmp_path, monkeypatch
):
    path = tmp_path / "runtime" / "demo" / "rehearsal.sqlite3"
    monkeypatch.setattr(demo_reset, "DEMO_DATABASE", path)
    assert demo_reset.reset(path)["exists"] is False
    assert not path.parent.exists()
