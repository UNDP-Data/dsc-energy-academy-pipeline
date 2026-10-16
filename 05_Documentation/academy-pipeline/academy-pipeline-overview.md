# Academy Pipeline Overview

This repository is the content processing pipeline for the Sustainable Energy Academy, part of the UNDP Sustainable Energy Digital Intelligence Platform. It converts Academy planning inputs and Figma-authored learning content into JSON and media artifacts consumed by downstream Academy frontend/backend systems.

## Purpose

The pipeline turns source material into deployable Academy content:

- Builds English module and lesson JSON from Figma documents and planning workbooks.
- Uploads and normalizes image assets to Azure Blob Storage.
- Generates chart JSON, DOCX review/editing exports, spellcheck/review reports, avatar scripts, and HeyGen-related avatar assets.
- Translates module structure, lessons, UI strings, and avatar scripts into configured target languages.
- Produces output folders that mirror frontend/API content bundles.

## How Figma Content Becomes Frontend/Strapi-Ready JSON

The observed flow is:

1. `02_Inputs/data/SEA Table of Contents.xlsx` defines module, chapter, lesson, description, estimated time, and structure metadata.
2. `core-pipeline.ipynb` calls `sea_pipeline.core.runner`.
3. `structure_generation` writes `03_Outputs/SEA_Modules/en/module_structure.json`.
4. `figma_extraction_export` executes the refactored legacy extraction notebook snapshot at `01_Code/sea_pipeline/_legacy_notebooks/conversion-pipeline.json`.
5. Figma JSON is loaded from or downloaded into `02_Inputs/figma_jsons/figma_document1.json`, `figma_document2.json`, and `figma_document3.json`.
6. Entity models in `01_Code/entities` parse Figma pages, sections, frames, and named layers into lesson segment objects.
7. Lesson files are written to `03_Outputs/SEA_Modules/en/Module_<n>/<lesson_id>.json`.
8. Post-processing inserts next-lesson links, polls, AI avatar video segments, image-bank substitutions for learning objective/key takeaway cards, validation/sanitization, and audit outputs.
9. Translation stages write corresponding localized files under `03_Outputs/SEA_Modules/{fr,es,pt,ar,zh,ru}`.
10. Publication or handoff copies/uses these generated folders. The repository also contains `00_API/SEA_Modules`, which appears to be an API-ready mirror or downstream bundle; exact sync mechanism is Unknown / requires confirmation.

## Main Input Sources

- Figma file IDs from env vars `FIGMA_DOCUMENT_ID1`, `FIGMA_DOCUMENT_ID2`, `FIGMA_DOCUMENT_ID3`.
- Cached Figma JSON in `02_Inputs/figma_jsons/`.
- Table of contents workbook: `02_Inputs/data/SEA Table of Contents.xlsx`.
- Module/chapter details: `02_Inputs/data/Module-Chapter-Details.csv`.
- Photobank and matching inputs: `02_Inputs/data/photobank.csv`, `02_Inputs/piwigo.csv`.
- Quiz workbook: `02_Inputs/SEA Quizzes.xlsx`.
- CSV-driven polls workbook: `02_Inputs/SEA Polls.xlsx`.
- AI avatar mapping: `02_Inputs/SEA AI Avatars.csv`.
- Chart source files under `02_Inputs/Charts/`.
- Manual translation cache files under `02_Inputs/manual-translation-cache/`.
- Environment configuration in `01_Code/.env` or process environment.

## Main Output Artifacts

- English and translated modules: `03_Outputs/SEA_Modules/{en,fr,es,pt,ar,zh,ru}`.
- API/content mirror: `00_API/SEA_Modules/{en,fr,es,pt,ar,zh,ru}`.
- Lesson translation cache: `03_Outputs/Lesson_Translation/translations_cache.json`.
- UI translations: `03_Outputs/UI_Translations` when present.
- Charts: `03_Outputs/Charts/Auto Charts/LightMode` and `03_Outputs/Charts/Auto Charts/DarkMode` when generated.
- DOCX exports: `03_Outputs/SEA_Module_Docx`.
- Photo export logs: `03_Outputs/Photo_Export_Logs`.
- Review workbook/cache: `03_Outputs/Review/academy_review.xlsx`, `03_Outputs/Review/review_cache.json`.
- Spellcheck report: `03_Outputs/spellcheck_audit_report.csv`.
- Avatar artifacts/status: `03_Outputs/avatars`, including `ai_avatar_blob_status.csv`.
- All lesson IDs: `03_Outputs/all_lesson_ids.txt` and `00_API/all_lesson_ids.txt`.

## Relationship To Academy Frontend And Backend

The generated JSON is structured as modules, chapters, lessons, and ordered lesson `segments`. Segment `template_id` values map to frontend rendering components such as covers, text blocks, charts, infographics, videos, quizzes, polls, key concepts, and resources.

Observed backend/API relationship:

- `00_API/SEA_Modules` contains language-specific `module_structure.json` and lesson JSON files, suggesting an API-ready or frontend-ready copy.
- `00_API/SEA_Data` contains `sea_network_graph_config.json` and `interactive-functions.js`, suggesting additional frontend data assets.
- Direct Strapi sync code was not found in the inspected pipeline package. Backend/Strapi dependency for each schema is therefore marked Unknown / requires confirmation unless inferable from paths or naming.

## Relationship To Azure Blob Storage

Azure Blob Storage is used as the canonical media host for images, videos, resource thumbnails, and avatar outputs. Generated JSON references URLs like:

```text
https://sehseadata.blob.core.windows.net/images/Modules/Module_1/3605_621.webp
https://sehseadata.blob.core.windows.net/images/Resources/Module_4/resource-4521.webp
https://sehseadata.blob.core.windows.net/images/Avatars/en/1/Videos/Lesson-1.4.0_en.mp4
```

Photo export uses `SAS_URL` to list, upload, and check blobs. The photo pipeline avoids redundant uploads through existing blob listing, Figma `imageRef` cache comparison, and resumable journals under `03_Outputs/Photo_Export_Logs`.

## Driver Notebooks

- `01_Code/core-pipeline.ipynb`: English structure generation, Figma extraction/export, AI avatar tagging, lesson ID export, sanitization, overflow audit.
- `01_Code/photo-export.ipynb`: image upload and infographic export to Azure Blob Storage.
- `01_Code/translation-pipeline.ipynb`: UI, module structure, lesson, manual cache, manual analysis, and avatar script translation.
- `01_Code/auxiliary-pipeline.ipynb`: charts, DOCX exports, spellcheck, indicator links, LLM polls, avatar operations, photo caption matching, resource image WebP backfill.
- `01_Code/review.ipynb`: Academy content QA/review workbook generation.

