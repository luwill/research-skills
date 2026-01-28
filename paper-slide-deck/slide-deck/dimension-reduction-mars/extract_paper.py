import fitz  # PyMuPDF
import re


def extract_paper_info(pdf_path):
    doc = fitz.open(pdf_path)

    # Extract text from first few pages
    full_text = ""
    for i in range(min(10, len(doc))):
        page = doc[i]
        full_text += page.get_text()

    # Split into lines
    lines = [line.strip() for line in full_text.split("\n") if line.strip()]

    # Find title: often first non-empty line that is not a header, not all caps, not a date
    title = ""
    for line in lines:
        if len(line) > 20 and len(line) < 200:
            if not line.isupper() and not re.match(r"^\d", line):
                # Exclude common metadata
                if "journal" not in line.lower() and "volume" not in line.lower():
                    title = line
                    break

    # Find authors: look for lines after title with common author patterns
    authors = []
    author_pattern = r"[A-Z][a-z]+ [A-Z][a-z]+(?:, [A-Z][a-z]+ [A-Z][a-z]+)*"
    for i, line in enumerate(lines):
        if line == title:
            # Look at next few lines
            for j in range(i + 1, min(i + 5, len(lines))):
                if re.match(author_pattern, lines[j]):
                    authors.append(lines[j])
            break

    # Find abstract: look for the word "Abstract"
    abstract = ""
    for i, line in enumerate(lines):
        if "abstract" in line.lower():
            # Collect lines until next section
            abstract_lines = []
            for j in range(i + 1, len(lines)):
                if re.match(r"^[1-9]\.|[A-Z][A-Z\s]{3,}$", lines[j]):
                    break
                abstract_lines.append(lines[j])
            abstract = " ".join(abstract_lines[:200])  # Limit length
            break

    # Find section headings
    sections = []
    section_patterns = [
        r"^\d+(\.\d+)*\s+[A-Z]",  # Numbered sections
        r"^(Introduction|Related Work|Methodology|Methods|Experiments|Results|Conclusion|References|Acknowledgements)",
        r"^[A-Z][A-Z\s]{3,}$",  # All caps headings
    ]
    for line in lines:
        for pattern in section_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                sections.append(line)
                break

    doc.close()

    return {
        "title": title,
        "authors": authors,
        "abstract": abstract[:500] + "..." if len(abstract) > 500 else abstract,
        "sections": sections[:20],
    }


if __name__ == "__main__":
    info = extract_paper_info("source-paper.pdf")
    print("Title:", info["title"])
    print("\nAuthors:", info["authors"])
    print("\nAbstract preview:", info["abstract"])
    print("\nSections found:")
    for sec in info["sections"]:
        print(f"  - {sec}")
