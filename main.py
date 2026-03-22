import os
import re
import csv
import sys

import anthropic

# --- Configuration ---
# Update these to match your CSV file before running.
FEEDBACK_FILE = "feedback.csv"   # Path to your CSV
FEEDBACK_COLUMN = "feedback"     # Name of the column containing the feedback text
MAX_ITEMS = 500                  # Cap to avoid hitting token limits on large files


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
                print(f"Error: Column '{column}' not found in {filepath}.")
                print(f"Available columns: {list(row.keys())}")
                print("Update FEEDBACK_COLUMN at the top of this script.")
                sys.exit(1)
            text = row.get(column, "").strip()
            if text:
                items.append(text)
    return items


# --- Analyze with Claude ---

def analyze_feedback(items):
    """Send PII-stripped feedback to Claude and return the analysis as a string."""
    client = anthropic.Anthropic()

    # Number each item so Claude can reference them and count frequencies
    numbered = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))

    prompt = f"""You are analyzing customer feedback to surface product insights.

The feedback below has already had PII removed. There are {len(items)} items total.

FEEDBACK:
{numbered}

Please analyze this and return:

1. TOP 5 THEMES
   For each theme:
   - Theme name (short, descriptive)
   - Product area it relates to (if identifiable from the feedback)
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

    # Fail early if the CSV doesn't exist
    if not os.path.exists(FEEDBACK_FILE):
        print(f"Error: '{FEEDBACK_FILE}' not found.")
        print("Update FEEDBACK_FILE at the top of this script to point to your CSV.")
        sys.exit(1)

    print(f"Loading feedback from {FEEDBACK_FILE}...")
    items = load_feedback(FEEDBACK_FILE, FEEDBACK_COLUMN)
    print(f"Found {len(items)} feedback items.")

    if len(items) > MAX_ITEMS:
        print(f"Note: Capping at {MAX_ITEMS} items to stay within token limits.")
        items = items[:MAX_ITEMS]

    print("Stripping PII...")
    stripped = [strip_pii(item) for item in items]

    print("Sending to Claude for analysis (this may take 30-60 seconds)...")
    report = analyze_feedback(stripped)

    # Print to console
    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    # Save report to file
    output_file = "feedback_report.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("Feedback Analysis Report\n")
        f.write(f"Source: {FEEDBACK_FILE} ({len(stripped)} items analyzed)\n")
        f.write("=" * 60 + "\n\n")
        f.write(report)

    print(f"\nReport saved to {output_file}")


if __name__ == "__main__":
    main()
