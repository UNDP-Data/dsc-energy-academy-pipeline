# AI Avatar Workflow

## Overview

AI avatar workflows are split between:

- Lesson JSON tagging in the core pipeline.
- Script generation and HeyGen operations in the auxiliary pipeline.
- Blob status checks against Azure.

Existing detailed documentation:

- `05_Documentation/avatars/avatars_technical_documentation.md`
- `05_Documentation/avatars/avatars_user_guide.md`

## Input Scripts And Metadata

Observed inputs:

- `02_Inputs/SEA AI Avatars.csv`: used by core `ai_avatar_tagging` and avatar blob status checks.
- `02_Inputs/avatars/Avatars.xlsx`: used by HeyGen payload generation.
- `02_Inputs/avatars/Avatars-test.xlsx`: test/avatar input workbook.
- `02_Inputs/avatars/payload_template.json`: HeyGen payload template.
- `02_Inputs/avatars/avatars.json`, `voices.json`, `locales.json`, `assets.json`: HeyGen resource metadata.
- Generated avatar scripts under `03_Outputs/avatars/avatar_scripts` or related output paths depending on legacy notebook/script stage.

Exact canonical script input/output folder is inconsistent across legacy docs and code snapshots; Unknown / requires confirmation.

## Lesson JSON Avatar Tagging

Core stage:

```python
run_core_stage(config, "ai_avatar_tagging")
```

Observed behavior:

- Reads `02_Inputs/SEA AI Avatars.csv`.
- Expects at least columns `Lesson` and `Language`.
- Builds lesson JSON path `03_Outputs/SEA_Modules/{language}/Module_{module}/{lesson_id}.json`.
- Appends or manages a `video` segment for the lesson.
- Avatar video URL pattern:

```text
https://sehseadata.blob.core.windows.net/images/Avatars/{language}/{module}/Videos/Lesson-{lesson_id}_{language}.mp4
```

- Poster URL pattern:

```text
https://sehseadata.blob.core.windows.net/images/Avatars/{language}/{module}/Photos/Lesson-{lesson_id}_{language}.webp
```

## Payload Generation

Auxiliary stage:

```python
run_auxiliary_stage(config, "generate_payloads")
```

Wrapper:

```text
01_Code/sea_pipeline/auxiliary/avatars/heygen.py
```

Subprocess script:

```text
01_Code/avatars/generate_payloads_avatars.py
```

Observed from existing avatar docs:

- Reads `02_Inputs/avatars/Avatars.xlsx`.
- Reads scripts from generated script DOCX files.
- Resolves avatar, voice, locale, and background assets.
- Writes payload JSON under `03_Outputs/avatars/payloads`.

## HeyGen API Usage

Auxiliary stage:

```python
run_auxiliary_stage(config, "generate_videos")
```

Subprocess script:

```text
01_Code/avatars/generate_avatars_heygen.py
```

Environment variable:

```text
HEYGEN_API_KEY
```

Observed endpoint from existing docs:

```text
https://api.heygen.com/v2/video/generate
```

The current wrapper only runs scripts and captures stdout/stderr; detailed API error handling lives in the underlying script and existing avatar docs.

## Output Storage

Observed Azure naming:

Final avatar videos:

```text
Avatars/{language}/{module}/Videos/Lesson-{lesson_id}_{language}.mp4
```

Intermediate HeyGen videos:

```text
AI_Avatars/Lesson-{lesson_id}_{language}_{part}.mp4
```

Status CSV output:

```text
03_Outputs/avatars/ai_avatar_blob_status.csv
```

Columns:

- `lesson_id`
- `status`

## Tracker Files

Observed tracker/status inputs and outputs:

- `02_Inputs/SEA AI Avatars.csv`
- `02_Inputs/avatars/Avatars.xlsx`
- `03_Outputs/avatars/ai_avatar_blob_status.csv`

Other tracker files may be written by `generate_avatars_heygen.py`; exact paths are Unknown / requires confirmation without deeper script-specific run inspection.

## Error Handling

Observed handling:

- Missing `SAS_URL` raises an error for blob status checks.
- Missing `Lesson` or `Language` columns in avatar status input raises an error.
- Blob status classifies lessons as `complete`, `partial`, or `missing`.
- Subprocess stages return status `ok` or `error` based on return code and include stdout/stderr.
- HeyGen API failures are handled in scripts under `01_Code/avatars`; see existing avatar technical docs.

