"""scripts/cold_start.py: its hand-encoded frames, and a run against the provider."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from anolis.deviceprovider.v1 import envelope_pb2, status_pb2

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "cold_start.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("cold_start", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_frames_match_the_protocol_bindings() -> None:
    cold_start = load()
    hello = envelope_pb2.Request(request_id=1)
    hello.hello.protocol_version = "v1"
    wait_ready = envelope_pb2.Request(request_id=2)
    wait_ready.wait_ready.SetInParent()
    assert cold_start.HELLO == hello.SerializeToString()
    assert cold_start.WAIT_READY == wait_ready.SerializeToString()


def test_it_measures_the_provider_in_mock_mode() -> None:
    provider = shutil.which("anolis-provider-adafruit", path=str(Path(sys.executable).parent))
    assert provider
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), provider, str(REPO / "config" / "conformance.yaml"), "--runs", "2"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "hello ms: median" in proc.stdout and "ready ms: median" in proc.stdout


def response(code: int, *, ready: str | None = None, start_error: str = "") -> bytes:
    r = envelope_pb2.Response(request_id=2)
    r.status.code = code
    if code != status_pb2.Status.CODE_OK:
        r.status.message = "it went wrong"
    if ready is not None:
        r.wait_ready.diagnostics["ready"] = ready
        r.wait_ready.diagnostics["init_time_ms"] = "12"
        if start_error:
            r.wait_ready.diagnostics["start_error"] = start_error
    return bytes(r.SerializeToString())


def test_a_reply_is_checked_for_its_status_and_readiness() -> None:
    cold_start = load()
    ok = status_pb2.Status.CODE_OK
    cold_start.check_reply("Hello", response(ok))
    cold_start.check_reply("WaitReady", response(ok, ready="true"))
    with pytest.raises(cold_start.ColdStartError, match="Hello returned status code 12: it went wrong"):
        cold_start.check_reply("Hello", response(status_pb2.Status.CODE_FAILED_PRECONDITION))
    with pytest.raises(cold_start.ColdStartError, match="not ready: OSError: cannot open"):
        cold_start.check_reply("WaitReady", response(ok, ready="false", start_error="OSError: cannot open"))
    with pytest.raises(cold_start.ColdStartError, match="not ready"):
        cold_start.check_reply("WaitReady", response(ok))  # no ready flag at all
    with pytest.raises(cold_start.ColdStartError, match="status code 0"):
        cold_start.check_reply("Hello", envelope_pb2.Response(request_id=1).SerializeToString())


# A provider that answers Hello and WaitReady. argv[1] names the reply to fail
# with FAILED_PRECONDITION, or is "not_ready" for an OK WaitReady that reports
# ready=false. It needs the protocol bindings, so it runs under this interpreter.
FAKE = """
import struct, sys
from anolis.deviceprovider.v1 import envelope_pb2, status_pb2
failing = sys.argv[1]
for name in ("hello", "wait_ready"):
    (length,) = struct.unpack("<I", sys.stdin.buffer.read(4))
    request = envelope_pb2.Request.FromString(sys.stdin.buffer.read(length))
    reply = envelope_pb2.Response(request_id=request.request_id)
    if name == failing:
        reply.status.code = status_pb2.Status.CODE_FAILED_PRECONDITION
        reply.status.message = "not today"
    else:
        reply.status.code = status_pb2.Status.CODE_OK
    getattr(reply, name).SetInParent()
    if name == "wait_ready":
        not_ready = failing == "not_ready"
        reply.wait_ready.diagnostics["ready"] = "false" if not_ready else "true"
        if not_ready:
            reply.wait_ready.diagnostics["start_error"] = "OSError: no bus today"
    body = reply.SerializeToString()
    sys.stdout.buffer.write(struct.pack("<I", len(body)) + body)
    sys.stdout.buffer.flush()
"""


def run_against_fake(tmp_path: Path, failing: str) -> subprocess.CompletedProcess[str]:
    fake = tmp_path / "provider.py"
    fake.write_text(FAKE)
    binary = tmp_path / "provider"
    # cold_start runs `<binary> --config <config>`; the wrapper drops both.
    binary.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{fake}" {failing}\n')
    binary.chmod(0o755)
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(binary), "unused.yaml", "--runs", "1"],
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize(("failing", "name"), [("hello", "Hello"), ("wait_ready", "WaitReady")])
def test_a_reply_that_is_not_ok_fails_the_run(tmp_path: Path, failing: str, name: str) -> None:
    proc = run_against_fake(tmp_path, failing)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert f"{name} returned status code 12: not today" in proc.stderr
    assert "hello ms" not in proc.stdout


def test_an_ok_waitready_that_is_not_ready_fails_the_run(tmp_path: Path) -> None:
    proc = run_against_fake(tmp_path, "not_ready")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "WaitReady: the provider is not ready: OSError: no bus today" in proc.stderr
    assert "ready ms" not in proc.stdout


def test_it_fails_when_the_provider_is_not_ready(tmp_path: Path) -> None:
    # No /dev/i2c-99: the provider's startup host check leaves it up but not
    # ready, with an OK WaitReady reply.
    provider = shutil.which("anolis-provider-adafruit", path=str(Path(sys.executable).parent))
    assert provider
    config = tmp_path / "config.yaml"
    config.write_text("i2c_bus: 99\ndevices:\n  - id: env0\n    type: bme280\n")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), provider, str(config), "--runs", "1"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "not ready" in proc.stderr
    assert "ready ms" not in proc.stdout


def test_a_not_ready_reply_names_the_unmet_host_requirement() -> None:
    # With an unmet host requirement the SDK sets host_check and host_unmet and
    # no start_error; the script's own message must say why.
    cold_start = load()
    r = envelope_pb2.Response(request_id=2)
    r.status.code = status_pb2.Status.CODE_OK
    d = r.wait_ready.diagnostics
    d["ready"], d["init_time_ms"], d["host_check"] = "false", "3", "unmet"
    d["host_unmet"] = "i2c_bus: /dev/i2c-99 does not exist"
    with pytest.raises(cold_start.ColdStartError, match="host requirements unmet: i2c_bus: /dev/i2c-99 does not exist"):
        cold_start.check_reply("WaitReady", bytes(r.SerializeToString()))
