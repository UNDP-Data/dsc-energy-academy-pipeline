# Academy Processing Workflow

## Execution Order

Recommended full content update order based on repository runners:

1. Run `01_Code/core-pipeline.ipynb`.
2. Run `01_Code/photo-export.ipynb`.
3. Run `01_Code/translation-pipeline.ipynb`.
4. Run `01_Code/auxiliary-pipeline.ipynb` for charts, DOCX, spellcheck, polls, avatars, and media helpers as needed.
5. Run `01_Code/review.ipynb` for QA workbook and spellcheck/review outputs.
6. Copy or sync generated artifacts to frontend/backend/API destinations. Exact deployment process is Unknown / requires confirmation.

## Core Pipeline

Notebook: `01_Code/core-pipeline.ipynb`

Runner: `sea_pipeline.core.runner`

Stages:

- `validate_env`: checks `FIGMA_TOKEN`, `FIGMA_DOCUMENT_ID1`, `FIGMA_DOCUMENT_ID2`, `FIGMA_DOCUMENT_ID3`.
- `structure_generation`: reads `02_Inputs/data/SEA Table of Contents.xlsx` and writes English `module_structure.json`.
- `figma_extraction_export`: loads/downloads Figma documents, parses Figma sections/frames, writes English lesson JSON, and applies learning-card image bank substitution.
- `ai_avatar_tagging`: inserts avatar `video` segments from `02_Inputs/SEA AI Avatars.csv`.
- `export_lesson_ids`: writes all lesson IDs.
- `sanitize_json_outputs`: replaces invalid numeric values such as NaN/Infinity.
- `overflow_audit`: estimates segment overflow using text template height rules.

Important options:

- `config.stage_options["figma_redownload"]`: controls whether Figma documents are redownloaded.
- `config.stage_options["image_bank_seed"]`: deterministic seed for learning objective/key takeaway image replacement.

## Photo Export Pipeline

Notebook: `01_Code/photo-export.ipynb`

Runner: `sea_pipeline.photo.runner`

Stages:

- `validate_env`: checks Figma and `SAS_URL`.
- `image_upload`: scans Figma pages for image rectangles and uploads WebP blobs.
- `infographic_export`: finds `infographic` frames and exports their single child frame as a WebP blob.

Important options:

- `photo_export_overwrite`: passed into upload logic.
- `photo_export_run_mode`: `standard` or `retry_missed`.
- `PHOTO_EXPORT_LOG_DIR`: defaults to `03_Outputs/Photo_Export_Logs`.

## Translation Pipeline

Notebook: `01_Code/translation-pipeline.ipynb`

Runner: `sea_pipeline.translation.runner`

Stages:

- `validate_env`: checks Azure OpenAI env vars.
- `module_structure_translation`: translates `module_structure.json` using cache-aware structure translation.
- `lesson_translation`: scans English lesson JSON and translates missing/changed lesson content.
- `ui_translations`: translates UI JSON bundles.
- `manual_translation_files`: exports unresolved cache entries for manual translators.
- `manual_translation_analysis`: analyzes manual translation completeness.
- `manual_translation_cache_import`: imports manual translation cache files into `translations_cache.json`.
- `avatar_script_translation`: translates generated avatar scripts.

Target languages default to:

```python
("fr", "es", "pt", "ar", "zh", "ru")
```

## Auxiliary Pipeline

Notebook: `01_Code/auxiliary-pipeline.ipynb`

Runner: `sea_pipeline.auxiliary.runner`

Stages:

- `charts_extract_and_merge`
- `charts_render`
- `docx_export_text`
- `docx_export_with_images`
- `resource_image_webp_backfill`
- `avatar_blob_status_csv`
- `spellcheck_audit`
- `indicator_links`
- `polls_generate`
- `polls_insert`
- `avatar_script_generation`
- `generate_payloads`
- `generate_videos`
- `list_blob_clips`
- `download_blob_clips`
- `add_backgrounds`

## Review Pipeline

Notebook: `01_Code/review.ipynb`

Runner: `sea_pipeline.review.runner`

Component-by-component stages:

- takeaways
- concepts
- resources
- quiz
- poll
- case study
- spellcheck audit
- workbook write
- completion summary

Review hard limits are stored in `01_Code/sea_pipeline/review/review_controls.csv`.

## Environment Variables

Required by observed stages:

- `FIGMA_TOKEN`
- `FIGMA_DOCUMENT_ID1`
- `FIGMA_DOCUMENT_ID2`
- `FIGMA_DOCUMENT_ID3`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`
- `SAS_URL`
- `HEYGEN_API_KEY`

Optional/feature-specific variables observed:

- `PIWIGO_BASE_URL`
- `PIWIGO_USERNAME`
- `PIWIGO_PASSWORD`

## Figma API Usage

Observed endpoints:

- Figma file download: `https://api.figma.com/v1/files/{key}`.
- Figma image export: `https://api.figma.com/v1/images/{file_id}` with params `ids`, `format`, and `scale`.

Auth header:

```text
X-Figma-Token: <FIGMA_TOKEN>
```

## Data Cleaning

Observed cleaning/normalization:

- Non-breaking spaces are normalized in module structure generation.
- Text templates strip leading/trailing whitespace and boundary line breaks.
- Exactly triple line breaks are normalized to double line breaks.
- Four or more line breaks are flagged in validation.
- AI keyword tags preserve matched source capitalization.
- Key takeaway first sentence can be split into title and remaining sentence(s) into description.
- Stray dash artifacts after the first takeaway sentence are removed.
- Invalid JSON numeric values are sanitized.
- Arabic translations receive `<bdi dir="ltr">...</bdi>` wrappers around acronym-like Latin tokens.

## Validation And Audits

Observed validation/audit mechanisms:

- Environment validation per notebook.
- Figma `TEXT_PATH` cleanup reporting.
- Missing layer warnings during frame parsing.
- JSON invalid-number scan and sanitize.
- Overflow audit based on text template height rules.
- Photo export missed CSV/JSON logs.
- Review workbook with deterministic and optional AI review checks.
- Spellcheck report.
- Resource image blob existence checks in review.

## Image Processing

Image processing includes:

- Generic Figma rectangle export to WebP.
- Infographic child-frame export to WebP.
- Resource image WebP backfill from sibling PNG blob.
- Learning objective/key takeaway image bank assignment from uploaded Academy images.
- Photo caption matching against Piwigo through auxiliary tooling.

## Chart Processing

Chart processing uses:

- `02_Inputs/Charts/Metadata/Charts Tracker.xlsx`
- `02_Inputs/Charts/Metadata/Charts Config.xlsx`
- `02_Inputs/Charts/Data/Charts/*.xlsx`
- `02_Inputs/Charts/Templates/*.json`

Outputs:

- Light mode chart JSON under `03_Outputs/Charts/Auto Charts/LightMode`.
- Dark mode chart JSON under `03_Outputs/Charts/Auto Charts/DarkMode`.

Figma `chart` frames reference these outputs by figure ID.

## Quiz Processing

Observed inputs and outputs:

- Input workbook: `02_Inputs/SEA Quizzes.xlsx`.
- Output template: `scored_quiz` segment inside module quiz files like `Module_1/1.-1.0.json`.
- Questions have IDs, prompt, `multiple`, options, solution IDs, and correct/wrong messages.
- Review controls require at least 10 questions, with 12 preferred.

Exact quiz workbook parsing code is in a legacy notebook snapshot and not fully typed in a module. Some details are Unknown / requires confirmation.

## Key Concept And Resource Integration

Key concepts are parsed from Figma `key_concepts` frames and written as glossary-like concept objects.

Key resources are parsed from Figma/resource cards and enriched from table-of-contents data. The pipeline has a specific resource-link helper and tests around using `Resource Link` rather than source fields.

Resource images are expected under Azure `images/Resources/...` URLs and can be checked/backfilled with the auxiliary/review pipelines.

## Output Publication

Observed publication-style folders:

- `03_Outputs/SEA_Modules`
- `00_API/SEA_Modules`
- `00_API/SEA_Data`

The exact command or process that copies from `03_Outputs` to `00_API`, Strapi, or frontend deployment is Unknown / requires confirmation.

