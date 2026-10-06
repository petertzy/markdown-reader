"""
tests/test_sidecar_watchdog.py
==============================
Tests for the parent watchdog in backend/main.py.

The packaged app starts the backend as a Tauri sidecar and passes its own pid
in ``MARKDOWN_READER_PARENT_PID`` (frontend/src-tauri/src/lib.rs). The sidecar
then runs a thread that exits it once that pid is gone, so closing the desktop
app does not leave a backend behind holding the port it advertised.

``os.kill(pid, 0)`` is the POSIX way to ask whether a pid is still running
without touching the process, but it is not a probe on Windows. There, every
signal outside the two console events goes straight to ``TerminateProcess``
(CPython ``Modules/posixmodule.c``, ``os_kill_impl``; documented at
https://docs.python.org/3/library/os.html#os.kill). Signal 0 therefore kills
the Tauri host rather than inspecting it, and release.yml builds and ships the
packaged Windows app -- so the watchdog closed the app it was protecting.
"""

from __future__ import annotations

import contextlib
import ctypes
import threading
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend import main

# STILL_ACTIVE (STILL_ACTIVE) is what GetExitCodeProcess reports for a process
# that has not exited yet; STAINED_EXIT is a real exit code.
STILL_ACTIVE = 259
HOST_PID = 4242

# PROCESS_QUERY_LIMITED_INFORMATION: the narrowest right that still answers
# "has this process exited", and the one an unprivileged caller actually holds.
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class _Stop(Exception):
    """Ends the watchdog loop once the scripted clock runs out of iterations."""


class _ScriptedTime:
    """`time` stand-in that lets the watchdog loop run a fixed iteration count.

    ``sleep`` raises after the scripted iterations so the ``while True`` loop
    terminates. The thread records that through ``threading.excepthook``, which
    is also how the tests below assert that the loop really did keep going.
    """

    def __init__(self, iterations: int = 1) -> None:
        self._left = iterations
        self.slept: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        if self._left <= 0:
            raise _Stop
        self._left -= 1


class _FakeOS:
    """Stands in for the `os` module: records instead of acting."""

    def __init__(self, name: str, kill_effect: BaseException | None = None) -> None:
        self.name = name
        self.environ = {"MARKDOWN_READER_PARENT_PID": str(HOST_PID)}
        self.signalled: list[tuple[int, int]] = []
        self.exit_codes: list[int] = []
        self._kill_effect = kill_effect

    def kill(self, pid: int, sig: int) -> None:
        self.signalled.append((pid, sig))
        if self._kill_effect is not None:
            raise self._kill_effect

    def _exit(self, code: int) -> None:
        self.exit_codes.append(code)


class _FakeKernel32:
    """The two kernel32 entry points the Windows liveness probe needs.

    ``OpenProcess`` yields no handle when ``exit_code`` is None, which is what
    Windows does once the pid names nothing at all. The probe assigns
    ``argtypes``/``restype`` on these, so they have to be plain functions
    rather than bound methods.
    """

    def __init__(self, exit_code: int | None, *, last_error: int = 87) -> None:
        self._exit_code = exit_code
        self._last_error = last_error
        self.opened: list[tuple[int, int]] = []
        self.closed: list[int] = []

        def open_process(access, inherit, pid):  # noqa: ANN001, ANN202
            self.opened.append((access, pid))
            return 0x1234 if self._exit_code is not None else 0

        def get_exit_code(handle, code_ptr):  # noqa: ANN001, ANN202
            assert self._exit_code is not None, "queried a handle that was never opened"
            code_ptr._obj.value = self._exit_code
            return 1

        def close_handle(handle):  # noqa: ANN001, ANN202
            self.closed.append(handle)
            return 1

        def get_last_error():  # noqa: ANN202
            return self._last_error

        self.OpenProcess = open_process
        self.GetExitCodeProcess = get_exit_code
        self.CloseHandle = close_handle
        self.GetLastError = get_last_error


@contextlib.contextmanager
def _one_iteration():
    """Run the watchdog thread for one probe and swallow its loop-stop."""
    seen: list[BaseException] = []
    original = threading.excepthook
    threading.excepthook = lambda args: seen.append(args.exc_value)
    try:
        yield seen
    finally:
        threading.excepthook = original


def _run_watchdog(
    test: unittest.TestCase,
    os_stub: _FakeOS,
    *,
    kernel32: _FakeKernel32 | None = None,
    iterations: int = 1,
) -> None:
    """Start the watchdog, let it probe `iterations` times, then stop it."""
    clock = _ScriptedTime(iterations)
    started: list[threading.Thread] = []
    real_thread = threading.Thread

    def _recording_thread(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        thread = real_thread(*args, **kwargs)
        started.append(thread)
        return thread

    with (
        _one_iteration() as seen,
        mock.patch.object(main, "os", os_stub),
        mock.patch.object(main, "time", clock),
        mock.patch.object(threading, "Thread", _recording_thread),
        mock.patch.object(ctypes, "WinDLL", lambda *_a, **_k: kernel32, create=True),
    ):
        main._start_parent_watchdog()
        test.assertEqual(len(started), 1, "the watchdog thread was never started")
        started[0].join(timeout=5)
        test.assertFalse(started[0].is_alive(), "the watchdog loop never stopped")

    test.assertEqual(len(seen), 1, "the watchdog loop did not run to its stop")
    test.assertIsInstance(seen[0], _Stop)
    # The scripted clock answers one call per iteration plus the one that ends
    # the loop, so this also pins the 2 s poll interval.
    test.assertEqual(clock.slept, [2.0] * (iterations + 1))


class TestSidecarRequestAuthentication(unittest.TestCase):
    def test_packaged_sidecar_rejects_missing_or_incorrect_tokens(self):
        with mock.patch.object(main, "_BACKEND_AUTH_TOKEN", "test-session-token"):
            with TestClient(main.app) as client:
                self.assertEqual(client.get("/api/health").status_code, 401)
                self.assertEqual(
                    client.get(
                        "/api/health",
                        headers={"X-Markdown-Reader-Token": "wrong-token"},
                    ).status_code,
                    401,
                )
                self.assertEqual(
                    client.get(
                        "/api/health",
                        headers={"X-Markdown-Reader-Token": "test-session-token"},
                    ).status_code,
                    200,
                )


class TestWatchdogNeverSignalsTheParent(unittest.TestCase):
    """Regression: os.kill(pid, 0) terminates the target on Windows."""

    def test_windows_probe_does_not_signal_the_host(self):
        os_stub = _FakeOS("nt")
        kernel = _FakeKernel32(exit_code=STILL_ACTIVE)

        _run_watchdog(self, os_stub, kernel32=kernel)

        self.assertEqual(
            os_stub.signalled,
            [],
            "the Windows liveness probe must read the exit code, not os.kill: "
            "signal 0 reaches TerminateProcess there and closes the app",
        )
        self.assertEqual(os_stub.exit_codes, [], "the host is still running")
        self.assertEqual(
            kernel.opened,
            [(PROCESS_QUERY_LIMITED_INFORMATION, HOST_PID)],
            "the probe must ask for the exit code, not PROCESS_ALL_ACCESS",
        )
        self.assertEqual(kernel.closed, [0x1234], "the process handle must be released")

    def test_windows_probe_declares_its_handle_prototypes(self):
        # ctypes hands back a c_int unless told otherwise, and a process handle
        # is pointer-sized: a truncated one is then closed and queried as if it
        # were the real handle, which on 64-bit Windows is usually not.
        os_stub = _FakeOS("nt")
        kernel = _FakeKernel32(exit_code=STILL_ACTIVE)

        _run_watchdog(self, os_stub, kernel32=kernel)

        self.assertIs(kernel.OpenProcess.restype, ctypes.c_void_p)
        self.assertIs(kernel.OpenProcess.argtypes[0], ctypes.c_uint32)
        self.assertIs(kernel.GetExitCodeProcess.restype, ctypes.c_int)
        self.assertEqual(kernel.CloseHandle.argtypes, (ctypes.c_void_p,))
        self.assertEqual(kernel.CloseHandle.restype, ctypes.c_int)

    def test_windows_probe_exits_the_sidecar_when_the_host_is_gone(self):
        # OpenProcess yields nothing, which is how Windows reports a pid that
        # names no process (ERROR_INVALID_PARAMETER) -- there is no handle left
        # to query.
        os_stub = _FakeOS("nt")

        _run_watchdog(self, os_stub, kernel32=_FakeKernel32(exit_code=None))

        self.assertEqual(os_stub.signalled, [])
        self.assertEqual(os_stub.exit_codes, [0])

    def test_windows_access_denied_keeps_the_sidecar_running(self):
        # OpenProcess can fail with ERROR_ACCESS_DENIED for a live process. The
        # watchdog must not orphan itself merely because it cannot inspect it.
        os_stub = _FakeOS("nt")

        _run_watchdog(
            self, os_stub, kernel32=_FakeKernel32(exit_code=None, last_error=5)
        )

        self.assertEqual(os_stub.signalled, [])
        self.assertEqual(os_stub.exit_codes, [])

    def test_windows_probe_exits_the_sidecar_once_the_host_has_exited(self):
        # A handle can outlive the process it names, so a successful open is not
        # proof of life: the exit code is what decides.
        os_stub = _FakeOS("nt")

        _run_watchdog(self, os_stub, kernel32=_FakeKernel32(exit_code=0))

        self.assertEqual(os_stub.signalled, [])
        self.assertEqual(os_stub.exit_codes, [0])


class TestWatchdogOnPosix(unittest.TestCase):
    """Signal 0 is the POSIX idiom, so the POSIX path must keep using it."""

    def test_running_host_is_left_alone(self):
        os_stub = _FakeOS("posix")

        _run_watchdog(self, os_stub)

        self.assertEqual(os_stub.signalled, [(HOST_PID, 0)])
        self.assertEqual(os_stub.exit_codes, [])

    def test_missing_host_exits_the_sidecar(self):
        os_stub = _FakeOS("posix", kill_effect=ProcessLookupError())

        _run_watchdog(self, os_stub)

        self.assertEqual(os_stub.signalled, [(HOST_PID, 0)])
        self.assertEqual(os_stub.exit_codes, [0])

    def test_host_owned_by_another_user_counts_as_running(self):
        # EPERM means the pid exists but is not ours to signal.
        os_stub = _FakeOS("posix", kill_effect=PermissionError())

        _run_watchdog(self, os_stub)

        self.assertEqual(os_stub.signalled, [(HOST_PID, 0)])
        self.assertEqual(os_stub.exit_codes, [])

    def test_no_watchdog_without_the_environment_variable(self):
        os_stub = _FakeOS("nt")
        os_stub.environ = {}

        with mock.patch.object(main, "os", os_stub):
            main._start_parent_watchdog()

        self.assertEqual(os_stub.signalled, [])
        self.assertEqual(os_stub.exit_codes, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
