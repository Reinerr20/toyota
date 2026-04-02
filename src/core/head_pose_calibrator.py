from collections import deque
from dataclasses import dataclass
from math import isfinite
from statistics import mean, pstdev


@dataclass(frozen=True)
class CalibratedPose:
    pitch_raw: float
    yaw_raw: float
    roll_raw: float

    pitch_rel: float
    yaw_rel: float
    roll_rel: float

    baseline_pitch: float | None
    baseline_yaw: float | None
    baseline_roll: float | None

    is_calibrated: bool
    sample_count: int


class HeadPoseCalibrator:
    """
    Session-level neutral head pose calibration.

    Purpose:
    - collect stable early-session pose samples
    - estimate neutral baseline
    - output relative pose (pose - baseline)

    Notes:
    - This class DOES NOT compute pose. It only calibrates already-computed pose.
    - It should stay separate from HeadPoseEstimator to preserve SRP.
    """

    def __init__(self, cfg: dict):
        self.enabled = bool(cfg.get("enabled", True))
        self.min_valid_frames = int(cfg.get("min_valid_frames", 20))
        self.max_pitch_std_deg = float(cfg.get("max_pitch_std_deg", 3.0))
        self.max_yaw_std_deg = float(cfg.get("max_yaw_std_deg", 4.0))
        self.max_roll_std_deg = float(cfg.get("max_roll_std_deg", 4.0))
        self.face_confidence_min = float(cfg.get("face_confidence_min", 0.5))

        self._pitch_samples = deque(maxlen=self.min_valid_frames)
        self._yaw_samples = deque(maxlen=self.min_valid_frames)
        self._roll_samples = deque(maxlen=self.min_valid_frames)

        self._baseline_pitch = None
        self._baseline_yaw = None
        self._baseline_roll = None

        self._is_calibrated = False

    def reset(self) -> None:
        self._pitch_samples.clear()
        self._yaw_samples.clear()
        self._roll_samples.clear()

        self._baseline_pitch = None
        self._baseline_yaw = None
        self._baseline_roll = None

        self._is_calibrated = False

    def update(
        self,
        *,
        pitch: float,
        yaw: float,
        roll: float,
        face_confidence: float = 1.0,
        face_detected: bool = True,
    ) -> CalibratedPose:
        pitch = float(pitch)
        yaw = float(yaw)
        roll = float(roll)
        face_confidence = float(face_confidence)

        if not self.enabled:
            return CalibratedPose(
                pitch_raw=pitch,
                yaw_raw=yaw,
                roll_raw=roll,
                pitch_rel=pitch,
                yaw_rel=yaw,
                roll_rel=roll,
                baseline_pitch=None,
                baseline_yaw=None,
                baseline_roll=None,
                is_calibrated=False,
                sample_count=0,
            )

        if self._is_valid_sample(
            pitch=pitch,
            yaw=yaw,
            roll=roll,
            face_confidence=face_confidence,
            face_detected=face_detected,
        ):
            if not self._is_calibrated:
                self._pitch_samples.append(pitch)
                self._yaw_samples.append(yaw)
                self._roll_samples.append(roll)

                if self._can_finalize_baseline():
                    self._baseline_pitch = mean(self._pitch_samples)
                    self._baseline_yaw = mean(self._yaw_samples)
                    self._baseline_roll = mean(self._roll_samples)
                    self._is_calibrated = True

        if self._is_calibrated:
            pitch_rel = pitch - float(self._baseline_pitch)
            yaw_rel = yaw - float(self._baseline_yaw)
            roll_rel = roll - float(self._baseline_roll)
        else:
            # before calibration is complete, keep relative pose neutral/disabled
            pitch_rel = 0.0
            yaw_rel = 0.0
            roll_rel = 0.0

        return CalibratedPose(
            pitch_raw=pitch,
            yaw_raw=yaw,
            roll_raw=roll,
            pitch_rel=float(pitch_rel),
            yaw_rel=float(yaw_rel),
            roll_rel=float(roll_rel),
            baseline_pitch=self._baseline_pitch,
            baseline_yaw=self._baseline_yaw,
            baseline_roll=self._baseline_roll,
            is_calibrated=self._is_calibrated,
            sample_count=len(self._pitch_samples),
        )

    def _is_valid_sample(
        self,
        *,
        pitch: float,
        yaw: float,
        roll: float,
        face_confidence: float,
        face_detected: bool,
    ) -> bool:
        if not face_detected:
            return False

        if face_confidence < self.face_confidence_min:
            return False

        if not (isfinite(pitch) and isfinite(yaw) and isfinite(roll)):
            return False

        return True

    def _can_finalize_baseline(self) -> bool:
        if len(self._pitch_samples) < self.min_valid_frames:
            return False

        pitch_std = pstdev(self._pitch_samples)
        yaw_std = pstdev(self._yaw_samples)
        roll_std = pstdev(self._roll_samples)

        return (
            pitch_std <= self.max_pitch_std_deg
            and yaw_std <= self.max_yaw_std_deg
            and roll_std <= self.max_roll_std_deg
        )