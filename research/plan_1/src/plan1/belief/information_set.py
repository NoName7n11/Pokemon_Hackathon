from __future__ import annotations

from typing import Any

from plan1.game.records import PublicObservationRecord
from plan1.reproducibility import canonical_json_hash


def _erase_native_serials(value: Any) -> None:
    if isinstance(value, dict):
        if "serial" in value:
            value["serial"] = 0
        for child in value.values():
            _erase_native_serials(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _erase_native_serials(child)


def policy_feature_payload(record: PublicObservationRecord, root_player: int) -> dict[str, Any]:
    """Return the root player's observation-limited policy payload.

    Determinized hands, prize identities, deck identities, private look cards,
    logs, and legal-option descriptors are excluded. Counts and public board
    state remain. The live root action list is handled separately by the legal
    action generator.
    """
    payload = record.to_dict()
    payload["logs"] = []
    state = payload.get("state")
    if state is not None:
        state["turn_action_count"] = 0
        state["looking"] = None
        for index, player in enumerate(state["players"]):
            if index != root_player:
                player["hand"] = None
            # Face-down prizes are already None in public observations. Keep
            # genuinely revealed prize cards because they are public facts.
    selection = payload.get("selection")
    if selection is not None:
        selection["deck"] = None
        selection["options"] = []
    # Synthetic cards are allocated native serials while a hidden world is
    # reconstructed. Those allocation details are not game information and
    # must not split otherwise identical information sets.
    _erase_native_serials(payload)
    payload["root_player"] = int(root_player)
    return payload


def information_set_key(record: PublicObservationRecord, root_player: int) -> str:
    return canonical_json_hash(policy_feature_payload(record, root_player))
