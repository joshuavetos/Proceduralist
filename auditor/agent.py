"""Action extraction v2 and contradiction detection."""
from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests

from auditor import auditor as auditor_identity, clauses


@dataclass
class Action:
    label: str
    resolved_url: str
    fallback: str


class _ActionParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.actions: List[Action] = []
        self.disabled_labels: List[str] = []
        self.error_nodes: List[str] = []
        self._button_stack: List[int] = []
        self._seen = 0
        self._anchor_checks: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attr_map = {k: v for k, v in attrs}
        self._seen += 1
        index_suffix = f"{tag}-{self._seen}"
        fallback = f"{self.base_url}#{index_suffix}"
        classes = (attr_map.get("class") or "").lower().split()
        if "error" in classes or "alert" in classes:
            self.error_nodes.append(index_suffix)
        onclick = attr_map.get("onclick") or ""
        href = attr_map.get("href") or ""
        role = attr_map.get("role") or ""
        type_attr = (attr_map.get("type") or "").lower()
        disabled_flag = (
            "disabled" in classes
            or attr_map.get("disabled") is not None
            or attr_map.get("aria-disabled") == "true"
        )
        label = (
            attr_map.get("aria-label")
            or attr_map.get("title")
            or attr_map.get("name")
            or attr_map.get("value")
            or tag
        )
        resolved = ""
        if tag == "button" or role == "button":
            resolved = self._resolve_href(href)
            self._button_stack.append(len(self.actions))
            self.actions.append(self._build_action(label, resolved, fallback))
        if tag == "input" and type_attr == "submit":
            resolved = self._resolve_href(href)
            self.actions.append(self._build_action(label or "submit", resolved, fallback))
        if onclick:
            resolved = self._resolve_onclick(onclick)
            if not resolved:
                resolved = self._resolve_href(href)
            self.actions.append(self._build_action(label, resolved, fallback))
        if tag == "a":
            if href == "#":
                self.actions.append(self._build_action(label, "", fallback))
            else:
                resolved = self._resolve_href(href)
                self.actions.append(self._build_action(label, resolved, fallback))
                if resolved:
                    self._anchor_checks.append(resolved)
        if disabled_flag:
            self.disabled_labels.append(label)

    def handle_data(self, data: str) -> None:
        if not data.strip():
            return
        if self._button_stack:
            idx = self._button_stack[-1]
            action = self.actions[idx]
            updated_label = action.label if action.label not in {"button", "submit"} else data.strip()
            self.actions[idx] = Action(label=updated_label, resolved_url=action.resolved_url, fallback=action.fallback)

    def handle_endtag(self, tag: str) -> None:
        if tag == "button" and self._button_stack:
            self._button_stack.pop()

    def _resolve_href(self, href: str) -> str:
        if not href or href == "#":
            return ""
        return urljoin(self.base_url, href)

    def _resolve_onclick(self, onclick: str) -> str:
        match = re.search(r"https?://[^'\"]+", onclick)
        if match:
            return match.group(0)
        fragment = re.search(r"['\"](/[^'\"]+)['\"]", onclick)
        if fragment:
            return urljoin(self.base_url, fragment.group(1))
        return ""

    def _build_action(self, label: str, resolved: str, fallback: str) -> Action:
        target = resolved or fallback
        return Action(label=label or "action", resolved_url=target, fallback=fallback)


def find_actions_v2(html: str, current_url: str) -> List[Dict[str, str]]:
    parser = _ActionParser(current_url)
    parser.feed(html)
    actions: List[Dict[str, str]] = []
    for action in parser.actions:
        actions.append({"label": action.label, "resolved_url": action.resolved_url, "fallback": action.fallback})
    return actions


def _check_link_status(url: str, timeout: float = 3.0) -> bool:
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        if response.status_code == 404:
            return False
        if response.status_code >= 500:
            return False
        return True
    except requests.RequestException:
        return False


def _find_contradictions(html: str, current_url: str, history: Optional[List[str]] = None) -> List[Dict[str, str]]:
    parser = _ActionParser(current_url)
    parser.feed(html)
    contradictions: List[Dict[str, str]] = []
    for label in parser.disabled_labels:
        contradictions.append({
            "label": label,
            "contradiction_type": "disabled_action",
            "detail": f"Disabled control detected: {label}",
        })
    for node in parser.error_nodes:
        contradictions.append({
            "label": node,
            "contradiction_type": "error_message",
            "detail": "Error or alert element present",
        })
    seen = set(history or [])
    if current_url in seen:
        contradictions.append({
            "label": current_url,
            "contradiction_type": "redirect_loop",
            "detail": "Redirect loop detected",
        })
    for link in parser._anchor_checks[:5]:
        if not _check_link_status(link):
            contradictions.append({
                "label": link,
                "contradiction_type": "broken_link",
                "detail": "Link returned error status",
            })
    return contradictions


auditor_metadata = {"auditor": auditor_identity, "clauses": clauses}
