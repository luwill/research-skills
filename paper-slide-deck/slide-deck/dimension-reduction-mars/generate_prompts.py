import os
import re


def parse_outline(outline_path):
    """Parse the outline file and extract slides and style instructions."""
    with open(outline_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract STYLE_INSTRUCTIONS block
    style_match = re.search(
        r"<STYLE_INSTRUCTIONS>(.*?)</STYLE_INSTRUCTIONS>", content, re.DOTALL
    )
    style_instructions = style_match.group(1).strip() if style_match else ""

    # Split content into slides (separated by '---' after the style block)
    # Find the end of STYLE_INSTRUCTIONS block
    end_style_pos = content.find("</STYLE_INSTRUCTIONS>")
    if end_style_pos == -1:
        end_style_pos = 0

    # Get the rest after style instructions
    rest_content = content[end_style_pos + len("</STYLE_INSTRUCTIONS>") :]

    # Split by '---' to get individual slides
    slide_sections = re.split(r"\n---\n", rest_content)

    slides = []
    for section in slide_sections:
        section = section.strip()
        if not section or section.startswith("# Slide Deck Outline"):
            continue

        # Parse slide information
        slide = {}

        # Extract slide number and total
        slide_num_match = re.search(r"## Slide (\d+) of (\d+)", section)
        if slide_num_match:
            slide["number"] = int(slide_num_match.group(1))
            slide["total"] = int(slide_num_match.group(2))

        # Extract type and filename
        type_match = re.search(r"\*\*Type\*\*: (.+)", section)
        if type_match:
            slide["type"] = type_match.group(1).strip()

        filename_match = re.search(r"\*\*Filename\*\*: (.+)", section)
        if filename_match:
            slide["filename"] = filename_match.group(1).strip()

        # Extract narrative goal
        narrative_match = re.search(
            r"// NARRATIVE GOAL\n(.+?)(?=\n//|\n\*\*|\n---|\n$)", section, re.DOTALL
        )
        if narrative_match:
            slide["narrative"] = narrative_match.group(1).strip()

        # Extract key content
        key_content_match = re.search(
            r"// KEY CONTENT\n(.+?)(?=\n//|\n\*\*|\n---|\n$)", section, re.DOTALL
        )
        if key_content_match:
            key_content = key_content_match.group(1).strip()
            # Parse headline, sub-headline, body
            lines = key_content.split("\n")
            slide["headline"] = ""
            slide["subheadline"] = ""
            slide["body"] = []

            for line in lines:
                line = line.strip()
                if line.startswith("Headline:"):
                    slide["headline"] = line.replace("Headline:", "").strip()
                elif line.startswith("Sub-headline:"):
                    slide["subheadline"] = line.replace("Sub-headline:", "").strip()
                elif line.startswith("Body:"):
                    # Body lines start with '-'
                    continue
                elif line.startswith("-"):
                    slide["body"].append(line[1:].strip())

        # Extract visual description
        visual_match = re.search(
            r"// VISUAL\n(.+?)(?=\n//|\n\*\*|\n---|\n$)", section, re.DOTALL
        )
        if visual_match:
            slide["visual"] = visual_match.group(1).strip()

        # Extract layout
        layout_match = re.search(
            r"// LAYOUT\nLayout: (.+?)(?=\n//|\n\*\*|\n---|\n$)", section, re.DOTALL
        )
        if layout_match:
            slide["layout"] = layout_match.group(1).strip()

        # Extract image source
        image_source_match = re.search(
            r"// IMAGE_SOURCE\nSource: (.+?)(?=\n//|\n\*\*|\n---|\n$)",
            section,
            re.DOTALL,
        )
        if image_source_match:
            slide["image_source"] = image_source_match.group(1).strip()
        else:
            slide["image_source"] = "generate"

        if slide:  # Only add if we found slide info
            slides.append(slide)

    return style_instructions, slides


def create_prompt(base_prompt_path, style_instructions, slide):
    """Create a prompt for a specific slide."""
    with open(base_prompt_path, "r", encoding="utf-8") as f:
        base_prompt = f.read()

    # Replace STYLE_INSTRUCTIONS placeholder
    prompt = base_prompt.replace(
        "[Insert style-specific instructions here]", style_instructions
    )

    # Add slide-specific content
    prompt += f"\n\n## SLIDE CONTENT\n\n"
    prompt += f"**Slide {slide['number']}/{slide['total']}**\n"
    prompt += f"**Type**: {slide['type']}\n"
    prompt += f"**Layout**: {slide.get('layout', 'default')}\n\n"

    prompt += f"**Narrative Goal**:\n{slide.get('narrative', '')}\n\n"

    prompt += f"**Headline**: {slide.get('headline', '')}\n"
    if slide.get("subheadline"):
        prompt += f"**Sub-headline**: {slide['subheadline']}\n"

    if slide.get("body"):
        prompt += f"\n**Body Content**:\n"
        for i, item in enumerate(slide["body"]):
            prompt += f"{i + 1}. {item}\n"

    prompt += f"\n**Visual Description**:\n{slide.get('visual', '')}\n"

    # Add layout guidance if specified
    if slide.get("layout"):
        layout_guidance = get_layout_guidance(slide["layout"])
        if layout_guidance:
            prompt += f"\n**Layout Guidance**:\n{layout_guidance}\n"

    return prompt


def get_layout_guidance(layout_name):
    """Return layout-specific guidance for the prompt."""
    layout_guidance = {
        "paper-title": "Centered title at top, authors and affiliations below, conference/venue at bottom. Formal academic style.",
        "bullet-list": "Clean bullet points with consistent indentation and markers. Generous line spacing.",
        "split-screen": "Two equal panels side by side. Left and right content clearly separated.",
        "binary-comparison": "Side-by-side comparison with clear labels. Highlight differences.",
        "linear-progression": "Sequential flow from left to right with arrows connecting steps.",
        "equation-focus": "Centered mathematical equation with variable definitions around it.",
        "methods-diagram": "Central diagram with labeled components and data flow arrows.",
        "agenda": "Numbered steps with clear progression. Highlight current step if applicable.",
        "results-chart": "Clean chart or table with axis labels, legends, and highlighted results.",
        "qualitative-grid": "2x2 or 3x2 grid of images with consistent sizing and labels.",
        "hub-spoke": "Central concept in middle with related items radiating outward.",
        "contributions": "Numbered list with icons or checkmarks. Clear visual hierarchy.",
        "references-list": "Two-column reference list with proper citation formatting.",
    }
    return layout_guidance.get(layout_name, "")


def main():
    outline_path = "outline.md"
    base_prompt_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "references", "base-prompt.md"
    )
    prompts_dir = "prompts"

    # Parse outline
    style_instructions, slides = parse_outline(outline_path)

    print(f"Parsed {len(slides)} slides")

    # Generate prompts for each slide
    for slide in slides:
        prompt = create_prompt(base_prompt_path, style_instructions, slide)

        # Save prompt file
        prompt_filename = os.path.splitext(slide["filename"])[0] + ".md"
        prompt_path = os.path.join(prompts_dir, prompt_filename)

        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)

        print(f"Generated: {prompt_path}")

    print(f"\nAll prompts generated in {prompts_dir}/")


if __name__ == "__main__":
    main()
