# Profile README setup

This profile card is generated from text. The portrait itself is ASCII; the SVG files only preserve spacing, contrast, colors, and GitHub light/dark mode switching.

## Edit the visible text

Open `profile.json`. Every value in the right-hand terminal panel is editable there.

## Edit the portrait

- `ascii/light.txt` controls the portrait shown in light mode.
- `ascii/dark.txt` controls the portrait shown in dark mode.
- Each portrait must stay at exactly **25 lines** and no more than **44 characters per line**.
- Spaces are the transparent/background area around your face and body.

## Rebuild locally

```bash
python build_profile.py --offline
```

That creates:

- `light_mode.svg`
- `dark_mode.svg`

## Automatic updates

The GitHub Action in `.github/workflows/build.yml` runs whenever the source files change and once daily. It regenerates both SVGs and refreshes public repository, star, and follower counts.

The profile README uses an HTML `<picture>` element, so GitHub automatically selects the correct card for the viewer's light or dark theme.

Layout inspired by Andrew6rant's profile README, rebuilt for Corbin Floyd with editable source files and a simplified generator.
