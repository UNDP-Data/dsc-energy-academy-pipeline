# Technical Documentation: AI Avatar Generation Pipeline

## Overview

This pipeline automates the generation of AI avatar videos using the HeyGen API. It processes lesson scripts in multiple languages, generates video payloads, manages video generation through the HeyGen API, and handles Azure blob storage for video distribution.

## Architecture

The pipeline consists of 6 Python scripts that must be executed sequentially:

1. `split_avatar_scripts.py` - Script preprocessing
2. `generate_payloads_avatars.py` - Payload generation
3. `generate_avatars_heygen.py` - Video generation and tracking
4. `list_avatar_clips_in_azure_blob.py` - Storage verification (optional)
5. `download_avatar_clips_from_azure_blob.py` - Local download (optional)
6. `add_background_avatars.py` - Background replacement (optional)

---

## 1. split_avatar_scripts.py

### Purpose
Splits Word document scripts that exceed HeyGen's 1500-character limit into multiple parts.

### Input
- **Location**: `../../02_Inputs/avatars/.../Module X/` folders
- **Format**: `.docx` files named `{Lesson}-{Language}.docx`
- **Structure**: Word documents containing lesson scripts

### Processing Logic
```python
def split_paragraphs(doc):
    # Extracts non-empty paragraphs from document
    return [p.text for p in doc.paragraphs if p.text.strip()]
```

**Algorithm**:
1. Walks through all Module folders recursively
2. Identifies `.docx` files without `_` suffix (avoids re-splitting)
3. Reads all paragraphs from document
4. Calculates split point at approximately 50% of total characters
5. Divides paragraphs into two parts at the calculated index

### Output
- **Location**: Same directory as input files
- **Format**: Two new `.docx` files
  - `{original_name}_1.docx` - First half
  - `{original_name}_2.docx` - Second half
- **Behavior**: Original file remains unchanged

### Key Functions
- `split_paragraphs(doc)`: Extracts text paragraphs from Word document
- `save_docx(paragraphs, filepath)`: Creates new Word document from paragraph list

### Dependencies
- `python-docx`: Word document manipulation
- `os`: File system operations

---

## 2. generate_payloads_avatars.py

### Purpose
Generates JSON payloads for HeyGen API by matching Excel data with HeyGen resources (avatars, voices, locales, assets).

### Input Files

#### Primary Dataset
- **Path**: `../../02_Inputs/avatars/Avatars.xlsx`
- **Required Columns**:
  - `Lesson`: Lesson identifier (e.g., "1.0.-1")
  - `Language`: Language code (e.g., "en", "ru")
  - `Part`: Script part number (1 or 2)
  - `Name`: Avatar name
  - `Voice`: Voice name
  - `Gender`: Voice gender
  - `Accent`: Voice accent locale
  - `Background`: Background asset name

#### Script Files
- **Path**: `../../03_Outputs/avatars/avatar_scripts/Module X/`
- **Naming**: `{Lesson}-{Language}_{Part}.docx`
- **Content**: Lesson script text (≤1500 characters)

#### Payload Template
- **Path**: `../../02_Inputs/avatars/payload_template.json`
- **Structure**: HeyGen API v2 video generation template
- **Placeholders**: Fields to be populated with dynamic values

### Processing Flow

#### Step 1: Fetch HeyGen Resources
```python
get_avatars(api_key, path_avatars)  # Fetch available avatars
get_voices(api_key, path_voices)    # Fetch available voices
get_locales(api_key, path_locales)  # Fetch supported locales
get_assets(api_key, path_assets)    # Fetch background assets
```

**API Endpoints**:
- Avatars: `https://api.heygen.com/v2/avatars`
- Voices: `https://api.heygen.com/v2/voices`
- Locales: `https://api.heygen.com/v2/voices/locales`
- Assets: `https://api.heygen.com/v1/asset/list` (paginated)

**Output**: JSON files saved to `../../03_Outputs/avatars/`:
- `avatars.json`
- `voices.json`
- `locales.json`
- `assets.json`

#### Step 2: Resource Matching
```python
def find_avatar_id(name):
    # Matches avatar name (case-insensitive) to avatar_id
    
def find_voice_id(voice_name, language, gender):
    # Matches voice name (case-insensitive) to voice_id
    
def find_locale_id(accent):
    # Matches accent string to locale code
    
def find_asset_id(asset_name):
    # Matches background name to asset_id
```

#### Step 3: Script Loading
```python
def load_script(row, path_scripts):
    # Constructs path: Module {first_char}/Lesson-Language_Part.docx
    # Reads Word document and joins paragraphs
    # Returns "NO SCRIPT FOUND" if file missing
```

#### Step 4: Payload Generation
```python
def generate_video_payloads_from_template(df, avatars_json, voices_json, 
                                          locales_json, assets, template, 
                                          path_scripts):
```

**For each Excel row**:
1. Look up avatar_id, voice_id, locale_id, asset_id
2. Load corresponding script text
3. Validate all required data exists
4. Deep copy template
5. Populate template fields:
   - `video_inputs[0].character.avatar_id`
   - `video_inputs[0].voice.voice_id`
   - `video_inputs[0].voice.input_text`
   - `video_inputs[0].voice.locale` (if not "Original")
   - `video_inputs[0].background.video_asset_id`
6. Skip if any validation fails (prints warnings)

### Output
- **Location**: `../../03_Outputs/avatars/payloads/`
- **Format**: Individual JSON files per lesson/language/part
- **Naming**: `{Lesson}_{Language}_{Part}.json`
- **Structure**:
```json
{
  "lesson": "1.0.-1",
  "language": "en",
  "part": 1,
  "payload": {
    // HeyGen API payload structure
  }
}
```

### Validation Rules
- Avatar ID must exist
- Voice ID must exist
- Locale ID must exist (or "Original")
- Asset ID must exist
- Script file must exist
- Script text must be non-empty
- Script length must be ≤1500 characters

Any validation failure causes the script to skip that entry and print a warning.

### Key Functions
- `load_json_file(path)`: Generic JSON loader with error handling
- `load_payload_template(path)`: Loads HeyGen template
- `save_payloads(payloads, folder)`: Saves individual payload JSON files

### Dependencies
- `pandas`: Excel file reading
- `requests`: API calls
- `python-docx`: Script loading
- `json`: JSON manipulation
- `dotenv`: Environment variable loading

---

## 3. generate_avatars_heygen.py

### Purpose
Submits payloads to HeyGen API, monitors video generation progress, and uploads completed videos to Azure blob storage.

### Input
- **Payloads**: `../../03_Outputs/avatars/payloads/*.json`
- **Dataset**: `../../02_Inputs/avatars/Avatars.xlsx` (for status tracking)
- **Environment Variables**:
  - `HEYGEN_API_KEY`: HeyGen API authentication
  - `SAS_URL`: Azure blob storage SAS URL

### Processing Flow

#### Step 1: Load Payloads
```python
def load_payloads(folder):
    # Reads all JSON files from payloads folder
    # Parses filename to extract lesson, language, part
    # Returns list of payload objects
```

**Filename Parsing**: `{Lesson}_{Language}_{Part}.json` → splits on first 2 underscores

#### Step 2: Check Generation Status
```python
# Skip if already generated
mask = (df['Lesson'] == lesson) & 
       (df['Language'] == language) & 
       (df['Part'].astype(str) == str(part))
if (df.loc[mask, 'Status'] == 'generated').any():
    continue
```

#### Step 3: Generate Video
```python
def generate_heygen_video(api_key: str, item: dict) -> dict:
```

**API Request**:
- **Endpoint**: `https://api.heygen.com/v2/video/generate`
- **Method**: POST
- **Headers**:
  - `X-Api-Key`: API key
  - `Content-Type`: application/json
- **Body**: Payload from JSON file

**Response Handling**:
```python
{
    "lesson": "1.0.-1",
    "language": "en",
    "part": 1,
    "video_id": "abc123..."  # or "error": "message"
}
```

#### Step 4: Monitor Video Status
```python
def wait_for_video_completion(api_key: str, video_id: str, 
                               poll_interval: int = 60, 
                               max_retries: int = 30) -> dict:
```

**Polling Configuration**:
- **Default interval**: 30 seconds (script overrides to 30)
- **Max retries**: 120 (script override from 30)
- **Total max wait**: 60 minutes (120 × 30s)

**API Request**:
- **Endpoint**: `https://api.heygen.com/v1/video_status.get?video_id={video_id}`
- **Method**: GET
- **Headers**: `X-Api-Key`, `Accept: application/json`

**Status Values**:
- `pending`, `waiting`, `processing` → Continue polling
- `completed` → Extract `video_url` and return success
- `failed` → Extract error message and return failure
- Other → Log warning and continue polling

**Response Structure**:
```python
{
    "status": "completed",
    "video_url": "https://..."
}
# or
{
    "status": "failed",
    "error": "Error message"
}
# or
{
    "status": "timeout",
    "error": "Video generation timed out."
}
```

#### Step 5: Upload to Azure
```python
async def upload_video_to_azure(video_url: str, blob_name: str) -> str:
```

**Process**:
1. Download video from HeyGen URL using `aiohttp`
2. Read video data into memory (timeout: 300s)
3. Get Azure blob client from SAS URL
4. Upload with:
   - `overwrite=True`
   - `content_type="video/mp4"`
5. Return Azure blob URL (without SAS token)

**Blob Naming**:
```python
def format_video_blob_name(lesson: str, language: str, part: str) -> str:
    safe_lesson = lesson.replace(" ", "_").replace("/", "-")
    safe_language = language.replace(" ", "_")
    return f"AI_Avatars/Lesson-{safe_lesson}_{safe_language}_{part}.mp4"
```

#### Step 6: Update Excel Status
```python
df.loc[(df['Lesson'] == lesson) & 
       (df['Language'] == language) & 
       (df['Part'].astype(str) == str(part)), 
       'Status'] = 'generated'
df.to_excel(path_dataset, index=False)
```

### Error Handling

**Generation Errors**:
- API request failures → Log error, skip video
- Invalid JSON response → Log error, skip video
- No video_id in response → Log error, skip video

**Status Polling Errors**:
- Request failures → Return failed status
- JSON parsing errors → Return failed status
- Timeout (120 retries) → Return timeout status

**Upload Errors**:
- Download failures → Log HTTP status, skip video
- Azure upload failures → Log exception, skip video

### Azure Configuration
```python
def get_container_client():
    # Creates Azure ContainerClient from SAS URL
    # Supports optional insecure SSL for testing
```

### Key Functions
- `load_payloads(folder)`: Loads and parses all payload files
- `generate_heygen_video(api_key, item)`: Submits video generation request
- `wait_for_video_completion(...)`: Polls until complete/failed/timeout
- `upload_video_to_azure(video_url, blob_name)`: Downloads and uploads to Azure
- `download_and_upload_video(...)`: Wrapper combining upload with blob naming

### Dependencies
- `pandas`: Excel status tracking
- `requests`: Synchronous API calls
- `aiohttp`: Async video download
- `asyncio`: Async execution
- `azure.storage.blob.aio`: Async Azure upload
- `ssl`: Optional SSL configuration
- `dotenv`: Environment variables

### Main Execution
```python
async def main():
    # Validates environment variables
    # Loads Excel and payloads
    # Iterates through payloads
    # Generates, waits, uploads each video
    # Updates Excel status after each success
```

---

## 4. list_avatar_clips_in_azure_blob.py

### Purpose
Lists all video files in the Azure blob storage container for verification.

### Input
- **Environment Variable**: `SAS_URL` from `.env`

### Processing
```python
container_client = ContainerClient.from_container_url(sas_url)
for blob in container_client.list_blobs(name_starts_with="AI_Avatars/"):
    print(f"- {blob.name}")
```

### Output
- Console output listing all blob names under `AI_Avatars/` prefix
- Format: `AI_Avatars/Lesson-X_lang_part.mp4`

### Use Case
Verify which videos have been successfully uploaded to Azure storage.

### Dependencies
- `azure.storage.blob`: Azure SDK
- `dotenv`: Environment variables

---

## 5. download_avatar_clips_from_azure_blob.py

### Purpose
Downloads all video files from Azure blob storage to local filesystem.

### Input
- **Environment Variable**: `SAS_URL` from `.env`
- **Azure Path**: `AI_Avatars/*.mp4` (and other video formats)

### Processing
```python
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm")

for blob in container_client.list_blobs(name_starts_with="AI_Avatars/"):
    if blob.name.lower().endswith(VIDEO_EXTENSIONS):
        blob_name = blob.name.split("/")[-1]  # Extract filename
        local_path = os.path.join(download_folder, blob_name)
        
        if os.path.exists(local_path):
            continue  # Skip existing files
        
        blob_client = container_client.get_blob_client(blob)
        data = blob_client.download_blob()
        # Write to local file
```

### Output
- **Location**: `../../03_Outputs/avatars/downloads/`
- **Format**: Video files (`.mp4`, etc.)
- **Naming**: Original blob filename (e.g., `Lesson-1.0.-1_en_1.mp4`)

### Features
- Skips already downloaded files
- Supports multiple video formats
- Creates download directory if missing

### Dependencies
- `azure.storage.blob`: Azure SDK (synchronous)
- `dotenv`: Environment variables

---

## 6. add_background_avatars.py

### Purpose
Replaces green-screen backgrounds in avatar videos with custom backgrounds using chroma key compositing.

### Input Files

#### Avatar Videos
- **Location**: `../../03_Outputs/avatars/downloads/`
- **Format**: `.mp4` files with green-screen background
- **Naming**: `Lesson-{Lesson}_{Language}_{Part}.mp4`

#### Background Videos
- **Location**: `../../02_Inputs/avatars/backgrounds/`
- **Format**: `.mp4` files
- **Naming**: `{BackgroundName}.mp4`

#### Excel Mapping
- **Path**: `../../02_Inputs/avatars/Avatars.xlsx`
- **Purpose**: Maps lesson/language/part to background name

### Processing Flow

#### Step 1: Parse Filename
```python
def lookup_background(entry_string: str, df):
    pattern = r"Lesson-(?P<lesson>(?:-?\d+\.)*-?\d+)_(?P<lang>[a-zA-Z]+)_(?P<part>\d+)"
    # Extracts: lesson, language, part
```

**Example**: `Lesson-1.0.-1_ru_1` → `lesson="1.0.-1"`, `lang="ru"`, `part=1`

#### Step 2: Excel Lookup
```python
row = df[
    (df["Lesson"] == lesson) &
    (df["Language"] == language) &
    (df["Part"] == part)
]
return row.iloc[0]["Background"]
```

#### Step 3: Chroma Key Processing
```python
def chroma_key_replace_video_bg(
    input_path,
    bg_video_path,
    output_path,
    key_color_hex="#04f404",  # Green screen color
    threshold=180,
    smoothing_erode=5,
    smoothing_distance=5,
    temporal_smoothing=0.8
):
```

**Algorithm**:

1. **Initialize Video Captures**:
   - Foreground (avatar with green screen)
   - Background (replacement video)
   - Output writer (temporary file)

2. **For Each Frame**:
   
   a. **Read Frames**:
   - Foreground frame
   - Background frame (loops if shorter)
   - Resize background to match foreground dimensions

   b. **Calculate Color Distance**:
   ```python
   diff = np.linalg.norm(frame_fg.astype(np.float32) - key_color_bgr, axis=2)
   fg_mask = np.uint8(diff >= threshold) * 255
   ```
   - Computes Euclidean distance from each pixel to key color
   - Creates binary mask (0=background, 255=foreground)

   c. **Mask Refinement**:
   ```python
   # Edge smoothing
   fg_mask = cv2.erode(fg_mask, kernel)
   fg_mask = cv2.GaussianBlur(fg_mask, kernel)
   
   # Distance-based feathering
   dist = cv2.distanceTransform(inv_mask, cv2.DIST_L2, 5)
   dist = np.clip(dist / smoothing_distance, 0, 1)
   ```

   d. **Temporal Smoothing**:
   ```python
   mask_float = temporal_smoothing * prev_mask_float + 
                (1 - temporal_smoothing) * current_mask
   ```
   - Reduces flickering between frames
   - Higher value = more smoothing (0.6 used in script)

   e. **Green Spill Removal**:
   ```python
   spill_mask = 1 - mask_float
   frame_fg_float[:, :, 1] *= (1 - 0.5 * spill_mask)
   ```
   - Reduces green reflection on avatar edges

   f. **Composite**:
   ```python
   result = frame_fg * mask + frame_bg * (1 - mask)
   ```

3. **Audio Merging**:
   ```bash
   ffmpeg -i temp_video.mp4 -i input_path \
          -c:v copy -c:a aac \
          -map 0:v:0 -map 1:a:0 \
          output_path
   ```
   - Copies processed video stream
   - Copies audio from original avatar video
   - Removes temporary video file

### Output
- **Location**: `../../03_Outputs/avatars/downloads_with_backgrounds/`
- **Format**: `.mp4` files with replaced backgrounds
- **Naming**: Same as input files

### Parameters Explained

- **key_color_hex**: RGB hex code of green screen (default: `#04f404`)
- **threshold**: Color distance threshold for masking (higher = more strict)
- **smoothing_erode**: Kernel size for edge erosion/blur
- **smoothing_distance**: Distance transform range for feathering
- **temporal_smoothing**: Frame-to-frame smoothing factor (0-1)
- **debug_mask**: If True, overlays mask visualization

### Main Pipeline
```python
def process_avatar_videos_with_backgrounds():
    # Loads Excel
    # Iterates through all MP4 files in downloads/
    # Looks up background name
    # Processes video with chroma key
    # Saves to downloads_with_backgrounds/
```

### Dependencies
- `opencv-python` (cv2): Video processing and chroma key
- `numpy`: Array operations
- `pandas`: Excel reading
- `tqdm`: Progress bars
- `subprocess`: FFmpeg execution for audio merging

---

## Environment Configuration

### Required `.env` File
Located at parent directory level (`../.env`):

```env
HEYGEN_API_KEY=your_heygen_api_key_here
SAS_URL=https://your_storage_account.blob.core.windows.net/container?sas_token
```

### HeyGen API Key
- Obtain from HeyGen dashboard
- Used for authentication in all API calls
- Required for scripts 2 and 3

### Azure SAS URL
- Shared Access Signature URL for blob container
- Must have read/write/list permissions
- Required for scripts 3, 4, 5

---

## Data Flow Diagram

```
Excel Dataset → [generate_payloads] → JSON Payloads
                     ↓
Script Files ────────┘
                     
JSON Payloads → [generate_avatars] → HeyGen API
                     ↓
HeyGen Videos → Azure Blob Storage
                     ↓
         [optional: download_clips]
                     ↓
         Local Video Files
                     ↓
         [optional: add_background]
                     ↓
         Videos with Custom Backgrounds
```

---

## Debugging Tips

### Enable Debug Output
```python
# Script 3: generate_avatars_heygen.py
# Set max_retries lower for testing:
wait_for_video_completion(api_key, video_id, poll_interval=10, max_retries=6)

# Script 6: add_background_avatars.py
# Enable mask visualization:
chroma_key_replace_video_bg(..., debug_mask=True)
```

### Check Intermediate Files
- Payloads: `03_Outputs/avatars/payloads/*.json`
- HeyGen resources: `03_Outputs/avatars/{avatars,voices,locales,assets}.json`
- Excel status column: Check for "generated" values

### Common Issues
1. **Script length errors**: Run script 1 to split long scripts
2. **Missing voice/avatar**: Check HeyGen resource JSON files
3. **Upload failures**: Verify SAS URL has write permissions
4. **Green screen not removed**: Adjust `threshold` parameter in script 6

---

## Security Considerations

- Store API keys in `.env` file (never commit to version control)
- SAS URLs should have minimal required permissions
- SAS URLs should have expiration dates
- Consider IP restrictions on SAS URLs for production
