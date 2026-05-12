# LLM Prompt Templates for Figma to Code

## System Prompt Configuration

The system prompt in `generate_code.py` covers the general case. Use these
variations for specific scenarios.

### For React + Tailwind (Default)

See `generate_code.py` SYSTEM_PROMPT constant. Covers:
- React function components with TypeScript
- Tailwind CSS utility classes
- Auto Layout → Flexbox mapping
- Component extraction from Figma instances
- Asset reference handling

### For Vue 3 + Tailwind

To switch to Vue 3, modify the system prompt:

```
You are an expert frontend developer specializing in Vue 3, TypeScript, and Tailwind CSS.
Convert Figma node trees into Vue 3 Single File Components (SFC) with `<script setup lang="ts">`.

- Use Composition API (`<script setup lang="ts">`)
- Use `defineProps<>()` for component props with TypeScript types
- Use Tailwind CSS for all styling
- Emit events with `defineEmits<>()` when needed
- Scoped styles only if Tailwind can't express something
```

### For React Native + Tailwind (NativeWind)

```
You are an expert React Native developer using NativeWind (Tailwind for RN).
Convert Figma node trees into React Native components.

- Use `<View>`, `<Text>`, `<Image>`, `<ScrollView>`, `<Pressable>` 
- Import from 'react-native'
- Use NativeWind className for styling (works like Tailwind but for RN)
- RN does not support CSS grid, so always use flex layout
- Images use `source={require('./assets/...')}`
```

## Prompt Engineering Tips

### 1. Context Window Management

Figma trees can be very large. To stay within LLM context limits:

- Preprocess to remove noise (done in `generate_code.py`)
- Process one frame at a time with `--frame`
- For very large frames, split by top-level children

### 2. Improving Output Quality

If the LLM output is not satisfactory:

**Problem: Components not being extracted**
→ In the user prompt, explicitly list component instances:
```
The node "Button/Primary" (id: 123:456) appears 5 times. Create a reusable 
`PrimaryButton` component and use it everywhere this instance appears.
```

**Problem: Tailwind classes wrong**
→ Add a Tailwind cheatsheet to the system prompt with exact mapping rules.

**Problem: Layout broken**
→ Ask the LLM to validate: "After generating, verify all flex containers have
correct justify/items alignment."

**Problem: Missing interactive states**
→ Add to prompt: "Add hover, focus, active states using Tailwind variants
(hover:bg-*, focus:ring-*, etc.)"

### 3. Two-Pass Generation (for complex designs)

Pass 1: Ask the LLM to identify and list all reusable components.
Pass 2: Feed the component list back and ask for full code generation.

```
Pass 1 prompt: "Analyze this Figma tree and identify all reusable components.
List them with their names, IDs, and suggested component names."

Pass 2 prompt: "Now generate all components. Here is the component list: 
[result from pass 1]. Generate leaf components first, then compose upward."
```
