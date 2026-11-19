#!/usr/bin/env python3
"""Move the dashboard's large embedded fallback datasets into static JSON files."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "_layouts" / "dashboard.html"
DATA = ROOT / "assets" / "data"


def extract(text: str, pattern: str, label: str) -> tuple[str, object]:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        raise SystemExit(f"Could not find embedded {label}")
    return match.group(0), json.loads(match.group(1))


def main() -> None:
    text = LAYOUT.read_text(encoding="utf-8")
    records_line, records = extract(text, r"^let R=(\[.*\]);$", "records")
    world_line, world = extract(text, r"^const WORLD=(\[.*\]);$", "world map")
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "offline-records.json").write_text(
        json.dumps(records, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (DATA / "world.json").write_text(
        json.dumps(world, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    text = text.replace(records_line, "let R=[];", 1)
    text = text.replace(world_line, "let WORLD=[];", 1)
    loader = """try{const [fallbackResponse,worldResponse]=await Promise.all([fetch(new URL('assets/data/offline-records.json',document.baseURI),{cache:'force-cache',signal:AbortSignal.timeout(8000)}),fetch(new URL('assets/data/world.json',document.baseURI),{cache:'force-cache',signal:AbortSignal.timeout(8000)})]);if(fallbackResponse.ok)R=await fallbackResponse.json();if(worldResponse.ok)WORLD=await worldResponse.json();}catch(error){console.warn('Static fallback data could not be loaded.',error.message);}\n"""
    anchor = "let ARCHIVE_AS_OF=SNAPSHOT_AS_OF;\n"
    if anchor not in text:
        raise SystemExit("Could not find archive loader anchor")
    text = text.replace(anchor, loader + anchor, 1)
    LAYOUT.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps({"records": len(records), "worldShapes": len(world)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
