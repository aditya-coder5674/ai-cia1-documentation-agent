"""Small Gemini REST client used by the Streamlit app."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def ask_gemini(prompt: str, api_key: str | None = None, json_response: bool = False):
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY or use Offline mode.")
    model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    config = {"temperature": 0.2}
    if json_response:
        config["responseMimeType"] = "application/json"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": config,
    }).encode("utf-8")
    request = urllib.request.Request(url, body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="ignore")[:500]
        raise RuntimeError(f"Gemini HTTP {error.code}: {detail}") from error
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("Gemini returned an unexpected response.") from error
    if json_response:
        text = text.removeprefix("```json").removesuffix("```").strip()
        return json.loads(text)
    return text
