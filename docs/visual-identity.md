# Sports Trivia 1v1 - Visual Identity

## Brand Essence
**"Stadium Pulse"** - The electric tension of a championship moment, distilled into every interaction.

## Design Principles

1. **Tension Builds**: Every element should contribute to the competitive atmosphere
2. **Speed Matters**: Interfaces feel instant, responsive, zero-lag
3. **Celebrate Victory**: Wins deserve explosive feedback
4. **Dark Arena**: The UI is a digital stadium at night

---

## Color System

### Primary Palette
| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| Void Black | `#0D0D0F` | 13, 13, 15 | Primary background |
| Surface | `#1A1A1F` | 26, 26, 31 | Cards, elevated surfaces |
| Electric Cyan | `#00F5D4` | 0, 245, 212 | Primary accent, CTAs, highlights |
| Pulse Orange | `#FF6B35` | 255, 107, 53 | Warning state, medium urgency |
| Victory Green | `#00FF87` | 0, 255, 135 | Success, correct answers, wins |
| Loss Red | `#FF3366` | 255, 51, 102 | Errors, incorrect, losses |

### Neutral Palette
| Name | Hex | Usage |
|------|-----|-------|
| White | `#FFFFFF` | Primary text |
| Gray 400 | `#9CA3AF` | Secondary text |
| Gray 500 | `#6B7280` | Tertiary text, hints |
| Gray 700 | `#374151` | Borders, dividers |
| Gray 900 | `#111827` | Subtle backgrounds |

### Timer Urgency Gradient
```
60s-30s: Electric Cyan (#00F5D4)
30s-15s: Pulse Orange (#FF6B35)
15s-5s:  Loss Red (#FF3366) + pulse animation
5s-0s:   Loss Red + screen shake + border throb
```

---

## Typography

### Font Stack
```css
--font-display: 'Bebas Neue', Impact, sans-serif;
--font-body: 'DM Sans', -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', 'SF Mono', monospace;
--font-numbers: 'Oswald', 'Bebas Neue', sans-serif;
```

### Type Scale
| Style | Font | Size | Weight | Usage |
|-------|------|------|--------|-------|
| Hero | Bebas Neue | 64px | 400 | Main titles, "SPORTS TRIVIA" |
| H1 | Bebas Neue | 48px | 400 | Screen titles |
| H2 | Bebas Neue | 32px | 400 | Section headers |
| H3 | DM Sans | 24px | 600 | Card titles |
| Body | DM Sans | 16px | 400 | General text |
| Caption | DM Sans | 14px | 400 | Secondary info |
| Timer | Oswald | 72px | 500 | Countdown numbers |
| Score | Oswald | 36px | 500 | Point displays |
| Code | JetBrains Mono | 24px | 500 | Room codes |

---

## Spacing System

Base unit: 4px

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Tight spacing |
| sm | 8px | Inner padding |
| md | 16px | Standard gaps |
| lg | 24px | Section spacing |
| xl | 32px | Large gaps |
| 2xl | 48px | Screen padding |
| 3xl | 64px | Hero spacing |

---

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| sm | 4px | Buttons, small elements |
| md | 8px | Cards, inputs |
| lg | 12px | Large cards |
| xl | 16px | Modals, sheets |
| full | 9999px | Pills, avatars |

---

## Shadows & Effects

### Glow Effects (signature look)
```css
/* Cyan glow - primary elements */
--glow-cyan: 0 0 20px rgba(0, 245, 212, 0.3),
             0 0 40px rgba(0, 245, 212, 0.1);

/* Orange glow - warning state */
--glow-orange: 0 0 20px rgba(255, 107, 53, 0.4),
               0 0 40px rgba(255, 107, 53, 0.2);

/* Red glow - urgent/error */
--glow-red: 0 0 30px rgba(255, 51, 102, 0.5),
            0 0 60px rgba(255, 51, 102, 0.3);

/* Victory glow */
--glow-green: 0 0 30px rgba(0, 255, 135, 0.4),
              0 0 60px rgba(0, 255, 135, 0.2);
```

### Card Shadows
```css
--shadow-card: 0 4px 6px -1px rgba(0, 0, 0, 0.3),
               0 2px 4px -2px rgba(0, 0, 0, 0.2);

--shadow-elevated: 0 10px 15px -3px rgba(0, 0, 0, 0.4),
                   0 4px 6px -4px rgba(0, 0, 0, 0.3);
```

---

## Animation Specifications

### Timing Functions
```css
--ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
--ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1);
```

### Durations
| Token | Value | Usage |
|-------|-------|-------|
| instant | 100ms | Button feedback |
| fast | 200ms | UI transitions |
| normal | 300ms | Standard animations |
| slow | 500ms | Page transitions |
| reveal | 800ms | Dramatic reveals |

### Key Animations

**Pulse Effect** (urgency indicator)
```
Scale: 1.0 → 1.05 → 1.0
Opacity: 1.0 → 0.8 → 1.0
Duration: 1000ms (slow) → 500ms (fast)
```

**Shake Effect** (wrong answer)
```
X offset: 0 → -10px → 10px → -10px → 10px → 0
Duration: 400ms
Easing: ease-in-out
```

**Score Pop** (points earned)
```
Scale: 0 → 1.2 → 1.0
Y offset: 20px → 0
Duration: 500ms
Easing: ease-bounce
```

**Confetti Burst** (victory)
```
Particle count: 100
Spread: 360°
Duration: 3000ms
Colors: [#00F5D4, #00FF87, #FFFFFF]
```

---

## Component Patterns

### Buttons
- **Primary**: Cyan background, dark text, glow on hover
- **Secondary**: Transparent, cyan border, cyan text
- **Danger**: Red background, white text
- **Ghost**: No background, gray text, subtle hover

### Inputs
- **Default**: Dark surface, gray border, white text
- **Focus**: Cyan border, cyan glow
- **Error**: Red border, red glow
- **Success**: Green border, green glow

### Cards
- **Default**: Surface background, subtle border
- **Active**: Cyan border, cyan glow
- **Submitted**: Green border, checkmark icon
- **Opponent**: Slightly different surface, waiting indicator

---

## Iconography

Use **Material Icons** with:
- Stroke width: 2px equivalent
- Size: 24px (standard), 20px (small), 32px (large)
- Color: Inherit from text color

Key icons:
- Basketball: `sports_basketball`
- Soccer: `sports_soccer`
- Check: `check` / `check_circle`
- Copy: `copy`
- Share: `share`
- Timer: `timer`
- Trophy: `emoji_events`
- Person: `person`
- Exit: `exit_to_app`

---

## Sound Design (Optional)

| Event | Sound | Duration |
|-------|-------|----------|
| Button tap | Soft click | 50ms |
| Submit | Whoosh | 200ms |
| Wrong answer | Low buzz | 300ms |
| Correct answer | Triumphant ding | 500ms |
| Timer warning | Tick (increasing tempo) | Loop |
| Victory | Celebration fanfare | 1500ms |

---

## Responsive Breakpoints

| Breakpoint | Width | Usage |
|------------|-------|-------|
| Mobile | < 600px | Single column, stacked layout |
| Tablet | 600-900px | Two column where appropriate |
| Desktop | > 900px | Full layout, max-width containers |

### Max Content Widths
- Cards: 500px
- Game area: 600px
- Full width with padding: 100% - 48px

---

## Accessibility

### Color Contrast
All text meets WCAG AA standards:
- Primary text (#FFFFFF) on background (#0D0D0F): 18.1:1
- Secondary text (#6B7280) on background: 5.2:1
- Accent colors used sparingly and with icons/text backup

### Focus States
- Visible focus rings using cyan glow
- Tab order follows visual flow
- Interactive elements minimum 44x44px touch target

### Motion
- Respect `prefers-reduced-motion`
- Critical animations only in reduced motion mode
- No auto-playing animations that can't be paused
