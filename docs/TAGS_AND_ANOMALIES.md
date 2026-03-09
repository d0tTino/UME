# Event Tags and Anomalies


> Canonical architecture reference: [`ARCHITECTURE_OVERVIEW.md`](ARCHITECTURE_OVERVIEW.md).
## Event Tags

UME classifies each ingested event and appends the resulting tags to the event's `classification` field. Tags originate from registered classifiers. Built‑in classifiers include a keyword matcher and optional external services such as `tino_storm`.

## Querying by Tag

Tags can be used to filter event history:

```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/events?tag=phishing"
```

## Registering Custom Classifiers

```python
from ume.classification.plugins import register_classifier, Classifier, TagResult

class MyClassifier(Classifier):
    def classify(self, payload: dict) -> list[TagResult]:
        # inspect payload and return tag results
        return [TagResult(tag="custom", confidence=1.0)]

register_classifier("MY_EVENT", MyClassifier())
```

## Anomaly Detection

The `AnomalyDetector` keeps tag statistics per entity (based on `source` or `subject_entity`). If a tag's frequency shifts beyond the configured threshold, the detector emits an `ANOMALY_DETECTED` event:

```json
{
  "event_type": "ANOMALY_DETECTED",
  "timestamp": 1713275452,
  "payload": {"entity_id": "agent_42", "tags": ["phishing"]},
  "source": "agent_42"
}
```

## Configuration Examples

### Register a new classifier

The previous Python snippet can be placed in your service startup code to register a classifier. Alternatively, you can load classifiers conditionally using environment variables.

### Adjust anomaly threshold

```python
from ume.anomaly_detection import AnomalyDetector

threshold = 0.2  # more sensitive
# threshold = float(os.environ.get("ANOMALY_THRESHOLD", 0.4))

detector = AnomalyDetector(threshold=threshold)
```

```dotenv
ANOMALY_THRESHOLD=0.2
```

Setting a lower threshold makes the detector more sensitive to changes in tag frequencies.
