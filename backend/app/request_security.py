from fastapi import Request

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def local_write_rejection(request: Request) -> str | None:
    """Reject browser writes initiated by another site.

    Native launcher and test clients do not send browser origin headers, so
    headerless local requests remain supported.
    """
    if request.method not in UNSAFE_METHODS:
        return None
    if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
        return "拒绝跨站写入请求。"

    origin = request.headers.get("origin")
    if origin is None:
        return None
    host = request.headers.get("host", "")
    expected_origin = f"{request.url.scheme}://{host}".rstrip("/")
    if origin.rstrip("/") != expected_origin:
        return "拒绝跨站写入请求。"
    return None
