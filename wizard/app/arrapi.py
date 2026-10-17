"""Tiny stdlib HTTP client used to talk to every service."""
import copy
import http.cookiejar
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


CANCEL = threading.Event()  # set by the Stop button; polling loops and installer steps stop at once


class Fatal(Exception):
    """Raised inside a wait_for callback to stop polling immediately."""


class ApiError(Exception):
    def __init__(self, status, body, url=""):
        super().__init__(f"HTTP {status} {url} {str(body)[:300]}")
        self.status = status
        self.body = body


class Recorder:
    """Lets the setup code run as a preview. Every write (PUT/POST/DELETE) is captured instead of sent ("audit"), or sent only when the
    settings group it belongs to was not switched off ("apply"). Reads always go to the real app, so the preview shows what the person's
    apps hold right now next to what the setup would write."""

    def __init__(self, mode="audit", skip=()):
        self.mode, self.skip = mode, set(skip)
        self.group, self.changes, self.cache, self.seq = None, {}, {}, 0

    # reads are remembered so a later write can be compared with what the app held
    def remember(self, api, path, data):
        self.cache[(api.base, path.split("?")[0])] = copy.deepcopy(data)      # the setup code edits what it reads: keep the original

    def before_for(self, api, path, body=None):
        path = path.split("?")[0]
        if path.endswith("/Library/VirtualFolders/LibraryOptions") and isinstance(body, dict):      # Jellyfin: one library's options
            for v in self.cache.get((api.base, "/Library/VirtualFolders")) or []:
                if v.get("ItemId") == body.get("Id"):
                    return {"LibraryOptions": v.get("LibraryOptions")}
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "Users" and parts[2] in ("Configuration", "Policy"):      # Jellyfin: a user's settings
            u = self.cache.get((api.base, "/Users/" + parts[1]))
            if isinstance(u, dict):
                return u.get(parts[2])
        if path.endswith("/update"):
            return self.cache.get((api.base, path[:-len("/update")]))
        if (api.base, path) in self.cache:
            return self.cache[(api.base, path)]
        parent, _, last = path.rpartition("/")
        data = self.cache.get((api.base, parent))
        if isinstance(data, list) and last.isdigit():
            return next((x for x in data if isinstance(x, dict) and str(x.get("id")) == last), None)
        if isinstance(data, dict) and str(data.get("id")) == last:
            return data
        return None

    def skipped(self):
        return self.mode == "audit" or self.group in self.skip

    def intercept(self, api, method, path, body):
        if method == "POST" and path.split("?")[0].rstrip("/").endswith(("/test", "/testall", "/command")):
            return {} if self.skipped() else NotImplemented       # a connection test or a command is not a setting
        before = self.before_for(api, path, body)
        if method == "POST" and not isinstance(before, dict):
            before = None
        self.changes.setdefault(self.group or "other", []).append(
            {"method": method, "path": path, "before": before, "after": body, "app": api.base})
        if not self.skipped():
            return NotImplemented               # the caller really sends it
        if method == "DELETE":
            return None
        if isinstance(body, dict):
            out = dict(body)
            if method == "POST" and not out.get("id"):
                self.seq -= 1
                out["id"] = self.seq             # a stand-in id so the rest of the setup can carry on in the preview
            return out
        return body


REC = {"r": None}


class Api:
    def __init__(self, base, key=None, prefix="", headers=None, cookies=False):
        self.base = base.rstrip("/")
        self.prefix = prefix
        self.headers = dict(headers or {})
        if key:
            self.headers["X-Api-Key"] = key
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        ) if cookies else urllib.request.build_opener()

    def call(self, method, path, body=None, params=None, form=None, timeout=60, raw=False):
        rec = REC["r"]
        if rec and method != "GET" and not getattr(self, "bypass", False):
            sent = body if body is not None else (form if form is not None else None)
            r = rec.intercept(self, method, path, sent)
            if r is not NotImplemented:
                return (200, "") if raw else r
        url = f"{self.base}{self.prefix}{path}"
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        data = None
        headers = dict(self.headers)
        if form is not None:
            data = urllib.parse.urlencode(form, doseq=True).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with self.opener.open(req, timeout=timeout) as r:
                text = r.read().decode("utf-8", "replace")
                if raw:
                    if rec and method == "GET":
                        try:
                            rec.remember(self, path, json.loads(text))
                        except ValueError:
                            pass
                    return r.status, text
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")
            raise ApiError(e.code, text, url) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            raise ApiError(0, str(e), url) from None
        if not text.strip():
            return None
        try:
            data = json.loads(text)
        except ValueError:
            return text
        if rec and method == "GET":
            rec.remember(self, path, data)
        return data

    def get(self, path, **kw): return self.call("GET", path, **kw)
    def post(self, path, body=None, **kw): return self.call("POST", path, body=body, **kw)
    def put(self, path, body=None, **kw): return self.call("PUT", path, body=body, **kw)
    def delete(self, path, **kw): return self.call("DELETE", path, **kw)


def wait_for(fn, timeout=240, interval=3, what="service"):
    """Poll fn() until it returns truthy without raising."""
    end = time.time() + timeout
    last = None
    while time.time() < end:
        if CANCEL.is_set():
            raise Fatal("Stopped")
        try:
            r = fn()
            if r:
                return r
        except Fatal:
            raise
        except Exception as e:  # noqa: BLE001 - polling, any failure means "not yet"
            last = e
        time.sleep(interval)
    raise TimeoutError(f"{what} did not become ready in {timeout}s ({last})")
