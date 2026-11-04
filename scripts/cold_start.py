#!/usr/bin/env python3
"""Measure the provider's cold start: process launch to the Hello reply, and to
the WaitReady reply (start-up done, boards opened).

Needs only python3 and the provider binary, so it runs on a bare target:

    python3 cold_start.py /opt/anolis/bin/anolis-provider-adafruit <config> [--runs 5]

The runtime gives a provider hello_timeout_ms (default 5000) to answer Hello,
and ready_timeout_ms to answer WaitReady. Exits 1 when the slowest Hello is
over --hello-budget-ms, or when a Hello or WaitReady reply's status is not OK.
"""

from __future__ import annotations

import argparse
import statistics
import struct
import subprocess
import sys
import time
from typing import IO

# Request{request_id: 1, hello: {protocol_version: "v1"}} and
# Request{request_id: 2, wait_ready: {}}, serialized. tests/test_cold_start.py
# checks these against the anolis-protocol bindings.
HELLO = bytes.fromhex("080152040a027631")
WAIT_READY = bytes.fromhex("0802820100")
# Response.status is field 2; Status.code is field 1 and Status.message field 2.
CODE_OK = 1


class NotOk(Exception):
    """A reply whose status is not OK."""


def frame(body: bytes) -> bytes:
    return struct.pack("<I", len(body)) + body


def read_frame(stream: IO[bytes]) -> bytes:
    header = stream.read(4)
    if len(header) != 4:
        raise RuntimeError("the provider closed stdout before replying")
    (length,) = struct.unpack("<I", header)
    return stream.read(length)


def _varint(data: bytes, i: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        byte = data[i]
        i += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return value, i


def _fields(data: bytes) -> dict[int, int | bytes]:
    """The top-level fields of a protobuf message, last one winning. Enough of
    the wire format for a Response and its Status: varints and length-delimited."""
    fields: dict[int, int | bytes] = {}
    i = 0
    while i < len(data):
        key, i = _varint(data, i)
        number, wire = key >> 3, key & 7
        if wire == 0:
            fields[number], i = _varint(data, i)
        elif wire == 2:
            length, i = _varint(data, i)
            fields[number] = data[i : i + length]
            i += length
        elif wire in (1, 5):
            i += 8 if wire == 1 else 4
        else:
            raise ValueError(f"unexpected wire type {wire} in a reply")
    return fields


def check_ok(name: str, reply: bytes) -> None:
    """Raise NotOk unless the reply's status code is OK."""
    status = _fields(reply).get(2, b"")
    fields = _fields(status) if isinstance(status, bytes) else {}
    code = fields.get(1, 0)
    if code != CODE_OK:
        message = fields.get(2, b"")
        text = message.decode("utf-8", "replace") if isinstance(message, bytes) else ""
        raise NotOk(f"{name} returned status code {code}, not OK (1): {text or 'no message'}")


def one_run(binary: str, config: str) -> tuple[float, float]:
    began = time.monotonic()
    proc = subprocess.Popen([binary, "--config", config], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    assert proc.stdin and proc.stdout
    try:
        proc.stdin.write(frame(HELLO))
        proc.stdin.flush()
        hello = read_frame(proc.stdout)
        hello_ms = (time.monotonic() - began) * 1000
        check_ok("Hello", hello)
        proc.stdin.write(frame(WAIT_READY))
        proc.stdin.flush()
        ready = read_frame(proc.stdout)
        ready_ms = (time.monotonic() - began) * 1000
        check_ok("WaitReady", ready)
    finally:
        proc.stdin.close()
        proc.wait(timeout=30)
    return hello_ms, ready_ms


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("binary")
    parser.add_argument("config")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--hello-budget-ms", type=float, default=5000.0)
    args = parser.parse_args()

    try:
        runs = [one_run(args.binary, args.config) for _ in range(args.runs)]
    except NotOk as err:
        print(f"cold_start: {err}", file=sys.stderr)
        return 1
    hello = [h for h, _ in runs]
    ready = [r for _, r in runs]
    print(f"runs: {args.runs}")
    print(f"hello ms: median {statistics.median(hello):.0f}, max {max(hello):.0f} (budget {args.hello_budget_ms:.0f})")
    print(f"ready ms: median {statistics.median(ready):.0f}, max {max(ready):.0f}")
    return 1 if max(hello) > args.hello_budget_ms else 0


if __name__ == "__main__":
    sys.exit(main())
