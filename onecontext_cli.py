#!/usr/bin/env python3
"""
onecontext_cli.py
CLI for OneContext: Ingest project documents, generate context packs, and capture decisions.
Usage:
  python onecontext_cli.py ingest <file> --project <id>
  python onecontext_cli.py pack "<task>" --target <name> --project <id>
  python onecontext_cli.py capture "<text>" --project <id>
"""

import argparse
import os
import sys
from pathlib import Path
import requests

DEFAULT_API_URL = os.environ.get("ONECONTEXT_API_URL", os.environ.get("API_URL", "http://localhost:8000"))


def cmd_ingest(args):
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File '{file_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    if file_path.suffix.lower() not in (".md", ".txt"):
        print("Error: Only .md and .txt files are supported for ingestion.", file=sys.stderr)
        sys.exit(1)

    url = f"{args.api_url}/projects/{args.project}/ingest-file"
    try:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "text/plain")}
            data = {"source_type": args.source_type}
            resp = requests.post(url, files=files, data=data, timeout=30)

        if resp.status_code == 200:
            res = resp.json()
            print(f"[Ingested] {res['source_name']}")
            print(f"  Total chunks:    {res['chunks_total']}")
            print(f"  Chunks retained: {res['chunks_retained']}")
            print(f"  Chunks skipped:  {res['chunks_skipped']} (duplicates)")
        else:
            print(f"Ingest failed ({resp.status_code}): {resp.text}", file=sys.stderr)
            sys.exit(1)
    except requests.RequestException as exc:
        print(f"Network error connecting to {url}: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_pack(args):
    url = f"{args.api_url}/projects/{args.project}/context-pack"
    payload = {
        "task": args.task,
        "target": args.target,
        "max_chars": args.max_chars,
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            # Print the pack directly to stdout so it can be piped or copied
            print(data["pack"])
        else:
            print(f"Context pack generation failed ({resp.status_code}): {resp.text}", file=sys.stderr)
            sys.exit(1)
    except requests.RequestException as exc:
        print(f"Network error connecting to {url}: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_capture(args):
    url = f"{args.api_url}/projects/{args.project}/capture"
    payload = {
        "text": args.text,
        "source_name": args.source_name,
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            print(f"[Captured] Decision saved to project '{args.project}' (ID: {data['memory_id']})")
            if data.get("has_conflict"):
                print("\n[WARNING: POLICY CONTRADICTION DETECTED]")
                conflict = data.get("conflict", {})
                if isinstance(conflict, dict):
                    print(f"Explanation: {conflict.get('explanation', 'Conflicts with existing memory')}")
                    conf_mem = conflict.get("conflicting_memory")
                    if conf_mem:
                        print(f"Conflicting existing memory: {conf_mem.get('text')}")
        else:
            print(f"Capture failed ({resp.status_code}): {resp.text}", file=sys.stderr)
            sys.exit(1)
    except requests.RequestException as exc:
        print(f"Network error connecting to {url}: {exc}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="OneContext CLI: One project. One memory. Every AI assistant.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"OneContext backend API URL (default: {DEFAULT_API_URL})",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest command
    parser_ingest = subparsers.add_parser("ingest", help="Ingest a .md or .txt file into project memory")
    parser_ingest.add_argument("file", help="Path to markdown or text document")
    parser_ingest.add_argument("--project", required=True, help="Target project ID")
    parser_ingest.add_argument("--source-type", default="doc", choices=["doc", "decision", "chat_export", "note"], help="Source type classification")
    parser_ingest.set_defaults(func=cmd_ingest)

    # Pack command
    parser_pack = subparsers.add_parser("pack", help="Generate a compact context pack for an AI assistant")
    parser_pack.add_argument("task", help="The coding task or question for the assistant")
    parser_pack.add_argument("--project", required=True, help="Target project ID")
    parser_pack.add_argument("--target", default="generic", choices=["chatgpt", "claude", "cursor", "codex", "generic"], help="Target AI assistant")
    parser_pack.add_argument("--max-chars", type=int, default=3000, help="Maximum characters in pack (default: 3000)")
    parser_pack.set_defaults(func=cmd_pack)

    # Capture command
    parser_capture = subparsers.add_parser("capture", help="Capture a new project decision with conflict checking")
    parser_capture.add_argument("text", help="Decision or rule text to retain")
    parser_capture.add_argument("--project", required=True, help="Target project ID")
    parser_capture.add_argument("--source-name", default="cli_capture", help="Source identifier label")
    parser_capture.set_defaults(func=cmd_capture)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
