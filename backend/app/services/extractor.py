from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.models import ArtifactContext


async def extract_artifact_context(url: str) -> ArtifactContext:
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": "TisTruBot/0.1"})
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    title = _first_content(soup, [("meta", {"property": "og:title"}), ("meta", {"name": "twitter:title"})])
    if not title and soup.title:
        title = soup.title.get_text(strip=True)

    description = _first_content(
        soup,
        [
            ("meta", {"property": "og:description"}),
            ("meta", {"name": "twitter:description"}),
            ("meta", {"name": "description"}),
        ],
    )

    caption = _first_content(
        soup,
        [
            ("meta", {"property": "og:caption"}),
            ("meta", {"name": "twitter:text:title"}),
        ],
    )

    images = _media_urls(soup, url, "image")
    videos = _media_urls(soup, url, "video")
    text = _readable_text(soup)

    return ArtifactContext(
        source_url=url,
        title=title,
        caption=caption,
        description=description,
        text=text,
        images=images,
        videos=videos,
    )


def _first_content(soup: BeautifulSoup, selectors: list[tuple[str, dict[str, str]]]) -> str | None:
    for tag_name, attrs in selectors:
        node = soup.find(tag_name, attrs=attrs)
        if node and node.get("content"):
            return node["content"].strip()
    return None


def _media_urls(soup: BeautifulSoup, base_url: str, media_type: str) -> list[str]:
    urls: list[str] = []
    properties = [f"og:{media_type}", f"twitter:{media_type}"]
    for prop in properties:
        for node in soup.find_all("meta", attrs={"property": prop}):
            content = node.get("content")
            if content:
                urls.append(urljoin(base_url, content.strip()))

    tag_name = "img" if media_type == "image" else "video"
    for node in soup.find_all(tag_name):
        src = node.get("src")
        if src:
            urls.append(urljoin(base_url, src.strip()))

    return list(dict.fromkeys(urls))[:8]


def _readable_text(soup: BeautifulSoup) -> str:
    for node in soup(["script", "style", "noscript", "svg"]):
        node.decompose()
    chunks = [part.strip() for part in soup.get_text(" ").split()]
    return " ".join(chunks)[:6000]
