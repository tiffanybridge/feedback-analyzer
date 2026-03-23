import os
import re
import csv
import sys

import anthropic

# Maximum number of feedback items to send. Keeps token costs manageable.
MAX_ITEMS = 500

# How many stripped items to show during the dry-run preview.
PREVIEW_COUNT = 5


# --- PII Stripping ---

# Regex patterns for common PII types. These run locally — nothing is sent to the
# AI until after stripping. Note: first names and last names are hard to detect
# reliably without a trained NLP model, so they are not caught here.
PII_PATTERNS = [
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL]"),
    (r"(\+?1[\s.\-]?)?(\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})", "[PHONE]"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]"),
    (r"\b(?:\d{4}[\s\-]?){3}\d{4}\b", "[CARD]"),
    (r"https?://\S+", "[URL]"),
    (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP]"),
]


def strip_pii(text):
    """Remove common PII patterns from a string before sending to the AI."""
    for pattern, replacement in PII_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


# --- Load Feedback ---

def load_feedback(filepath, column):
    """Load feedback items from a CSV file, returning a list of strings."""
    items = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            # Check column exists on the first row
            if i == 0 and column not in row:
                print(f"\nError: Column '{column}' not found.")
                print(f"Available columns: {list(row.keys())}")
                sys.exit(1)
            text = row.get(column, "").strip()
            if text:
                items.append(text)
    return items


# --- Analyze with Claude ---

def analyze_feedback(items, products=None):
    """Send PII-stripped feedback to Claude and return the analysis as a string."""
    client = anthropic.Anthropic()

    # Build the numbered list, optionally prefixing each item with product type
    if products:
        numbered = "\n".join(
            f"{i + 1}. [{products[i]}] {item}" for i, item in enumerate(items)
        )
        product_note = "Each item is prefixed with [Product Type] in brackets."
    else:
        numbered = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))
        product_note = ""

    prompt = f"""You are analyzing customer feedback to surface product insights.

The feedback below has already had PII removed. There are {len(items)} items total.
{product_note}

FEEDBACK:
{numbered}

Please analyze this and return:

1. TOP 5 THEMES
   For each theme:
   - Theme name (short, descriptive)
   - Product area it relates to (if identifiable from the feedback)
   - Which product types are most affected (if product type data is available)
   - Frequency: approximate % of the {len(items)} items that relate to this theme
   - Sentiment score: 1 (very negative) to 5 (very positive)
   - 2-3 representative quotes, verbatim from the feedback above (max 20 words each)
   - One-sentence insight a PM could act on

2. OVERALL SENTIMENT
   A single score from 1-5 with a one-sentence explanation.

3. EXECUTIVE SUMMARY
   2-3 sentences on the most important things to know from this feedback.

Format clearly with headers. Be specific and actionable."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    )

    # The response may contain a thinking block before the text block — find the text
    for block in response.content:
        if block.type == "text":
            return block.text

    return "[No text response received]"


# --- Main ---

def main():
    # Fail early if the API key is missing
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable is not set.")
        print("Set it with: export ANTHROPIC_API_KEY=your-key-here")
        sys.exit(1)

    print("Feedback Analyzer")
    print("=" * 60)

    # Ask for the CSV file path
    feedback_file = input("\nPath to your CSV file: ").strip()
    if not os.path.exists(feedback_file):
        print(f"Error: '{feedback_file}' not found. Check the path and try again.")
        sys.exit(1)

    # Ask for the column name
    feedback_column = input("Column name containing feedback text: ").strip()

    # Ask for an optional product type column
    product_column_input = input("Column name for product type (press Enter to skip): ").strip()
    product_column = product_column_input if product_column_input else None

    # Load and validate
    print(f"\nLoading feedback...")
    items = load_feedback(feedback_file, feedback_column)
    products = load_feedback(feedback_file, product_column) if product_column else []
    print(f"Found {len(items)} feedback items.")

    if len(items) > MAX_ITEMS:
        print(f"Note: Capping at {MAX_ITEMS} items to stay within token limits.")
        items = items[:MAX_ITEMS]
        if products:
            products = products[:MAX_ITEMS]

    # Strip PII locally before anything goes to Claude
    print("Stripping PII...")
    stripped = [strip_pii(item) for item in items]

    # Show a preview so the user can verify PII was removed correctly
    preview_count = min(PREVIEW_COUNT, len(stripped))
    print(f"\n--- STRIPPED PREVIEW ({preview_count} of {len(stripped)} items) ---")
    for i, item in enumerate(stripped[:preview_count]):
        prefix = f"[{products[i]}] " if products else ""
        print(f"{i + 1}. {prefix}{item}")
    print("---")
    print("\nCheck the preview above. PII should appear as [EMAIL], [PHONE], etc.")
    print("Note: names are not automatically detected and may still be present.")

    confirm = input("\nDoes the stripping look correct? Send to Claude for analysis? [y/n]: ").strip().lower()
    if confirm != "y":
        print("Aborted. No data was sent to Claude.")
        sys.exit(0)

    print("\nSending to Claude for analysis (this may take 30-60 seconds)...")
    report = analyze_feedback(stripped, products or None)

    # Print to console
    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    # Save report to file
    output_file = "feedback_report.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Feedback Analysis Report\n\n")
        f.write(f"**Source:** {feedback_file}  \n")
        f.write(f"**Items analyzed:** {len(stripped)}\n\n")
        f.write("---\n\n")
        f.write(report)

    print(f"\nReport saved to {output_file} — drag it into Claude Code to explore further.")


if __name__ == "__main__":
    main()
