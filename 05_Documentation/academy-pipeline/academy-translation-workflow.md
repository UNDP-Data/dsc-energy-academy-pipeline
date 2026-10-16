# Academy Translation Workflow

## Overview

The translation pipeline translates module structure, lesson JSON, UI strings, and avatar scripts using Azure OpenAI plus a persistent translation cache.

Driver notebook:

```text
01_Code/translation-pipeline.ipynb
```

Package:

```text
01_Code/sea_pipeline/translation
```

## Languages Supported

Default target languages:

- `fr`
- `es`
- `pt`
- `ar`
- `zh`
- `ru`

English (`en`) is the source language.

## Environment Variables

Required for machine translation:

- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`

## Cache

Primary cache:

```text
03_Outputs/Lesson_Translation/translations_cache.json
```

Cache entries are keyed by hashes of normalized source strings. Cache entries contain target-language translations and often the source English text.

Module structure translation uses the same cache file through `sea_pipeline.translation.structure_cache`.

## Keys Translated

Module structure translation keys:

- `title`
- `description`
- `tooltip`
- `aiPrompt`

Lesson translation keys are extracted from lesson JSON sentence/text fields in the legacy translation pipeline. Exact field list is partially embedded in `translation-pipeline.json`; strict coverage is Unknown / requires confirmation.

UI translation reads JSON bundles under:

```text
03_Outputs/UI_Translations/UI
```

Avatar script translation reads generated English DOCX scripts and writes translated DOCX scripts.

## Structure Preservation

The translation logic preserves JSON structure:

- Non-translatable fields such as IDs, URLs, image paths, and template IDs are retained.
- Translatable string fields are replaced in-place.
- HTML tags are preserved in prompts for module structure translation.
- Arabic LTR acronym-like text is wrapped with `<bdi dir="ltr">...</bdi>`.

## Language Grouping

Module structure and lesson translation use language groups:

```python
[["fr", "es", "pt"], ["ar", "zh", "ru"]]
```

The grouped fallback is used after a full-language attempt fails or when only some languages are missing. This helps avoid model/token/format failures while still preferring full cache-complete entries.

## Arabic Bidi Handling

Arabic translation handling:

- Wraps Latin acronyms, mixed-case technical terms, and short acronym-like runs in `<bdi dir="ltr">...</bdi>`.
- Protects URLs from being wrapped.
- Converts legacy Unicode isolate wrappers into `<bdi>` tags.
- Normalizes existing cache entries during structure translation and manual cache import.

Example:

```html
<bdi dir="ltr">SDG</bdi> 7
```

## Manual Translation Workflow

Manual translation files can be generated for unresolved translations, analyzed, and imported:

- Input manual cache candidates: `02_Inputs/manual-translation-cache/*.json`.
- Generated manual files: `03_Outputs/SEA_Modules/Lesson_Translation/Manual` when present.
- Analysis outputs:
  - `03_Outputs/Lesson_Translation/manual_translation_analysis.json`
  - `03_Outputs/Lesson_Translation/manual_translation_analysis_entries.csv`
- Import target: `03_Outputs/Lesson_Translation/translations_cache.json`.

Manual analysis classifies entries as:

- complete candidate
- placeholder
- unchanged source
- abridged
- very short
- invalid JSON

It also detects missing language files and possible stop points.

## Review Process

Observed review mechanisms:

- Manual translation completeness analysis.
- Cache import skips unresolved `[needs translation]` placeholders by default.
- Arabic cache values are normalized during import.
- Translation pipeline prints cache hits/misses and progress.

Formal linguistic review workflow outside the cache/manual files is Unknown / requires confirmation.

## Known Limitations

- The lesson translation implementation remains partly in a legacy notebook snapshot rather than fully typed module code.
- Cache keys depend on normalized source text; small source edits can produce new cache entries.
- Duplicate English source strings may share cache entries.
- Portuguese manual cache was noted as absent in current manual input files.
- Arabic acronym rendering depends on pattern matching and may require manual QA for edge cases.
- Direct Strapi/backend localization sync is Unknown / requires confirmation.

