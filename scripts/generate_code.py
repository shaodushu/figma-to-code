#!/usr/bin/env python3
"""
Figma to Code Generator
Reads Figma node-tree JSON and generates React + Tailwind CSS components
using a local LLM (DeepSeek-v4-flash, OpenAI-compatible API).

Usage:
  python generate_code.py tree.json -o ./output
  python generate_code.py tree.json --dry-run         # Preview prompt without API call
  python generate_code.py tree.json --frame LoginForm # Only process a specific frame
"""

import argparse
import json
import os
import re
import sys
import textwrap
from pathlib import Path

# ── Config from env vars ──────────────────────────────────────────────
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "http://localhost:8000/v1")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
MAX_TOKENS = int(os.environ.get("DEEPSEEK_MAX_TOKENS", "8192"))


# ── System Prompt ─────────────────────────────────────────────────────
SYSTEM_PROMPT = textwrap.dedent("""\
You are an expert frontend developer specializing in React, TypeScript, and Tailwind CSS.
Your task is to convert a Figma node tree (provided as JSON) into clean, production-ready
React function components with Tailwind CSS styling.

## Rules

1. **Output format**: Output ONLY the code files. Each file must be wrapped in a markdown code
   block with the file path:
   ```tsx filename="src/components/ComponentName.tsx"
   // code here
   ```

2. **Component extraction**: Identify nodes with `"isComponent": true` or `"isInstance": true`.
   Same `componentId` across instances = same reusable component. Extract these as separate
   named components.

3. **Layout mapping** (Auto Layout → Tailwind Flexbox):
   - `layoutMode: "HORIZONTAL"` → `flex flex-row`
   - `layoutMode: "VERTICAL"` → `flex flex-col`
   - `primaryAxisAlignItems: "MIN"` → `justify-start`
   - `primaryAxisAlignItems: "CENTER"` → `justify-center`
   - `primaryAxisAlignItems: "MAX"` → `justify-end`
   - `primaryAxisAlignItems: "SPACE_BETWEEN"` → `justify-between`
   - `counterAxisAlignItems: "MIN"` → `items-start`
   - `counterAxisAlignItems: "CENTER"` → `items-center`
   - `counterAxisAlignItems: "MAX"` → `items-end`
   - `itemSpacing` → `gap-{value/4}`
   - `paddingLeft/Right/Top/Bottom` → `px-* py-* pt-* pr-* pb-* pl-*`
   - `layoutWrap: "WRAP"` → `flex-wrap`

4. **Style mapping** (Figma → Tailwind):
   - Solid fill color → `bg-[#hex]` or Tailwind color if it matches exactly
   - Corner radius → `rounded-{value/4}` or `rounded-tl-*` etc for individual corners
   - Opacity → `opacity-{percent}` or inline `opacity` style for non-standard values
   - Drop shadow → `shadow-lg` etc, use arbitrary values for precise specs
   - Stroke → `border` with `border-[#hex]` and `border-{weight}`
   - Width/Height → `w-[value/4]` `h-[value/4]` or `w-full` etc. Use Tailwind sizing
     when the value maps exactly, otherwise use arbitrary values.
   - Font size → `text-{size}` or `text-[14px]` for non-standard sizes
   - Font weight → `font-{weight}` (font-normal, font-medium, font-semibold, font-bold)
   - Text color → `text-[#hex]`
   - Line height → `leading-*` or `leading-[value/4]`
   - Letter spacing → `tracking-*` or `tracking-[value/4]`
   - Text alignment → `text-left|center|right`

5. **Text nodes**:
   - Large text (fontSize >= 24) → `<h1>` or `<h2>`
   - Medium text (fontSize >= 18) → `<h3>` or `<p>` depending on context
   - Small text → `<span>` or `<p>`

6. **Asset references**: When a node has `assetRef`, use an `<img>` tag:
   ```tsx
   <img src="./assets/asset_name.svg" alt="" className="..." />
   ```

7. **Code quality**:
   - Use TypeScript with proper typing (no `any`)
   - Use `React.FC` or explicit return type
   - Keep components focused and small; extract sub-components when a file exceeds 100 lines
   - Use semantic HTML where possible
   - Add `alt` text to images based on node name
   - Import assets relatively: `import logoImg from './assets/logo.svg'`

8. **Naming**: Component names in PascalCase based on Figma node name. Sanitize:
   remove special chars, convert spaces/kebab/snake to PascalCase.

9. **Layout depth limit**: If nesting exceeds 8 levels, flatten or extract intermediate
   components.

Output each component as a separate file. Start with the leaf components (no children),
then compose them upward. The last file should be the top-level page/frame component.""")


# ── Preprocessing ─────────────────────────────────────────────────────

def preprocess_tree(tree: dict) -> dict:
    """Clean and simplify the Figma tree for LLM consumption."""
    # Preserve meta if present
    processed = {}
    if "meta" in tree:
        processed["meta"] = tree["meta"]

    processed["pages"] = []
    for page in tree.get("pages", []):
        processed_page = _preprocess_node(page)
        if processed_page:
            processed["pages"].append(processed_page)
    return processed


def _preprocess_node(node: dict) -> dict | None:
    """Process a single node, removing noise and simplifying."""
    if not node.get("visible", True):
        return None

    clean = {
        "id": node["id"],
        "name": node["name"],
        "type": node["type"],
    }

    # Geometry
    if "x" in node:
        clean["x"] = node["x"]
    if "y" in node:
        clean["y"] = node["y"]
    clean["w"] = node.get("width", 0)
    clean["h"] = node.get("height", 0)

    # Opacity
    if node.get("opacity", 1) < 1:
        clean["opacity"] = node["opacity"]

    # Fills (keep only solid and gradient, skip image fill details)
    fills = node.get("fills", [])
    solid_fills = [f for f in fills if f.get("type") in ("SOLID", "GRADIENT_LINEAR", "GRADIENT_RADIAL")]
    if solid_fills:
        clean["fills"] = solid_fills

    # Strokes
    if node.get("strokes"):
        strokes = node["strokes"]
        if isinstance(strokes, dict) and strokes.get("paints"):
            clean["strokes"] = {
                "paints": [p for p in strokes["paints"] if p.get("type") == "SOLID"],
                "weight": strokes.get("weight", 1),
            }

    # Corner radius
    if "cornerRadius" in node:
        clean["r"] = node["cornerRadius"]
    if "topLeftRadius" in node:
        clean["r"] = [
            node.get("topLeftRadius", 0),
            node.get("topRightRadius", 0),
            node.get("bottomRightRadius", 0),
            node.get("bottomLeftRadius", 0),
        ]

    # Effects
    effects = node.get("effects", [])
    if effects:
        clean["effects"] = effects

    # Auto Layout
    if node.get("autoLayout"):
        clean["layout"] = node["autoLayout"]

    # Clips content
    if node.get("clipsContent"):
        clean["clipsContent"] = True

    # Component info
    if node.get("isComponent"):
        clean["isComponent"] = True
    if node.get("isInstance"):
        clean["isInstance"] = True
        if node.get("componentId"):
            clean["componentId"] = node["componentId"]
        if node.get("componentName"):
            clean["componentName"] = node["componentName"]

    # Text
    if node.get("text"):
        clean["text"] = node["text"]

    # Asset ref
    if node.get("assetRef"):
        clean["assetRef"] = node["assetRef"]

    # Rotation
    if node.get("rotation"):
        clean["rotation"] = node["rotation"]

    # Blend mode
    if node.get("blendMode"):
        clean["blendMode"] = node["blendMode"]

    # Children
    if "children" in node:
        processed_children = []
        for child in node["children"]:
            pc = _preprocess_node(child)
            if pc:
                processed_children.append(pc)
        if processed_children:
            clean["children"] = processed_children

    return clean


# ── Component Analysis ────────────────────────────────────────────────

def find_reusable_components(tree: dict) -> dict[str, list[dict]]:
    """Find nodes that appear as instances (same componentId) and group them."""
    component_groups: dict[str, list[dict]] = {}

    def walk(node: dict):
        if node.get("isInstance") and node.get("componentId"):
            cid = node["componentId"]
            component_groups.setdefault(cid, []).append(node)
        for child in node.get("children", []):
            walk(child)

    for page in tree.get("pages", []):
        for node in page.get("children", []):
            walk(node)

    # Only keep groups with >1 occurrence (truly reusable)
    return {k: v for k, v in component_groups.items()}


def extract_frame_names(tree: dict) -> list[str]:
    """Extract top-level frame names for selective processing."""
    names = []
    for page in tree.get("pages", []):
        for node in page.get("children", []):
            if node.get("type") in ("FRAME", "COMPONENT", "COMPONENT_SET"):
                names.append(node.get("name", "Unnamed"))
    return names


# ── LLM Client ────────────────────────────────────────────────────────

def call_llm(system_prompt: str, user_prompt: str, dry_run: bool = False) -> str:
    """Call the LLM API (OpenAI-compatible) with the given prompts."""
    if dry_run:
        print("=" * 60)
        print("SYSTEM PROMPT:")
        print("=" * 60)
        print(system_prompt)
        print("\n" + "=" * 60)
        print("USER PROMPT:")
        print("=" * 60)
        print(user_prompt)
        return ""

    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai package required. Install with: pip install openai", file=sys.stderr)
        sys.exit(1)

    if not API_KEY:
        print("Error: DEEPSEEK_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=MAX_TOKENS,
        temperature=0.3,
    )

    return response.choices[0].message.content or ""


# ── Output Parsing ─────────────────────────────────────────────────────

def parse_llm_output(output: str) -> list[tuple[str, str]]:
    """Parse LLM output into list of (file_path, file_content) tuples."""
    files = []
    pattern = re.compile(r'```(?:tsx|jsx|typescript|javascript)?\s*(?:filename="([^"]+)")?\s*\n(.*?)```', re.DOTALL)
    for match in pattern.finditer(output):
        filename = match.group(1) or "Component.tsx"
        content = match.group(2).strip()
        files.append((filename, content))
    return files


# ── Main Pipeline ─────────────────────────────────────────────────────

def build_user_prompt(tree: dict, frame_name: str | None, reusable: dict[str, list[dict]]) -> str:
    """Build the user prompt with the node tree and instructions."""
    # Select the target frame(s)
    target_nodes = []
    for page in tree.get("pages", []):
        for node in page.get("children", []):
            if frame_name:
                if node.get("name") == frame_name:
                    target_nodes.append(node)
            else:
                target_nodes.append(node)

    if frame_name and not target_nodes:
        available = extract_frame_names(tree)
        print(f"Frame '{frame_name}' not found. Available frames: {available}", file=sys.stderr)
        sys.exit(1)

    # Build tree snippet
    tree_json = json.dumps(target_nodes if frame_name else tree, indent=2, ensure_ascii=False)

    # Reusable components hint
    reusable_hint = ""
    if reusable:
        names = set()
        for instances in reusable.values():
            for inst in instances:
                cn = inst.get("componentName")
                if cn:
                    names.add(cn)
        if names:
            reusable_hint = (
                "\n## Reusable Components\n"
                "The following component instances appear multiple times in the design. "
                "Extract each as a single reusable component:\n"
                + "\n".join(f"- {n}" for n in sorted(names))
                + "\n"
            )

    prompt = textwrap.dedent(f"""\
    Convert the following Figma node tree into React + Tailwind CSS components.

    {reusable_hint}
    ## Figma Node Tree (JSON)

    ```json
    {tree_json}
    ```

    Generate ALL components. Start with leaf/child components, then compose them upward.
    The top-level frame(s) should be the final component(s) that compose everything together.
    """)

    return prompt


def main():
    global MAX_TOKENS
    parser = argparse.ArgumentParser(description="Generate React+Tailwind code from Figma JSON")
    parser.add_argument("input", type=Path, help="Path to figma_tree.json")
    parser.add_argument("-o", "--output", type=Path, default=Path("./output"),
                        help="Output directory (default: ./output)")
    parser.add_argument("--frame", type=str, help="Only process a specific frame by name")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without calling LLM")
    parser.add_argument("--list-frames", action="store_true", help="List available frames and exit")
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS, help="Max tokens for LLM response")
    args = parser.parse_args()

    # Read input
    if not args.input.exists():
        print(f"Error: {args.input} not found.", file=sys.stderr)
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        raw_tree = json.load(f)

    # List frames mode
    if args.list_frames:
        frames = extract_frame_names(raw_tree)
        print("Available frames:")
        for name in frames:
            print(f"  - {name}")
        return

    # Preprocess
    print("Preprocessing tree...")
    processed = preprocess_tree(raw_tree)

    # Find reusable components
    reusable = find_reusable_components(processed)
    if reusable:
        print(f"Found {sum(len(v) for v in reusable.values())} instances of {len(reusable)} reusable components")

    # Build prompt
    user_prompt = build_user_prompt(processed, args.frame, reusable)

    # Call LLM
    print(f"Calling {MODEL}...")
    MAX_TOKENS = args.max_tokens
    result = call_llm(SYSTEM_PROMPT, user_prompt, args.dry_run)

    if args.dry_run:
        return

    # Parse and write output
    files = parse_llm_output(result)
    if not files:
        print("Warning: No code blocks found in LLM output.", file=sys.stderr)
        print("Raw output:", file=sys.stderr)
        print(result, file=sys.stderr)
        sys.exit(1)

    args.output.mkdir(parents=True, exist_ok=True)
    for file_path, content in files:
        # Normalize path
        file_path = file_path.replace("src/components/", "").replace("src/", "")
        dest = args.output / file_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  Wrote: {dest}")

    print(f"\nGenerated {len(files)} files to {args.output}/")


if __name__ == "__main__":
    main()
