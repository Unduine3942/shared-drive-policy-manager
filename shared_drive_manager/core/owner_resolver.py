from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

try:
    import win32security as _w32s
    import pywintypes as _pywintypes
    _WIN32 = True
except ImportError:
    _w32s = None        # type: ignore[assignment]
    _pywintypes = None  # type: ignore[assignment]
    _WIN32 = False

# (sid_string | None, owner_name | None)
OwnerInfo = tuple[str | None, str | None]


def is_available() -> bool:
    return _WIN32


def resolve_owner(path: str) -> OwnerInfo:
    """Return (sid_string, owner_name) for *path*.

    Falls back gracefully:
    - If the SID cannot be read, returns (None, None).
    - If the SID is read but the account name lookup fails (orphaned SID,
      unreachable DC, etc.) returns (sid_str, None) so the SID is still
      stored and searchable.
    """
    if not _WIN32:
        return None, None

    # Step 1: read the security descriptor and extract the owner SID.
    try:
        sd = _w32s.GetFileSecurity(path, _w32s.OWNER_SECURITY_INFORMATION)
        sid = sd.GetSecurityDescriptorOwner()
        sid_str = str(sid)
    except Exception as exc:
        # Includes pywintypes.error (access denied, trust failure, etc.) — expected on network shares.
        _log.debug("owner SID unavailable for %r: %s", path, exc)
        return None, None

    # Step 2: resolve SID → human-readable name (best-effort).
    try:
        name, domain, _ = _w32s.LookupAccountSid(None, sid)
        owner_name: str | None = f"{domain}\\{name}" if domain else name
    except Exception as exc:
        # Trust relationship failures, orphaned SIDs, and unreachable DCs are all normal
        # on shared drives with domain accounts — SID is still stored and searchable.
        _log.debug("SID name lookup failed for %r (SID=%s): %s", path, sid_str, exc)
        owner_name = None

    return sid_str, owner_name
