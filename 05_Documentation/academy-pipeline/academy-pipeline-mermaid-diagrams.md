# Academy Pipeline Mermaid Diagrams

## Figma-To-JSON Pipeline

```mermaid
flowchart TD
  A["SEA Table of Contents.xlsx"] --> B["structure_generation"]
  B --> C["module_structure.json"]
  D["Figma documents"] --> E["Cached figma_document1-3.json"]
  E --> F["Figma extraction/export"]
  F --> G["entities.Document / Node / Frame models"]
  G --> H["Lesson segment JSON"]
  C --> H
  H --> I["Post-processing"]
  I --> J["03_Outputs/SEA_Modules/en"]
  J --> K["Translation pipeline"]
  K --> L["03_Outputs/SEA_Modules/{fr,es,pt,ar,zh,ru}"]
```

## Image Extraction And Upload Flow

```mermaid
flowchart TD
  A["Figma module page"] --> B["Scan RECTANGLE nodes with IMAGE fills"]
  B --> C["Build blob name Modules/Module_n/node_id.webp"]
  C --> D["Compare existing blobs"]
  D --> E["Compare image_refs_cache.json"]
  E --> F{"Needs upload?"}
  F -- "No" --> G["Skip as up to date"]
  F -- "Yes" --> H["Request Figma image URL"]
  H --> I{"URL returned?"}
  I -- "No" --> J["Journal no_url miss"]
  I -- "Yes" --> K["Download image bytes"]
  K --> L{"Bytes returned?"}
  L -- "No" --> M["Journal no_bytes miss"]
  L -- "Yes" --> N["Convert to WebP"]
  N --> O["Upload to Azure Blob Storage"]
  O --> P["Update cache and journal"]
```

## Translation Flow

```mermaid
flowchart TD
  A["English module/lesson JSON"] --> B["Extract translatable strings"]
  B --> C["Normalize and hash source text"]
  C --> D{"Cache complete?"}
  D -- "Yes" --> E["Reuse translations_cache.json"]
  D -- "No" --> F["Call Azure OpenAI"]
  F --> G{"Full language set succeeded?"}
  G -- "Yes" --> H["Merge translations into cache"]
  G -- "No" --> I["Retry language groups"]
  I --> H
  H --> J["Arabic bdi normalization"]
  E --> K["Rebuild localized JSON"]
  J --> K
  K --> L["03_Outputs/SEA_Modules/<lang>"]
```

## Chart Processing Flow

```mermaid
flowchart TD
  A["Charts Tracker.xlsx"] --> B["Extract metadata"]
  C["Module chart dataset workbooks"] --> D["Extract datasets"]
  B --> E["Merge metadata and datasets"]
  D --> E
  F["Charts Config.xlsx"] --> G["Load chart config"]
  H["Chart templates JSON"] --> I["Apply ECharts templates"]
  E --> I
  G --> I
  I --> J["LightMode chart JSON"]
  I --> K["DarkMode chart JSON"]
  K --> L["Figma chart frame references figure ID"]
  L --> M["echarts_chart segment"]
```

## AI Avatar Generation Flow

```mermaid
flowchart TD
  A["Lesson JSON outputs"] --> B["Avatar script generation"]
  B --> C["English avatar scripts"]
  C --> D["Avatar script translation"]
  D --> E["Translated avatar scripts"]
  E --> F["Generate HeyGen payloads"]
  G["Avatars.xlsx and HeyGen resources"] --> F
  F --> H["HeyGen video generation"]
  H --> I["AI_Avatars intermediate blobs"]
  I --> J["Download/list clips"]
  J --> K["Add backgrounds"]
  K --> L["Final Avatars/<lang>/<module>/Videos blobs"]
  L --> M["Core avatar video segment insertion"]
```

## Academy Publication Flow

```mermaid
flowchart TD
  A["03_Outputs/SEA_Modules"] --> B["QA review workbook"]
  A --> C["Translation outputs"]
  D["Azure Blob media"] --> E["Lesson JSON media URLs"]
  C --> F["00_API/SEA_Modules"]
  E --> F
  F --> G["Academy frontend/API consumption"]
  H["Charts/UI translations/SEA_Data"] --> G
  I["Strapi/backend sync"] -. "Unknown / requires confirmation" .-> G
```

