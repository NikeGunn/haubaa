"""Tests for FileTool."""

from __future__ import annotations

from pathlib import Path

import pytest

from hauba.tools.files import FileTool


@pytest.fixture
def file_tool() -> FileTool:
    return FileTool()


@pytest.mark.asyncio
async def test_write_and_read(file_tool: FileTool, tmp_path: Path) -> None:
    fpath = str(tmp_path / "test.txt")
    result = await file_tool.execute(action="write", path=fpath, content="hello world")
    assert result.success

    result = await file_tool.execute(action="read", path=fpath)
    assert result.success
    assert result.output == "hello world"


@pytest.mark.asyncio
async def test_append(file_tool: FileTool, tmp_path: Path) -> None:
    fpath = str(tmp_path / "test.txt")
    await file_tool.execute(action="write", path=fpath, content="line1\n")
    await file_tool.execute(action="append", path=fpath, content="line2\n")

    result = await file_tool.execute(action="read", path=fpath)
    assert "line1" in result.output
    assert "line2" in result.output


@pytest.mark.asyncio
async def test_mkdir(file_tool: FileTool, tmp_path: Path) -> None:
    dpath = str(tmp_path / "newdir" / "subdir")
    result = await file_tool.execute(action="mkdir", path=dpath)
    assert result.success
    assert Path(dpath).is_dir()


@pytest.mark.asyncio
async def test_list_dir(file_tool: FileTool, tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")

    result = await file_tool.execute(action="list", path=str(tmp_path))
    assert result.success
    assert "a.txt" in result.output
    assert "b.txt" in result.output


@pytest.mark.asyncio
async def test_exists(file_tool: FileTool, tmp_path: Path) -> None:
    fpath = str(tmp_path / "exists.txt")
    result = await file_tool.execute(action="exists", path=fpath)
    assert result.output == "False"

    Path(fpath).write_text("x")
    result = await file_tool.execute(action="exists", path=fpath)
    assert result.output == "True"


@pytest.mark.asyncio
async def test_read_nonexistent(file_tool: FileTool, tmp_path: Path) -> None:
    result = await file_tool.execute(action="read", path=str(tmp_path / "nope.txt"))
    assert not result.success


@pytest.mark.asyncio
async def test_missing_params(file_tool: FileTool) -> None:
    result = await file_tool.execute(action="read")
    assert not result.success
