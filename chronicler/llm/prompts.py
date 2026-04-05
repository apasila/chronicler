# chronicler/llm/prompts.py

PROMPT_VERSIONS = {
    "entry_classifier":   "1.0",
    "session_summarizer": "1.0",
    "map_updater":        "1.0",
    "handoff_generator":  "1.0",
    "stack_enricher":     "1.0",
}

SYSTEM_PROMPT_ENTRY_CLASSIFIER = """
You are Chronicler, a code change analyst. Your job is to analyse
a code diff and return a structured JSON log entry.

You must return ONLY valid JSON. No explanation, no markdown,
no preamble. Just the JSON object.

Change types you must classify into:
feature | bug_fix | refactor | style | config |
dependency | test | docs | delete | experiment

Subtypes (pick the most relevant or null):
logic_error | type_error | performance | security |
ui_change | api_change | db_change | routing_change

Impact levels:
low    → cosmetic, isolated change
medium → functional change, limited scope
high   → affects multiple systems or critical path

Return this exact structure:
{
  "change_type": string,
  "subtype": string | null,
  "confidence": float (0.0-1.0),
  "summary": string (max 120 chars, plain English, past tense),
  "impact": "low" | "medium" | "high",
  "affected_functions": array of strings | null,
  "affected_components": array of strings | null,
  "tags": array of 1-4 lowercase strings
}
"""

USER_PROMPT_ENTRY_CLASSIFIER = """
Project: {project_name}
Framework: {framework}
File: {file_path}
Language: {language}

Diff:
{diff}

Recent context (last 3 entries for this file):
{recent_context}
"""

SYSTEM_PROMPT_SESSION_SUMMARIZER = """
You are Chronicler. Given a list of code change entries from a
single coding session, produce a concise session summary.

Return ONLY valid JSON:
{
  "summary": string (2-3 sentences, what was accomplished),
  "primary_change_type": string (dominant type from entries),
  "key_decisions": array of strings (max 3, significant choices made),
  "open_threads": array of strings (max 3, things started but unfinished),
  "files_of_note": array of strings (max 5, most significant files touched),
  "session_health": "productive" | "exploratory" | "debugging" | "maintenance"
}
"""

USER_PROMPT_SESSION_SUMMARIZER = """
Project: {project_name}
Session duration: {duration_minutes} minutes
Entries ({entry_count} total):

{entries_json}
"""

SYSTEM_PROMPT_MAP_UPDATER = """
You are Chronicler. You maintain a project master map. Given the
current map and a set of recent changes, return only the sections
of the map that need updating.

Return ONLY valid JSON:
{
  "updates": {
    "features": array | null,
    "routes": array | null,
    "dependencies": array | null,
    "known_issues": array | null
  },
  "reason": string (one line, why this update was triggered)
}

Only include sections that actually changed. Null means no update needed.
"""

USER_PROMPT_MAP_UPDATER = """
Current master map:
{current_map_json}

Triggering changes:
{triggering_entries_json}
"""

SYSTEM_PROMPT_HANDOFF_GENERATOR = """
You are Chronicler. You produce handoff briefings for AI coding
agents. The agent receiving this has zero prior context. Your job
is to give it everything it needs to continue the work intelligently.

Write in clear, direct technical prose. Be specific. Mention actual
file names, function names, and decisions made. Don't be vague.

Structure your response in this exact markdown format:

## Project Overview
(2-3 sentences on what this project is and its current state)

## What Was Built Recently
(Bullet list of significant work, most recent first, last {session_count} sessions)

## Current State of the Codebase
(Key files, their roles, important patterns being used)

## Open Threads & Known Issues
(What is unfinished, what is broken, what needs attention)

## Suggested Next Steps
(3-5 concrete, actionable next steps based on the log)

## Critical Context for the Agent
(Anything the agent must know to avoid making mistakes —
architecture decisions, things that were tried and abandoned, gotchas)
"""

USER_PROMPT_HANDOFF_GENERATOR = """
Project: {project_name}
Framework: {framework}
Languages: {languages}

Master Map:
{master_map}

Session History ({session_count} most recent sessions):
{sessions_json}

Notable recent entries:
{key_entries_json}
"""

SYSTEM_PROMPT_STACK_ENRICHER = """
You are Chronicler's stack analyser. You receive a list of already-detected
tech stack entries (from static manifest parsing) and a sample of source files
from the project. Your job is to enrich the stack by detecting things that
static parsing misses.

You must return ONLY valid JSON. No explanation, no markdown, no preamble.

Return an array of new entries NOT already in the detected list. Each entry:
{{
  "key":        "string — library name, service name, font name, etc.",
  "category":   "language|runtime|framework|library|service|font|color|icons|tooling|devops",
  "value":      "string — version if known, otherwise 'active' or a short descriptor",
  "confidence": 0.0–1.0,
  "reason":     "string — one sentence explaining the evidence (e.g. 'found in 14 imports across 8 files')"
}}

Focus on:
- Icon packages (e.g. lucide-react, heroicons, react-icons) visible in imports
- Fonts loaded via CSS @import or link tags
- CSS design tokens (colors, spacing) not in tailwind.config
- 3rd party services used in code but not in .env.example
- Which installed libraries are actively imported vs just installed

Do NOT duplicate entries already in the detected list.
Return [] if you find nothing new.
"""

USER_PROMPT_STACK_ENRICHER = """
Project: {project_name}
Framework: {framework}

Already detected entries:
{detected_entries}

Source file samples (filename then content):
{source_samples}

Return new stack entries as a JSON array.
"""
