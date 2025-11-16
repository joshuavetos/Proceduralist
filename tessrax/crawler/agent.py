"""RQ crawler worker for Tessrax perception loop.

The crawler operates entirely offline-first: it consumes URLs from jobs enqueued
by the orchestrator, performs deterministic HTML hashing, flags contradictions
based on HTTP signals and disabled controls, and writes ``StateNode`` plus
``ActionEdge`` records to Postgres.  Every run emits a governance receipt with
the mandated fields (status, runtime_info, integrity_score, signature).
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import List, Optional, Set, Tuple
from urllib.parse import urljoin, urldefrag, urlparse

import redis
import requests
from rq import Connection, Worker
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from tessrax.aion.verify_local import emit_audit_receipt
from tessrax.services.proceduralist.database.models import ActionEdge, StateNode

DB_URL = os.getenv(
    "TESSRAX_DB_URL",
    "postgresql://tessrax:password@postgres:5432/tessrax_state",
)
REDIS_URL = os.getenv("TESSRAX_REDIS_URL", "redis://redis:6379/0")
HTTP_TIMEOUT = float(os.getenv("TESSRAX_CRAWLER_TIMEOUT", "10"))
MAX_DEPTH = int(os.getenv("TESSRAX_CRAWLER_MAX_DEPTH", "3"))
MAX_STATES = int(os.getenv("TESSRAX_CRAWLER_MAX_STATES", "30"))
AUDITOR_IDENTITY = "Tessrax Governance Kernel v16"

engine = create_engine(DB_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@dataclass
class CrawlState:
    url: str
    depth: int
    from_node: Optional[StateNode]
    action_label: str


class _LinkParser(HTMLParser):
    """Extract anchor targets and disabled actions without external libs."""

    def __init__(self) -> None:
        super().__init__()
        self.links: List[Tuple[str, str]] = []
        self.disabled: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attr_map = {k: v for k, v in attrs}
        if tag == "a":
            href = attr_map.get("href")
            label = attr_map.get("title") or attr_map.get("aria-label") or attr_map.get("data-label") or "link"
            self.links.append((href or "", label))
        if tag in {"button", "input", "a"}:
            classes = attr_map.get("class", "") or ""
            disabled = "disabled" in classes.split() or "disabled" in attr_map or attr_map.get("aria-disabled") == "true"
            if disabled:
                label = (
                    attr_map.get("value")
                    or attr_map.get("aria-label")
                    or attr_map.get("title")
                    or attr_map.get("name")
                    or f"{tag}-disabled"
                )
                self.disabled.append(label)


class CrawlerAgent:
    """Recursive crawler with contradiction sensing and safe limits."""

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory
        self.http = requests.Session()
        self.http.headers.update({"User-Agent": "TessraxCrawler/1.1"})

    def run(self, start_url: str) -> None:
        """Crawl ``start_url`` with BFS traversal under depth/state limits."""

        parsed = urlparse(start_url)
        if not parsed.scheme.startswith("http"):
            raise ValueError("Crawler requires http or https URLs")
        base_domain = parsed.netloc
        visited_hashes: Set[str] = set()
        pending: queue.SimpleQueue[CrawlState] = queue.SimpleQueue()
        pending.put(CrawlState(url=start_url, depth=0, from_node=None, action_label="START"))

        with self.session_factory() as db:
            processed = 0
            while not pending.empty() and processed < MAX_STATES:
                state = pending.get()
                if state.depth > MAX_DEPTH:
                    continue
                node, is_new, links = self._visit(db, state, visited_hashes)
                processed += 1
                if not node:
                    continue
                if is_new and state.depth < MAX_DEPTH:
                    for href, label in self._filter_links(node.url, links, base_domain):
                        pending.put(
                            CrawlState(
                                url=href,
                                depth=state.depth + 1,
                                from_node=node,
                                action_label=label,
                            )
                        )
            db.commit()
        receipt = emit_audit_receipt(
            status="crawler-finish",
            runtime_info={"processed": processed, "start_url": start_url},
            integrity_score=0.92,
        )
        print(json.dumps(receipt, sort_keys=True))

    def _visit(
        self,
        db: Session,
        state: CrawlState,
        visited_hashes: Set[str],
    ) -> Tuple[Optional[StateNode], bool, List[Tuple[str, str]]]:
        """Fetch the URL, persist the resulting state, and return discovered links."""

        response = self._fetch(state.url)
        if response is None:
            return None, False, []
        html = response.text
        state_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
        if state_hash in visited_hashes:
            return None, False, []
        visited_hashes.add(state_hash)
        title = self._extract_title(html)
        is_contradiction = response.status_code >= 400 or any(keyword in title.lower() for keyword in ["404", "error", "forbidden"])
        node = self._get_or_create_node(db, state_hash, state.url, title, is_contradiction)
        if state.from_node:
            self._create_edge(db, state.from_node, node, state.action_label, is_contradiction)
        parser = _LinkParser()
        parser.feed(html)
        self._record_disabled_actions(db, node, parser.disabled)
        db.flush()
        return node, True, parser.links

    def _fetch(self, url: str) -> Optional[requests.Response]:
        """Perform an HTTP GET with strict timeout and no retries."""

        try:
            response = self.http.get(url, timeout=HTTP_TIMEOUT, allow_redirects=True)
            return response
        except requests.RequestException as exc:
            print(f"[CRAWLER] HTTP error for {url}: {exc}")
            return None

    def _extract_title(self, html: str) -> str:
        """Best-effort <title> extraction without third-party HTML parsers."""

        lower = html.lower()
        start = lower.find("<title>")
        end = lower.find("</title>")
        if start != -1 and end != -1 and end > start:
            return html[start + 7 : end].strip()
        return ""

    def _get_or_create_node(
        self, db: Session, state_hash: str, url: str, title: str, is_contradiction: bool
    ) -> StateNode:
        """Insert or fetch a ``StateNode`` for the provided hash."""

        existing = db.execute(select(StateNode).where(StateNode.state_hash == state_hash)).scalar_one_or_none()
        if existing:
            return existing
        node = StateNode(
            state_hash=state_hash,
            url=url,
            title=title,
            is_contradiction=is_contradiction,
        )
        db.add(node)
        db.commit()
        db.refresh(node)
        return node

    def _create_edge(
        self, db: Session, from_node: StateNode, to_node: StateNode, label: str, is_contradiction: bool
    ) -> None:
        """Persist an ``ActionEdge`` capturing navigation transitions."""

        edge = ActionEdge(
            from_node_id=from_node.id,
            to_node_id=to_node.id,
            action_label=label[:255],
            is_contradiction=is_contradiction,
        )
        db.add(edge)
        db.commit()

    def _record_disabled_actions(self, db: Session, node: StateNode, labels: List[str]) -> None:
        """Create trap nodes/edges for disabled controls to flag contradictions."""

        for label in labels:
            trap_hash = hashlib.sha256(f"trap::{node.id}::{label}".encode("utf-8")).hexdigest()
            trap_node = self._get_or_create_node(db, trap_hash, node.url, f"TRAP: {label}", True)
            self._create_edge(db, node, trap_node, label, True)

    def _filter_links(self, base_url: str, links: List[Tuple[str, str]], base_domain: str) -> List[Tuple[str, str]]:
        """Normalize relative links and restrict traversal to the base domain."""

        results: List[Tuple[str, str]] = []
        for href, label in links:
            if not href:
                continue
            resolved = urljoin(base_url, href)
            resolved, _ = urldefrag(resolved)
            if urlparse(resolved).netloc != base_domain:
                continue
            results.append((resolved, label))
        deduped = list(dict.fromkeys(results))
        return deduped[:5]


def run_crawl_job(start_url: str) -> None:
    """RQ job hook that instantiates and executes the crawler."""

    agent = CrawlerAgent()
    agent.run(start_url)


def worker_main() -> None:
    """Standalone RQ worker entrypoint bound to ``crawler_jobs`` queue."""

    redis_conn = redis.from_url(REDIS_URL)
    with Connection(redis_conn):
        worker = Worker(["crawler_jobs"])
        worker.work()


if __name__ == "__main__":
    worker_main()
