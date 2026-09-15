"""Convert the supplied master PNG to a multi-resolution Windows icon."""
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[1]
with Image.open(root / 'assets/app.png') as master:
    if master.width != master.height or master.width < 256:
        raise ValueError('Use a square master PNG of at least 256 pixels.')
    master = master.convert('RGBA')
    # User requested deterministic trimming; never redraw the supplied artwork.
    bounds=master.getchannel('A').getbbox()
    if bounds is None:raise ValueError('The icon image is completely transparent.')
    tile=master.crop(bounds)
    side=round(max(tile.size)/.96)
    master=Image.new('RGBA',(side,side))
    master.paste(tile,((side-tile.width)//2,(side-tile.height)//2))
    print('Source alpha bounds:',bounds,'trimmed canvas:',master.size)
    master.save(root / 'assets/app.ico', format='ICO',
        sizes=[(n, n) for n in (16, 20, 24, 28, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 128, 160, 192, 256)])
    for size in (256, 512, 1024):
        master.resize((size, size), Image.Resampling.LANCZOS).save(root / f'assets/icon-{size}.png')
with Image.open(root / 'assets/app.ico') as icon:
    print('Icon sizes:', sorted(icon.ico.sizes()))
