# Figma Node Type to Code Mapping Reference

## Layout Nodes

### FRAME (no Auto Layout)
```tsx
<div className="relative w-[320px] h-[240px] bg-[#ffffff] rounded-lg shadow-md">
  {children}
</div>
```
- FRAME with `clipsContent: true` → add `overflow-hidden`

### FRAME with Auto Layout: HORIZONTAL
```tsx
<div className="flex flex-row justify-start items-center gap-4 px-6 py-4">
  {children}
</div>
```

### FRAME with Auto Layout: VERTICAL
```tsx
<div className="flex flex-col justify-start items-stretch gap-3 px-4 py-2">
  {children}
</div>
```

### GROUP
```tsx
<div className="relative">
  {children}
</div>
```

## Shape Nodes

### RECTANGLE
```tsx
<div className="w-[200px] h-[48px] bg-[#3b82f6] rounded-lg" />
```
- Solid fill → `bg-[#hex]`
- Image fill → `<img src={asset} />`
- Gradient fill → inline style or `bg-gradient-*`
- Corner radius → `rounded-*` or `rounded-tl-[8px]` etc for individual corners

### ELLIPSE
```tsx
<div className="w-[64px] h-[64px] rounded-full bg-[#ef4444]" />
```

### LINE
Exported as SVG asset → `<img src={asset} />`

### VECTOR / BOOLEAN_OPERATION / STAR / POLYGON
Always exported as SVG → `<img src={assetRef} />`

## Text Nodes

### TEXT
```tsx
<span className="text-[14px] font-medium leading-[1.5] tracking-[0.02em] text-[#1f2937]">
  {content}
</span>
```

**Tag selection based on fontSize:**
| fontSize | HTML Tag |
|----------|----------|
| >= 32px  | `<h1>`   |
| 24-31px  | `<h2>`   |
| 18-23px  | `<h3>`   |
| 14-17px  | `<p>`    |
| < 14px   | `<span>` |

**Font weight mapping:**
| Figma fontWeight | Tailwind Class |
|-----------------|----------------|
| 100 (Thin)      | `font-thin`    |
| 300 (Light)     | `font-light`   |
| 400 (Regular)   | `font-normal`  |
| 500 (Medium)    | `font-medium`  |
| 600 (Semibold)  | `font-semibold`|
| 700 (Bold)      | `font-bold`    |
| 800 (ExtraBold) | `font-extrabold`|

**Text align mapping:**
| Figma textAlignHorizontal | Tailwind   |
|--------------------------|------------|
| LEFT                     | text-left  |
| CENTER                   | text-center|
| RIGHT                    | text-right |
| JUSTIFIED                | text-justify|

## Component Nodes

### INSTANCE
```tsx
<ButtonCard />
```
- Use the extracted reusable component name
- Map `componentName` to PascalCase component name

### COMPONENT / COMPONENT_SET
These define the reusable component. Extract as a named React component.

## Auto Layout → Tailwind Flexbox Mapping

### Direction
| layoutMode    | Tailwind       |
|---------------|----------------|
| HORIZONTAL    | flex flex-row  |
| VERTICAL      | flex flex-col  |

### Primary Axis Alignment (justify-*)
| primaryAxisAlignItems | Tailwind          |
|----------------------|-------------------|
| MIN                  | justify-start     |
| CENTER               | justify-center    |
| MAX                  | justify-end       |
| SPACE_BETWEEN        | justify-between   |

### Counter Axis Alignment (items-*)
| counterAxisAlignItems | Tailwind       |
|----------------------|----------------|
| MIN                  | items-start    |
| CENTER               | items-center   |
| MAX                  | items-end      |
| BASELINE             | items-baseline |

### Spacing
| itemSpacing    | Tailwind    |
|---------------|-------------|
| 0             | gap-0       |
| 4             | gap-1       |
| 8             | gap-2       |
| 12            | gap-3       |
| 16            | gap-4       |
| 20            | gap-5       |
| 24            | gap-6       |
| 32            | gap-8       |
| 40            | gap-10      |
| 48            | gap-12      |
| Other values  | gap-[16px]  |

## Effects Mapping

### Shadow
| Figma Drop Shadow   | Tailwind               |
|--------------------|------------------------|
| radius <= 4, light | shadow-sm              |
| radius 4-8         | shadow                 |
| radius 8-16        | shadow-md              |
| radius 16-24       | shadow-lg              |
| radius >= 24       | shadow-xl              |
| Precise spec       | shadow-[0_4px_8px_rgba(0,0,0,0.1)] |

### Blur
| Effect Type     | Tailwind       |
|----------------|----------------|
| LAYER_BLUR     | blur-sm/md/lg  |
| BACKGROUND_BLUR| backdrop-blur-sm/md/lg |

## Sizing

- Fixed dimensions → `w-[200px] h-[48px]`
- Full width → `w-full`
- Fill parent (layoutGrow: 1) → `flex-1`
- Hug content (HUG sizing) → `w-fit` or don't specify width

## Color Values

- Hex values use arbitrary bracket syntax: `bg-[#3b82f6]`, `text-[#1f2937]`
- If color matches a Tailwind palette color exactly, use the Tailwind class
- rgba() values → inline style or `bg-[#hex]` (converted)
