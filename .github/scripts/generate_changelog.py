#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import sys

CATEGORY_MAP = [
	("feat", "✨ Features"),
	("fix", "🔧 Fixes"),
	("docs", "📚 Documentation"),
	("refactor", "♻️ Refactoring"),
	("style", "🎨 Style"),
	("ci", "⚙️ CI/CD"),
	("test", "🧪 Tests"),
	("chore", "🧹 Chores"),
]

COMMIT_RE = re.compile(r"^([a-z]+)(\([^)]*\))?(!)?:\s*(.+)$")
BOT_MARKERS = ("github-actions[bot]", "[bot]", "unknown")
MERGE_RE = re.compile(r"^merge pull request #\d+", re.IGNORECASE)


def get_commits(repo_slug, from_ref, to_ref):
	result = subprocess.run(
		["gh", "api", f"repos/{repo_slug}/compare/{from_ref}...{to_ref}"],
		capture_output=True,
		text=True,
		check=True,
	)
	data = json.loads(result.stdout)

	commits = []
	for item in data.get("commits", []):

		subject = item["commit"]["message"].split("\n")[0].strip()
		commit_name = (item["commit"]["author"] or {}).get("name", "unknown").strip()
		author = (item.get("author") or {}).get("login")

		commits.append((subject, commit_name, author))

	return commits


def is_bot(commit_name, author):
	lowered = f"{commit_name} {author or ''}".lower()
	return any(marker in lowered for marker in BOT_MARKERS)


def format_author(author):
	if author:
		return f" (@{author})"
	return ""


def categorize(commits):
	buckets = {label: [] for _, label in CATEGORY_MAP}
	other = []
	bot_commits = []

	for subject, commit_name, author in commits:
		if MERGE_RE.match(subject):
			continue

		if is_bot(commit_name, author):
			bot_commits.append(subject)
			continue

		author_tag = format_author(author)

		match = COMMIT_RE.match(subject)
		if not match:
			other.append((subject, author_tag))
			continue

		commit_type, scope, _, message = match.groups()
		label = next((lbl for prefix, lbl in CATEGORY_MAP if commit_type == prefix), None)

		if label is None:
			other.append((subject, author_tag))
			continue

		if scope:
			scope_name = scope.strip("()")
			message = f"**{scope_name}:** {message}"

		buckets[label].append((message, author_tag))

	return buckets, other, bot_commits


def dedupe_preserve_order(items):
	seen = set()
	result = []
	for item in items:
		key = item if isinstance(item, str) else item[0]
		if key in seen:
			continue
		seen.add(key)
		result.append(item)
	return result


def build_body(version, buckets, other, bot_commits):
	lines = [f"## AndroSH v{version} Release Changelog", ""]

	for _, label in CATEGORY_MAP:
		items = dedupe_preserve_order(buckets.get(label, []))
		if not items:
			continue
		lines.append(f"### {label}")
		lines.append("")
		for message, author_tag in items:
			lines.append(f"- {message}{author_tag}")
		lines.append("")

	if other:
		items = dedupe_preserve_order(other)
		lines.append("### 📦 Other")
		lines.append("")
		for message, author_tag in items:
			lines.append(f"- {message}{author_tag}")
		lines.append("")

	if bot_commits:
		items = dedupe_preserve_order(bot_commits)
		lines.append("### 🤖 Automated")
		lines.append("")
		for subject in items:
			lines.append(f"- {subject}")
		lines.append("")

	return "\n".join(lines).strip() + "\n"


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--from", dest="from_ref", required=True)
	parser.add_argument("--to", dest="to_ref", default="HEAD")
	parser.add_argument("--version", required=True)
	parser.add_argument("--output", default="changelog_body.md")
	parser.add_argument("--repo-slug", default="ahmed-alnassif/AndroSH")
	args = parser.parse_args()

	commits = get_commits(args.repo_slug, args.from_ref, args.to_ref)
	buckets, other, bot_commits = categorize(commits)
	body = build_body(args.version, buckets, other, bot_commits)

	with open(args.output, "w") as f:
		f.write(body)


if __name__ == "__main__":
	sys.exit(main())
