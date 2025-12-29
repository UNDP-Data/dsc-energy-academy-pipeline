import os
import re
import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm
import subprocess


# ==============================
# Excel Lookup
# ==============================
def lookup_background(entry_string: str, df):
    """
    Parse an input like 'Lesson-1.0.-1_ru_1' and return the Background value.
    """

    pattern = r"Lesson-(?P<lesson>(?:-?\d+\.)*-?\d+)_(?P<lang>[a-zA-Z]+)_(?P<part>\d+)"
    match = re.match(pattern, entry_string)

    if not match:
        print(f"❌ Could not parse: {entry_string}")
        return None

    lesson = match.group("lesson")
    language = match.group("lang")
    part = int(match.group("part"))

    row = df[
        (df["Lesson"] == lesson) &
        (df["Language"] == language) &
        (df["Part"] == part)
    ]

    if row.empty:
        print(f"❌ No background found for: {entry_string}")
        return None

    return row.iloc[0]["Background"]




# ==============================
# Video Processing Core
# ==============================
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def chroma_key_replace_video_bg(
    input_path,
    bg_video_path,
    output_path,
    key_color_hex="#04f404",
    threshold=180,
    smoothing_erode=5,
    smoothing_distance=5,
    temporal_smoothing=0.8,
    debug_mask=False
):
    """Full chroma key pipeline (unchanged from your original)."""

    key_color_rgb = np.array(hex_to_rgb(key_color_hex))
    key_color_bgr = key_color_rgb[::-1]

    cap_fg = cv2.VideoCapture(input_path)
    cap_bg = cv2.VideoCapture(bg_video_path)

    if not cap_fg.isOpened():
        raise IOError("Cannot open input video: " + input_path)
    if not cap_bg.isOpened():
        raise IOError("Cannot open background video: " + bg_video_path)

    width = int(cap_fg.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap_fg.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap_fg.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap_fg.get(cv2.CAP_PROP_FRAME_COUNT))

    temp_video = "temp_video.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(temp_video, fourcc, fps, (width, height))

    prev_mask_float = None

    for _ in tqdm(range(total_frames), desc=f"Processing {os.path.basename(input_path)}"):
        ret_fg, frame_fg = cap_fg.read()
        ret_bg, frame_bg = cap_bg.read()
        if not ret_fg:
            break
        if not ret_bg:
            cap_bg.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret_bg, frame_bg = cap_bg.read()

        frame_bg = cv2.resize(frame_bg, (width, height))

        diff = np.linalg.norm(frame_fg.astype(np.float32) - key_color_bgr, axis=2)
        fg_mask = np.uint8(diff >= threshold) * 255

        if smoothing_erode > 0:
            kernel_size = (smoothing_erode | 1, smoothing_erode | 1)
            fg_mask = cv2.erode(fg_mask, np.ones(kernel_size, np.uint8))
            fg_mask = cv2.GaussianBlur(fg_mask, kernel_size, 0)

        if smoothing_distance > 0:
            inv_mask = 255 - fg_mask
            dist = cv2.distanceTransform(inv_mask, cv2.DIST_L2, 5)
            dist = np.clip(dist / smoothing_distance, 0, 1)
            fg_mask = fg_mask.astype(np.float32) * dist + fg_mask.astype(np.float32) * (1 - dist)
            fg_mask = np.clip(fg_mask, 0, 255).astype(np.uint8)

        mask_float = fg_mask.astype(np.float32) / 255.0
        if prev_mask_float is not None and temporal_smoothing > 0:
            mask_float = temporal_smoothing * prev_mask_float + (1 - temporal_smoothing) * mask_float
        prev_mask_float = mask_float

        spill_mask = 1 - mask_float
        frame_fg_float = frame_fg.astype(np.float32)
        frame_fg_float[:, :, 1] *= (1 - 0.5 * spill_mask)

        mask_3ch = cv2.merge([mask_float, mask_float, mask_float])
        result = frame_fg_float * mask_3ch + frame_bg.astype(np.float32) * (1 - mask_3ch)
        result = np.uint8(result)

        if debug_mask:
            overlay = cv2.addWeighted(result, 0.7, cv2.cvtColor(np.uint8(mask_float * 255), cv2.COLOR_GRAY2BGR), 0.3, 0)
            out.write(overlay)
        else:
            out.write(result)

    cap_fg.release()
    cap_bg.release()
    out.release()

    cmd = [
        "ffmpeg",
        "-y",
        "-i", temp_video,
        "-i", input_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        output_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(temp_video)

    print(f"🎉 Final video saved: {output_path}")



# ==============================
# Combined Pipeline
# ==============================
def process_avatar_videos_with_backgrounds(
    avatar_folder="../../03_Outputs/avatars/downloads",
    background_folder="../../02_Inputs/avatars/backgrounds",
    excel_path="../../02_Inputs/avatars/Avatars.xlsx",
    output_folder="../../03_Outputs/avatars/downloads_with_backgrounds",
    key_color_hex="#04f404"
):

    print("📘 Loading Excel sheet...")
    df = pd.read_excel(excel_path)

    os.makedirs(output_folder, exist_ok=True)

    video_files = [f for f in os.listdir(avatar_folder) if f.lower().endswith(".mp4")]

    for filename in video_files:
        entry_string = filename[:-4]  # remove .mp4
        print(f"\n🔍 Processing: {entry_string}")

        # 1 — Lookup background name
        bg_name = lookup_background(entry_string, df)
        if bg_name is None:
            print("Skipping due to missing background...")
            continue

        # Background file must be located in backgrounds/
        bg_video_path = os.path.join(background_folder, f"{bg_name}.mp4")

        if not os.path.exists(bg_video_path):
            print(f"❌ Background video not found: {bg_video_path}")
            continue

        input_path = os.path.join(avatar_folder, filename)
        output_path = os.path.join(output_folder, filename)

        # 2 — Process video
        chroma_key_replace_video_bg(
            input_path=input_path,
            bg_video_path=bg_video_path,
            output_path=output_path,
            key_color_hex=key_color_hex,
            threshold=180,
            smoothing_erode=5,
            smoothing_distance=5,
            temporal_smoothing=0.6,
            debug_mask=False
        )

    print("\n✅ All videos processed with correct backgrounds.")



# ==============================
# Run Pipeline
# ==============================
if __name__ == "__main__":
    process_avatar_videos_with_backgrounds()
