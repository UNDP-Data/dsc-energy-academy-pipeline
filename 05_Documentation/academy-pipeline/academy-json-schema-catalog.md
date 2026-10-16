# Academy JSON Schema Catalog

There are no standalone JSON Schema files in the inspected repository. The generated schemas are inferred from:

- `01_Code/entities/frames.py`
- `01_Code/entities/components.py`
- `01_Code/sea_pipeline/core/structure.py`
- observed generated files in `03_Outputs/SEA_Modules/en`

Strict frontend/Strapi requirements are Unknown / requires confirmation unless noted.

## Top-Level Module Structure

Object type: `module_structure`

Path: `03_Outputs/SEA_Modules/<lang>/module_structure.json`

Required fields observed:

- `modules`: array of module objects

Example:

```json
{
  "modules": [
    {
      "id": "1",
      "title": "Intro to Sustainable Energy for Development",
      "color": "#00C1FF",
      "icon": "https://sehseadata.blob.core.windows.net/images/Icons/Modules/module1.svg",
      "image": {"src": "https://sehseadata.blob.core.windows.net/images/HeaderImages/Modules/module1.webp", "caption": ""},
      "description": "Module description...",
      "aiPrompt": "Module description...",
      "percentComplete": "0",
      "estimatedTime": "140 min",
      "chapters": []
    }
  ]
}
```

Frontend rendering component: module/chapter/lesson navigation and progress UI. Backend/Strapi sync dependency: Unknown / requires confirmation.

## Module Object

Required fields observed: `id`, `title`, `color`, `icon`, `image`, `description`, `aiPrompt`, `percentComplete`, `estimatedTime`, `chapters`.

Optional fields observed: none at module root beyond generated fields.

## Chapter Object

Required fields observed: `id`, `title`, `lessons`.

Optional fields observed: `icon`, `image`, `description`, `aiPrompt`, `estimatedTime`, `tooltip`.

Example:

```json
{
  "id": "1.1",
  "title": "Chapter 1: <strong>Introduction to Energy Systems</strong>",
  "icon": "https://sehseadata.blob.core.windows.net/images/Icons/Chapters/chapter1.1.svg",
  "image": {"src": "https://sehseadata.blob.core.windows.net/images/HeaderImages/Chapters/chapter1.1.webp", "caption": ""},
  "description": "Chapter description...",
  "aiPrompt": "Chapter description...",
  "estimatedTime": "30 min",
  "tooltip": "Tooltip HTML...",
  "lessons": []
}
```

## Lesson Navigation Object

Required fields observed: `type`, `id`, `title`, `progress`.

Optional fields observed: `description`, `aiPrompt`, `image`, `frame`.

Example:

```json
{
  "type": "lesson",
  "id": "1.1.1",
  "title": "Lesson 1: <strong>The Great Energy Dilemma</strong>",
  "progress": "not_started",
  "description": "Lesson description...",
  "aiPrompt": "Lesson description...",
  "frame": {"src": "https://sehseadata.blob.core.windows.net/images/Lessons/frame/lesson111_frame.webp", "caption": ""},
  "image": {"src": "https://sehseadata.blob.core.windows.net/images/Lessons/image/lesson111_image.webp", "caption": ""}
}
```

## Lesson JSON File

Object type: `lesson`

Path: `03_Outputs/SEA_Modules/<lang>/Module_<n>/<lesson_id>.json`

Required fields observed:

- `id`
- `segments`

Example:

```json
{
  "id": "1.1.1",
  "segments": [
    {
      "template_id": "lesson_cover",
      "color_scheme": "dark",
      "content": {}
    }
  ]
}
```

Frontend rendering component: segment renderer keyed by `template_id`. Backend/Strapi dependency: Unknown / requires confirmation.

## Shared Segment Wrapper

Required fields observed:

- `template_id`
- `content`

Optional fields observed:

- `color_scheme`
- `size`

Example:

```json
{
  "template_id": "text",
  "color_scheme": "light",
  "content": {
    "text_elements": []
  }
}
```

## Shared Image Object

Required fields observed: `src`, `caption`.

Optional fields observed: `url`.

Example:

```json
{"src": "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/3605_621.webp", "caption": ""}
```

## Cover Segments

Template IDs: `module_cover`, `chapter_cover`, `lesson_cover`, `lesson_part_cover`, `lesson_subpart_cover`, `case_study_cover`

Required fields observed:

- `image`
- `title`

Additional required fields by type:

- `module_cover`: `module`, `cta`
- `chapter_cover`: `chapter`, `cta`, `intro`
- `lesson_cover`: `lesson`, `cta`, `intro`
- `lesson_part_cover`: `intro`
- `lesson_subpart_cover`: `intro`
- `case_study_cover`: `intro`, `subtitle`

Example:

```json
{
  "template_id": "lesson_cover",
  "color_scheme": "dark",
  "content": {
    "image": {"src": "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/3605_621.webp", "caption": ""},
    "lesson": {"label": "Lesson", "number": "1"},
    "title": "The Great Energy Dilemma",
    "cta": "",
    "intro": "M1: Introduction to Sustainable Energy System Transformation"
  }
}
```

Frontend rendering component: cover/card hero components. Backend/Strapi dependency: Unknown / requires confirmation.

## Text Segment

Template ID: `text`

Required fields observed:

- `content.text_elements`: array

Text element required fields:

- `template_id`
- `content`

Text element content fields vary by nested template:

- Paragraph/subtitle/quote: `text`
- Bullet: `title`, `body`
- Bullet with highlight: `title`, `body`, `source`
- Numbered bullet: `number`, `title`, `body`
- KPI highlight: `value`, `text`

Example:

```json
{
  "template_id": "text",
  "color_scheme": "light",
  "content": {
    "text_elements": [
      {
        "template_id": "paragraph_medium",
        "content": {
          "text": "Text with <strong>bold</strong> and <a href=\"https://example.org\">links</a>."
        }
      }
    ]
  }
}
```

Frontend rendering component: rich text renderer keyed by nested `text_elements[].template_id`.

## Key Concepts Segment

Template ID: `key_concepts`

Required fields observed: `title`, `intro`, `concepts`.

Concept object required fields observed: `title`, `body`, `source`.

Example:

```json
{
  "template_id": "key_concepts",
  "color_scheme": "dark",
  "content": {
    "title": "Key Concepts",
    "intro": "Explore foundational ideas from this lesson.",
    "concepts": [
      {"title": "energy trilemma", "body": "Definition text.", "source": ""}
    ]
  }
}
```

Frontend rendering component: glossary/concept cards.

## Learning Objectives Segment

Template ID: `learning_objectives`

Required fields observed: `title`, `intro`, `objectives`.

Objective object required fields observed: `image`, `title`, `description`.

Example:

```json
{
  "template_id": "learning_objectives",
  "color_scheme": "dark",
  "content": {
    "title": "Learning Objectives",
    "intro": "",
    "objectives": [
      {"image": {"src": "https://...", "caption": ""}, "title": "Learn to analyze...", "description": ""}
    ]
  }
}
```

Frontend rendering component: objective cards.

## Key Takeaways Segment

Template ID: `key_takeaways`

Required fields observed: `title`, `intro`, `takeaways`.

Takeaway object required fields observed: `image`, `title`, `description`.

Example:

```json
{
  "template_id": "key_takeaways",
  "color_scheme": "dark",
  "content": {
    "title": "Key Takeaways",
    "intro": "",
    "takeaways": [
      {
        "image": {"src": "https://...", "caption": ""},
        "title": "Addressing these challenges requires inclusive solutions.",
        "description": "This can include culturally sensitive financial tools."
      }
    ]
  }
}
```

Frontend rendering component: takeaway/result cards.

## Key Resources Segment

Template ID: `key_resources`

Required fields observed: `title`, `resources`.

Resource object required fields observed: `image`, `href`, `text`, `cta`.

Example:

```json
{
  "template_id": "key_resources",
  "color_scheme": "dark",
  "content": {
    "title": "Key Resources",
    "resources": [
      {
        "image": {"src": "https://sehseadata.blob.core.windows.net/images/Resources/Module_4/resource-4521.webp", "caption": ""},
        "href": "https://www.unwomen.org/...",
        "text": "Intersectionality Resource Guide and Toolkit",
        "cta": "Click to download"
      }
    ]
  }
}
```

Frontend rendering component: resource/download cards. Blob dependency: resource image should exist in Azure Blob Storage.

## List Of Lessons Segment

Template ID: `list_of_lessons`

Required fields observed: `title`, `lessons`.

Lesson thumbnail required fields observed: `title`, `lessonId`, `type`, `description`, `progress`, `cta`, `image`.

Example:

```json
{
  "template_id": "list_of_lessons",
  "color_scheme": "dark",
  "content": {
    "title": "What's next in this chapter?",
    "lessons": [
      {
        "title": "Lesson 1: ...",
        "lessonId": "1.4.1",
        "type": "lesson",
        "description": "Description...",
        "progress": "not_started",
        "cta": "Go to the lesson",
        "image": {"src": "https://...", "caption": ""}
      }
    ]
  }
}
```

## Photo Segments

Template IDs: `photo_vertical`, `photo-horizontal`, `photo_full_height`

Required fields observed:

- `image`

Optional fields for `photo-horizontal`:

- `title`
- `description`
- `caption`

Example:

```json
{
  "template_id": "photo_full_height",
  "color_scheme": "light",
  "content": {
    "image": {"src": "https://sehseadata.blob.core.windows.net/images/Photos/Module_5/M5_C3_Outro_1.png", "caption": ""}
  }
}
```

## Infographic Segment

Template ID: `infographic`

Required fields observed: `image`, `metadata`.

Metadata fields observed: `title`, `subtitle`, `description`, `footnote`.

Example:

```json
{
  "template_id": "infographic",
  "color_scheme": "light",
  "size": "full",
  "content": {
    "image": {"src": "https://sehseadata.blob.core.windows.net/images/Modules/Module_4/8001_5443.webp", "caption": ""},
    "metadata": {
      "title": "The flow of public finance...",
      "subtitle": "",
      "description": "NGO =",
      "footnote": "Source: IRENA..."
    }
  }
}
```

Frontend rendering component: infographic image plus caption/source text.

## ECharts Chart Segment

Template ID: `echarts_chart`

Required fields from model: `size`, `metadata`, `option`.

Observed/generated content fields can include `metadata` and `option`; tests/fixtures may include `chart_id` or `title`, but the parser model uses `metadata` and `option`.

Example:

```json
{
  "template_id": "echarts_chart",
  "color_scheme": "dark",
  "size": "full",
  "content": {
    "metadata": {"title": "Chart title", "subtitle": "", "description": "", "footnote": ""},
    "option": {"series": []}
  }
}
```

Frontend rendering component: Apache ECharts renderer. Backend/Strapi dependency: Unknown / requires confirmation.

## Embed Segment

Template ID: `embed`

Required fields observed: `title`, `url`.

Example:

```json
{
  "template_id": "embed",
  "color_scheme": "light",
  "size": "full",
  "content": {"title": "", "url": "M2_C2_0"}
}
```

Frontend rendering component: embed/interactivity renderer. Exact URL/code semantics are Unknown / requires confirmation.

## Video Segment

Template ID: `video`

Required fields observed: `src`, `poster`.

Example:

```json
{
  "template_id": "video",
  "color_scheme": "light",
  "size": "full",
  "content": {
    "src": "https://sehseadata.blob.core.windows.net/images/Avatars/en/1/Videos/Lesson-1.4.0_en.mp4",
    "poster": "https://sehseadata.blob.core.windows.net/images/Avatars/en/1/Photos/Lesson-1.4.0_en.webp"
  }
}
```

Frontend rendering component: video player.

## Poll Segment

Template ID: `poll`

Required fields from model: `pollId`, `title`, `description`, `options`, `labels`.

Option fields: `id`, `value`.

Example:

```json
{
  "template_id": "poll",
  "color_scheme": "light",
  "content": {
    "pollId": "poll-123-456",
    "title": "Poll title",
    "description": "Poll question",
    "options": [{"id": 1, "value": "Option A"}],
    "labels": {"submit": "Submit", "cancel": "Cancel"}
  }
}
```

Frontend rendering component: poll/voting UI.

## Scored Quiz Segment

Template ID: `scored_quiz`

Required fields observed: `title`, `intro`, `final`, `labels`, `passingScore`, `questions`.

Question required fields observed: `id`, `prompt`, `multiple`, `options`, `solution`, `messages`.

Option fields: `id`, `value`.

Messages: `correct`, `wrong`, each with `title`, `body`.

Example:

```json
{
  "template_id": "scored_quiz",
  "color_scheme": "dark",
  "content": {
    "title": "Scored quiz <br/><strong>Module 1</strong>",
    "intro": "This quiz covers all the lessons in this module.",
    "final": true,
    "passingScore": 0.8,
    "questions": [
      {
        "id": 1,
        "prompt": "Which pair best represents the energy dilemma in development?",
        "multiple": false,
        "options": [{"id": 1, "value": "Energy access and climate risk"}],
        "solution": [1],
        "messages": {
          "correct": {"title": "Correct", "body": "Feedback..."},
          "wrong": {"title": "Incorrect", "body": "Feedback..."}
        }
      }
    ],
    "labels": {}
  }
}
```

Frontend rendering component: scored quiz.

## Connection Segment

Template IDs: `connection_next`, `connection_back`

Required fields observed for `connection_next`: `image`, `intro`, `title`, `cta`, `nextLessonId`.

Example:

```json
{
  "template_id": "connection_next",
  "color_scheme": "dark",
  "content": {
    "image": {"src": "https://sehseadata.blob.core.windows.net/images/HeaderImages/Modules/module4.webp", "caption": ""},
    "intro": "Next up",
    "title": "Chapter 5 Outro",
    "cta": "Continue learning",
    "nextLessonId": "4.5.-1"
  }
}
```

Frontend rendering component: next/back navigation card.

## Chapter And Module Outro Segments

Template IDs: `chapter_outro`, `module_outro`

Required fields observed: `intro`, `title`, `subtitle`, `body`, `nextBlock`.

`nextBlock` fields observed: `intro`, `title`, `cta`, `button_cta`, `image`, `nextBlockId`, `buttonCta`.

Example:

```json
{
  "template_id": "module_outro",
  "color_scheme": "light",
  "content": {
    "intro": "Congratulations, you have concluded",
    "title": "Module 4",
    "subtitle": "Financing Just Energy Transition",
    "body": "Thank you...",
    "nextBlock": {
      "intro": "Module 5",
      "title": "Sustainable Energy Governance",
      "cta": "",
      "button_cta": "Launch the Graded Quiz",
      "buttonCta": "Next module",
      "nextBlockId": "5.0.0",
      "image": {"src": "https://...", "caption": ""}
    }
  }
}
```

## Image Hotspot Segment

Template ID: `image-hotspot`

Required fields from model: `image`, `hotspots`.

Example:

```json
{
  "template_id": "image-hotspot",
  "content": {
    "image": {"src": "https://...", "caption": ""},
    "hotspots": []
  }
}
```

Implementation completeness: Unknown / requires confirmation. The current parser calls `to_dict()` on selected hotspot nodes, but `Node` does not define `to_dict()` in the inspected code.

