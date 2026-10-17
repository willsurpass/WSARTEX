# WSARTEX wordmark

The wordmark uses **Inter Bold Italic (700, optical size 32)** with uppercase
`WSARTEX`. Glyphs are stored as SVG paths so rendering does not depend on fonts
installed on the viewing device. The visible lettering is centered by its ink
bounds on both axes.

- `logo-light.svg` / `.png`: centered black lettering on a white 1920 × 1920 canvas.
- `logo-dark.svg` / `.png`: centered white lettering on a black 1920 × 1920 canvas.
- `wordmark.svg`: black lettering on a transparent 880 × 160 canvas.
- `wordmark-white.svg`: white lettering on a transparent 880 × 160 canvas.
- `icon.svg`: square browser icon adapting to the system light/dark preference.

`../logo.svg`, `../logo.png`, `../../src/app/icon.png` and
`../../src/app/favicon.ico` are derived from the light variant. Run the normal
static frontend build and copy its output into `server/webui/dist` before
rebuilding the embedded Go application.
