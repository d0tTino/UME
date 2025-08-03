from __future__ import annotations

from collections import defaultdict
import time
from typing import Dict, List, Optional

from .event import Event, EventType


class AnomalyDetector:
    """Maintain tag statistics per entity and flag anomalies.

    The detector keeps simple occurrence counts of classification tags per
    ``entity`` (derived from ``event.source`` or ``event.subject_entity``). If a
    tag's frequency deviates from the historical frequency for that entity by
    more than ``threshold``, an ``ANOMALY_DETECTED`` event is produced.
    """

    def __init__(self, threshold: float = 0.4) -> None:
        self.threshold = threshold
        self._tag_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._total_counts: Dict[str, int] = defaultdict(int)

    def _entity_id(self, event: Event) -> Optional[str]:
        if event.source:
            return event.source
        if event.subject_entity and isinstance(event.subject_entity, dict):
            ent = event.subject_entity.get("id")
            if isinstance(ent, str):
                return ent
        return None

    def process_event(self, event: Event) -> Optional[Event]:
        """Update statistics for ``event`` and return an anomaly event if needed."""

        if event.event_type == EventType.ANOMALY_DETECTED:
            return None

        entity = self._entity_id(event)
        if entity is None:
            return None

        classification = event.payload.get("classification")
        if not isinstance(classification, list):
            return None
        tags: List[str] = []
        for item in classification:
            tag = item.get("tag") if isinstance(item, dict) else None
            if isinstance(tag, str):
                tags.append(tag)
        if not tags:
            return None

        anomalies: List[str] = []
        total = self._total_counts[entity]
        for tag in tags:
            count = self._tag_counts[entity][tag]
            prev_freq = count / total if total else 0.0
            new_freq = (count + 1) / (total + 1)
            if total and abs(new_freq - prev_freq) > self.threshold:
                anomalies.append(tag)
        for tag in tags:
            self._tag_counts[entity][tag] += 1
        self._total_counts[entity] += 1

        if anomalies:
            return Event(
                event_type=EventType.ANOMALY_DETECTED,
                timestamp=int(time.time()),
                payload={"entity_id": entity, "tags": anomalies},
                source=event.source,
            )
        return None
