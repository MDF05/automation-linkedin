"""
Search Service — Pencarian Referensi dari Google atau Perplexity.

Komponen ini menyediakan:
- ``search_references(topic, source)`` — cari referensi berdasarkan topik
  dari Google (via SerpAPI atau HTML scraping) atau Perplexity AI.

Digunakan oleh Content_Generator sebelum memanggil AI untuk mengumpulkan
konteks referensi yang relevan (Requirement 2.2).

Requirements: 2.2
"""

from __future__ import annotations

import logging
import os
from typing import List, TypedDict

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class SearchResult(TypedDict):
    """Satu hasil pencarian referensi."""
    title: str
    snippet: str
    url: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_RESULTS = 5

# SerpAPI
_SERPAPI_BASE_URL = "https://serpapi.com/search.json"

# Google web scraping fallback
_GOOGLE_SEARCH_URL = "https://www.google.com/search"
_GOOGLE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Perplexity API
_PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
_PERPLEXITY_MODEL = "llama-3-sonar-small-32k-online"

# HTTP timeouts (seconds)
_REQUEST_TIMEOUT = 15.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def search_references(topic: str, source: str = "google") -> List[SearchResult]:
    """
    Cari referensi untuk ``topic`` dari sumber yang ditentukan.

    Args:
        topic:  Topik atau kata kunci yang ingin dicari.
        source: Sumber pencarian — ``'google'`` atau ``'perplexity'``.
                Default: ``'google'``.

    Returns:
        List hingga 5 dict ``{title, snippet, url}``.
        Mengembalikan list kosong jika terjadi error atau sumber tidak tersedia.

    Requirements: 2.2
    """
    if not topic or not topic.strip():
        logger.warning("search_references: topic kosong, return []")
        return []

    topic = topic.strip()

    if source == "google":
        return await _search_google(topic)
    elif source == "perplexity":
        return await _search_perplexity(topic)
    else:
        logger.warning("search_references: source '%s' tidak dikenali, return []", source)
        return []


# ---------------------------------------------------------------------------
# Google Search
# ---------------------------------------------------------------------------

async def _search_google(topic: str) -> List[SearchResult]:
    """
    Cari referensi di Google.

    Urutan percobaan:
    1. SerpAPI jika env var ``SERPAPI_KEY`` tersedia.
    2. HTML scraping via requests jika SerpAPI tidak tersedia.

    Returns:
        List hasil pencarian, atau [] jika semua metode gagal.
    """
    serpapi_key = os.environ.get("SERPAPI_KEY", "").strip()

    if serpapi_key:
        results = await _search_via_serpapi(topic, serpapi_key)
        if results:
            return results
        # Fallback ke scraping jika SerpAPI gagal
        logger.warning("search_references: SerpAPI gagal, mencoba HTML scraping.")

    return await _search_via_html_scraping(topic)


async def _search_via_serpapi(topic: str, api_key: str) -> List[SearchResult]:
    """
    Cari via SerpAPI (https://serpapi.com/search.json).

    Args:
        topic:   Query pencarian.
        api_key: API key SerpAPI dari env ``SERPAPI_KEY``.

    Returns:
        List ``SearchResult``, atau [] jika gagal.
    """
    params = {
        "q": topic,
        "api_key": api_key,
        "num": _MAX_RESULTS,
        "hl": "id",  # bahasa Indonesia
    }

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.get(_SERPAPI_BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        organic = data.get("organic_results", [])
        results: List[SearchResult] = []

        for item in organic[:_MAX_RESULTS]:
            title = item.get("title", "").strip()
            snippet = item.get("snippet", "").strip()
            url = item.get("link", "").strip()

            if title and url:
                results.append({"title": title, "snippet": snippet, "url": url})

        logger.info("search_references[serpapi]: ditemukan %d hasil untuk '%s'", len(results), topic)
        return results

    except Exception as exc:
        logger.warning("search_references[serpapi]: error — %s", exc)
        return []


async def _search_via_html_scraping(topic: str) -> List[SearchResult]:
    """
    Cari via HTML scraping Google Search (fallback tanpa API key).

    Menggunakan BeautifulSoup untuk parse HTML response dari
    ``https://www.google.com/search?q={topic}``.

    Returns:
        List ``SearchResult``, atau [] jika gagal.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning(
            "search_references[html_scraping]: BeautifulSoup tidak tersedia. "
            "Install dengan: pip install beautifulsoup4"
        )
        return []

    try:
        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT,
            headers=_GOOGLE_HEADERS,
            follow_redirects=True,
        ) as client:
            resp = await client.get(
                _GOOGLE_SEARCH_URL,
                params={"q": topic, "num": 10, "hl": "id"},
            )
            resp.raise_for_status()
            html = resp.text

        soup = BeautifulSoup(html, "html.parser")
        results: List[SearchResult] = []

        # Selector utama untuk Google Search result containers
        # Google menggunakan <div class="g"> sebagai container hasil
        for container in soup.select("div.g")[:_MAX_RESULTS * 2]:
            # Judul — biasanya dalam <h3>
            h3 = container.find("h3")
            if not h3:
                continue
            title = h3.get_text(strip=True)

            # URL — ambil dari <a> pertama dengan href
            a_tag = container.find("a", href=True)
            url = ""
            if a_tag:
                href = a_tag["href"]
                # Lewati link internal Google
                if href.startswith("/url?q="):
                    url = href.split("/url?q=")[1].split("&")[0]
                elif href.startswith("http"):
                    url = href

            # Snippet — cari span atau div dengan teks deskripsi
            snippet = ""
            for sel in ["div.VwiC3b", "span.aCOpRe", "div[data-sncf]", "div.s"]:
                el = container.select_one(sel)
                if el:
                    snippet = el.get_text(strip=True)
                    break

            if title and url and url.startswith("http"):
                results.append({"title": title, "snippet": snippet, "url": url})
                if len(results) >= _MAX_RESULTS:
                    break

        logger.info(
            "search_references[html_scraping]: ditemukan %d hasil untuk '%s'",
            len(results),
            topic,
        )
        return results

    except Exception as exc:
        logger.warning("search_references[html_scraping]: error — %s", exc)
        return []


# ---------------------------------------------------------------------------
# Perplexity Search
# ---------------------------------------------------------------------------

async def _search_perplexity(topic: str) -> List[SearchResult]:
    """
    Cari referensi via Perplexity AI API.

    Menggunakan ``PERPLEXITY_API_KEY`` dari environment.
    Jika tidak tersedia, mengembalikan list kosong.

    Perplexity mengembalikan jawaban berbasis pencarian web dengan citations.
    Kita ekstrak citations sebagai SearchResult.

    Returns:
        List ``SearchResult`` dari citations, atau [] jika tidak dikonfigurasi/gagal.
    """
    api_key = os.environ.get("PERPLEXITY_API_KEY", "").strip()

    if not api_key:
        logger.info(
            "search_references[perplexity]: PERPLEXITY_API_KEY tidak dikonfigurasi, return []"
        )
        return []

    payload = {
        "model": _PERPLEXITY_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Berikan informasi terkini dan relevan tentang topik yang diberikan. "
                    "Fokus pada fakta, statistik, dan referensi yang dapat digunakan "
                    "untuk membuat konten LinkedIn yang informatif."
                ),
            },
            {
                "role": "user",
                "content": f"Cari referensi dan informasi terkini tentang: {topic}",
            },
        ],
        "max_tokens": 1024,
        "return_citations": True,
        "search_recency_filter": "month",
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.post(
                _PERPLEXITY_API_URL,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        # Ekstrak citations dari response Perplexity
        citations = data.get("citations", [])
        answer_text = ""

        choices = data.get("choices", [])
        if choices:
            answer_text = choices[0].get("message", {}).get("content", "")

        results: List[SearchResult] = []

        # Jika ada citations, gunakan sebagai SearchResult
        for i, citation_url in enumerate(citations[:_MAX_RESULTS]):
            if isinstance(citation_url, str) and citation_url.startswith("http"):
                results.append({
                    "title": f"Referensi {i + 1} untuk: {topic}",
                    "snippet": answer_text[:200] if i == 0 else "",
                    "url": citation_url,
                })

        # Jika tidak ada citations tapi ada jawaban, buat satu result dari jawaban
        if not results and answer_text:
            results.append({
                "title": f"Perplexity: {topic}",
                "snippet": answer_text[:500],
                "url": f"https://www.perplexity.ai/search?q={topic.replace(' ', '+')}",
            })

        logger.info(
            "search_references[perplexity]: ditemukan %d hasil untuk '%s'",
            len(results),
            topic,
        )
        return results

    except Exception as exc:
        logger.warning("search_references[perplexity]: error — %s", exc)
        return []
