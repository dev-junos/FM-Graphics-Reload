# Application icon

Master image supplied by JunHo as `FM_Graphics_Reload_icon.png` for FM Graphics Reload 0.16.

- `app.png`: unmodified supplied PNG master, 1254 × 1254.
- `app.ico`: Windows conversion using Pillow, sizes 16, 20, 24, 28, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 128, 160, 192 and 256 pixels. Alpha preserved. Used for both EXE and window icons.
- `icon-256.png`, `icon-512.png`, `icon-1024.png`: high resolution window icon sources. Version 0.18 trims the supplied master's exterior transparent padding and centers its unchanged artwork on a 96%-occupied square before resizing. User explicitly chose deterministic code trimming. The source PNG remains unchanged. The image-generation candidate was not used.
- Version 0.17 selects native small/large icons using the window DPI and updates them when moving between monitors. At 200% DPI, the large native icon is 64 pixels instead of stretching 32 pixels.
- Rebuild the ICO with `python packaging/make_icon.py` after replacing the master.
- Included in the source package with the user's requested application icon.

No image generation or content editing was used for this replacement.

## Optional donation QR

`donation-qr.png` is the unchanged 820×820 PNG supplied by JunHo in `후원qr/ko-fi_qrcode.png`. Its decoded target is `https://ko-fi.com/Y7I7271PYH/?ref=qr&v=2`. It contains 33×33 QR modules plus a four-module white quiet zone on every side. `donation.json` records that target and the total 41 modules. The UI uses nearest-neighbor scaling to a whole number of pixels per module. The QR and target are public release assets explicitly supplied for the optional donation panel.
