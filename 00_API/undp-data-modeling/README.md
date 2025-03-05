# UNDP Data Modeling

This is a work in progress to define data structures for the UNDP Sustainable Energy Academy project. The data structures illustrated here are meant to provide an example of the data format that should be returned by the UNDP Api and do not include, at the moment, additional information such as language, user progress and completion state.

## Conventions

We define the following units of content, in decreasing granularity:

- **Templates**
- **Lessons**
- **Chapters**
- **Modules**

### Templates

A template is the smallest unit of content and represents one of several data structures which can be seen [here](https://www.figma.com/design/WK7tMVgZFYdyv5bzLBamAr/UNDP_Sustainable-Energy-Academy_Draft_29%2F10%2F2024?node-id=56-15572&m=dev).
Each structure in the design file has its corresponding template element, which is defined by two properties:

template_id
: the unique string identifying the template corresponding to a specific data structure.

content
: an object holding the text and media content to be inserted in the template. Each template has its own shape for the content object which depends on its data structure.

### Lessons

Lessons are a collection of templates, and are identified by a unique id.

### Chapters

Chapters are a collection of Lessons, each identified by a unique id.

### Modules

A module represents the largest unit of content, it is defined as a collection of chapters and is identified itself by a unique id.

## Allowed markup in API response

To customize the style of textual content, the following HTML tags are allowed in the API response:

- `<strong />` for bold text
- `<em/>` for italics text
- `<a/>` for external links
- `<u/>` for underlined text
- `<span class='large-text'/>` to increase the font size of the text
- `<br />` for line breaks

Any other tags will be stripped from the API response before rendering the text, for both security and style consistency reasons.
