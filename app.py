"""Web Page Intelligence: a small, dependency-light web page analyzer."""
from __future__ import annotations

import ipaddress
import json
import socket
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

USER_AGENT = "WebPageIntelligence/1.0 (+https://github.com/)"
MAX_HTML_BYTES = 2_000_000


def _validate_public_url(raw_url: str) -> str:
    """Validate a URL and reject localhost/private-network targets."""
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise ValueError("A URL is required.")
    url = raw_url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must use http:// or https://.")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL hostname is missing.")
    lowered = hostname.lower().rstrip(".")
    if lowered in {"localhost", "localhost.localdomain"}:
        raise ValueError("Localhost URLs are not allowed.")
    try:
        addresses = socket.getaddrinfo(lowered, None)
    except socket.gaierror as exc:
        raise ValueError("The hostname could not be resolved.") from exc
    for address in {item[4][0] for item in addresses}:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("Private or local-network URLs are not allowed.")
    return url


def analyze_html(html: str, source_url: str | None = None) -> dict:
    """Extract useful, deterministic content and SEO signals from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description_tag = soup.find("meta", attrs={"name": lambda value: value and value.lower() == "description"})
    description = description_tag.get("content", "").strip() if description_tag else ""
    headings = {
        f"h{i}": [node.get_text(" ", strip=True) for node in soup.find_all(f"h{i}")]
        for i in range(1, 7)
    }
    links = []
    for anchor in soup.find_all("a", href=True):
        text = anchor.get_text(" ", strip=True)
        links.append({"text": text, "href": anchor["href"]})
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ", strip=True).split())
    words = text.split() if text else []
    images = soup.find_all("img")
    missing_alt = sum(1 for image in images if not image.get("alt", "").strip())
    return {
        "source_url": source_url,
        "title": title,
        "title_length": len(title),
        "description": description,
        "description_length": len(description),
        "headings": headings,
        "word_count": len(words),
        "links_count": len(links),
        "links": links[:100],
        "images_count": len(images),
        "images_missing_alt": missing_alt,
        "signals": {
            "has_title": bool(title),
            "has_description": bool(description),
            "has_h1": bool(headings["h1"]),
            "title_length_ok": 30 <= len(title) <= 60 if title else False,
            "description_length_ok": 70 <= len(description) <= 160 if description else False,
            "all_images_have_alt": missing_alt == 0,
        },
    }


def fetch_and_analyze(url: str) -> dict:
    url = _validate_public_url(url)
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=(5, 15),
        allow_redirects=True,
        stream=True,
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        raise ValueError("The URL did not return an HTML document.")
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=65536):
        total += len(chunk)
        if total > MAX_HTML_BYTES:
            raise ValueError("The HTML document is too large to analyze.")
        chunks.append(chunk)
    encoding = response.encoding or "utf-8"
    html = b"".join(chunks).decode(encoding, errors="replace")
    result = analyze_html(html, response.url)
    result["status_code"] = response.status_code
    return result


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "web-page-intelligence"})


@app.get("/.well-known/agent-card.json")
def agent_card():
    return jsonify({
        "name": "Web Page Intelligence",
        "description": "Analyze public HTML pages for content and basic SEO signals.",
        "url": request.url_root.rstrip("/"),
        "version": "1.0.0",
        "capabilities": {"streaming": False},
        "skills": [{
            "id": "analyze-web-page",
            "name": "Analyze web page",
            "description": "Fetch a public HTML URL and return structured content signals.",
            "input_modes": ["application/json"],
            "output_modes": ["application/json"],
        }],
    })


@app.post("/api/analyze")
@app.post("/v1/analyze")
def analyze_endpoint():
    payload = request.get_json(silent=True) or {}
    try:
        if payload.get("html") is not None:
            result = analyze_html(str(payload["html"]), payload.get("url"))
        else:
            result = fetch_and_analyze(payload.get("url", ""))
        return jsonify({"ok": True, "result": result})
    except requests.RequestException as exc:
        return jsonify({"ok": False, "error": f"Could not fetch the page: {exc}"}), 502
    except (ValueError, UnicodeError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception:
        app.logger.exception("Unexpected analysis failure")
        return jsonify({"ok": False, "error": "Unexpected analysis failure."}), 500


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Not found."}), 404
    return render_template("index.html"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)


# Keep json imported for simple deployment smoke checks and agent integrations.
_ = json
