# UI.md — React Native + NativeWind Design System (Compact)

This is the single source of truth for UI in this project. Any time a screen or
component is built (by me, a teammate, or an AI assistant), it follows this
file — not personal preference in the moment. If a new pattern is needed,
add it here first, then use it.

**Stack assumed:** React Native (Expo), NativeWind v4 (Tailwind classes via
`className`), `lucide-react-native` for icons, `react-native-reanimated` for
animation (optional).

**Density philosophy:** this system defaults to **compact** — tighter padding,
smaller type, more content visible per screen without feeling cramped. The
one thing that never shrinks is the **44x44 minimum touch target** — if a
visual element is smaller than that, pad the tappable area with `hitSlop`
rather than making the element itself bigger than it needs to look.

---

## 1. Design Tokens

All tokens live in `tailwind.config.js` — never hardcode a hex value or a
raw pixel number inside a component. If a value isn't in the scale below,
add it to the config, don't inline it.

```js
// tailwind.config.js
module.exports = {
  content: ["./app/**/*.{js,jsx,ts,tsx}", "./components/**/*.{js,jsx,ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#4F46E5", // indigo-600 — swap to your brand color
          light: "#818CF8",
          dark: "#3730A3",
        },
        surface: "#FFFFFF",
        background: "#F8F9FB",
        border: "#E5E7EB",
        text: {
          primary: "#111827",
          muted: "#6B7280",
          faint: "#9CA3AF",
          inverse: "#FFFFFF",
        },
        success: "#16A34A",
        warning: "#D97706",
        danger: "#DC2626",
        info: "#2563EB",
      },
      fontFamily: {
        sans: ["Inter_400Regular"],
        "sans-medium": ["Inter_500Medium"],
        "sans-semibold": ["Inter_600SemiBold"],
        "sans-bold": ["Inter_700Bold"],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "8px",
        md: "8px",
        lg: "10px",
      },
    },
  },
};
```

> Swap `primary` and fonts to match your brand — everything else in this doc
> references these token names, not raw values, so a rebrand only touches
> this one file.

### Typography scale (compact)
| Use | Classes |
|---|---|
| Screen title | `text-xl font-sans-bold text-text-primary` |
| Section heading | `text-base font-sans-semibold text-text-primary` |
| Body | `text-sm font-sans text-text-primary` |
| Secondary / helper text | `text-xs font-sans text-text-muted` |
| Caption / meta | `text-[11px] font-sans text-text-faint` |
| Button label | `text-sm font-sans-semibold` |

### Spacing (compact)
- Screen horizontal padding: `px-3` (mobile default), `px-5` on tablets
- Vertical rhythm between sections: `gap-4` (not `gap-6` — keep sections close)
- Card internal padding: `p-3`
- Row / list item padding: `px-3 py-2`
- Minimum touch target: **44x44 — hard floor, never reduced.** Compactness
  applies to visuals, not to tap area. Use `hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}`
  on any element whose visual bounds are smaller than 44x44.

### Radius & elevation
- Cards / inputs / buttons: `rounded-md` (tighter than a "spacious" system —
  8px, not 14px)
- Pills / avatars / badges: `rounded-full`
- Modals / sheets: `rounded-t-lg`
- Shadow (iOS): `shadow-sm` on resting cards, `shadow` on elevated/active elements
- Shadow (Android): pair every `shadow-*` class with an explicit `elevation`
  style prop (e.g. `style={{ elevation: 1 }}`) — NativeWind's shadow classes
  don't reliably map to Android alone.

---

## 2. Layout Rules

Every screen follows this shell — don't reinvent the container per screen:

```tsx
<SafeAreaView className="flex-1 bg-background">
  <View className="flex-1 px-3">
    {/* screen content */}
  </View>
</SafeAreaView>
```

- Lists: use `FlatList`/`FlashList` with
  `contentContainerStyle={{ padding: 12, gap: 8 }}` rather than wrapping each
  row in margin classes — keeps spacing consistent and avoids double-margin
  bugs at list edges.
- Headers: sticky header pattern is
  `flex-row items-center justify-between px-3 py-2 bg-surface border-b border-border`.
- Never nest `ScrollView` inside `ScrollView`. If content needs independent
  scroll regions, use `FlatList`'s own scroll or `nestedScrollEnabled`
  deliberately, not by default.

---

## 3. Core Components

Every component below lives in `components/ui/`, one file per component,
PascalCase filename matching the export. Import via a barrel
(`components/ui/index.ts`).

### Button

```tsx
// components/ui/Button.tsx
import { Pressable, Text, ActivityIndicator } from "react-native";

type Variant = "primary" | "secondary" | "ghost" | "destructive";
type Size = "sm" | "md" | "lg";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: "bg-primary active:bg-primary-dark",
  secondary: "bg-surface border border-border active:bg-background",
  ghost: "bg-transparent active:bg-background",
  destructive: "bg-danger active:opacity-90",
};

const TEXT_CLASSES: Record<Variant, string> = {
  primary: "text-text-inverse",
  secondary: "text-text-primary",
  ghost: "text-primary",
  destructive: "text-text-inverse",
};

// Compact sizing — "sm" is the default across the app, "lg" is the exception
// reserved for primary CTAs (e.g. "Submit", "Continue") on their own screen.
const SIZE_CLASSES: Record<Size, string> = {
  sm: "px-3 py-2",
  md: "px-3.5 py-2.5",
  lg: "px-4 py-3",
};

export function Button({
  label,
  onPress,
  variant = "primary",
  size = "sm",
  loading = false,
  disabled = false,
}: {
  label: string;
  onPress: () => void;
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      accessibilityRole="button"
      accessibilityLabel={label}
      className={`rounded-md items-center justify-center flex-row gap-1.5 ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${
        disabled ? "opacity-50" : ""
      }`}
    >
      {loading && <ActivityIndicator size="small" />}
      <Text className={`font-sans-semibold text-sm ${TEXT_CLASSES[variant]}`}>
        {label}
      </Text>
    </Pressable>
  );
}
```

**Rule:** every interactive element uses `Pressable`, never bare `View` +
`onTouchEnd`, and always has an `active:` state class so touch feedback is
never silent. `hitSlop` is mandatory whenever the visual button is smaller
than 44x44 — which, at compact `sm` sizing, is often the case.

### TextField

```tsx
// components/ui/TextField.tsx
import { View, Text, TextInput } from "react-native";

export function TextField({
  label,
  error,
  helperText,
  ...inputProps
}: { label: string; error?: string; helperText?: string } & React.ComponentProps<typeof TextInput>) {
  return (
    <View className="gap-1">
      <Text className="text-xs font-sans-medium text-text-primary">{label}</Text>
      <TextInput
        className={`rounded-md border px-3 py-2.5 text-sm font-sans text-text-primary bg-surface ${
          error ? "border-danger" : "border-border"
        }`}
        placeholderTextColor="#9CA3AF"
        {...inputProps}
      />
      {error ? (
        <Text className="text-[11px] font-sans text-danger">{error}</Text>
      ) : helperText ? (
        <Text className="text-[11px] font-sans text-text-muted">{helperText}</Text>
      ) : null}
    </View>
  );
}
```

### Card

```tsx
// components/ui/Card.tsx
import { View } from "react-native";

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <View
      className={`bg-surface rounded-md p-3 border border-border shadow-sm ${className}`}
      style={{ elevation: 1 }}
    >
      {children}
    </View>
  );
}
```

### Badge / Chip

```tsx
// components/ui/Badge.tsx
import { View, Text } from "react-native";

type Tone = "neutral" | "success" | "warning" | "danger" | "info";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "bg-background text-text-muted",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  danger: "bg-danger/10 text-danger",
  info: "bg-info/10 text-info",
};

export function Badge({ label, tone = "neutral" }: { label: string; tone?: Tone }) {
  const [bgClass, textClass] = TONE_CLASSES[tone].split(" ").reduce(
    (acc, cls) => (cls.startsWith("text-") ? [acc[0], cls] : [cls, acc[1]]),
    ["", ""]
  );
  return (
    <View className={`self-start rounded-full px-2 py-0.5 ${bgClass}`}>
      <Text className={`text-[11px] font-sans-semibold ${textClass}`}>{label}</Text>
    </View>
  );
}
```

### Dense list row (new — the compact-list workhorse)

Use this for any data-dense list (results, records, transactions) instead of
building a bespoke row per screen.

```tsx
// components/ui/DenseRow.tsx
import { Pressable, View, Text } from "react-native";
import { ChevronRight } from "lucide-react-native";

export function DenseRow({
  title,
  subtitle,
  trailing,
  onPress,
}: {
  title: string;
  subtitle?: string;
  trailing?: React.ReactNode;
  onPress?: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole={onPress ? "button" : undefined}
      className="flex-row items-center justify-between px-3 py-2 bg-surface rounded-md border border-border active:bg-background"
    >
      <View className="flex-1 gap-0.5 pr-2">
        <Text numberOfLines={1} className="text-sm font-sans-medium text-text-primary">
          {title}
        </Text>
        {subtitle ? (
          <Text numberOfLines={1} className="text-xs font-sans text-text-muted">
            {subtitle}
          </Text>
        ) : null}
      </View>
      <View className="flex-row items-center gap-1.5">
        {trailing}
        {onPress && <ChevronRight size={16} color="#9CA3AF" />}
      </View>
    </Pressable>
  );
}
```

### Empty state (always include one — never ship a blank screen)

```tsx
export function EmptyState({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <View className="flex-1 items-center justify-center px-6 py-12 gap-1.5">
      <Text className="text-base font-sans-semibold text-text-primary text-center">{title}</Text>
      {subtitle && <Text className="text-xs font-sans text-text-muted text-center">{subtitle}</Text>}
    </View>
  );
}
```

---

## 4. Interaction & State Rules

- Every `Pressable` gets visible feedback: `active:opacity-80`, `active:bg-*`,
  or a scale transform via Reanimated — never a component that looks
  identical pressed vs. unpressed.
- Loading states replace content, they don't hide it behind a spinner overlay
  unless the action is a full-screen block (e.g. initial auth check).
- Disabled state = `opacity-50` + `disabled` prop, always both together.
- Error states on forms show inline (`TextField`'s `error` prop), never only
  a toast — toasts supplement, they don't replace inline validation.
- Destructive actions (delete, remove, sign out) always confirm via an
  `Alert.alert` or bottom sheet before firing — never a single-tap
  destructive button.
- Compact ≠ crowded: keep `gap-2`/`gap-1.5` between related elements inside a
  component, but never remove the `gap-4` rhythm *between* distinct sections
  — density comes from trimming padding, not from deleting whitespace that
  separates unrelated content.

---

## 5. Dark Mode (if/when enabled)

NativeWind supports `dark:` variants out of the box with `useColorScheme`.
When dark mode is turned on for this app, double every semantic token:

```js
colors: {
  surface: { DEFAULT: "#FFFFFF", dark: "#1C1F26" },
  background: { DEFAULT: "#F8F9FB", dark: "#111318" },
  // ...
}
```

Then components use `bg-surface dark:bg-surface-dark` — never a separate
dark-mode component variant. Don't build this speculatively; add it only
when dark mode is actually scoped for a release.

---

## 6. Accessibility Baseline (non-negotiable, every component)

- `accessibilityRole` set correctly (`button`, `header`, `text`, `image`, etc.)
- `accessibilityLabel` on anything icon-only (no visible text label)
- Minimum touch target **44x44 — this is the one place compactness never
  applies.** Pad with `hitSlop`, don't shrink the tap area to match a small
  visual element.
- Never rely on color alone to convey state (pair `danger` red with an icon
  or text label, not just a red dot).
- Respect system font scaling — don't set `allowFontScaling={false}` unless
  there's a specific, documented layout reason. At compact type sizes
  (`text-xs`, `text-[11px]`) this matters more, not less — test with a
  larger system font size to confirm nothing clips.

---

## 7. File & Naming Conventions

```
components/
  ui/
    Button.tsx
    TextField.tsx
    Card.tsx
    Badge.tsx
    DenseRow.tsx
    EmptyState.tsx
    index.ts          # barrel: export * from "./Button" etc.
  screens/
    HomeScreen.tsx
    ProfileScreen.tsx
```

- One component per file, PascalCase filename = export name.
- Props typed with an inline type or a named `XProps` interface directly
  above the component — no separate `types.ts` per component.
- Never inline a `style={{...}}` object for anything expressible in Tailwind
  classes — `style` prop is reserved for values Tailwind can't express
  (e.g. `elevation`, dynamic runtime values).

---

## 8. Pre-Ship Checklist (run this on every new screen/component)

- [ ] Uses only tokens from Section 1 — no raw hex/px values
- [ ] Built from `components/ui/*` primitives, not bespoke one-off styling
- [ ] Follows compact spacing (`px-3`, `p-3`, `gap-4` between sections) —
      not the old spacious defaults (`px-4`, `p-4`, `gap-6`)
- [ ] Has a loading state, an empty state, and an error state (all three)
- [ ] Every tappable element has visible pressed feedback + `accessibilityLabel`
      + `hitSlop` if visually under 44x44
- [ ] Touch targets ≥ 44x44 regardless of visual size
- [ ] Tested on both iOS and Android (shadow/elevation, safe area insets)
- [ ] No nested `ScrollView`s
- [ ] Dense lists use `DenseRow`, not a bespoke row per screen

---

*When this file and the actual code disagree, this file wins — update the
code, or update this file first and then the code. Don't let them drift apart.*
