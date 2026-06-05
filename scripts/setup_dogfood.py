"""Phase 7 setup: ensures proposals table, verifies rg + git remote, smoke-tests skills."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys


async def main() -> int:
    print("─ Phase 7 dogfood setup ─")

    # 1. proposals table
    from neuros.memory.postgres import PostgresStore

    pg = PostgresStore()
    try:
        await pg.create_tables()
        print("✓ Postgres tables ensured (incl. proposals)")
    except Exception as e:
        print(f"✗ Postgres table creation failed: {e}")
        return 1

    # 2. ripgrep
    if shutil.which("rg"):
        print("✓ ripgrep available")
    else:
        print("⚠ ripgrep not found — falling back to grep (slower). brew install ripgrep")

    # 3. git remote
    try:
        out = subprocess.check_output(["git", "remote", "-v"], text=True)
        if out.strip():
            print("✓ git remote configured")
        else:
            print("⚠ no git remotes set — push will fail until configured")
    except subprocess.CalledProcessError as e:
        print(f"⚠ git remote check failed: {e}")

    # 4. read_file smoke
    from neuros.skills.code.reader import ReadFileSkill, SearchCodeSkill

    r = await ReadFileSkill().run(path="neuros/main.py", start_line=1, end_line=5)
    if r.success:
        print(f"✓ read_file works ({r.data['line_count']} lines in neuros/main.py)")
    else:
        print(f"✗ read_file failed: {r.error}")
        return 1

    # 5. search_code smoke
    s = await SearchCodeSkill().run(query="def recall", file_pattern="*.py")
    if s.success:
        print(f"✓ search_code works ({s.data['total']} matches for 'def recall')")
    else:
        print(f"✗ search_code failed: {s.error}")
        return 1

    print("─ Done ─")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
