"""
Face tracking module — maintains identity across video frames.

Uses IoU-based greedy matching to associate new detections with existing
tracks. Tracks are aged out after max_age frames without a match.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class TrackedFace:
    """A face being tracked across frames.

    Attributes:
        track_id: Unique integer ID for this track.
        bbox: Bounding box as (x, y, w, h).
        identity: Assigned identity name, or None if unknown.
        confidence: Detection confidence of the last matched detection.
        age: Frames since this track was last matched to a detection.
        embedding: Last known face embedding, or None.
    """

    track_id: int
    bbox: Tuple[int, int, int, int]
    identity: Optional[str] = None
    confidence: float = 1.0
    age: int = 0
    embedding: Optional[np.ndarray] = None


class FaceTracker:
    """Tracks multiple faces across video frames using IoU matching.

    Args:
        max_age: Maximum number of frames a track can go unmatched before
            being removed.
        algorithm: Matching algorithm — "iou" or "deepsort" (both use IoU
            in this implementation; "deepsort" is a placeholder).
    """

    _IOU_THRESHOLD: float = 0.3

    def __init__(self, max_age: int = 30, algorithm: str = "iou") -> None:
        self.max_age = max_age
        self.algorithm = algorithm
        self._tracks: Dict[int, TrackedFace] = {}
        self._next_id: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(
        self,
        detections: List[object],
        embeddings: Optional[List[np.ndarray]] = None,
    ) -> List[TrackedFace]:
        """Update tracks with new detections.

        Args:
            detections: List of Detection objects with a .bbox attribute
                (x, y, w, h) and .confidence attribute.
            embeddings: Optional list of embeddings aligned with detections.

        Returns:
            List of all active TrackedFace objects (age <= max_age).
        """
        # 1. Age all existing tracks
        for track in self._tracks.values():
            track.age += 1

        # 2. Remove stale tracks
        self._tracks = {
            tid: t for tid, t in self._tracks.items() if t.age <= self.max_age
        }

        if not detections:
            return self.get_active_tracks()

        track_ids = list(self._tracks.keys())
        track_bboxes = [self._tracks[tid].bbox for tid in track_ids]

        det_bboxes = [self._get_bbox(d) for d in detections]
        det_confs = [self._get_conf(d) for d in detections]

        matched_tracks: set[int] = set()
        matched_dets: set[int] = set()

        # 3. Greedy IoU matching
        if track_bboxes:
            iou_matrix = np.zeros((len(track_ids), len(det_bboxes)), dtype=np.float32)
            for ti, tb in enumerate(track_bboxes):
                for di, db in enumerate(det_bboxes):
                    iou_matrix[ti, di] = self._compute_iou(tb, db)

            # Greedy: pick highest IoU pairs first
            flat_order = np.argsort(iou_matrix.ravel())[::-1]
            for idx in flat_order:
                ti, di = divmod(int(idx), len(det_bboxes))
                if iou_matrix[ti, di] < self._IOU_THRESHOLD:
                    break
                if ti in matched_tracks or di in matched_dets:
                    continue
                matched_tracks.add(ti)
                matched_dets.add(di)
                tid = track_ids[ti]
                self._tracks[tid].bbox = det_bboxes[di]
                self._tracks[tid].age = 0
                self._tracks[tid].confidence = det_confs[di]
                if embeddings and di < len(embeddings):
                    self._tracks[tid].embedding = embeddings[di]

        # 4. Create new tracks for unmatched detections
        for di in range(len(detections)):
            if di in matched_dets:
                continue
            emb = embeddings[di] if embeddings and di < len(embeddings) else None
            new_track = TrackedFace(
                track_id=self._next_id,
                bbox=det_bboxes[di],
                confidence=det_confs[di],
                age=0,
                embedding=emb,
            )
            self._tracks[self._next_id] = new_track
            self._next_id += 1

        return self.get_active_tracks()

    def assign_identity(self, track_id: int, identity: str) -> bool:
        """Assign an identity name to a track.

        Returns:
            True if the track was found and updated, False otherwise.
        """
        if track_id not in self._tracks:
            return False
        self._tracks[track_id].identity = identity
        return True

    def get_active_tracks(self) -> List[TrackedFace]:
        """Return all tracks with age <= max_age."""
        return [t for t in self._tracks.values() if t.age <= self.max_age]

    def reset(self) -> None:
        """Clear all tracks and reset the ID counter."""
        self._tracks.clear()
        self._next_id = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_iou(
        bbox1: Tuple[int, int, int, int],
        bbox2: Tuple[int, int, int, int],
    ) -> float:
        """Intersection over Union for two (x, y, w, h) bounding boxes."""
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2

        ix = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
        iy = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
        intersection = ix * iy

        union = w1 * h1 + w2 * h2 - intersection
        if union <= 0:
            return 0.0
        return float(intersection / union)

    @staticmethod
    def _get_bbox(detection: object) -> Tuple[int, int, int, int]:
        """Extract (x, y, w, h) from a detection object or tuple."""
        if hasattr(detection, "bbox"):
            return tuple(detection.bbox)  # type: ignore[return-value]
        return tuple(detection)  # type: ignore[return-value]

    @staticmethod
    def _get_conf(detection: object) -> float:
        if hasattr(detection, "confidence"):
            return float(detection.confidence)
        return 1.0
