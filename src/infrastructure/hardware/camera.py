"""
Unified camera interface for Picamera2 or OpenCV webcam.

Environment variables:
- DS_CAMERA_SOURCE: picamera2 | opencv | auto (default: auto)
- DS_CAMERA_INDEX: device index for OpenCV (default: 0)
- DS_CAMERA_RES: resolution like 640x480 (default: 640x480)
"""
import os
import cv2
import time
import logging
import numpy as np
from typing import Optional, Tuple, Union

log = logging.getLogger(__name__)

# Safe Picamera2 import
try:
    from picamera2 import Picamera2
    HAVE_PICAM2 = True
except (ImportError, RuntimeError):
    HAVE_PICAM2 = False
    Picamera2 = None


class Camera:
    """Unified camera with auto-fallback: Picamera2 → OpenCV webcam."""
    
    def __init__(
        self,
        source: str = "auto",
        resolution: Tuple[int, int] = (640, 480),
        index: Union[int, str] = "auto",
    ):
        # Parse environment
        self.source = os.getenv("DS_CAMERA_SOURCE", source).lower()
        self.index_arg = str(os.getenv("DS_CAMERA_INDEX", str(index))).strip().lower()
        self.device_index: Optional[int] = None
        self.detected_indices = []
        
        # Parse resolution from env (e.g., 640x480)
        res_env = os.getenv("DS_CAMERA_RES")
        if res_env and "x" in res_env:
            try:
                w, h = res_env.split("x")
                resolution = (int(w), int(h))
            except ValueError:
                pass
        
        self.resolution = resolution
        self.picam2 = None
        self.cap = None
        self.backend = None
        self.ready = False
        
        # Initialize
        self._init()
        
        if self.ready:
            log.info("✓ Camera ready: %s @ %sx%s", self.backend, *self.resolution)
        else:
            log.error("✗ Camera failed to initialize")
    
    def _init(self):
        """Initialize camera based on source preference."""
        if self.source == "opencv":
            self._init_opencv()
        elif self.source == "picamera2":
            self._init_picamera2()
        else:  # auto
            if self.index_arg != "auto":
                self._init_opencv()
                return
            if HAVE_PICAM2 and self._init_picamera2():
                return
            log.info("Falling back to OpenCV webcam...")
            self._init_opencv()
    
    def _init_picamera2(self) -> bool:
        """Try Picamera2. Returns True if successful."""
        if not HAVE_PICAM2:
            return False
        
        try:
            self.picam2 = Picamera2()
            config = self.picam2.create_preview_configuration(
                main={"size": self.resolution, "format": "RGB888"}
            )
            self.picam2.configure(config)
            self.picam2.start()
            time.sleep(0.5)  # Warmup
            
            # Verify capture works
            test_frame = self.picam2.capture_array()
            if test_frame is None or test_frame.size == 0:
                raise RuntimeError("Capture test failed")
            
            self.backend = "picamera2"
            self.ready = True
            return True
            
        except Exception as e:
            log.warning("Picamera2 init failed: %s", e)
            if self.picam2:
                try:
                    self.picam2.stop()
                    self.picam2.close()
                except:
                    pass
                self.picam2 = None
            return False
    
    def _init_opencv(self) -> bool:
        """Try OpenCV at an exact index, or scan indices 0..4 when index=auto."""
        if self.index_arg == "auto":
            detected = []
            for idx in range(5):
                cap = self._open_opencv_capture(idx)
                if cap is not None:
                    detected.append(idx)
                    cap.release()

            self.detected_indices = detected
            if not detected:
                log.error("No OpenCV camera detected while scanning indices 0..4.")
                return False
            if len(detected) > 1:
                log.warning("Multiple OpenCV cameras detected at indices %s; using %d", detected, detected[0])
            return self._init_opencv_index(detected[0])

        try:
            idx_to_try = int(self.index_arg)
        except ValueError:
            log.error("Invalid OpenCV camera index: %r", self.index_arg)
            return False

        return self._init_opencv_index(idx_to_try)

    def _init_opencv_index(self, idx_to_try: int) -> bool:
        cap = self._open_opencv_capture(idx_to_try)
        if cap is None:
            log.error("OpenCV camera at index %d failed to open or read.", idx_to_try)
            return False

        self.cap = cap
        self.device_index = idx_to_try
        self.backend = "opencv"
        self.ready = True
        log.info("OpenCV camera ready: index=%d", idx_to_try)
        return True

    def _open_opencv_capture(self, idx_to_try: int):
        """Open and validate one OpenCV camera index. Caller owns returned capture."""
        try:
            cap = cv2.VideoCapture(idx_to_try)
            if not cap.isOpened():
                return None
            
            # Configure
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            time.sleep(0.1)
            
            # Test read
            ret, frame = cap.read()
            if ret and frame is not None:
                return cap
            
            # If read test fails
            cap.release()
            return None
            
        except Exception as e:
            log.debug("Failed to init OpenCV at index %d: %s", idx_to_try, e)
            return None
    
    def read(self, color: str = "rgb") -> Optional[np.ndarray]:
        """
        Capture frame.

        color:
          - "bgr": returns BGR (best for OpenCV drawing/imshow; avoids extra conversions)
          - "rgb": returns RGB (best for MediaPipe)
        """
        if not self.ready:
            return None

        color = (color or "rgb").lower()

        try:
            if self.backend == "picamera2":
                frame = self.picam2.capture_array()
                if frame is None or frame.size == 0:
                    return None

                # Picamera2 returns BGR despite RGB888 config
                if color == "bgr":
                    return frame
                return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            elif self.backend == "opencv":
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    return None

                if color == "bgr":
                    return frame
                return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        except Exception as e:
            log.debug("Capture error: %s", e)
            return None
    
    def release(self):
        """Release camera resources."""
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
            except:
                pass
            self.picam2 = None
        
        if self.cap:
            try:
                self.cap.release()
            except:
                pass
            self.cap = None
        
        self.ready = False
        log.info("Camera released")
    
    def close(self):
        """Alias for release()."""
        self.release()
        
if __name__ == "__main__":
    import sys
    
    # Konfigurasi Logging agar output terlihat
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("------------------------------------------------")
    print("   Manual Camera Test (src/infrastructure/hardware/camera.py)")
    print("------------------------------------------------")

    # Inisialisasi Kamera (Auto-detect)
    cam = Camera(source="auto", resolution=(640, 480))
    
    if not cam.ready:
        log.error("Camera init failed. Exiting.")
        sys.exit(1)

    print("Camera initialized successfully.")
    print("Press CTRL+C to stop the preview loop.")

    try:
        while True:
            # Ambil frame dalam format BGR (untuk OpenCV imshow)
            frame = cam.read(color="bgr")
            
            if frame is None:
                log.warning("Empty frame received.")
                time.sleep(0.1)
                continue

            cv2.imshow("Camera Manual Test", frame)
            
            # Tekan ESC atau 'q' untuk keluar
            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord('q'):
                print("Stopping...")
                break
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception as e:
        log.error(f"Error in loop: {e}")
    finally:
        cam.release()
        cv2.destroyAllWindows()
        print("Camera released. Test finished.")
