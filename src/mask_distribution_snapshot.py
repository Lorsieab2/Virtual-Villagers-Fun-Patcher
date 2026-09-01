"""Identity snapshots for additive village-wide mask distribution safeguards.

This module is deliberately game-agnostic and has no native-memory access.  A
per-game adapter supplies verified fields; the existing native planners remain
the authority until an adapter is explicitly enabled.
"""
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Optional


@dataclass(frozen=True)
class VillagerSnapshot:
    record_key: int
    name: str
    parentage: Optional[tuple[Any, ...]]
    skill_progress: tuple[Any, ...]
    preferred_skill: Any
    likes: tuple[Any, ...]
    dislikes: tuple[Any, ...]
    head: Any
    body: Any
    nursing: Any
    elderly: Any
    health: Any
    special_role: Optional[str] = None

    def fingerprint(self) -> str:
        """Return a deterministic comparison key, excluding record_key.

        The native record key is retained separately as a tie-breaker; it is
        not folded into this value so save/reload identity remains explicit.
        """
        payload = {
            "name": self.name,
            "parentage": self.parentage,
            "skill_progress": self.skill_progress,
            "preferred_skill": self.preferred_skill,
            "likes": self.likes,
            "dislikes": self.dislikes,
            "head": self.head,
            "body": self.body,
            "nursing": self.nursing,
            "elderly": self.elderly,
            "health": self.health,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


SPECIAL_ROLES = frozenset({
    "golden_child",       # VV1
    "tribal_chief",       # VV3
    "retired_chief",      # VV5
})


def eligible_for_additive_distribution(snapshot: VillagerSnapshot) -> bool:
    """Keep known special villagers out of an additive mask batch."""
    return snapshot.special_role not in SPECIAL_ROLES

