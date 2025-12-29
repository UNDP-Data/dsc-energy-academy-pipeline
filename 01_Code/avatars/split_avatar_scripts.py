import os
from docx import Document

# Base folder containing Module subfolders
path_scripts = "../../02_Inputs/avatars/..."

# Maximum characters allowed per script
#MAX_CHARS = 1500

def split_paragraphs(doc):
    """Returns a list of paragraphs from the doc that are not empty."""
    return [p.text for p in doc.paragraphs if p.text.strip()]

def save_docx(paragraphs, filepath):
    """Save a list of paragraphs to a .docx file."""
    doc = Document()
    for para in paragraphs:
        doc.add_paragraph(para)
    doc.save(filepath)
    print(f"💾 Saved split file: {filepath}")

# Walk through all Module folders
for root, dirs, files in os.walk(path_scripts):
    for file in files:
        if file.endswith(".docx") and "_" not in file[-6:]:  # ignore already split files (_1/_2)
            file_path = os.path.join(root, file)
            doc = Document(file_path)
            paragraphs = split_paragraphs(doc)
            full_text = "\n".join(paragraphs)

            #if len(full_text) > MAX_CHARS:
                # Split paragraphs roughly in the middle
            total_chars = 0
            split_index = 0
            for i, para in enumerate(paragraphs):
                total_chars += len(para) + 1  # +1 for newline
                if total_chars >= len(full_text) / 2:
                    split_index = i + 1
                    break

            part1 = paragraphs[:split_index]
            part2 = paragraphs[split_index:]

            # Save the two new files
            base_name = os.path.splitext(file)[0]
            file1 = os.path.join(root, f"{base_name}_1.docx")
            file2 = os.path.join(root, f"{base_name}_2.docx")

            save_docx(part1, file1)
            save_docx(part2, file2)
