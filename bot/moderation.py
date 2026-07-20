"""Moderation checker: check_prompt(prompt) -> (blocked bool, rule, severity, matched)."""
from __future__ import annotations
import re
from typing import Tuple
import db

async def check_prompt(prompt: str) -> Tuple[bool, dict | None, str | None, str | None]:
    """Check prompt against all active moderation_rules.
    Returns (blocked, rule_dict, severity, matched_text).
    blocked True when severity == 'block' or 'high' (configurable, here block only high/block).
    For word: case-insensitive contains.
    For regex: search IGNORECASE.
    For category: treat pattern as word contains but intended for category label.
    """
    if not prompt:
        return False, None, None, None
    try:
        rules = await db.get_moderation_rules(active_only=True)
    except Exception:
        return False, None, None, None
    low_prompt = prompt.lower()
    for rule in rules:
        pat = rule.get("pattern") or ""
        rtype = rule.get("type") or "word"
        sev = rule.get("severity") or "block"
        if not pat:
            continue
        matched = None
        try:
            if rtype == "word":
                if pat.lower() in low_prompt:
                    matched = pat
            elif rtype == "regex":
                # compile safely; IGNORECASE
                rx = re.compile(pat, re.IGNORECASE)
                m = rx.search(prompt)
                if m:
                    matched = m.group(0)[:200]
            elif rtype == "category":
                # category e.g. nsfw/politic/selfharm — if prompt contains pattern OR simple heuristic?
                # For now contains check lower
                if pat.lower() in low_prompt:
                    matched = pat
                else:
                    # also treat category label as umbrella: if pattern is exactly nsfw/politic/selfharm, we still only match if present as word
                    # No extra heuristic
                    pass
        except re.error:
            continue
        except Exception:
            continue
        if matched:
            blocked = sev in ("block", "high")
            return blocked, rule, sev, matched
    return False, None, None, None

async def log_block(user_id: int, prompt: str, rule: dict | None, matched: str, severity: str):
    action = "block" if severity in ("block","high") else "warn"
    rid = rule.get("id") if rule else None
    pat = rule.get("pattern") if rule else matched
    try:
        await db.log_moderation(user_id, prompt, pat or matched, rid, action)
    except Exception:
        pass
