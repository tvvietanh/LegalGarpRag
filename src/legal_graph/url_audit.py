"""Bounded optional URL collection; final offline release consumes frozen observations."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import ssl
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from .rule_graph import BuildError, canonical, digest, digest_bytes, parse_json


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value)).casefold().replace("đ", "d")
    return "".join(c for c in text if c.isalnum() and not unicodedata.combining(c))


def source_url(node):
    row = node["properties"]["source_properties"]
    for key in ("source_url", "view_url", "official_url", "canonical_url", "download_url"):
        if isinstance(row.get(key), str) and row[key].strip():
            return key, row[key]
    return "source_url", ""


def classify(node, observation):
    """Conservative lineage+fresh-header identity; HTTP200/hash alone never verifies."""
    row = node["properties"]["source_properties"]
    if observation.get("access_error") or observation.get("http_status") != 200 or observation.get("truncated"):
        return "BLOCKED", ["ACCESS_LIMITATION_OR_NON_200"]
    final = urllib.parse.urlsplit(observation.get("final_url", ""))
    if not final.scheme or final.path in ("", "/") or "search" in final.path.casefold():
        return "UNRESOLVED", ["HOMEPAGE_OR_SEARCH_REDIRECT_NOT_DOCUMENT_IDENTITY"]
    evidence = observation.get("identity_evidence", {})
    if not observation.get("response_is_pdf"):
        return "UNRESOLVED", ["NO_REVIEWED_HTML_IDENTITY_PROOF"]
    if not evidence.get("local_source_sha256_match"):
        return "UNRESOLVED", ["FETCHED_BYTES_NOT_MATCHED_TO_LOCAL_SOURCE"]
    if row.get("metadata_verified") is not True:
        return "UNRESOLVED", ["SOURCE_IDENTITY_METADATA_NOT_INDEPENDENTLY_VERIFIED"]
    if not all(evidence.get(k) is True for k in ("number_match", "title_match", "authority_match")):
        return "UNRESOLVED", ["FRESH_HEADER_IDENTITY_INCOMPLETE"]
    return "VERIFIED", ["EXACT_LOCAL_BYTES_PLUS_REVIEWED_IDENTITY_AND_FRESH_HEADER"]


class Redirects(urllib.request.HTTPRedirectHandler):
    max_redirections = 5
    def __init__(self):
        self.chain = []
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        self.chain.append({"from_url": request.full_url, "to_url": newurl, "http_status": code})
        if urllib.parse.urlsplit(newurl).scheme not in {"http", "https"}:
            raise urllib.error.URLError("Unsupported redirect scheme")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def fetch(url, timeout=20, max_bytes=20 * 1024 * 1024):
    redirects = Redirects()
    opener = urllib.request.build_opener(redirects, urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "requested_url": url, "tls_verification": "DEFAULT_CERTIFICATE_VERIFICATION"}
    if urllib.parse.urlsplit(url).scheme not in {"http", "https"}:
        return {**result, "access_error": "MISSING_OR_UNSUPPORTED_URL", "redirect_chain": []}, b""
    request = urllib.request.Request(url, headers={"User-Agent": "LegalGarpRag-source-identity-audit/1.0"})
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            raw = raw[:max_bytes]
            result.update({"http_status": response.status, "final_url": response.geturl(), "redirect_chain": redirects.chain,
                           "content_type": response.headers.get("Content-Type", ""), "response_bytes": len(raw), "response_sha256": digest_bytes(raw),
                           "truncated": truncated, "response_is_pdf": raw.lstrip().startswith(b"%PDF-")})
            return result, raw
    except urllib.error.HTTPError as exc:
        result.update({"http_status": exc.code, "final_url": exc.geturl(), "redirect_chain": redirects.chain, "access_error": "HTTP_ERROR"})
    except (OSError, ValueError, urllib.error.URLError) as exc:
        result.update({"redirect_chain": redirects.chain, "access_error": type(exc).__name__ + ": " + str(exc)[:300]})
    return result, b""


def collect_one(node, data, fetcher=fetch):
    key, original = source_url(node)
    observation, raw = fetcher(original.strip())
    observation.update({"schema_version": "url-observation-v1", "document_node_id": node["id"], "document_node_sha256": digest(node),
                        "source_url_field": key, "original_url": original})
    row = node["properties"]["source_properties"]
    identity = {"method": "EXACT_LOCAL_BYTES_AND_FRESH_PDF_HEADER", "local_source_sha256_match": False,
                "number_match": False, "title_match": False, "authority_match": False,
                "source_metadata_verified": row.get("metadata_verified") is True}
    relative = row.get("local_file_path")
    if isinstance(relative, str) and relative:
        path = (data / relative).resolve()
        if path.is_relative_to(data.resolve()) and path.is_file():
            local_hash = digest_bytes(path.read_bytes())
            identity.update({"local_source_path": relative, "local_source_sha256": local_hash,
                             "declared_local_sha256_match": local_hash == row.get("local_sha256"),
                             "local_source_sha256_match": local_hash == observation.get("response_sha256") and local_hash == row.get("local_sha256")})
    header = ""
    if observation.get("response_is_pdf") and not observation.get("truncated"):
        try:
            from pypdf import PdfReader
            import pypdf
            reader = PdfReader(BytesIO(raw), strict=False)
            header = "\n".join((page.extract_text() or "") for page in list(reader.pages[:2]))[:16000]
            identity.update({"header_extractor": "pypdf " + pypdf.__version__, "header_pages": min(2, len(reader.pages)),
                             "header_excerpt": header, "header_sha256": digest_bytes(header.encode("utf-8"))})
        except Exception as exc:
            identity["header_extraction_limitation"] = type(exc).__name__ + ": " + str(exc)[:200]
    expected = {"number": row.get("document_number") or row.get("instrument_number") or row.get("case_number") or "",
                "title": row.get("title") or "", "authority": row.get("issuer") or ""}
    normalized_header = normalize(header)
    for name, value in expected.items():
        needle = normalize(value)
        identity[name + "_match"] = bool(needle and len(needle) >= 4 and needle in normalized_header)
    identity["expected_source_identity"] = expected
    observation["identity_evidence"] = identity
    status, reasons = classify(node, observation)
    observation.update({"url_status": status, "reason_codes": reasons})
    if status == "VERIFIED":
        observation["resolved_url"] = observation["final_url"]
    return observation


def collect(nodes, data, output, workers=4):
    documents = sorted((n for n in nodes if n["type"] == "Document"), key=lambda n: n["id"])
    observations = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(collect_one, node, data): node["id"] for node in documents}
        for future in as_completed(futures):
            observation = future.result();observations.append(observation)
            print(f"audit {len(observations)}/{len(documents)} {observation['document_node_id']} {observation['url_status']} http={observation.get('http_status', 'NA')}", flush=True)
    observations.sort(key=lambda row: row["document_node_id"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"".join((canonical(row) + "\n").encode("utf-8") for row in observations))
    return observations
