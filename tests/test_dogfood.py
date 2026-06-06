"""Tests for the Phase 7 dogfood loop.

Mocks all file I/O at the boundary where safe; uses tmp_path for real file work
when that's simpler than mocking pathlib.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from neuros.config import settings
from neuros.models import ProposedChange
from neuros.skills.base import SkillResult
from neuros.skills.code import _safety
from neuros.skills.code.applier import ApplyChangeSkill
from neuros.skills.code.git_ops import GitCommitSkill, GitPushSkill
from neuros.skills.code.improver import ProposeImprovementSkill, _find_closest_test, _parse_response
from neuros.skills.code.reader import (
    ListFilesSkill,
    ReadFileSkill,
    SearchCodeSkill,
)
from neuros.skills.code.tester import RunTestsSkill, parse_pytest_output


@pytest.fixture
def fake_root(tmp_path, monkeypatch):
    """Point project_root at a tmp dir so file ops are isolated."""
    monkeypatch.setattr(_safety, "project_root", lambda: tmp_path.resolve())
    return tmp_path


@pytest.fixture
def project_settings_root(fake_root, monkeypatch):
    monkeypatch.setattr(settings, "project_root", str(fake_root))
    return fake_root


# ── reader.ReadFileSkill ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_file_returns_content(fake_root):
    f = fake_root / "hello.py"
    f.write_text("print('hi')\nprint('bye')\n")

    result = await ReadFileSkill().run(path="hello.py")
    assert result.success
    assert result.data["line_count"] == 2
    assert "hi" in result.data["content"]


@pytest.mark.asyncio
async def test_read_file_rejects_path_traversal(fake_root):
    result = await ReadFileSkill().run(path="../etc/passwd")
    assert not result.success
    assert "traversal" in result.error.lower() or "outside" in result.error.lower()


@pytest.mark.asyncio
async def test_read_file_rejects_outside_project_root(fake_root):
    result = await ReadFileSkill().run(path="/etc/passwd")
    assert not result.success


@pytest.mark.asyncio
async def test_read_file_rejects_bad_extension(fake_root):
    f = fake_root / "secret.bin"
    f.write_bytes(b"\x00\x01")
    result = await ReadFileSkill().run(path="secret.bin")
    assert not result.success


# ── reader.ListFilesSkill ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_files_returns_file_list(fake_root):
    (fake_root / "a.py").write_text("")
    (fake_root / "b.py").write_text("")
    (fake_root / "c.md").write_text("")

    result = await ListFilesSkill().run(path=".", pattern="*.py")
    assert result.success
    names = sorted(f["path"] for f in result.data["files"])
    assert names == ["a.py", "b.py"]
    assert result.data["count"] == 2


# ── reader.SearchCodeSkill ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_code_finds_pattern(fake_root):
    (fake_root / "x.py").write_text("def needle():\n    pass\n")
    (fake_root / "y.py").write_text("def haystack():\n    pass\n")

    result = await SearchCodeSkill().run(query="needle", file_pattern="*.py")
    assert result.success
    assert result.data["total"] >= 1
    assert any("x.py" in m["file"] for m in result.data["matches"])


# ── improver: response parsing ───────────────────────────────────────


def test_propose_improvement_parser_handles_well_formed():
    raw = (
        "SUMMARY: Add type hint to recall\n"
        "REASON: Improves readability\n"
        "RISK: low\n"
        "ORIGINAL:\n"
        "def recall(self, q):\n"
        "    return []\n"
        "REPLACEMENT:\n"
        "def recall(self, q: str) -> list:\n"
        "    return []\n"
        "TESTS_AFFECTED: tests/test_memory.py"
    )
    p = _parse_response(raw)
    assert p is not None
    assert p["summary"].startswith("Add type")
    assert p["risk"] == "low"
    assert "def recall(self, q):" in p["original"]
    assert p["tests_affected"] == ["tests/test_memory.py"]


def test_propose_improvement_parser_rejects_malformed():
    assert _parse_response("not the right format at all") is None


def test_find_closest_test_matches_by_stem():
    real_files = ["test_memory.py", "test_graph.py"]
    assert _find_closest_test("tests/test_memory_manager.py", real_files) == "test_memory.py"


def test_find_closest_test_no_match_returns_none():
    real_files = ["test_memory.py", "test_graph.py"]
    assert _find_closest_test("tests/test_completely_made_up.py", real_files) is None


@pytest.mark.asyncio
async def test_propose_improvement_validates_test_files_exist(project_settings_root, monkeypatch):
    project_root = project_settings_root
    tests_dir = project_root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_memory.py").write_text("")
    code_dir = project_root / "neuros" / "memory"
    code_dir.mkdir(parents=True)
    (code_dir / "manager.py").write_text("print('x')\n")

    raw = (
        "SUMMARY: Add better error handling\n"
        "REASON: Makes failures clearer\n"
        "RISK: low\n"
        "ORIGINAL:\nprint('x')\n"
        "REPLACEMENT:\nprint('y')\n"
        "TESTS_AFFECTED: tests/test_memory_manager.py"
    )
    monkeypatch.setattr("neuros.skills.code.improver.chat", AsyncMock(return_value=raw))

    result = await ProposeImprovementSkill().run(path="neuros/memory/manager.py")
    assert result.success
    assert result.data["tests_affected"] == ["tests/test_memory.py"]


@pytest.mark.asyncio
async def test_propose_improvement_falls_back_to_test_dogfood(project_settings_root, monkeypatch):
    project_root = project_settings_root
    tests_dir = project_root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_dogfood.py").write_text("")
    code_dir = project_root / "neuros" / "memory"
    code_dir.mkdir(parents=True)
    (code_dir / "manager.py").write_text("print('x')\n")

    raw = (
        "SUMMARY: Add better error handling\n"
        "REASON: Makes failures clearer\n"
        "RISK: low\n"
        "ORIGINAL:\nprint('x')\n"
        "REPLACEMENT:\nprint('y')\n"
        "TESTS_AFFECTED: tests/test_completely_made_up.py"
    )
    monkeypatch.setattr("neuros.skills.code.improver.chat", AsyncMock(return_value=raw))

    result = await ProposeImprovementSkill().run(path="neuros/memory/manager.py")
    assert result.success
    assert result.data["tests_affected"] == ["tests/test_dogfood.py"]


# ── applier ──────────────────────────────────────────────────────────


def _make_proposal(path: str, original: str, replacement: str, status="approved") -> ProposedChange:
    return ProposedChange(
        id="11111111-1111-1111-1111-111111111111",
        path=path,
        summary="s",
        reason="r",
        risk="low",
        original=original,
        replacement=replacement,
        tests_affected=["tests/"],
        proposed_at=datetime.now(UTC),
        status=status,
    )


@pytest.mark.asyncio
async def test_apply_change_requires_confirmed_true(fake_root):
    result = await ApplyChangeSkill().run(proposal_id="abc", confirmed=False)
    assert not result.success
    assert "confirmed" in result.error.lower()


@pytest.mark.asyncio
async def test_apply_change_requires_approved_status(fake_root):
    f = fake_root / "m.py"
    f.write_text("original\n")
    proposal = _make_proposal("m.py", "original", "replaced", status="pending")

    mock_pg = MagicMock()
    mock_pg.get_proposal = AsyncMock(return_value=proposal)
    mock_pg.update_proposal_status = AsyncMock()
    mock_mgr = MagicMock(_postgres=mock_pg)

    with patch("neuros.memory.manager.manager", mock_mgr):
        result = await ApplyChangeSkill().run(proposal_id=proposal.id, confirmed=True)

    assert not result.success
    assert "approved" in result.error.lower()


@pytest.mark.asyncio
async def test_apply_change_verifies_original_exists(fake_root):
    f = fake_root / "m.py"
    f.write_text("totally different content\n")
    proposal = _make_proposal("m.py", "nope nope nope", "replaced")

    mock_pg = MagicMock()
    mock_pg.get_proposal = AsyncMock(return_value=proposal)
    mock_pg.update_proposal_status = AsyncMock()
    mock_mgr = MagicMock(_postgres=mock_pg)

    with patch("neuros.memory.manager.manager", mock_mgr):
        result = await ApplyChangeSkill().run(proposal_id=proposal.id, confirmed=True)

    assert not result.success
    assert "no longer matches" in result.error


@pytest.mark.asyncio
async def test_apply_change_restores_backup_on_test_failure(fake_root):
    f = fake_root / "m.py"
    f.write_text("original\n")
    proposal = _make_proposal("m.py", "original", "replaced")

    mock_pg = MagicMock()
    mock_pg.get_proposal = AsyncMock(return_value=proposal)
    mock_pg.update_proposal_status = AsyncMock()
    mock_mgr = MagicMock(_postgres=mock_pg)

    fail = MagicMock(
        success=True, data={"passed": 0, "failed": 1, "success": False, "output": "BOOM"}
    )
    with (
        patch("neuros.memory.manager.manager", mock_mgr),
        patch.object(RunTestsSkill, "run", AsyncMock(return_value=fail)),
    ):
        result = await ApplyChangeSkill().run(proposal_id=proposal.id, confirmed=True)

    assert result.success
    assert result.data["applied"] is False
    assert result.data["tests_passed"] is False
    assert f.read_text() == "original\n"  # restored
    backups = list(fake_root.glob("m.py.neuros_backup_*"))
    assert backups == []  # backup cleaned


@pytest.mark.asyncio
async def test_apply_change_no_tests_collected_falls_back_to_full_suite(fake_root):
    f = fake_root / "m.py"
    f.write_text("original\n")
    proposal = _make_proposal("m.py", "original", "replaced")

    mock_pg = MagicMock()
    mock_pg.get_proposal = AsyncMock(return_value=proposal)
    mock_pg.update_proposal_status = AsyncMock()
    mock_mgr = MagicMock(_postgres=mock_pg)

    no_tests = SkillResult.ok(
        {"passed": 0, "failed": 0, "success": False, "output": "collected 0 items"},
        skill_name="run_tests",
    )
    full_suite = SkillResult.ok(
        {"passed": 3, "failed": 0, "success": True, "output": "all good"},
        skill_name="run_tests",
    )

    with (
        patch("neuros.memory.manager.manager", mock_mgr),
        patch.object(RunTestsSkill, "run", AsyncMock(side_effect=[no_tests, full_suite])),
    ):
        result = await ApplyChangeSkill().run(proposal_id=proposal.id, confirmed=True)

    assert result.success
    assert result.data["applied"] is True
    assert result.data["tests_passed"] is True
    assert f.read_text() == "replaced\n"
    backups = list(fake_root.glob("m.py.neuros_backup_*"))
    assert backups == []


@pytest.mark.asyncio
async def test_apply_change_full_suite_fails_after_fallback(fake_root):
    f = fake_root / "m.py"
    f.write_text("original\n")
    proposal = _make_proposal("m.py", "original", "replaced")

    mock_pg = MagicMock()
    mock_pg.get_proposal = AsyncMock(return_value=proposal)
    mock_pg.update_proposal_status = AsyncMock()
    mock_mgr = MagicMock(_postgres=mock_pg)

    no_tests = SkillResult.ok(
        {"passed": 0, "failed": 0, "success": False, "output": "no tests ran"},
        skill_name="run_tests",
    )
    full_suite = SkillResult.ok(
        {"passed": 1, "failed": 1, "success": False, "output": "FAILED"},
        skill_name="run_tests",
    )

    with (
        patch("neuros.memory.manager.manager", mock_mgr),
        patch.object(RunTestsSkill, "run", AsyncMock(side_effect=[no_tests, full_suite])),
    ):
        result = await ApplyChangeSkill().run(proposal_id=proposal.id, confirmed=True)

    assert result.success
    assert result.data["applied"] is False
    assert result.data["tests_passed"] is False
    assert "FAILED" in result.data["test_output"]
    assert f.read_text() == "original\n"
    backups = list(fake_root.glob("m.py.neuros_backup_*"))
    assert backups == []


@pytest.mark.asyncio
async def test_apply_change_deletes_backup_on_success(fake_root):
    f = fake_root / "m.py"
    f.write_text("original\n")
    proposal = _make_proposal("m.py", "original", "replaced")

    mock_pg = MagicMock()
    mock_pg.get_proposal = AsyncMock(return_value=proposal)
    mock_pg.update_proposal_status = AsyncMock()
    mock_mgr = MagicMock(_postgres=mock_pg)

    ok = MagicMock(success=True, data={"passed": 5, "failed": 0, "success": True, "output": "ok"})
    with (
        patch("neuros.memory.manager.manager", mock_mgr),
        patch.object(RunTestsSkill, "run", AsyncMock(return_value=ok)),
    ):
        result = await ApplyChangeSkill().run(proposal_id=proposal.id, confirmed=True)

    assert result.success
    assert result.data["applied"] is True
    assert f.read_text() == "replaced\n"
    backups = list(fake_root.glob("m.py.neuros_backup_*"))
    assert backups == []


# ── tester ──────────────────────────────────────────────────────────


def test_run_tests_parses_pytest_output():
    out = "============= 5 passed, 2 failed, 1 error in 1.2s ============="
    passed, failed, errors = parse_pytest_output(out)
    assert (passed, failed, errors) == (5, 2, 1)


@pytest.mark.asyncio
async def test_run_tests_timeout_handled(fake_root, monkeypatch):
    async def fake_wait(*a, **kw):
        raise TimeoutError()

    monkeypatch.setattr(asyncio, "wait_for", fake_wait)

    fake_proc = MagicMock()
    fake_proc.communicate = AsyncMock(return_value=(b"", b""))

    async def fake_exec(*args, **kwargs):
        return fake_proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await RunTestsSkill().run(test_path="tests/")
    assert not result.success
    assert "timed out" in result.error.lower()


@pytest.mark.asyncio
async def test_run_tests_nonexistent_path_runs_full_suite(project_settings_root, monkeypatch):
    project_root = project_settings_root
    (project_root / "tests").mkdir()

    calls: list[tuple] = []

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        fake_proc = MagicMock()
        fake_proc.communicate = AsyncMock(
            return_value=(
                b"============================= 1 passed in 0.1s =============================",
                b"",
            )
        )
        fake_proc.returncode = 0
        return fake_proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await RunTestsSkill().run(test_path="tests/test_missing.py")
    assert result.success
    assert calls
    assert "tests/" in calls[0]


@pytest.mark.asyncio
async def test_run_tests_no_tests_collected_reruns_full_suite(project_settings_root, monkeypatch):
    project_root = project_settings_root
    tests_dir = project_root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_empty.py").write_text("")

    calls: list[tuple] = []

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        fake_proc = MagicMock()
        if len(calls) == 1:
            fake_proc.communicate = AsyncMock(return_value=(b"collected 0 items", b""))
            fake_proc.returncode = 5
        else:
            fake_proc.communicate = AsyncMock(
                return_value=(
                    b"============================= 2 passed in 0.2s =============================",
                    b"",
                )
            )
            fake_proc.returncode = 0
        return fake_proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await RunTestsSkill().run(test_path="tests/test_empty.py")
    assert result.success
    assert len(calls) == 2
    assert "tests/test_empty.py" in calls[0]
    assert "tests/" in calls[1]


@pytest.mark.asyncio
async def test_run_tests_missing_list_paths_falls_back_to_full_suite(
    project_settings_root, monkeypatch
):
    project_root = project_settings_root
    (project_root / "tests").mkdir()

    calls: list[tuple] = []

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        fake_proc = MagicMock()
        fake_proc.communicate = AsyncMock(
            return_value=(
                b"============================= 4 passed in 0.2s =============================",
                b"",
            )
        )
        fake_proc.returncode = 0
        return fake_proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await RunTestsSkill().run(
        test_path=["tests/test_missing_a.py", "tests/test_missing_b.py"]
    )
    assert result.success
    assert calls
    assert "tests/" in calls[0]


# ── git ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_git_commit_rejects_empty_message():
    result = await GitCommitSkill().run(message="", confirmed=True)
    assert not result.success


@pytest.mark.asyncio
async def test_git_commit_rejects_short_message():
    result = await GitCommitSkill().run(message="hi", confirmed=True)
    assert not result.success


@pytest.mark.asyncio
async def test_git_push_rejects_main_branch():
    with patch("neuros.skills.code.git_ops._current_branch", AsyncMock(return_value="main")):
        result = await GitPushSkill().run(confirmed=True)
    assert not result.success
    assert "main" in result.error


@pytest.mark.asyncio
async def test_git_push_requires_confirmed():
    result = await GitPushSkill().run(confirmed=False)
    assert not result.success


# ── graph intent classification ──────────────────────────────────────


def test_dogfood_intent_classification():
    from neuros.graph import _classify_dogfood

    assert _classify_dogfood("improve neuros/memory/manager.py") == "improve"
    assert _classify_dogfood("fix the recall node") == "improve"
    assert _classify_dogfood("refactor selector.py") == "improve"
    assert _classify_dogfood("apply 12345678-1234-1234-1234-123456789012") == "apply"
    assert _classify_dogfood("commit") == "commit"
    assert _classify_dogfood("reject it") == "reject"
    assert _classify_dogfood("yes") is None
    assert _classify_dogfood("no") is None
    assert _classify_dogfood("what is the weather") is None
    assert _classify_dogfood("tell me about graphiti") is None


# ── full loop (mocked) ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_dogfood_loop_propose_approve_apply_commit(fake_root):
    f = fake_root / "m.py"
    f.write_text("def f():\n    return 1\n")

    proposal = _make_proposal(
        "m.py",
        "def f():\n    return 1\n",
        "def f() -> int:\n    return 1\n",
        status="pending",
    )

    saved = {}

    async def save(p):
        saved["proposal"] = p
        return p.id

    async def get(pid):
        return saved.get("proposal")

    async def update(pid, status, test_result=None):
        if saved.get("proposal"):
            saved["proposal"].status = status

    mock_pg = MagicMock()
    mock_pg.save_proposal = AsyncMock(side_effect=save)
    mock_pg.get_proposal = AsyncMock(side_effect=get)
    mock_pg.update_proposal_status = AsyncMock(side_effect=update)
    mock_mgr = MagicMock(_postgres=mock_pg)
    mock_mgr.store = AsyncMock()

    # seed
    await save(proposal)

    # approve + apply
    await update(proposal.id, "approved")

    ok = MagicMock(success=True, data={"passed": 1, "failed": 0, "success": True, "output": "ok"})
    with (
        patch("neuros.memory.manager.manager", mock_mgr),
        patch.object(RunTestsSkill, "run", AsyncMock(return_value=ok)),
    ):
        result = await ApplyChangeSkill().run(proposal_id=proposal.id, confirmed=True)

    assert result.success
    assert result.data["applied"] is True
    assert "def f() -> int" in f.read_text()
    assert saved["proposal"].status == "applied"
