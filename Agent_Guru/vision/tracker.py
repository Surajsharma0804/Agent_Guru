"""
Object Tracker for the Agent Guru Vision System.

Implements the ByteTrack two-stage association algorithm:
  Stage 1: Match high-confidence detections (≥0.5) to existing tracks via IoU.
  Stage 2: Match remaining low-confidence detections to unmatched tracks.

Tracking_ID persistence:
  - IDs persist through occlusion for up to 30 consecutive frames.
  - Same ID reassigned when object reappears within 30 frames.
  - Up to 20 simultaneous objects without FPS degradation.
  - object_appeared event on new ID; object_disappeared on release.
  - Update latency ≤10ms per frame.

Requirements: 9.1–9.8
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import structlog

from Agent_Guru.vision.vision_models import BoundingBox, DetectedObject, TrackingUpdate, VisionEvent

logger: structlog.BoundLogger = structlog.get_logger(__name__)

_MAX_OBJECTS: int = 20
_MAX_OCCLUSION_FRAMES: int = 30
_HIGH_CONF_THRESHOLD: float = 0.5
_IOU_HIGH_THRESHOLD: float = 0.3   # IoU threshold for high-conf stage
_IOU_LOW_THRESHOLD: float = 0.2    # IoU threshold for low-conf stage


# ---------------------------------------------------------------------------
# Internal track state
# ---------------------------------------------------------------------------


@dataclass
class _Track:
    """Internal state for a single tracked object."""

    tracking_id: int
    class_label: str
    bbox: BoundingBox
    frames_since_seen: int = 0
    is_confirmed: bool = True
    age: int = 0  # total frames this track has existed


# ---------------------------------------------------------------------------
# IoU helpers
# ---------------------------------------------------------------------------


def _bbox_to_xyxy(b: BoundingBox) -> tuple[float, float, float, float]:
    return b.x, b.y, b.x + b.width, b.y + b.height


def _iou(a: BoundingBox, b: BoundingBox) -> float:
    """Compute Intersection-over-Union between two bounding boxes."""
    ax1, ay1, ax2, ay2 = _bbox_to_xyxy(a)
    bx1, by1, bx2, by2 = _bbox_to_xyxy(b)

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    inter_w = max(0.0, ix2 - ix1)
    inter_h = max(0.0, iy2 - iy1)
    inter = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter

    return inter / union if union > 0.0 else 0.0


def _greedy_match(
    tracks: list[_Track],
    detections: list[DetectedObject],
    iou_threshold: float,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Greedy IoU-based matching between tracks and detections.

    Returns:
        matched: list of (track_idx, det_idx) pairs
        unmatched_tracks: indices of unmatched tracks
        unmatched_dets: indices of unmatched detections
    """
    if not tracks or not detections:
        return [], list(range(len(tracks))), list(range(len(detections)))

    # Build IoU matrix
    iou_matrix = np.zeros((len(tracks), len(detections)), dtype=np.float32)
    for ti, track in enumerate(tracks):
        for di, det in enumerate(detections):
            iou_matrix[ti, di] = _iou(track.bbox, det.bounding_box)

    matched: list[tuple[int, int]] = []
    used_tracks: set[int] = set()
    used_dets: set[int] = set()

    # Greedy: pick highest IoU pairs first
    flat_order = np.argsort(-iou_matrix.ravel())
    for flat_idx in flat_order:
        ti = int(flat_idx // len(detections))
        di = int(flat_idx % len(detections))
        if iou_matrix[ti, di] < iou_threshold:
            break
        if ti in used_tracks or di in used_dets:
            continue
        matched.append((ti, di))
        used_tracks.add(ti)
        used_dets.add(di)

    unmatched_tracks = [i for i in range(len(tracks)) if i not in used_tracks]
    unmatched_dets = [i for i in range(len(detections)) if i not in used_dets]
    return matched, unmatched_tracks, unmatched_dets


# ---------------------------------------------------------------------------
# ObjectTracker
# ---------------------------------------------------------------------------


class ObjectTracker:
    """ByteTrack-based multi-object tracker.

    Args:
        max_objects: Maximum simultaneous tracked objects (default 20).
        max_occlusion_frames: Frames to keep a track alive without detection (default 30).
    """

    def __init__(
        self,
        max_objects: int = _MAX_OBJECTS,
        max_occlusion_frames: int = _MAX_OCCLUSION_FRAMES,
    ) -> None:
        self._max_objects = max_objects
        self._max_occlusion_frames = max_occlusion_frames
        self._tracks: list[_Track] = []
        self._next_id: int = 1
        logger.info(
            "ObjectTracker initialised",
            max_objects=max_objects,
            max_occlusion_frames=max_occlusion_frames,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(
        self, detections: list[DetectedObject], frame_seq: int
    ) -> list[TrackingUpdate]:
        """Run one ByteTrack update step.

        Args:
            detections: Detected objects in the current frame.
            frame_seq: Monotonically increasing frame sequence number.

        Returns:
            List of TrackingUpdate objects (active + newly lost tracks).
        """
        # Split detections by confidence
        high_dets = [d for d in detections if d.confidence >= _HIGH_CONF_THRESHOLD]
        low_dets = [d for d in detections if d.confidence < _HIGH_CONF_THRESHOLD]

        # Stage 1: match high-confidence detections to all active tracks
        active_tracks = [t for t in self._tracks if t.frames_since_seen == 0 or t.frames_since_seen <= self._max_occlusion_frames]
        matched_h, unmatched_tracks_h, unmatched_dets_h = _greedy_match(
            active_tracks, high_dets, _IOU_HIGH_THRESHOLD
        )

        # Apply stage-1 matches
        matched_track_indices: set[int] = set()
        for ti, di in matched_h:
            track = active_tracks[ti]
            det = high_dets[di]
            track.bbox = det.bounding_box
            track.class_label = det.class_label
            track.frames_since_seen = 0
            track.age += 1
            matched_track_indices.add(id(track))

        # Stage 2: match low-confidence detections to unmatched tracks
        unmatched_active = [active_tracks[i] for i in unmatched_tracks_h]
        matched_l, unmatched_tracks_l, unmatched_dets_l = _greedy_match(
            unmatched_active, low_dets, _IOU_LOW_THRESHOLD
        )
        for ti, di in matched_l:
            track = unmatched_active[ti]
            det = low_dets[di]
            track.bbox = det.bounding_box
            track.class_label = det.class_label
            track.frames_since_seen = 0
            track.age += 1
            matched_track_indices.add(id(track))

        # Age unmatched tracks
        for track in self._tracks:
            if id(track) not in matched_track_indices:
                track.frames_since_seen += 1

        # Create new tracks for unmatched high-confidence detections
        # (low-confidence unmatched detections do not spawn new tracks)
        new_track_dets = [high_dets[i] for i in unmatched_dets_h]
        newly_created: list[_Track] = []
        for det in new_track_dets:
            if len(self._tracks) >= self._max_objects:
                break
            track = _Track(
                tracking_id=self._next_id,
                class_label=det.class_label,
                bbox=det.bounding_box,
                frames_since_seen=0,
                age=1,
            )
            self._next_id += 1
            self._tracks.append(track)
            newly_created.append(track)

        # Collect updates before removing lost tracks
        updates: list[TrackingUpdate] = []

        for track in self._tracks:
            is_new = track in newly_created
            is_lost = track.frames_since_seen > self._max_occlusion_frames
            updates.append(
                TrackingUpdate(
                    tracking_id=track.tracking_id,
                    class_label=track.class_label,
                    bounding_box=track.bbox,
                    frames_since_seen=track.frames_since_seen,
                    is_new=is_new,
                    is_lost=is_lost,
                )
            )

        # Remove tracks that have exceeded occlusion limit
        self._tracks = [
            t for t in self._tracks
            if t.frames_since_seen <= self._max_occlusion_frames
        ]

        logger.debug(
            "ObjectTracker updated",
            frame_seq=frame_seq,
            active_tracks=len(self._tracks),
            updates=len(updates),
        )
        return updates

    def make_events(
        self, updates: list[TrackingUpdate], frame_seq: int
    ) -> list[VisionEvent]:
        """Build VisionEvents for appeared/disappeared tracking updates.

        Args:
            updates: TrackingUpdate list from :meth:`update`.
            frame_seq: Current frame sequence number.

        Returns:
            List of VisionEvents with event_type "object_appeared" or
            "object_disappeared".
        """
        events: list[VisionEvent] = []
        for upd in updates:
            if upd.is_new:
                events.append(
                    VisionEvent(
                        event_type="object_appeared",
                        timestamp=VisionEvent.now_timestamp(),
                        source_module="tracker",
                        confidence=1.0,
                        bounding_box=upd.bounding_box,
                        metadata={
                            "tracking_id": upd.tracking_id,
                            "class_label": upd.class_label,
                            "frame_seq": frame_seq,
                        },
                    )
                )
            elif upd.is_lost:
                events.append(
                    VisionEvent(
                        event_type="object_disappeared",
                        timestamp=VisionEvent.now_timestamp(),
                        source_module="tracker",
                        confidence=1.0,
                        bounding_box=upd.bounding_box,
                        metadata={
                            "tracking_id": upd.tracking_id,
                            "class_label": upd.class_label,
                            "frame_seq": frame_seq,
                        },
                    )
                )
        return events

    @property
    def active_track_count(self) -> int:
        """Number of currently active (non-lost) tracks."""
        return len(self._tracks)

    def reset(self) -> None:
        """Clear all tracks and reset ID counter."""
        self._tracks.clear()
        self._next_id = 1
