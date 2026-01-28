import sys
import re

try:
    import fitz  # PyMuPDF

    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    try:
        import PyPDF2

        HAS_PYPDF2 = True
    except ImportError:
        HAS_PYPDF2 = False


def extract_text_with_fitz(pdf_path, max_pages=10):
    """Extract text using PyMuPDF."""
    doc = fitz.open(pdf_path)
    text = ""
    for i in range(min(max_pages, len(doc))):
        page = doc[i]
        text += page.get_text()
    doc.close()
    return text


def extract_text_with_pypdf2(pdf_path, max_pages=10):
    """Extract text using PyPDF2."""
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        text = ""
        for i in range(min(max_pages, len(reader.pages))):
            text += reader.pages[i].extract_text()
    return text


def extract_sections(text):
    """Identify potential section headings."""
    lines = text.split("\n")
    sections = []
    for line in lines:
        line = line.strip()
        # Look for all caps or numbered sections
        if re.match(r"^(?:\d+(?:\.\d+)*\s+)?[A-Z][A-Z\s]{2,}$", line):
            sections.append(line)
        elif re.match(
            r"^(Abstract|Introduction|Related Work|Methods|Experiments|Results|Conclusion|References)",
            line,
            re.I,
        ):
            sections.append(line)
    return sections


def main():
    pdf_path = "source-paper.pdf"

    if HAS_FITZ:
        text = extract_text_with_fitz(pdf_path, max_pages=5)
    elif HAS_PYPDF2:
        text = extract_text_with_pypdf2(pdf_path, max_pages=5)
    else:
        print("No PDF library found. Install PyMuPDF or PyPDF2.")
        sys.exit(1)

    sections = extract_sections(text)
    print("=== Extracted Sections (first 5 pages) ===")
    for sec in sections[:20]:
        print(f"- {sec}")

    # Look for title (first non-empty line that looks like a title)
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if line and len(line) > 10 and len(line) < 200:
            if not line.isupper() and not re.match(r"^\d", line):
                print(f"\nPossible title: {line}")
                break


if __name__ == "__main__":
    main()
