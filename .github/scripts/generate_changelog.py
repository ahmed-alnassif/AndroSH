#!/usr/bin/env python3

import argparse
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
SEP = "\x01"
BOT_MARKERS = ("github-actions[bot]", "[bot]", "unknown")


def get_commits(from_ref, to_ref):
	range_spec = f"{from_ref}..{to_ref}" if from_ref else to_ref
	result = subprocess.run(
		["git", "log", range_spec, f"--pretty=format:%s{SEP}%an", "--no-merges"],
		capture_output=True,
		text=True,
		check=True,
	)
	commits = []
	for line in result.stdout.splitlines():
		if not line.strip():
			continue
		subject, _, author = line.partition(SEP)
		commits.append((subject, (author or "unknown").strip()))
	return commits


def is_bot(author):
	lowered = author.lower()
	return any(marker in lowered for marker in BOT_MARKERS)


def categorize(commits):
	buckets = {label: [] for _, label in CATEGORY_MAP}
	other = []
	bot_commits = []

	for subject, author in commits:
		if is_bot(author):
			bot_commits.append(subject)
			continue

		match = COMMIT_RE.match(subject)
		if not match:
			other.append((subject, author))
			continue

		commit_type, scope, _, message = match.groups()
		label = next((lbl for prefix, lbl in CATEGORY_MAP if commit_type == prefix), None)

		if label is None:
			other.append((subject, author))
			continue

		if scope:
			scope_name = scope.strip("()")
			message = f"**{scope_name}:** {message}"

		buckets[label].append((message, author))

	return buckets, other, bot_commits


def format_author(author):
	handle = author.strip().replace(" ", "-")
	return f" (@{handle})"


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


def build_body(version, prev_version, buckets, other, bot_commits, repo_slug):
	lines = [f"## v{version} Release Changelog", ""]

	for _, label in CATEGORY_MAP:
		items = dedupe_preserve_order(buckets.get(label, []))
		if not items:
			continue
		lines.append(f"### {label}")
		lines.append("")
		for message, author in items:
			lines.append(f"- {message}{format_author(author)}")
		lines.append("")

	if other:
		items = dedupe_preserve_order(other)
		lines.append("### 📦 Other")
		lines.append("")
		for message, author in items:
			lines.append(f"- {message}{format_author(author)}")
		lines.append("")

	if bot_commits:
		items = dedupe_preserve_order(bot_commits)
		lines.append("### 🤖 Automated")
		lines.append("")
		for subject in items:
			lines.append(f"- {subject}")
		lines.append("")

	if prev_version:
		lines.append(f"**Full Changelog**: {prev_version}...v{version}")

	return "\n".join(lines).strip() + "\n"


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--from", dest="from_ref", default="")
	parser.add_argument("--to", dest="to_ref", default="HEAD")
	parser.add_argument("--version", required=True)
	parser.add_argument("--prev-version", dest="prev_version", default="")
	parser.add_argument("--output", default="changelog_body.md")
	parser.add_argument("--repo-slug", default="")
	args = parser.parse_args()

	commits = get_commits(args.from_ref, args.to_ref)
	buckets, other, bot_commits = categorize(commits)
	body = build_body(args.version, args.prev_version, buckets, other, bot_commits, args.repo_slug)

	with open(args.output, "w") as f:
		f.write(body)

	print(body)


if __name__ == "__main__":
	sys.exit(main())