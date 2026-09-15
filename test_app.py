from app import app, analyze_html


SAMPLE = """
<html><head><title>Example page</title><meta name="description" content="A useful example page for testing."></head>
<body><h1>Hello world</h1><h2>Details</h2><p>One two three.</p><img src="ok.png" alt="An example"><img src="missing.png"><a href="/about">About</a></body></html>
"""


def test_analyze_html_extracts_core_signals():
    result = analyze_html(SAMPLE, "https://example.com")
    assert result["title"] == "Example page"
    assert result["description"] == "A useful example page for testing."
    assert result["headings"]["h1"] == ["Hello world"]
    assert result["links_count"] == 1
    assert result["images_missing_alt"] == 1
    assert result["word_count"] > 0


def test_health_endpoint():
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_api_accepts_html_without_network():
    client = app.test_client()
    response = client.post("/api/analyze", json={"html": SAMPLE, "url": "https://example.com"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["result"]["title"] == "Example page"


def test_api_rejects_invalid_url():
    client = app.test_client()
    response = client.post("/api/analyze", json={"url": "http://localhost:5000"})
    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_agent_card_exists():
    client = app.test_client()
    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    assert response.get_json()["name"] == "Web Page Intelligence"
