---
name: figma-to-code
description: This skill should be used when the user asks to "convert figma to code", "figma to react", "figma 转代码", "设计稿转代码", "figma design to code", "generate code from figma file", or wants to export Figma designs as React/Vue components using a local LLM. Handles offline .fig file processing, Figma Desktop plugin usage, and code generation with DeepSeek-v4-flash.
version: 0.1.0
---

# Figma to Code

Convert Figma design files (`.fig`) into production-ready React + Tailwind CSS components
using a local DeepSeek-v4-flash LLM in an intranet/offline environment.

## Pipeline Overview

```
.fig file → Figma Desktop → Export Plugin → node-tree.json + assets/
                                              ↓
                                    generate_code.py + DeepSeek-v4-flash
                                              ↓
                                    React .tsx components + Tailwind
```

## When to Use

Trigger this skill when the user:
- Wants to generate React/Vue code from Figma designs
- Has a `.fig` file or Figma design they want to convert
- Mentions "figma to code", "design to code", "设计稿转代码"
- Needs to set up or debug the Figma export plugin
- Wants to improve code generation quality from Figma designs

## Workflow

### Step 1: Check Environment

Verify the prerequisites:
```bash
python3 -c "import openai; print('openai OK')" 2>&1 || echo "pip install openai"
```

Check environment variables:
```bash
echo "API Key: ${DEEPSEEK_API_KEY:0:8}..."
echo "Base URL: $DEEPSEEK_BASE_URL"
echo "Model: ${DEEPSEEK_MODEL:-deepseek-v4-flash}"
```

If not set, configure:
```bash
export DEEPSEEK_API_KEY="your-api-key"
export DEEPSEEK_BASE_URL="http://your-server:8000/v1"
export DEEPSEEK_MODEL="deepseek-v4-flash"
```

### Step 2: Export from Figma Desktop

The Figma export plugin is at `scripts/figma_export_plugin.js` in this skill's
project directory (`~/Code/figma-to-code/`).

**To load the plugin:**
1. Open Figma Desktop and open the design file
2. Right-click in the canvas → Plugins → Development → "Import plugin from manifest"
3. Select `scripts/figma_export_manifest.json`
4. Run the plugin: Plugins → Development → "Figma to Code Exporter"

The plugin will download:
- `{filename}_figma_tree.json` — the complete node tree
- SVG/PNG asset files — vector shapes, images

**Troubleshooting exports:**
- If the plugin doesn't appear, verify `main` and `ui` fields in manifest match actual filenames
- If download doesn't start, check browser pop-up blocker
- For large files, the plugin may take a minute to traverse all nodes

### Step 3: Generate Code

Run the generation script:
```bash
cd ~/Code/figma-to-code
python scripts/generate_code.py path/to/figma_tree.json -o ./output
```

**Common options:**
- `--frame FrameName` — process only a specific frame
- `--list-frames` — list all frames in the tree
- `--dry-run` — preview the prompt without calling the LLM
- `--max-tokens 4096` — limit output token count

**For large designs:**
Process one frame at a time to stay within context limits:
```bash
python scripts/generate_code.py tree.json --frame "LoginPage" -o ./output
python scripts/generate_code.py tree.json --frame "Dashboard" -o ./output
```

### Step 4: Integrate into Project

The generated files go to the output directory. Each component is a `.tsx` file
with imports. Copy them into your project:
```bash
cp -r output/* your-project/src/components/
cp -r assets/ your-project/src/assets/
```

Verify imports resolve correctly and adjust paths as needed.

## Improving Results

If code quality is poor:

1. **Frame too complex** → process sub-frames individually with `--frame`
2. **Components not extracted** → check that instances in Figma have proper component names
3. **Tailwind classes wrong** → review `references/node_mapping.md` for mapping rules
4. **Layout broken** → verify Figma nodes use Auto Layout (absolute positioned nodes
   generate worse code)

For prompt engineering details, read `references/prompt_templates.md`.

## Node Mapping Reference

For the complete Figma node type → React/Tailwind mapping, read
`references/node_mapping.md`. It covers:
- Auto Layout → Flexbox exact mapping
- Text styles → Tailwind typography classes
- Color, shadow, radius mappings
- Component instance handling

## Scripts

- `scripts/generate_code.py` — main code generation pipeline
- `scripts/figma_export_plugin.js` — Figma Desktop export plugin
- `scripts/figma_export_manifest.json` — Figma plugin manifest

## Limitations

- Absolute positioned layouts (no Auto Layout) produce lower quality code
- Complex animations and interactions are not captured from static designs
- Responsive breakpoints need manual adjustment after generation
- Component variants and states (hover, active, loading) may need manual addition
- Image/icon fills on complex shapes may not export perfectly as SVG
