"""Read creator/modifier metadata from Office Open XML (OOXML) files.

Supported formats: .docx/.docm/.dotx/.dotm, .xlsx/.xlsm/.xltx/.xltm,
                   .pptx/.pptm/.potx/.potm/.ppsx/.ppsm

These are ZIP archives containing docProps/core.xml with Dublin Core metadata.
Reading uses only stdlib zipfile + xml.etree.ElementTree — no network or domain
access required, so it works even when NTFS SID resolution fails.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass

_log = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".docx", ".docm", ".dotx", ".dotm",
    ".xlsx", ".xlsm", ".xltx", ".xltm",
    ".pptx", ".pptm", ".potx", ".potm", ".ppsx", ".ppsm",
})

_CORE_PATH = "docProps/core.xml"

_NS = {
    "cp":      "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc":      "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
}


@dataclass
class DocProperties:
    creator:  str | None = None   # dc:creator — original author
    modifier: str | None = None   # cp:lastModifiedBy — last person to save


def read_doc_properties(path: str, extension: str) -> DocProperties:
    """Extract creator and last-modifier from an OOXML file.

    Returns an empty DocProperties if the file is unsupported, unreadable,
    password-protected, or does not contain core properties.
    """
    if extension not in SUPPORTED_EXTENSIONS:
        return DocProperties()

    try:
        with zipfile.ZipFile(path, "r") as zf:
            if _CORE_PATH not in zf.namelist():
                return DocProperties()
            with zf.open(_CORE_PATH) as f:
                root = ET.parse(f).getroot()
    except Exception as exc:
        _log.debug("doc properties unreadable for %r: %s", path, exc)
        return DocProperties()

    def _text(tag: str, ns_key: str) -> str | None:
        el = root.find(f"{ns_key}:{tag}", _NS)
        return el.text.strip() if el is not None and el.text and el.text.strip() else None

    return DocProperties(
        creator=_text("creator", "dc"),
        modifier=_text("lastModifiedBy", "cp"),
    )
