---
name: figma-to-code
description: This skill should be used when the user asks to "convert figma to code", "figma to react", "figma 转代码", "设计稿转代码", "figma design to code", "generate code from figma file", or wants to export Figma designs as React/Vue components using a local LLM. Supports cross-network workflow: export on an internet-connected machine, transfer the intermediate JSON, then generate code on the intranet side with DeepSeek-v4-flash.
version: 0.2.0
---

# Figma to Code

Convert Figma design files (`.fig`) into production-ready React + Tailwind CSS components.
Designed for intranet environments where the LLM (DeepSeek-v4-flash) and Figma Desktop
live on different networks.

## Pipeline Overview

```
┌── 外网（有 Figma） ──────────────────────────────────────────────────┐
│                                                                       │
│   .fig file → Figma Desktop → Export Plugin → tree.json + assets/    │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
                          │
                    tree.json + assets/   ← 通过 USB / 安全传输
                          │
┌── 内网（有 DeepSeek） ────────────────────────────────────────────────┐
│                                                                       │
│   tree.json → generate_code.py + DeepSeek-v4-flash                    │
│                     ↓                                                 │
│   output/  (React .tsx 组件 + Tailwind)                               │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

两步分离，各取所需：外网用 Figma Desktop（正常登录，100% 准确），内网用自有 LLM。

## When to Use

Trigger this skill when the user:
- Wants to generate React/Vue/Tailwind code from Figma designs
- Has a `.fig` file or Figma design they want to convert
- Mentions "figma to code", "design to code", "设计稿转代码"
- Needs to set up or debug the Figma export plugin
- Is working in a cross-network environment (intranet LLM, internet Figma)

## Workflow

There are two steps, typically run on different machines.

### Step 1: Export on the Internet Machine (Figma Desktop)

This machine needs Figma Desktop with a logged-in account and internet access.

**Load the plugin (one-time setup):**
1. Copy `scripts/` from this repo to the internet machine
2. Open Figma Desktop → Plugins → Development → "Import plugin from manifest"
3. Select `scripts/figma_export_manifest.json`

**Export the design:**
1. Open the `.fig` file in Figma Desktop
2. Run: Plugins → Development → "Figma to Code Exporter"
3. The plugin downloads two things:
   - `{filename}_figma_tree.json` — complete node tree with layout, styles, text
   - SVG/PNG files — vector shapes and images

**Troubleshooting:**
- Plugin not visible → check `main` and `ui` fields in the manifest
- Download blocked → check browser pop-up blocker in Figma settings
- Large file → plugin may take 30-60 seconds for complex designs

### Step 2: Generate Code on the Intranet (DeepSeek-v4-flash)

Transfer `tree.json` + `assets/` to the intranet machine, then:

```bash
cd ~/Code/figma-to-code

# Check prerequisites
python3 -c "import openai; print('OK')" || pip install openai

# Configure DeepSeek connection
export DEEPSEEK_API_KEY="your-api-key"
export DEEPSEEK_BASE_URL="http://your-server:8000/v1"
export DEEPSEEK_MODEL="deepseek-v4-flash"

# Generate code
python scripts/generate_code.py path/to/figma_tree.json -o ./output
```

**Common options:**
| Flag | Purpose |
|------|---------|
| `--frame LoginForm` | Process a single frame by name |
| `--list-frames` | List all frames in the tree |
| `--dry-run` | Preview the prompt without calling LLM |
| `--max-tokens 4096` | Limit response token count |

**For large designs** — process frame by frame:
```bash
python scripts/generate_code.py tree.json --list-frames    # list frames
python scripts/generate_code.py tree.json --frame "Login" -o ./output
python scripts/generate_code.py tree.json --frame "Dashboard" -o ./output
```

### Step 3: Integrate into Your Project

```bash
cp -r output/src/components/* your-project/src/components/
cp -r assets/ your-project/src/assets/
```

Verify import paths resolve and adjust as needed.

## Complete One-Machine Workflow (Reference)

If both Figma Desktop and DeepSeek are accessible on the same machine:

```bash
# 1. Export using Figma Desktop plugin → tree.json + assets/
# 2. Generate
python scripts/generate_code.py tree.json -o ./output

# Or use the convenience script
python scripts/pipeline.py tree.json -o ./output
```

## Three Transfer Strategies

Choose based on bandwidth and data sensitivity:

| Strategy | Transfer | LLM runs on | Best for |
|----------|----------|-------------|----------|
| **A: JSON 传输** | tree.json (~百KB) | 内网 | 最推荐，JSON 极小 |
| **B: 代码传输** | 生成的 .tsx (~几十KB) | 外网 | LLM 在外网时 |
| **C: 全外网** | 最终组件 | 外网 | 最省事（如果允许） |

**Strategy A is the default.** JSON is small, portable, and the LLM stays in the intranet.

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

- `scripts/generate_code.py` — code generation via DeepSeek-v4-flash
- `scripts/figma_export_plugin.js` — Figma Desktop export plugin
- `scripts/figma_export_manifest.json` — Figma plugin manifest

## Limitations

- Absolute positioned layouts (no Auto Layout) produce lower quality code
- Complex animations and interactions are not captured from static designs
- Responsive breakpoints need manual adjustment after generation
- Component variants and states (hover, active, loading) may need manual addition
- Image/icon fills on complex shapes may not export perfectly as SVG
