// Figma to Code Exporter Plugin
// Recursively traverses all nodes and exports structured JSON + assets.
// Usage: Load in Figma Desktop via "Import plugin from manifest".

// ── Constants ────────────────────────────────────────────────────────
const EXPORT_SETTINGS = {
  svg: { format: 'SVG', svgOutlineText: true, svgIdAttribute: false },
  png: { format: 'PNG', constraint: { type: 'SCALE', value: 2 } },
};

// Nodes to export as SVG (vector/icon types)
const SVG_NODE_TYPES = new Set([
  'VECTOR', 'BOOLEAN_OPERATION', 'STAR', 'LINE', 'POLYGON', 'ELLIPSE',
]);

// Nodes to export as PNG (raster/复杂渲染)
const PNG_NODE_TYPES = new Set(['RECTANGLE', 'FRAME', 'GROUP']);

// Nodes that may have image fills
const IMAGE_FILL_NODES = new Set(['RECTANGLE', 'ELLIPSE', 'FRAME']);

// ── Helpers ──────────────────────────────────────────────────────────

function rgbToHex(color) {
  const r = Math.round(color.r * 255);
  const g = Math.round(color.g * 255);
  const b = Math.round(color.b * 255);
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
}

function rgbaToString(color, opacity = 1) {
  const r = Math.round(color.r * 255);
  const g = Math.round(color.g * 255);
  const b = Math.round(color.b * 255);
  const a = (color.a ?? 1) * opacity;
  if (a < 1) return `rgba(${r}, ${g}, ${b}, ${a.toFixed(2)})`;
  return rgbToHex(color);
}

function extractPaint(paint) {
  if (!paint || !paint.visible) return null;
  const base = { type: paint.type };
  if (paint.type === 'SOLID') {
    base.color = rgbaToString(paint.color, paint.opacity);
  }
  if (paint.type === 'GRADIENT_LINEAR' || paint.type === 'GRADIENT_RADIAL' || paint.type === 'GRADIENT_ANGULAR') {
    base.gradientType = paint.type;
    base.stops = (paint.gradientStops || []).map(s => ({
      position: s.position,
      color: rgbaToString(s.color),
    }));
    if (paint.gradientTransform) {
      base.gradientTransform = [
        [paint.gradientTransform[0][0], paint.gradientTransform[0][1], paint.gradientTransform[0][2]],
        [paint.gradientTransform[1][0], paint.gradientTransform[1][1], paint.gradientTransform[1][2]],
      ];
    }
  }
  if (paint.type === 'IMAGE') {
    base.imageHash = paint.imageHash;
    base.scaleMode = paint.scaleMode;
  }
  return base;
}

function extractFills(node) {
  if (!node.fills || !Array.isArray(node.fills)) return [];
  return node.fills.map(extractPaint).filter(Boolean);
}

function extractStrokes(node) {
  if (!node.strokes || !Array.isArray(node.strokes)) return [];
  return {
    paints: node.strokes.map(extractPaint).filter(Boolean),
    weight: node.strokeWeight || 0,
    align: node.strokeAlign || 'INSIDE',
    style: node.strokeStyle || 'SOLID',
  };
}

function extractEffects(node) {
  if (!node.effects || !Array.isArray(node.effects)) return [];
  return node.effects
    .filter(e => e.visible !== false)
    .map(e => {
      const effect = { type: e.type };
      if (e.type === 'DROP_SHADOW' || e.type === 'INNER_SHADOW') {
        effect.color = rgbaToString(e.color);
        effect.offset = { x: e.offset?.x || 0, y: e.offset?.y || 0 };
        effect.radius = e.radius || 0;
        effect.spread = e.spread || 0;
      }
      if (e.type === 'LAYER_BLUR' || e.type === 'BACKGROUND_BLUR') {
        effect.radius = e.radius || 0;
      }
      return effect;
    });
}

function extractTextStyles(node) {
  return {
    content: node.characters || '',
    fontSize: typeof node.fontSize === 'number' ? node.fontSize : undefined,
    fontName: node.fontName ? {
      family: node.fontName.family,
      style: node.fontName.style,
    } : undefined,
    fontWeight: typeof node.fontWeight === 'number' ? node.fontWeight : undefined,
    lineHeight: node.lineHeight?.value != null ? {
      value: node.lineHeight.value,
      unit: node.lineHeight.unit,
    } : undefined,
    letterSpacing: node.letterSpacing?.value != null ? {
      value: node.letterSpacing.value,
      unit: node.letterSpacing.unit,
    } : undefined,
    textAlignHorizontal: node.textAlignHorizontal,
    textAlignVertical: node.textAlignVertical,
    textAutoResize: node.textAutoResize,
    textDecoration: node.textDecoration,
    textCase: node.textCase,
    fills: extractFills(node),
    maxLines: node.maxLines,
  };
}

function extractAutoLayout(node) {
  if (!node.layoutMode || node.layoutMode === 'NONE') return null;
  return {
    layoutMode: node.layoutMode,
    primaryAxisAlignItems: node.primaryAxisAlignItems,
    counterAxisAlignItems: node.counterAxisAlignItems,
    paddingTop: node.paddingTop || 0,
    paddingRight: node.paddingRight || 0,
    paddingBottom: node.paddingBottom || 0,
    paddingLeft: node.paddingLeft || 0,
    itemSpacing: node.itemSpacing || 0,
    layoutWrap: node.layoutWrap || 'NO_WRAP',
    counterAxisSpacing: node.counterAxisSpacing,
    primaryAxisSizingMode: node.primaryAxisSizingMode,
    counterAxisSizingMode: node.counterAxisSizingMode,
  };
}

function extractConstraints(node) {
  return {
    horizontal: node.constraints?.horizontal,
    vertical: node.constraints?.vertical,
  };
}

async function tryExportImage(node, settings) {
  try {
    return await node.exportAsync(settings);
  } catch {
    return null;
  }
}

// ── Main Traversal ───────────────────────────────────────────────────

const collectedAssets = []; // { id, name, type, data: UInt8Array }

async function extractNode(node, depth = 0) {
  const info = {
    id: node.id,
    name: node.name,
    type: node.type,
    visible: node.visible !== false,
    x: Math.round(node.x * 100) / 100,
    y: Math.round(node.y * 100) / 100,
    width: Math.round(node.width * 100) / 100,
    height: Math.round(node.height * 100) / 100,
    opacity: node.opacity ?? 1,
    blendMode: node.blendMode !== 'PASS_THROUGH' ? node.blendMode : undefined,
  };

  // Rotation
  if (node.rotation && node.rotation !== 0) {
    info.rotation = Math.round(node.rotation * 100) / 100;
  }

  // Clips content
  if (node.clipsContent) info.clipsContent = true;

  // Fills
  const fills = extractFills(node);
  if (fills.length > 0) info.fills = fills;

  // Strokes
  if (node.strokes && node.strokes.length > 0) {
    info.strokes = extractStrokes(node);
  }

  // Corner radius
  if (node.cornerRadius && node.cornerRadius !== figma.mixed) {
    info.cornerRadius = node.cornerRadius;
  }
  if (node.topLeftRadius && node.topLeftRadius > 0) {
    info.topLeftRadius = node.topLeftRadius;
    info.topRightRadius = node.topRightRadius;
    info.bottomRightRadius = node.bottomRightRadius;
    info.bottomLeftRadius = node.bottomLeftRadius;
  }

  // Effects
  const effects = extractEffects(node);
  if (effects.length > 0) info.effects = effects;

  // Auto Layout
  const autoLayout = extractAutoLayout(node);
  if (autoLayout) info.autoLayout = autoLayout;

  // Constraints (for non-auto-layout nodes)
  if (!autoLayout && node.constraints) {
    info.constraints = extractConstraints(node);
  }

  // Component info
  if (node.type === 'COMPONENT' || node.type === 'COMPONENT_SET') {
    info.isComponent = true;
    info.componentId = node.id;
  }
  if (node.type === 'INSTANCE') {
    info.isInstance = true;
    if (node.componentId) info.componentId = node.componentId;
    if (node.mainComponent?.name) info.componentName = node.mainComponent.name;
    // Overrides
    if (node.overrides && Object.keys(node.overrides).length > 0) {
      info.overrides = node.overrides;
    }
  }

  // Text styles
  if (node.type === 'TEXT') {
    info.text = extractTextStyles(node);
  }

  // Export vector nodes as SVG
  if (SVG_NODE_TYPES.has(node.type)) {
    const data = await tryExportImage(node, EXPORT_SETTINGS.svg);
    if (data) {
      const assetName = `${sanitizeFileName(node.name)}_${node.id}.svg`;
      collectedAssets.push({ id: node.id, name: assetName, type: 'svg', data });
      info.assetRef = assetName;
    }
  }

  // Check for image fills on rectangles/ellipses
  if (IMAGE_FILL_NODES.has(node.type) && node.fills) {
    const imageFills = node.fills.filter(f => f.type === 'IMAGE' && f.visible !== false);
    for (const fill of imageFills) {
      const data = await tryExportImage(node, EXPORT_SETTINGS.png);
      if (data) {
        const assetName = `${sanitizeFileName(node.name)}_${node.id}_img.png`;
        // Avoid duplicates
        if (!collectedAssets.find(a => a.name === assetName)) {
          collectedAssets.push({ id: node.id, name: assetName, type: 'png', data });
        }
      }
    }
  }

  // Children
  if ('children' in node && node.children && node.children.length > 0) {
    info.children = [];
    for (const child of node.children) {
      const childInfo = await extractNode(child, depth + 1);
      if (childInfo) info.children.push(childInfo);
    }
  }

  // Skip invisible root-level nodes
  if (!info.visible && depth === 0) return null;

  return info;
}

function sanitizeFileName(name) {
  return name.replace(/[^a-zA-Z0-9一-鿿_-]/g, '_').slice(0, 60);
}

// ── UI / Export flow ─────────────────────────────────────────────────

figma.showUI(
  `<html>
    <body>
      <script>
        window.onmessage = async (event) => {
          const msg = event.data;
          if (msg.type === 'download-json') {
            const blob = new Blob([JSON.stringify(msg.data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = msg.filename;
            a.click();
            URL.revokeObjectURL(url);
            window.parent.postMessage({ pluginMessage: { type: 'json-downloaded' } }, '*');
          }
          if (msg.type === 'download-assets') {
            for (const asset of msg.assets) {
              const bytes = new Uint8Array(asset.data);
              const blob = new Blob([bytes]);
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = asset.name;
              a.click();
              URL.revokeObjectURL(url);
              await new Promise(r => setTimeout(r, 100));
            }
            window.parent.postMessage({ pluginMessage: { type: 'assets-downloaded' } }, '*');
          }
        };
      </script>
    </body>
  </html>`,
  { visible: false, width: 1, height: 1 }
);

(async () => {
  figma.ui.postMessage({ type: 'log', text: 'Starting export...' });

  const pages = figma.root.children;
  const results = [];

  for (const page of pages) {
    const pageData = {
      id: page.id,
      name: page.name,
      type: 'PAGE',
      children: [],
    };
    for (const node of page.children) {
      const extracted = await extractNode(node);
      if (extracted) pageData.children.push(extracted);
    }
    results.push(pageData);
  }

  // Build output
  const output = {
    meta: {
      fileName: figma.root.name,
      exportedAt: new Date().toISOString(),
      pageCount: results.length,
      nodeCount: countNodes(results),
      pluginVersion: '1.0.0',
    },
    pages: results,
  };

  // Download JSON
  figma.ui.postMessage({
    type: 'download-json',
    data: output,
    filename: `${sanitizeFileName(figma.root.name)}_figma_tree.json`,
  });

  // Download assets
  if (collectedAssets.length > 0) {
    const assetPayload = collectedAssets.map(a => ({
      name: a.name,
      data: Array.from(a.data),
    }));
    figma.ui.postMessage({
      type: 'download-assets',
      assets: assetPayload,
    });
  }

  // Wait for downloads then close
  let jsonDone = false;
  let assetsDone = collectedAssets.length === 0;

  figma.ui.onmessage = (msg) => {
    if (msg.type === 'json-downloaded') jsonDone = true;
    if (msg.type === 'assets-downloaded') assetsDone = true;
    if (jsonDone && assetsDone) {
      figma.closePlugin(`Exported ${collectedAssets.length} assets and tree with ${output.meta.nodeCount} nodes.`);
    }
  };
})();

function countNodes(pages) {
  let count = 0;
  function walk(node) {
    count++;
    if (node.children) node.children.forEach(walk);
  }
  pages.forEach(p => p.children.forEach(walk));
  return count;
}
