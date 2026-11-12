"""Synchronous client for the SeqChem HTTP API.

No dependencies — everything goes through :mod:`urllib`. The service is free and
needs no API key, so the client is just a thin, typed wrapper over the JSON
endpoints documented at https://seqandchem.com/api.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_BASE_URL = "https://seqandchem.com"
API_PREFIX = "/api/v1"

__all__ = ["Client", "SeqChemError", "DEFAULT_BASE_URL"]


class SeqChemError(RuntimeError):
    """Raised when the API returns ``ok: false`` or the request fails.

    Attributes:
        status: HTTP status code, or ``None`` for a network failure.
        detail: extra text from the service, when it provides any.
    """

    def __init__(self, message: str, status: Optional[int] = None, detail: str = "") -> None:
        super().__init__(message if not detail else f"{message} ({detail})")
        self.message = message
        self.status = status
        self.detail = detail


class Client:
    """Client for https://seqandchem.com.

    Args:
        base_url: override for self-hosted instances.
        timeout: seconds to wait for a response. 3D generation and batch jobs can
            take a while, so the default is generous.
        user_agent: sent with every request; useful if you run your own instance
            and want to identify traffic in the logs.

    Example:
        >>> from seqchem import Client
        >>> c = Client()
        >>> c.convert("CC(=O)Oc1ccccc1C(=O)O", to="inchi")["result"]
        'InChI=1S/C9H8O4/c1-6(10)13-8-5-3-2-4-7(8)9(11)12/h2-5H,1H3,(H,11,12)'
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 180.0,
        user_agent: str = "seqchem-python/0.1.0",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent

    # ---------------------------------------------------------------- transport

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = self.base_url + API_PREFIX + path
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", self.user_agent)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = exc.code
            try:
                data = json.loads(raw)
            except ValueError:
                data = {"error": raw[:200].decode("utf-8", "replace")}
            raise SeqChemError(
                data.get("error") or f"HTTP {status}",
                status,
                data.get("detail", ""),
            ) from None
        except urllib.error.URLError as exc:
            raise SeqChemError(f"network error: {exc.reason}") from None

        try:
            data = json.loads(raw)
        except ValueError:
            raise SeqChemError("service returned a non-JSON response", status) from None
        if not data.get("ok", True):
            raise SeqChemError(data.get("error", "request failed"), status, data.get("detail", ""))
        return data

    # ---------------------------------------------------------------- meta

    def formats(self) -> List[Dict[str, Any]]:
        """Every format OpenBabel can read or write, with ``read``/``write`` flags."""
        return self._request("GET", "/formats")["items"]

    def example(self, fmt: str = "smi") -> str:
        """Aspirin rendered in ``fmt`` — handy for testing a parser."""
        return self._request("GET", "/example", params={"format": fmt})["data"]

    # ---------------------------------------------------------------- chemistry

    def convert(
        self,
        data: str,
        to: str = "mol",
        frm: str = "smi",
        opts: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        """Convert molecule data between formats.

        Returns the raw response: text output is in ``result``, binary output
        (PNG, PDF, STL) is a base64 ``data_url`` with ``binary`` set.
        """
        return self._request(
            "POST", "/convert",
            {"data": data, "to": to, "from": frm, "opts": list(opts or [])},
        )

    def properties(self, data: str, frm: str = "smi") -> List[Dict[str, Any]]:
        """Descriptor rows: ``{"smiles": ..., "props": {...}}``, one per molecule."""
        return self._request("POST", "/properties", {"data": data, "from": frm})["rows"]

    def depict(self, data: str, frm: str = "smi") -> str:
        """2D structure as inline SVG markup."""
        return self._request("POST", "/depict", {"data": data, "from": frm})["svg"]

    def gen3d(self, data: str, frm: str = "smi") -> str:
        """3D conformer as an SDF block. Serialised server-side, so it can queue."""
        return self._request("POST", "/gen3d", {"data": data, "from": frm})["result"]

    def substructure(self, data: str, smarts: str, frm: str = "smi") -> List[str]:
        """Molecules from ``data`` that contain the SMARTS pattern."""
        return self._request(
            "POST", "/substructure", {"data": data, "smarts": smarts, "from": frm}
        )["matches"]

    def fingerprint(self, data: str, fp: str = "FP2", frm: str = "smi") -> Dict[str, Any]:
        """Raw fingerprint bits for the given molecule(s)."""
        return self._request("POST", "/fingerprint", {"data": data, "fp": fp, "from": frm})

    def similarity(self, a: str, b: str, fp: str = "FP2", frm: str = "smi") -> float:
        """Tanimoto coefficient between two molecules, 0.0 to 1.0."""
        return self._request(
            "POST", "/similarity", {"a": a, "b": b, "fp": fp, "from": frm}
        )["tanimoto"]

    def iupac(self, name: str) -> Dict[str, Any]:
        """Resolve an IUPAC name. Check ``resolved`` before using ``smiles``."""
        return self._request("POST", "/iupac", {"name": name})

    def batch(
        self,
        data: str,
        to: str = "smi",
        frm: str = "sdf",
        opts: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        """Bulk conversion. Limits: 64 MB input, 5000 records (500 for image output)."""
        return self._request(
            "POST", "/batch",
            {"data": data, "to": to, "from": frm, "opts": list(opts or [])},
        )

    def formula(self, formula: str) -> Dict[str, Any]:
        """Molecular weight and composition from a formula string."""
        return self._request("POST", "/formula", {"mode": "formula", "formula": formula})

    def formula_from_structure(self, data: str, frm: str = "smi") -> List[Dict[str, Any]]:
        """Formula and weight computed from structure data."""
        return self._request(
            "POST", "/formula", {"mode": "structure", "data": data, "from": frm}
        )["rows"]

    # ---------------------------------------------------------------- sequences

    def bio(self, op: str, data: str, frame: int = 0) -> Dict[str, Any]:
        """FASTA/FASTQ operation.

        ``op`` is one of ``fasta2fastq``, ``fastq2fasta``, ``revcomp``,
        ``translate`` or ``stats``.
        """
        return self._request("POST", "/bio", {"op": op, "data": data, "frame": frame})
