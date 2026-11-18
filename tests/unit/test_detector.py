from pathlib import Path

import pytest
from failure_detector.detector import Detector
@pytest.mark.asyncio
async def test_threshold_avoids_single_failure(tmp_path):
 d=Detector({'x':'http://127.0.0.1:1'},threshold=2,timeout=.01,event_file=Path(tmp_path)/'events.csv')
 await d.check('x','http://127.0.0.1:1'); assert not d.states['x'].detected_at

@pytest.mark.asyncio
async def test_outage_is_recorded_once_after_threshold(tmp_path):
 event_file = Path(tmp_path) / "events.csv"
 d = Detector({"x": "http://127.0.0.1:1"}, threshold=2, timeout=.01, event_file=event_file)
 await d.check("x", "http://127.0.0.1:1")
 await d.check("x", "http://127.0.0.1:1")
 await d.check("x", "http://127.0.0.1:1")
 rows = event_file.read_text().splitlines()
 assert len(rows) == 2 and "failure_detected" in rows[1]
