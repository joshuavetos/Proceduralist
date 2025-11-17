"""Selenium-powered crawler that builds temporary graphs in memory."""
from __future__ import annotations

from typing import Dict, List, Set, Tuple
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.remote.webdriver import WebDriver

from auditor.agent import find_actions_v2


def launch_browser() -> WebDriver:
    """Launch a headless browser using Selenium's WebDriver manager."""
    try:
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        return webdriver.Chrome(options=chrome_options)
    except Exception:
        firefox_options = FirefoxOptions()
        firefox_options.add_argument("-headless")
        firefox_options.add_argument("--no-sandbox")
        firefox_options.add_argument("--disable-dev-shm-usage")
        return webdriver.Firefox(options=firefox_options)


def fetch_html(url: str, driver: WebDriver | None = None) -> Tuple[str, str]:
    """Load the given URL and return a tuple of (html, final_url)."""
    browser = driver or launch_browser()
    created = driver is None
    try:
        browser.get(url)
        html = browser.page_source
        current_url = browser.current_url
        return html, current_url
    finally:
        if created:
            browser.quit()


def _enqueue_next(actions: List[Dict[str, str]], base_url: str, visited: Set[str]) -> List[str]:
    next_urls: List[str] = []
    for action in actions:
        target = action.get("resolved_url") or action.get("fallback") or ""
        if not target:
            continue
        absolute_target = urljoin(base_url, target)
        if absolute_target not in visited:
            next_urls.append(absolute_target)
    return next_urls


def crawl(start_url: str, max_depth: int = 2) -> Dict[str, List[Dict[str, object]]]:
    """Crawl the target URL up to ``max_depth`` and build an in-memory graph."""
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")

    browser = launch_browser()
    nodes: List[Dict[str, object]] = []
    edges: List[Dict[str, str]] = []
    visited: Set[str] = set()
    queue: List[Tuple[str, int]] = [(start_url, 0)]

    try:
        while queue:
            current_url, depth = queue.pop(0)
            if current_url in visited or depth > max_depth:
                continue
            visited.add(current_url)
            html, final_url = fetch_html(current_url, driver=browser)
            actions = find_actions_v2(html, final_url)
            nodes.append({"id": final_url, "url": final_url, "actions": actions})

            for action in actions:
                target = action.get("resolved_url") or action.get("fallback")
                if target:
                    edges.append({"source": final_url, "target": target})

            if depth < max_depth:
                for next_url in _enqueue_next(actions, final_url, visited):
                    if next_url not in visited:
                        queue.append((next_url, depth + 1))
    finally:
        browser.quit()

    return {"nodes": nodes, "edges": edges}
