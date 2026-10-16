# Figma Content Model

This document describes the Figma assumptions that are visible in the repository. Items not directly supported by code inspection are marked Unknown / requires confirmation.

## Figma File And Page Structure

The pipeline expects three Figma documents:

- `FIGMA_DOCUMENT_ID1`: pages `Module 1`, `Module 2`, `Module 3`
- `FIGMA_DOCUMENT_ID2`: pages `Module 4`, `Module 5`, `Module 6`
- `FIGMA_DOCUMENT_ID3`: pages `Module 7`, `Module 8`, `Module 9`

Cached copies are stored at:

- `02_Inputs/figma_jsons/figma_document1.json`
- `02_Inputs/figma_jsons/figma_document2.json`
- `02_Inputs/figma_jsons/figma_document3.json`

The Figma API document root is parsed through `entities.document.Document`, with node types validated by `entities.node.Node`.

## Module, Chapter, And Lesson Naming

Observed conventions:

- Figma canvas/page names are `Module 1` through `Module 9`.
- Figma document hierarchy includes module pages, chapter sections, lesson sections, and frame templates.
- Lesson IDs use `module.chapter.lesson`, for example `1.1.1`.
- Module intro/outro and chapter intro/outro use synthetic IDs:
  - Module preface: `1.0.-1`
  - Module introduction: `<module>.0.0`
  - Chapter introduction: `<module>.<chapter>.0`
  - Chapter outro: `<module>.<chapter>.-1`
  - Module quiz: `<module>.-1.0`
  - Module outro: `<module>.-1.-1`

Exact Figma section naming requirements beyond observed `Module`, `Chapter`, and `Lesson` labels are Unknown / requires confirmation.

## Supported Frame And Template Types

Supported frame/template types are defined by `01_Code/entities/frames.py` and observed in generated English output:

| Template ID | Purpose |
| --- | --- |
| `module_cover` | Module intro cover |
| `chapter_cover` | Chapter intro cover |
| `lesson_cover` | Lesson cover |
| `lesson_part_cover` | Lesson section cover |
| `lesson_subpart_cover` | Lesson subsection cover |
| `case_study_cover` | Case study intro card |
| `text` | Text frame containing nested text templates |
| `key_concepts` | Concept list |
| `learning_objectives` | Learning objective cards |
| `key_takeaways` | Key takeaway cards |
| `key_resources` | Resource cards |
| `list_of_lessons` | Chapter lesson list |
| `photo_vertical` | Vertical photo |
| `photo-horizontal` | Horizontal photo |
| `photo_full_height` | Full-height photo |
| `video` | Video placeholder/player segment |
| `connection_next` | Link to next lesson/block |
| `connection_back` | Back/previous connection |
| `chapter_outro` | Chapter wrap-up |
| `module_outro` | Module wrap-up |
| `echarts_chart` | ECharts chart segment generated from a Figma `chart` frame |
| `infographic` | Exported infographic image plus metadata |
| `embed` | Embedded external/interactivity block |
| `poll` | Poll segment |
| `scored_quiz` | Module quiz segment |
| `image-hotspot` | Image hotspot segment; implementation appears incomplete because it calls `to_dict()` on selected hotspot nodes |

## Text Template Types

The `text` frame contains grouped text elements. Supported nested `template_id` values include:

- `subtitle`
- `subtitle_small`
- `paragraph_large`
- `paragraph_medium`
- `paragraph_small`
- `bullet_point`
- `bullet_point_with_highlight`
- `bullet_point_with_number`
- `kpi_highlight_large`
- `kpi_highlight_medium`
- `quote_large_with_name`
- `quote_large_without_name`
- `quote_small_with_name`
- `quote_small_without_name`

Text style extraction preserves bold, italic, underline, and hyperlink data by wrapping content in HTML-like tags such as `<strong>`, `<em>`, `<u>`, and `<a href="">`.

## Required Layer Names

The parser selects descendants by node type and layer names. Common required or expected names:

- Cover frames: `image`, `title`, `subtitle`, `cta`, `intro`, and `module`, `chapter`, or `lesson` groups.
- Intro component groups: `label`, `number`.
- Text templates: group names matching text template IDs, with child text layers such as `text`, `title`, `body`, `source`, `number`, `value`, `quote`, and `author`.
- Key concepts: groups named `concepts`, with text layers `title`, `body`, and optional `source`.
- Learning objectives: groups named `objectives`, with child group `image`, and text layers `title`, optional `description`.
- Key takeaways: groups named `objectives`; first sentence can be split into title and remaining text into description when no explicit description is present.
- Key resources: groups named `resources`; reusable `Card` extraction expects image/title/description-style fields, and post-processing can map resource `href` from the table of contents `Resource Link` column.
- List of lessons: groups named `lessons`.
- Chapter/module outro: group `title` with `first_line` and `second_line`; group `quiz` for `nextBlock`.
- Polls: group `subtitle` with text `text`; group `paragraph_medium` with text `text`; repeated groups `answer_box` with text `body` or `title`.
- Video: first `RECTANGLE` with IMAGE fill; rectangle name becomes the base video filename for non-avatar videos.
- Embed: first direct `TEXT` layer named `title`; first direct `RECTANGLE` layer name becomes the URL or embed code.
- Chart: first direct `RECTANGLE` layer name is treated as the chart figure ID, for example `M1_C1_2`.
- Infographic: wrapper frame named `infographic`; exactly one child `FRAME` is exported as the design image.

## Image Extraction Assumptions

- Generic image upload scans every `RECTANGLE` with an IMAGE fill and `imageRef` in the selected module page.
- Blob names are generated as `Modules/Module_<n>/<node_id>.webp`, with `:` replaced by `_`.
- The Figma image export API is called as `https://api.figma.com/v1/images/{file_id}` with node ID, format, and scale.
- Export scale is calculated from the Figma node height, targeting approximately 1080 px with a max scale of 4.
- Images are converted to WebP before upload.
- Existing blob names and cached Figma `imageRef` values prevent unnecessary re-uploads.

## Infographic Assumptions

- Infographic wrapper frame name must case-sensitively be `infographic` in the current `scan_infographic_page` implementation.
- The wrapper must contain exactly one child `FRAME`; that child frame is exported.
- The child frame's node ID becomes the image/blob ID.
- Metadata is read from descendant text layers named `title`, `subtitle`, `description` or `summary`, and `footnote` or `source`.
- If there is not exactly one child frame, the infographic is skipped and logged in the photo export journal.

## Chart Assumptions

- A Figma frame named `chart` is parsed into template `echarts_chart`.
- The first direct `RECTANGLE` child name is interpreted as the figure ID.
- Matching chart JSON must exist for the figure ID. The auxiliary chart runner documents outputs under `03_Outputs/Charts/Auto Charts/...`, while the inspected chart parsing code references `../03_Outputs/charts/Auto Charts/DarkMode/<figure_id>.json`; the canonical casing/path should be confirmed on the target filesystem.
- Metadata is loaded from `02_Inputs/Charts/Metadata/Charts Tracker.xlsx`.
- Chart source data and configuration come from `02_Inputs/Charts/Data/Charts` and `02_Inputs/Charts/Metadata/Charts Config.xlsx`.

## Video Assumptions

- Avatar video segments are inserted from `02_Inputs/SEA AI Avatars.csv` and point to Azure paths like `Avatars/{language}/{module}/Videos/Lesson-{lesson_id}_{language}.mp4`.
- Poster paths point to `Avatars/{language}/{module}/Photos/Lesson-{lesson_id}_{language}.webp`.
- Figma-authored `video` frames use the first image rectangle name as a base filename under `Videos/src/<name>.mp4` and `Videos/poster/<name>.png`.
- DOCX exports currently render videos as a text placeholder such as `Video: Avatars/en/1/Videos/Lesson-1.4.0_en.mp4`.

## Known Figma Formatting Errors

- `TEXT_PATH` nodes are accepted by the current node type model but reported for cleanup by `Document.report_text_path_nodes`; these are text-on-path objects and can be hard to see in Figma.
- Missing expected layers produce warnings such as missing `title`, `body`, or `description`.
- Infographic frames with zero or multiple child frames are skipped.
- Chart frames without a rectangle figure ID, or without matching generated chart JSON, raise errors.
- Figma API can return no image URL for specific node IDs; those are logged as `no_url`.
- S3/Figma image URLs can timeout; those are logged as `no_bytes` with retry details.
