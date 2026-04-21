"""
Sprint 4 | client/sfbs_client.py
Multithreaded HTTP client for the SFBS REST API.
SE2 requirement: client-server architecture + multithreading.
Commit: Muhammad – Sprint 4
"""

import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import requests


# ─────────────────────────────────────────────────────────────────────────── #
#  Data classes                                                               #
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass
class ApiRequest:
    method:   str          # GET / POST / PUT / DELETE
    endpoint: str          # e.g.  "/facilities"
    payload:  dict         = field(default_factory=dict)
    params:   dict         = field(default_factory=dict)
    callback: Optional[Callable] = None


@dataclass
class ApiResponse:
    status_code: int
    data:        Any
    endpoint:    str
    error:       Optional[str] = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


# ─────────────────────────────────────────────────────────────────────────── #
#  Thread worker                                                              #
# ─────────────────────────────────────────────────────────────────────────── #

class WorkerThread(threading.Thread):
    """
    A single worker thread that pulls ApiRequest items from a shared queue
    and dispatches them via HTTP.
    SE2: demonstrates multithreading in the client.
    """

    def __init__(
        self,
        request_queue: queue.Queue,
        result_queue:  queue.Queue,
        base_url:      str,
        token:         str,
        worker_id:     int,
    ) -> None:
        super().__init__(daemon=True, name=f"SFBSWorker-{worker_id}")
        self._req_q   = request_queue
        self._res_q   = result_queue
        self._base    = base_url.rstrip("/")
        self._token   = token
        self._session = requests.Session()
        self._running = True

    def run(self) -> None:
        while self._running:
            try:
                request: ApiRequest = self._req_q.get(timeout=1)
                response = self._execute(request)
                self._res_q.put(response)
                if request.callback:
                    try:
                        request.callback(response)
                    except Exception as exc:
                        print(f"[{self.name}] Callback error: {exc}")
                self._req_q.task_done()
            except queue.Empty:
                continue

    def stop(self) -> None:
        self._running = False

    def _execute(self, request: ApiRequest) -> ApiResponse:
        url     = f"{self._base}{request.endpoint}"
        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            method = request.method.upper()
            if method == "GET":
                resp = self._session.get(url, params=request.params,
                                         headers=headers, timeout=10)
            elif method == "POST":
                resp = self._session.post(url, json=request.payload,
                                          headers=headers, timeout=10)
            elif method == "PUT":
                resp = self._session.put(url, json=request.payload,
                                         headers=headers, timeout=10)
            elif method == "DELETE":
                resp = self._session.delete(url, headers=headers, timeout=10)
            else:
                return ApiResponse(-1, None, request.endpoint,
                                   f"Unknown method: {method}")

            data = None
            if resp.content:
                try:
                    data = resp.json()
                except Exception:
                    data = resp.text

            return ApiResponse(resp.status_code, data, request.endpoint)

        except requests.exceptions.ConnectionError:
            return ApiResponse(0, None, request.endpoint,
                               "Connection refused — is the server running?")
        except requests.exceptions.Timeout:
            return ApiResponse(0, None, request.endpoint, "Request timed out")
        except Exception as exc:
            return ApiResponse(0, None, request.endpoint, str(exc))


# ─────────────────────────────────────────────────────────────────────────── #
#  SFBSClient                                                                 #
# ─────────────────────────────────────────────────────────────────────────── #

class SFBSClient:
    """
    High-level multithreaded client for the SFBS REST API.

    Maintains a pool of worker threads that process requests concurrently.
    Thread-safe:  all shared state uses locks or thread-safe queues.

    Usage
    -----
        client = SFBSClient("http://localhost:8000")
        client.start()
        client.login("admin", "password")
        facilities = client.get_facilities()
        client.stop()
    """

    DEFAULT_WORKERS = 4

    def __init__(
        self,
        base_url:    str = "http://localhost:8000",
        num_workers: int = DEFAULT_WORKERS,
    ) -> None:
        self._base_url    = base_url
        self._num_workers = num_workers
        self._token:      Optional[str] = None
        self._token_lock  = threading.Lock()
        self._req_queue:  queue.Queue   = queue.Queue()
        self._res_queue:  queue.Queue   = queue.Queue()
        self._workers:    List[WorkerThread] = []
        self._results:    List[ApiResponse]  = []
        self._results_lock = threading.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────── #

    def start(self) -> None:
        """Start the worker thread pool."""
        for i in range(self._num_workers):
            w = WorkerThread(
                self._req_queue, self._res_queue,
                self._base_url, self._token or "", i + 1,
            )
            w.start()
            self._workers.append(w)
        # Background result collector
        threading.Thread(target=self._collect_results, daemon=True).start()

    def stop(self) -> None:
        """Drain queue and stop all workers."""
        self._req_queue.join()
        for w in self._workers:
            w.stop()
        for w in self._workers:
            w.join()

    # ── Auth ──────────────────────────────────────────────────────────── #

    def login(self, username: str, password: str) -> Optional[str]:
        """
        Synchronous login — blocks until the token is received.
        Sets the token on all workers.
        """
        resp = self._sync_request("POST", "/auth/login",
                                  {"username": username, "password": password})
        if resp.ok and resp.data:
            token = resp.data.get("access_token")
            if token:
                with self._token_lock:
                    self._token = token
                    for w in self._workers:
                        w._token = token
                return token
        return None

    def register(self, username: str, email: str, password: str,
                 first_name: str, last_name: str) -> Optional[dict]:
        resp = self._sync_request("POST", "/auth/register", {
            "username": username, "email": email, "password": password,
            "first_name": first_name, "last_name": last_name,
        })
        return resp.data if resp.ok else None

    # ── Facilities ────────────────────────────────────────────────────── #

    def get_facilities(self, available_only: bool = False) -> List[dict]:
        resp = self._sync_request("GET", "/facilities",
                                  params={"available_only": str(available_only).lower()})
        return resp.data if resp.ok else []

    def get_facility(self, facility_id: str) -> Optional[dict]:
        resp = self._sync_request("GET", f"/facilities/{facility_id}")
        return resp.data if resp.ok else None

    # ── Bookings ──────────────────────────────────────────────────────── #

    def get_bookings(self) -> List[dict]:
        resp = self._sync_request("GET", "/bookings")
        return resp.data if resp.ok else []

    def create_booking(self, facility_id: str, start: datetime,
                       end: datetime, notes: str = "") -> Optional[dict]:
        resp = self._sync_request("POST", "/bookings", {
            "facility_id": facility_id,
            "start_time":  start.isoformat(),
            "end_time":    end.isoformat(),
            "notes":       notes,
        })
        return resp.data if resp.ok else None

    def cancel_booking(self, booking_id: str) -> bool:
        resp = self._sync_request("POST", f"/bookings/{booking_id}/cancel")
        return resp.ok

    # ── Payments ──────────────────────────────────────────────────────── #

    def create_payment_intent(self, booking_id: str,
                              method: str = "stripe") -> Optional[dict]:
        resp = self._sync_request("POST", "/payments/stripe/create-intent",
                                  {"booking_id": booking_id,
                                   "payment_method": method})
        return resp.data if resp.ok else None

    def request_offline_payment(self, booking_id: str,
                                amount: float) -> Optional[dict]:
        resp = self._sync_request("POST", "/payments/offline/request",
                                  {"booking_id": booking_id, "amount": amount})
        return resp.data if resp.ok else None

    # ── Async bulk requests ───────────────────────────────────────────── #

    def enqueue(self, method: str, endpoint: str,
                payload: dict = None, callback: Callable = None) -> None:
        """Non-blocking: enqueue a request for worker threads to process."""
        self._req_queue.put(ApiRequest(
            method=method, endpoint=endpoint,
            payload=payload or {}, callback=callback,
        ))

    def wait_all(self) -> None:
        """Block until all enqueued requests have been processed."""
        self._req_queue.join()

    def get_results(self) -> List[ApiResponse]:
        with self._results_lock:
            return list(self._results)

    # ── Internals ─────────────────────────────────────────────────────── #

    def _sync_request(self, method: str, endpoint: str,
                      payload: dict = None, params: dict = None) -> ApiResponse:
        """Send a single request synchronously (blocks the calling thread)."""
        result_holder: List[Optional[ApiResponse]] = [None]
        event = threading.Event()

        def _cb(response: ApiResponse):
            result_holder[0] = response
            event.set()

        self._req_queue.put(ApiRequest(
            method=method, endpoint=endpoint,
            payload=payload or {}, params=params or {}, callback=_cb,
        ))
        event.wait(timeout=15)
        return result_holder[0] or ApiResponse(0, None, endpoint, "Timeout")

    def _collect_results(self) -> None:
        while True:
            try:
                result = self._res_queue.get(timeout=1)
                with self._results_lock:
                    self._results.append(result)
                self._res_queue.task_done()
            except queue.Empty:
                continue
