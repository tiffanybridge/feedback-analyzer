# feedback-analyzer

A command-line tool that turns a CSV of raw customer feedback into a structured, AI-generated insights report — without sending PII to the cloud.

## The Problem

Customer feedback surveys produce hundreds of free-text responses that are too time-consuming to read manually and too unstructured to analyze in a spreadsheet. Most PMs either skim a sample (missing patterns) or wait for a data analyst to wrangle it (losing days). Existing AI tools that could help require pasting raw data directly into a chat interface, which creates a real risk of sending customer PII to third-party systems, which is bad for customers, and also bad for the company's compliance requirements.

## The Solution

This tool loads a feedback CSV, strips common PII patterns locally using regex before anything leaves the machine, then sends the cleaned text to Claude for analysis. It returns a structured report identifying the top 5 themes, sentiment scores, representative quotes, and an executive summary — saved as a markdown file ready to drop into a document or share with a team.

## How to Use

**Prerequisites**
- Python 3
- An Anthropic API key

**Setup**

```bash
git clone https://github.com/tiffanybridge/feedback-analyzer
cd feedback-analyzer
pip3 install -r requirements.txt
export ANTHROPIC_API_KEY=your-key-here
```

**Run**

```bash
python3 main.py
```

The script will prompt you for:
- Path to your CSV file
- Column name containing the feedback text
- Column name for product type (optional — press Enter to skip)

It then shows a preview of the PII-stripped data and asks for confirmation before sending anything to Claude.

**Output**

A `feedback_report.md` file in the current directory, structured with themes, sentiment scores, and an executive summary.

## How It Works

The script loads the specified CSV columns using Python's built-in `csv.DictReader`. Before any data leaves the machine, it runs each feedback item through a set of regex patterns that replace emails, phone numbers, SSNs, card numbers, URLs, and IP addresses with placeholder tokens like `[EMAIL]`. The stripped text — optionally paired with product type per row — is then sent to Claude (claude-opus-4-6 with adaptive thinking enabled) in a single prompt that asks for themed analysis. The response is written to a markdown file with metadata headers.

## Tradeoffs

**Regex PII stripping over an NLP model.** A trained named entity recognition model would catch names and addresses that regex misses. I chose regex because it runs locally with no additional dependencies, is transparent and auditable, and is fast enough to preview before each run. The script surfaces a warning that names may not be caught, putting the judgment call back with the user.

**Single prompt over chunked analysis.** For very large datasets, sending all feedback in one prompt gets expensive and hits token limits. I cap at 500 items and flag this in the output. A better approach for large files would be to cluster or sample first — that's a clear next step.

## What I Learned

**Stripping PII is a product decision, not just a technical one.** Deciding what counts as sensitive enough to redact required thinking about what a customer would expect, not just what regex can match. Names are the obvious gap — and surfacing that gap to the user felt more honest than silently missing it.

**The prompt structure matters as much as the model.** Asking Claude to return a specific format (theme name, product area, frequency, sentiment, quotes, PM insight) produced dramatically more useful output than a generic "summarize this feedback" prompt. The structure forced clarity about what the analysis was actually for.

**Interactive confirmation changes how you think about data safety.** Adding the dry-run preview wasn't just a safety feature — it made me realize I'd been thinking of PII stripping as an all-or-nothing gate. Showing the user the stripped output before sending it shifts the responsibility appropriately: the tool does what it can, the user makes the final call.

## Next Steps

1. **Sampling for large files.** Rather than a hard cap at 500 items, add a smart sampling mode that stratifies by product type so each segment is proportionally represented in the analysis.
2. **Multi-run comparison.** Accept two CSVs and prompt Claude to identify what changed between periods — useful for tracking whether issues were resolved after a product change.
3. **Name detection.** Integrate a lightweight NLP library like spaCy to catch person names that regex can't reliably detect.
