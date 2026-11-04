"""scripts/cold_start.py: its hand-encoded frames, and a run against the provider."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from anolis.deviceprovider.v1 import envelope_pb2

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


# A provider that answers Hello and WaitReady, failing the one named in argv[1]
# with FAILED_PRECONDITION. It needs the protocol bindings, so it runs under
# this interpreter.
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
    body = reply.SerializeToString()
    sys.stdout.buffer.write(struct.pack("<I", len(body)) + body)
    sys.stdout.buffer.flush()
"""


@pytest.mark.parametrize(("failing", "name"), [("hello", "Hello"), ("wait_ready", "WaitReady")])
def test_a_reply_that_is_not_ok_fails_the_run(tmp_path: Path, failing: str, name: str) -> None:
    fake = tmp_path / "provider.py"
    fake.write_text(FAKE)
    binary = tmp_path / "provider"
    # cold_start runs `<binary> --config <config>`; the wrapper drops both.
    binary.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{fake}" {failing}\n')
    binary.chmod(0o755)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(binary), "unused.yaml", "--runs", "1"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert f"{name} returned status code 12, not OK (1): not today" in proc.stderr
    assert "hello ms" not in proc.stdout
