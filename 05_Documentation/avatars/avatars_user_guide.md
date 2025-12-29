# User Guide: AI Avatar Generation Pipeline

## Introduction

This pipeline automates the creation of AI-powered avatar videos for educational lessons in multiple languages. The system takes lesson scripts, matches them with appropriate avatars and voices, generates videos through the HeyGen API, and stores them in Azure cloud storage.

---

## Prerequisites

### Required Software
- Python 3.8 or higher
- FFmpeg (for background replacement feature)
- Microsoft Excel or LibreOffice Calc

### Required Accounts
- **HeyGen Account**: For AI avatar video generation
  - Sign up at [heygen.com](https://heygen.com)
  - Obtain API key from account settings
- **Azure Storage Account**: For video storage
  - Create a blob storage container
  - Generate a SAS (Shared Access Signature) URL with read/write permissions

### Python Packages
Install required packages using:
```bash
pip install pandas requests python-docx openpyxl python-dotenv azure-storage-blob opencv-python numpy tqdm aiohttp
```

---

## Setup

### 1. Environment Configuration

Create a `.env` file in the parent directory with your credentials:

```env
HEYGEN_API_KEY=your_api_key_here
SAS_URL=https://yourstorage.blob.core.windows.net/container?sas_token_here
```

**Important**: Never share or commit this file to version control.

### 2. Folder Structure

Ensure the following folder structure exists:

```
project/
├── .env
├── 02_Inputs/
│   └── avatars/
│       ├── Avatars.xlsx
│       ├── payload_template.json
│       ├── backgrounds/
│       │   ├── background1.mp4
│       │   └── background2.mp4
│       └── .../
│           ├── Module 1/
│           │   ├── 1.0.-1-en.docx
│           │   ├── 1.0.-1-ru.docx
│           │   └── ...
│           └── Module 2/
│               └── ...
└── 03_Outputs/
    └── avatars/
        ├── payloads/
        ├── downloads/
        └── downloads_with_backgrounds/
```

### 3. Prepare Your Data

#### Excel File (`Avatars.xlsx`)
Create an Excel file with the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| Lesson | Lesson identifier | 1.0.-1 |
| Language | Language code | en |
| Part | Script part number | 1 |
| Name | Avatar name from HeyGen | Anna |
| Voice | Voice name from HeyGen | Joanna |
| Gender | Voice gender | female |
| Accent | Voice accent | Original |
| Background | Background video name | office |
| Status | Generation status (leave empty) | |

#### Script Files
- Create Word documents (`.docx`) for each lesson
- Place them in appropriate Module folders
- Name them: `{Lesson}-{Language}.docx`
- Example: `1.0.-1-en.docx` for Lesson 1.0.-1 in English

#### Background Videos (Optional)
- If using custom backgrounds, place `.mp4` files in the `backgrounds/` folder
- Name them to match the "Background" column in your Excel file
- These are used only if avatars are generated with green screens

---

## Workflow

### Step 1: Split Long Scripts

**Purpose**: HeyGen has a 1500-character limit per video. This step automatically splits longer scripts into multiple parts.

**When to run**: Run this whenever you add new scripts or update existing ones.

**Command**:
```bash
python split_avatar_scripts.py
```

**What it does**:
- Scans all Module folders for Word documents
- Identifies scripts that need splitting (without `_1` or `_2` suffix)
- Splits them approximately in half at paragraph boundaries
- Creates two new files: `{original}_1.docx` and `{original}_2.docx`

**Expected output**:
```
💾 Saved split file: ../../02_Inputs/avatars/.../Module 1/1.0.-1-en_1.docx
💾 Saved split file: ../../02_Inputs/avatars/.../Module 1/1.0.-1-en_2.docx
```

**After running**:
- Update your Excel file to include Part 2 entries for split scripts
- Copy the row and change the Part column from 1 to 2

---

### Step 2: Generate Payloads

**Purpose**: Creates the JSON configurations needed to generate each video.

**When to run**: After preparing all scripts and updating the Excel file.

**Command**:
```bash
python generate_payloads_avatars.py
```

**What it does**:
1. Fetches available avatars, voices, and backgrounds from HeyGen
2. Reads your Excel file
3. Matches each row with the appropriate resources
4. Loads the script text from Word documents
5. Creates individual JSON payload files

**Expected output**:
```
Avatars Response Status Code: 200
Voices Response Status Code: 200
Locales Response Status Code: 200
Assets Response Status Code: 200
Processing row: 1.0.-1, en, 1
💾 Saved payload for Lesson: '1.0.-1', Language: 'en', Part: '1' → ...
```

**Warnings to watch for**:
- `[WARN] Avatar ID not found`: Check avatar name spelling
- `[WARN] Voice ID not found`: Check voice name spelling
- `[WARN] No script file found`: Ensure script file exists and is named correctly
- `[WARN] Script too long`: Run Step 1 to split the script

**Result**: JSON files created in `03_Outputs/avatars/payloads/`

---

### Step 3: Generate Videos

**Purpose**: Submits video generation requests to HeyGen and uploads completed videos to Azure.

**When to run**: After generating payloads.

**Command**:
```bash
python generate_avatars_heygen.py
```

**What it does**:
1. Loads all payload files
2. Checks which videos are already generated (via Excel Status column)
3. For each new video:
   - Submits generation request to HeyGen
   - Monitors progress (checks every 30 seconds)
   - Downloads completed video
   - Uploads to Azure blob storage
   - Updates Excel Status to "generated"

**Expected output per video**:
```
▶️ Processing Lesson [1.0.-1] | Language [en] | Part [1]...
✅ Success for Lesson [1.0.-1] | Language [en] | Part [1]: Video ID = abc123...
[Attempt 1] Video ID abc123... status: processing
[Attempt 2] Video ID abc123... status: processing
...
✅ Video completed! URL: https://...
⬇️ Downloading and uploading to Azure: AI_Avatars/Lesson-1.0.-1_en_1.mp4
✅ Upload complete: https://yourstorage.blob.core.windows.net/...
🎉 Video successfully uploaded to Azure.
```

**Duration**: 
- 3-10 minutes per video depending on length and complexity
- For 20 videos: expect 1-3 hours total

**If interrupted**:
- The script can be safely restarted
- It automatically skips videos already marked as "generated" in Excel
- Already uploaded videos won't be regenerated

**Monitoring progress**:
- Watch the console output
- Check the Status column in Excel (updates after each successful upload)
- Use Step 4 to verify uploaded videos

---

### Step 4: Verify Uploaded Videos (Optional)

**Purpose**: Lists all videos that have been uploaded to Azure storage.

**When to run**: After Step 3 to confirm successful uploads.

**Command**:
```bash
python list_avatar_clips_in_azure_blob.py
```

**Expected output**:
```
📂 Listing contents in 'AI_Avatars/' folder:
- AI_Avatars/Lesson-1.0.-1_en_1.mp4
- AI_Avatars/Lesson-1.0.-1_en_2.mp4
- AI_Avatars/Lesson-1.0.-1_ru_1.mp4
...
```

---

### Step 5: Download Videos Locally (Optional)

**Purpose**: Downloads all videos from Azure to your local machine.

**When to run**: 
- When you need to review videos locally
- Before running background replacement (Step 6)
- For backup purposes

**Command**:
```bash
python download_avatar_clips_from_azure_blob.py
```

**What it does**:
- Connects to Azure storage
- Lists all video files in the AI_Avatars folder
- Downloads each file that doesn't already exist locally
- Skips files that are already downloaded

**Expected output**:
```
🔥 Downloading video files from 'AI_Avatars/' folder...

⬇️  Downloading: Lesson-1.0.-1_en_1.mp4 ...
   ✔️ Saved to: ../../03_Outputs/avatars/downloads/Lesson-1.0.-1_en_1.mp4
✅ Skipping (already exists): Lesson-1.0.-1_en_2.mp4
...

🎉 All video downloads complete!
```

**Result**: Videos saved in `03_Outputs/avatars/downloads/`

---

### Step 6: Add Custom Backgrounds (Optional)

**Purpose**: Replaces green-screen backgrounds with custom background videos.

**When to use**: 
- Your avatars were generated with green-screen backgrounds
- You want to use custom backgrounds instead of HeyGen's default backgrounds

**Prerequisites**:
- Videos must be downloaded locally (Step 5)
- Background video files must be in `02_Inputs/avatars/backgrounds/`
- Excel file must have the correct Background column values

**Command**:
```bash
python add_background_avatars.py
```

**What it does**:
1. Reads each video file from downloads folder
2. Looks up the appropriate background from Excel
3. Uses chroma key technology to remove green screen
4. Composites the avatar onto the new background
5. Preserves the original audio
6. Saves the final video with the new background

**Expected output**:
```
📘 Loading Excel sheet...

🔍 Processing: Lesson-1.0.-1_ru_1
Processing row: 1.0.-1, ru, 1
Processing Lesson-1.0.-1_ru_1.mp4: 100%|██████████| 450/450 [01:23<00:00, 5.38it/s]
🎉 Final video saved: ../../03_Outputs/avatars/downloads_with_backgrounds/Lesson-1.0.-1_ru_1.mp4

✅ All videos processed with correct backgrounds.
```

**Duration**: 
- Depends on video length and your computer's processing power
- Approximately 2-5 minutes per minute of video

**Result**: Videos with custom backgrounds saved in `03_Outputs/avatars/downloads_with_backgrounds/`

---

## Common Workflows

### Workflow A: Generate Videos with HeyGen Backgrounds
Perfect for quick generation using HeyGen's built-in backgrounds.

1. Prepare scripts and Excel file
2. Run Step 1: Split scripts (if needed)
3. Run Step 2: Generate payloads
4. Run Step 3: Generate videos
5. Done! Videos are in Azure storage

### Workflow B: Generate Videos with Custom Backgrounds
For professional production with your own backgrounds.

1. Prepare scripts and Excel file
2. Set Background column to "greenscreen" or similar in Excel
3. Run Step 1: Split scripts (if needed)
4. Run Step 2: Generate payloads
5. Run Step 3: Generate videos
6. Run Step 5: Download videos
7. Run Step 6: Add custom backgrounds
8. Upload final videos back to Azure (manually)

### Workflow C: Add New Lessons
To add new lessons without regenerating everything.

1. Add new scripts to Module folders
2. Add new rows to Excel file
3. Leave Status column empty for new entries
4. Run Step 1: Split scripts (if needed)
5. Run Step 2: Generate payloads (regenerates all, but fast)
6. Run Step 3: Generate videos (automatically skips existing)

---

## Troubleshooting

### Issue: "Script too long" warning
**Solution**: Run Step 1 to split the script, then add Part 2 entry to Excel.

### Issue: "Avatar ID not found"
**Solution**: 
1. Check the avatar name spelling in Excel
2. Run Step 2 again - it saves available avatars to `03_Outputs/avatars/avatars.json`
3. Open that file and find the correct `avatar_name`
4. Update Excel with the exact spelling

### Issue: "Voice ID not found"
**Solution**: Similar to avatar issue - check `03_Outputs/avatars/voices.json` for correct voice names.

### Issue: Video generation fails or times out
**Solution**:
- Check your HeyGen account for quota/credits
- Verify the API key is correct in `.env`
- Try regenerating - script automatically skips successful videos
- Check HeyGen dashboard for error details

### Issue: Upload to Azure fails
**Solution**:
- Verify SAS URL has write permissions
- Check if SAS URL has expired
- Ensure container exists in Azure storage
- Test SAS URL using Azure Storage Explorer

### Issue: Background replacement looks poor
**Solution**:
- Adjust the `threshold` parameter in `add_background_avatars.py` (line 180)
- Higher value = more strict green screen removal
- Try values between 150-200
- Ensure lighting in original video is even

### Issue: Script can't find files
**Solution**:
- Double-check folder structure matches the documented structure
- Verify file names match exactly (case-sensitive on some systems)
- Ensure paths in scripts match your setup (they use relative paths)

---

## Tips and Best Practices

### Script Preparation
- Keep scripts conversational and natural
- Aim for 1200-1400 characters per part (leaves buffer under 1500 limit)
- Break at natural paragraph boundaries
- Test pronunciation of technical terms

### Voice Selection
- Match voice gender to avatar
- Choose voices appropriate for your target audience
- Test different voices for the same script to find the best fit
- Consider accent preferences for international audiences

### Avatar Selection
- Use consistent avatars across a lesson series for branding
- Choose professional-looking avatars for educational content
- Consider diversity in avatar selection

### Background Selection
- Use backgrounds appropriate for lesson content
- Keep backgrounds simple to avoid distraction from the avatar
- Ensure sufficient contrast between avatar and background
- Test backgrounds with different lighting scenarios

### Batch Processing
- Generate in batches to monitor progress
- Run overnight for large batches
- Always check first few videos before generating large quantities

### Quality Control
- Download and review first video from each lesson
- Check audio clarity and synchronization
- Verify correct avatar-voice pairing
- Test on target platforms before full rollout

---

## Maintenance

### File Management
- Archive old scripts and payloads after successful generation
- Keep Excel file backed up
- Periodically clean up download folders
- Maintain version history of Excel configurations

### Security
- Rotate API keys every 6 months
- Regenerate SAS URLs with expiration dates
- Never commit `.env` file to version control
- Restrict Azure SAS URL to specific IP ranges in production

---

## Getting Help

### Log Files
All scripts print detailed progress to console. To save logs:
```bash
python generate_avatars_heygen.py > generation_log.txt 2>&1
```

### Excel Status Column
The Status column in your Excel file tracks which videos have been generated. Use this to:
- Monitor overall progress
- Identify failed videos (no "generated" status)
- Avoid regenerating existing videos

---

## Appendix: File Naming Conventions

### Script Files
- Format: `{Lesson}-{Language}_{Part}.docx`
- Example: `1.0.-1-en_1.docx`
- Lesson: Can contain dots and hyphens
- Language: 2-letter code (en, ru, de, etc.)
- Part: 1 or 2

### Video Files
- Format: `Lesson-{Lesson}_{Language}_{Part}.mp4`
- Example: `Lesson-1.0.-1_en_1.mp4`
- Note: "Lesson-" prefix added, dots/slashes sanitized

### Payload Files
- Format: `{Lesson}_{Language}_{Part}.json`
- Example: `1.0.-1_en_1.json`
- Used internally, not user-facing

---

## Quick Reference Commands

```bash
# Full workflow
python split_avatar_scripts.py
python generate_payloads_avatars.py
python generate_avatars_heygen.py

# Optional: Local processing
python download_avatar_clips_from_azure_blob.py
python add_background_avatars.py

# Verification
python list_avatar_clips_in_azure_blob.py
```

