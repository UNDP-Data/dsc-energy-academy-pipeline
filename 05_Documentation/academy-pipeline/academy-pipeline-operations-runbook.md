# Academy Pipeline Operations Runbook

## Local Setup

1. Use Python 3.13 or the local environment already used by the notebooks.
2. Install dependencies needed by the stages you will run. Known packages include pandas, openpyxl, python-dotenv, openai, python-docx, pillow, azure-storage-blob, aiohttp, requests, beautifulsoup4, tiktoken, and pytest. Exact lockfile is not present; dependency pinning is Unknown / requires confirmation.
3. Create or update `01_Code/.env` with required secrets.
4. Open notebooks from `01_Code`.
5. Restart the notebook kernel after code changes or run cells that explicitly reload modules.

## Required Environment Variables

Core/photo:

- `FIGMA_TOKEN`
- `FIGMA_DOCUMENT_ID1`
- `FIGMA_DOCUMENT_ID2`
- `FIGMA_DOCUMENT_ID3`
- `SAS_URL`

Translation/review AI:

- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`

Avatar generation:

- `HEYGEN_API_KEY`
- `SAS_URL`

Optional photo caption matching:

- `PIWIGO_BASE_URL`
- `PIWIGO_USERNAME`
- `PIWIGO_PASSWORD`

## Full Content Update

Recommended sequence:

1. Update inputs in `02_Inputs`, including table of contents, quizzes, polls, charts, avatar mapping, and manual translation files as needed.
2. Run `core-pipeline.ipynb`:
   - validate env
   - structure generation
   - Figma extraction/export
   - AI avatar tagging
   - export lesson IDs
   - sanitization
   - overflow audit
3. Run `photo-export.ipynb`:
   - image upload
   - infographic export
4. Run `translation-pipeline.ipynb`:
   - module structure translation
   - lesson translation
   - UI translations if UI source exists
   - manual cache analysis/import if manual files are ready
   - avatar script translation if scripts are updated
5. Run `auxiliary-pipeline.ipynb` as needed:
   - chart extract/render before Figma chart extraction if chart JSON has changed
   - DOCX export for editing/review
   - spellcheck and indicator links
   - LLM polls
   - avatar scripts and HeyGen operations
   - resource WebP backfill
6. Run `review.ipynb`:
   - set `REVIEW_TEST_LESSON_COUNT` for test mode or `False` for full mode
   - choose `REVIEW_AI_MODE`: `off`, `critical`, or `full`
   - run component cells and write workbook

## Validating Outputs

Minimum checks:

- `03_Outputs/SEA_Modules/en/module_structure.json` exists and has 9 modules.
- Expected lesson JSON files exist under `03_Outputs/SEA_Modules/en/Module_*`.
- Target-language folders contain translated `module_structure.json` and lesson files.
- `03_Outputs/Photo_Export_Logs/*_missed.csv` has no unresolved critical misses, or misses are understood.
- `03_Outputs/Review/academy_review.xlsx` has no unacceptable fails.
- `03_Outputs/spellcheck_audit_report.csv` has only known/whitelisted terms.
- Resource and avatar blob status checks are complete or documented.
- Generated JSON contains no invalid numbers.
- Overflow audit has no unresolved high-risk content.

## Hand Off Outputs To Frontend/Backend

Known handoff artifacts:

- `03_Outputs/SEA_Modules`
- `00_API/SEA_Modules`
- `03_Outputs/Charts`
- `03_Outputs/UI_Translations`
- Azure Blob Storage media

Exact deployment/sync to frontend/backend or Strapi is Unknown / requires confirmation. Do not assume `03_Outputs` automatically publishes to production.

## Common Figma Formatting Errors

- Frame name does not exactly match a supported template.
- Layer name does not match expected names such as `title`, `body`, `text`, `image`, `concepts`, `objectives`, `resources`, or `answer_box`.
- `TEXT_PATH` nodes appear from text-on-path objects.
- Infographic wrapper lacks exactly one child frame.
- Chart rectangle name does not match a generated chart figure ID.
- Image rectangle lacks IMAGE fill or `imageRef`.
- Video rectangle name does not match expected video asset base filename.
- Embed rectangle name does not contain intended URL/embed code.
- Four or more line breaks indicate template misuse and are flagged.

## QA Checklist Before Publishing

- Run environment validation in each relevant notebook.
- Confirm Figma cache freshness; set `figma_redownload=True` only when needed.
- Run core structure and Figma extraction successfully.
- Run photo export in `standard` mode, then rerun `retry_missed` if required.
- Review `image_upload_missed.csv` and `infographic_export_missed.csv`.
- Run translation and verify cache hit/miss behavior.
- Run manual translation analysis if manual caches were edited.
- Run review workbook in deterministic or critical AI mode.
- Check resource blob images and avatar blob status.
- Check chart outputs if charts changed.
- Export DOCX if content needs offline review.
- Confirm `00_API` or final destination receives the intended generated files. Exact sync step is Unknown / requires confirmation.

## Recovery Notes

- If Jupyter reuses stale code, restart the kernel or run reload cells.
- If Figma returns 403, verify token validity and file access.
- If Figma image URLs time out, use photo export journals and `retry_missed`.
- If a Figma node returns `no_url`, inspect the node ID and whether it can be exported by Figma.
- If translated output regresses, inspect `translations_cache.json` and manual cache imports.

