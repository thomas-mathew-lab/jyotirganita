"""An installed package: the kernel fetch command and the data without the registers.

``jyotirganita fetch-kernel`` fetches a registered kernel once from its
registry URL and verifies its size and hash; here the URL is a local
``file:`` URL, so the test runs offline and fetches nothing from JPL. A
tree that holds the package's data but not the authority fixtures (an
installed wheel) loads the same records. The engine's output is
evidence for nothing here.
"""

from __future__ import annotations

import dataclasses
import functools
import hashlib
import shutil
from pathlib import Path

import pytest
from jplephem.spk import SPK

from jyotirganita.data.datum import RECORD_IDS, context_for, load_records
from jyotirganita.io.cli import EXIT_FAILED, main
from jyotirganita.modern import kernels
from jyotirganita.modern.kernels import KernelError, fetch, load_registry

REPO = Path(__file__).resolve().parents[2]
PAYLOAD = b"not a kernel, a stand-in of known size and hash\n"


def _registry(tmp: Path, *, sha256: str | None = None) -> dict[str, kernels.KernelEntry]:
    src = tmp / "host" / "stand-in.bsp"
    src.parent.mkdir()
    src.write_bytes(PAYLOAD)
    good = load_registry()["de440"]
    digest = hashlib.sha256(PAYLOAD).hexdigest() if sha256 is None else sha256
    entry = dataclasses.replace(
        good,
        id="stand-in",
        url=src.as_uri(),
        file="stand-in.bsp",
        bytes=len(PAYLOAD),
        sha256=digest,
    )
    return {"stand-in": entry}


def test_fetch_downloads_once_and_verifies(tmp_path: Path) -> None:
    reg, out = _registry(tmp_path), tmp_path / "ephemerides"
    path = fetch("stand-in", registry=reg, directory=out)
    assert path == out / "stand-in.bsp" and path.read_bytes() == PAYLOAD
    assert sorted(p.name for p in out.iterdir()) == ["stand-in.bsp"]
    (tmp_path / "host" / "stand-in.bsp").unlink()
    assert fetch("stand-in", registry=reg, directory=out) == path


def test_verify_only_never_downloads(tmp_path: Path) -> None:
    reg, out = _registry(tmp_path), tmp_path / "ephemerides"
    with pytest.raises(KernelError, match="is not fetched"):
        fetch("stand-in", verify_only=True, registry=reg, directory=out)
    assert not out.exists()


def test_a_download_whose_hash_differs_is_refused(tmp_path: Path) -> None:
    reg, out = _registry(tmp_path, sha256="0" * 64), tmp_path / "ephemerides"
    with pytest.raises(KernelError, match="differs"):
        fetch("stand-in", registry=reg, directory=out)


def test_no_entry_or_no_recorded_hash_is_refused_before_any_download(tmp_path: Path) -> None:
    reg, out = _registry(tmp_path), tmp_path / "ephemerides"
    with pytest.raises(KernelError, match="no entry"):
        fetch("de999", registry=reg, directory=out)
    unrecorded = {"stand-in": dataclasses.replace(reg["stand-in"], sha256=None)}
    with pytest.raises(KernelError, match="no hash"):
        fetch("stand-in", registry=unrecorded, directory=out)
    assert not out.exists()


def test_the_command_fetches_and_reports_its_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    reg, out = _registry(tmp_path), tmp_path / "ephemerides"
    monkeypatch.setattr(kernels, "load_registry", lambda: reg)
    monkeypatch.setattr(kernels, "fetch", functools.partial(fetch, directory=out))
    assert main(["fetch-kernel", "stand-in", "--verify"]) == EXIT_FAILED
    assert "is not fetched" in capsys.readouterr().err
    assert main(["fetch-kernel", "stand-in"]) == 0
    assert "stand-in verified at" in capsys.readouterr().err
    assert main(["fetch-kernel", "de999"]) == EXIT_FAILED
    assert "no entry" in capsys.readouterr().err


def test_the_kernel_folder_is_the_package_s_unless_the_variable_names_another(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(kernels.KERNEL_DIR_VARIABLE, raising=False)
    assert kernels.kernel_directory() == kernels.EPHEMERIDES_DIR
    elsewhere = tmp_path / "kernels"
    monkeypatch.setenv(kernels.KERNEL_DIR_VARIABLE, str(elsewhere))
    assert kernels.kernel_directory() == elsewhere


@pytest.mark.parametrize("raw", ["", "  ", "relative/kernels"])
def test_an_empty_or_relative_kernel_folder_is_refused(
    raw: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(kernels.KERNEL_DIR_VARIABLE, raw)
    with pytest.raises(KernelError, match=kernels.KERNEL_DIR_VARIABLE):
        kernels.kernel_directory()


def test_the_command_and_the_loader_use_the_named_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    reg, elsewhere = _registry(tmp_path), tmp_path / "kernels"
    monkeypatch.setenv(kernels.KERNEL_DIR_VARIABLE, str(elsewhere))
    monkeypatch.setattr(kernels, "load_registry", lambda: reg)
    assert main(["fetch-kernel", "stand-in"]) == 0
    assert f"stand-in verified at {elsewhere / 'stand-in.bsp'}" in capsys.readouterr().err
    assert (elsewhere / "stand-in.bsp").read_bytes() == PAYLOAD
    assert not (kernels.EPHEMERIDES_DIR / "stand-in.bsp").exists()
    # the loader looks in the same folder, and a file there still has to match its hash
    assert kernels.verified_path("stand-in", registry=reg) == elsewhere / "stand-in.bsp"
    (elsewhere / "stand-in.bsp").write_bytes(PAYLOAD.upper())
    with pytest.raises(KernelError, match="SHA-256"):
        kernels.verified_path("stand-in", registry=reg)
    monkeypatch.setenv(kernels.KERNEL_DIR_VARIABLE, "relative/kernels")
    assert main(["fetch-kernel", "stand-in", "--verify"]) == EXIT_FAILED
    assert kernels.KERNEL_DIR_VARIABLE in capsys.readouterr().err


def test_the_engine_s_loader_opens_the_kernel_in_the_named_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reg, elsewhere = _registry(tmp_path), tmp_path / "kernels"
    elsewhere.mkdir()
    (elsewhere / "stand-in.bsp").write_bytes(PAYLOAD)
    monkeypatch.setenv(kernels.KERNEL_DIR_VARIABLE, str(elsewhere))
    opened: list[str] = []

    class Opened(Exception):
        pass

    def spk_open(path: str) -> None:
        opened.append(path)
        raise Opened  # the stand-in is no SPK file: stop once the path is known

    monkeypatch.setattr(SPK, "open", spk_open)
    with pytest.raises(Opened):
        kernels.Ephemeris.open("stand-in", registry=reg)
    assert opened == [str(elsewhere / "stand-in.bsp")]


@pytest.mark.parametrize("named", ["absent", "corrupt"])
def test_a_named_folder_never_falls_back_to_the_package_copy(
    named: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reg, package, elsewhere = _registry(tmp_path), tmp_path / "package", tmp_path / "kernels"
    package.mkdir()
    (package / "stand-in.bsp").write_bytes(PAYLOAD)  # a good copy in the package folder
    elsewhere.mkdir()
    if named == "corrupt":
        (elsewhere / "stand-in.bsp").write_bytes(PAYLOAD.upper())
    monkeypatch.setattr(kernels, "EPHEMERIDES_DIR", package)
    monkeypatch.setenv(kernels.KERNEL_DIR_VARIABLE, str(elsewhere))
    with pytest.raises(KernelError, match="is not fetched" if named == "absent" else "SHA-256"):
        kernels.verified_path("stand-in", registry=reg)
    monkeypatch.delenv(kernels.KERNEL_DIR_VARIABLE)
    assert kernels.verified_path("stand-in", registry=reg) == package / "stand-in.bsp"


def test_a_leading_tilde_is_the_home_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(kernels.KERNEL_DIR_VARIABLE, "~/kernels")
    assert kernels.kernel_directory() == tmp_path / "kernels"


def test_the_records_load_without_the_registers_or_the_fixtures(tmp_path: Path) -> None:
    shutil.copytree(
        REPO / "jyotirganita",
        tmp_path / "jyotirganita",
        ignore=shutil.ignore_patterns("__pycache__", "ephemerides"),
    )
    # the issue and decision ids the records cite travel with the data where the tree has them
    assert tmp_path.joinpath(*RECORD_IDS).is_file() == REPO.joinpath(*RECORD_IDS).is_file()
    shipped = load_records(tmp_path, context_for(tmp_path))
    full = load_records(REPO, context_for(REPO))
    assert shipped.data.keys() == full.data.keys() and not shipped.fixtures
