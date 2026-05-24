import sys
import os
import cv2
import numpy as np
from PIL import Image

def preprocess_video(input_path, output_path):
    """
    Reads an input video, resizes it to 128x64, applies high-quality Floyd-Steinberg
    dithering (using PIL's high-quality dithering engine), and packs each frame
    into a raw 1-bit binary chunk of 1024 bytes.
    Saves the entire video as a lightweight, pre-compiled binary file.
    """
    if not os.path.exists(input_path):
        print(f"[-] Error: Input video file not found: {input_path}")
        return False

    print(f"[+] Opening source video: {input_path}")
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print("[-] Error: Could not open video file with OpenCV.")
        return False

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"[+] Video details: {fps:.2f} FPS | {total_frames} total frames")

    # We will save as a binary file:
    # Header format:
    # 4 bytes: Magic bytes (e.g., b'R1B\x01' for Raw 1-Bit v1)
    # 4 bytes: float32 FPS
    # 4 bytes: uint32 total frames
    # Followed by (total_frames * 1024) bytes of raw frame data.
    
    print(f"[+] Compiling to 1-bit raw stream at {output_path}...")
    
    frame_count = 0
    with open(output_path, 'wb') as f:
        # Write 12-byte header
        f.write(b'R1B\x01')
        f.write(np.float32(fps).tobytes())
        f.write(np.uint32(total_frames).tobytes())

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 1. Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # 2. Resize to 128x64
            resized = cv2.resize(gray, (128, 64), interpolation=cv2.INTER_AREA)
            
            # 3. Floyd-Steinberg Dithering via PIL (extremely high quality, looks amazing!)
            pil_img = Image.fromarray(resized).convert("1")
            
            # 4. Get raw 1-bit pixel bytes (128 * 64 bits = 8192 bits = 1024 bytes)
            raw_bytes = pil_img.tobytes()
            if len(raw_bytes) != 1024:
                print(f"[-] Warning: Frame {frame_count} has unexpected size {len(raw_bytes)} bytes instead of 1024")
                # Pad or truncate just in case
                raw_bytes = raw_bytes[:1024].ljust(1024, b'\x00')

            f.write(raw_bytes)
            frame_count += 1

            if frame_count % 100 == 0 or frame_count == total_frames:
                print(f"    Processed {frame_count}/{total_frames} frames...")

    cap.release()
    print(f"[+] Successfully compiled video! Final size: {os.path.getsize(output_path) / (1024*1024):.2f} MB")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 preprocess_video.py <input_video.mp4> <output_video.bin>")
        sys.exit(1)
    preprocess_video(sys.argv[1], sys.argv[2])
