"""Rounded, DPI-aware donation button with standard ttk keyboard behavior."""
import tkinter.font as tkfont
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk


class DonationStyle:
    def __init__(self, root, family):
        self.root = root
        self.font = tkfont.Font(root=root, family=family, weight='bold')
        self.images = {}

    def apply(self, scale):
        style = ttk.Style(self.root)
        self.font.configure(size=-scale.px(12))
        size = scale.px(28)
        element = f'Donation{size}.background'
        if size not in self.images:
            images = []
            for fill, focused in (('#c4385c', False), ('#af294c', False),
                                  ('#92203f', False), ('#dce1ea', False),
                                  ('#c4385c', True), ('#af294c', True),
                                  ('#92203f', True)):
                image = Image.new('RGB', (size*4, size*4), '#f5f7fb')
                draw = ImageDraw.Draw(image)
                inset = max(1, scale.px(2))*4
                if focused:
                    draw.rounded_rectangle((0, 0, size*4-1, size*4-1),
                                           radius=scale.px(9)*4, fill='#88203e')
                draw.rounded_rectangle((inset, inset, size*4-1-inset, size*4-1-inset),
                                       radius=scale.px(7)*4, fill=fill)
                image = image.resize((size, size), Image.Resampling.LANCZOS)
                images.append(ImageTk.PhotoImage(image, master=self.root))
            self.images[size] = images
            style.element_create(element, 'image', images[0],
                                 ('disabled', images[3]),
                                 ('pressed', 'focus', images[6]),
                                 ('active', 'focus', images[5]),
                                 ('focus', images[4]),
                                 ('pressed', images[2]), ('active', images[1]),
                                 border=scale.px(10), sticky='nsew')
        style.layout('Donation.TButton', [(element, {'sticky': 'nsew', 'children': [
            ('Button.padding', {'sticky': 'nsew', 'children': [
                ('Button.label', {'sticky': 'nsew'})]})]})])
        style.configure('Donation.TButton', font=self.font, foreground='white',
                        padding=scale.px((11, 5)), anchor='center')
        style.map('Donation.TButton', foreground=[('disabled', '#697386'), ('!disabled', 'white')])
