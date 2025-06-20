"""
Fractal Explorer CPU (2-D) – v3
================================
Без-GPU Mandelbrot/Burning Ship/Tricorn рендерер для старих Mac.

*Tested on* Python 3.9 • Ursina 5.0 • NumPy 1.26 • Pillow 10 (macOS 13.7.2).

Controls
~~~~~~~~
Scroll      – zoom   •   Left-drag – pan   •   C – palette   •   B – back   •   R – reset

Choose set with the buttons in the top-left corner.
"""

from ursina import (
    Ursina,
    Entity,
    Button,
    window,
    mouse,
    color,
    Text,
    Texture,
    Vec2,
)
import numpy as np
from PIL import Image
import time

info_text = None  # HUD label assigned after window creation

# -----------------------------------------------------------------------------
#  Palettes (256×3 uint8) ------------------------------------------------------
# -----------------------------------------------------------------------------

def build_palette(idx: int) -> np.ndarray:
    t = np.linspace(0, 1, 256, dtype=np.float32)
    if idx == 0:  # smooth rainbow
        rgb = 0.5 + 0.5 * np.cos(6.28318 * (t[:, None] + np.array([0, .33, .67])))
    elif idx == 1:  # fiery
        rgb = np.stack((t, t**2, t**3), axis=1) ** np.array([.8, .9, 1.0])
    elif idx == 2:  # psychedelic
        rgb = 0.5 + 0.5 * np.cos(6.28318 * (t[:, None] * np.array([1, .7, .4]) + np.array([0, .15, .20])))
    else:           # grayscale
        rgb = np.repeat(t[:, None], 3, axis=1)
    return (rgb * 255).astype(np.uint8)

# -----------------------------------------------------------------------------
#  Fractal generators ----------------------------------------------------------
# -----------------------------------------------------------------------------

def next_z(fractal: str, z: np.ndarray, c: np.ndarray) -> np.ndarray:
    if fractal == 'Burning Ship':
        z = (np.abs(z.real) + 1j * np.abs(z.imag)) ** 2 + c
    elif fractal == 'Tricorn':
        z = np.conj(z) ** 2 + c
    else:  # Mandelbrot
        z = z ** 2 + c
    return z

def compute_fractal(fractal: str, cx: float, cy: float, scale: float, max_iter: int, w: int, h: int) -> np.ndarray:
    aspect = w / h if h else 1.0
    xs = np.linspace(-0.5 * scale * aspect + cx, 0.5 * scale * aspect + cx, w, dtype=np.float32)
    ys = np.linspace(-0.5 * scale + cy, 0.5 * scale + cy, h, dtype=np.float32)
    X, Y = np.meshgrid(xs, ys)
    C = X + 1j * Y

    Z = np.zeros_like(C, dtype=np.complex64)
    M = np.full(C.shape, True, dtype=bool)
    out = np.zeros(C.shape, dtype=np.uint16)

    for i in range(max_iter):
        Z[M] = next_z(fractal, Z[M], C[M])
        escaped = np.abs(Z) > 2.0
        newly = escaped & M
        out[newly] = i
        M &= ~escaped
        if not M.any():
            break
    out[M] = max_iter
    return out

# -----------------------------------------------------------------------------
#  Explorer entity -------------------------------------------------------------
# -----------------------------------------------------------------------------
class CPUFractalExplorer(Entity):
    """Interactive CPU-rendered fractal explorer (supports 3 sets)."""

    def __init__(self):
        super().__init__(
            model='quad',
            scale=(window.aspect_ratio * 2, 2),
            position=(0, 0, 1),
            texture=Texture(Image.new('RGB', (16, 16), 'black')),
        )

        # View state
        self.center = Vec2(0.0, 0.0)
        self.scale = 3.0
        self.max_iter = 300

        # Render options
        self.fractal_name = 'Mandelbrot'
        self.palette_idx = 0
        self.palette = build_palette(self.palette_idx)
        self.quality_factor = 2  # downscale for speed

        # Interaction
        self.zoom_speed = 0.8
        self.pan_speed = 1.0
        self.history: list[tuple[Vec2, float, int, str]] = []

        self._dirty = True  # initial render after window ready

    # ---------------- internal: render --------------------------------------
    def _render_to_texture(self):
        win_w, win_h = window.size
        if win_w < 2 or win_h < 2:
            return  # window not initialised yet
        t0 = time.time()
        w = max(64, int(win_w // self.quality_factor))
        h = max(64, int(win_h // self.quality_factor))

        data = compute_fractal(self.fractal_name, self.center.x, self.center.y, self.scale, self.max_iter, w, h)
        norm = (np.clip(data, 0, self.max_iter) * 255 // self.max_iter).astype(np.uint8)
        rgb = self.palette[norm]
        img = Image.fromarray(rgb[::-1], 'RGB')  # flip for Ursina texture coords
        self.texture = Texture(img)

        dt_ms = (time.time() - t0) * 1000
        if info_text:
            info_text.text = (
                f"Set   : {self.fractal_name}\n"
                f"Center: ({self.center.x:+.4f}, {self.center.y:+.4f})\n"
                f"Scale : {self.scale:.2e}\n"
                f"Iter  : {self.max_iter}   • {dt_ms:4.0f} ms"
            )
        self._dirty = False

    # ---------------- helpers ------------------------------------------------
    def save_state(self):
        self.history.append((Vec2(self.center), self.scale, self.max_iter, self.fractal_name))

    def go_back(self):
        if self.history:
            c, s, it, name = self.history.pop()
            self.center = Vec2(c)
            self.scale = s
            self.max_iter = it
            self.fractal_name = name
            self._dirty = True

    def reset_view(self):
        self.save_state()
        self.center = Vec2(0.0, 0.0)
        self.scale = 3.0
        self.max_iter = 300
        self._dirty = True

    def zoom(self, factor: float):
        uv = mouse.uv
        if not uv:
            return
        self.save_state()
        aspect = window.aspect_ratio
        focus = self.center + ((uv - 0.5) * self.scale) * Vec2(aspect, 1)
        self.scale *= factor
        self.center = focus - ((uv - 0.5) * self.scale) * Vec2(aspect, 1)
        self.max_iter = int(max(64, min(4000, 300 / self.scale ** 0.3)))
        self._dirty = True

    # ---------------- Ursina callbacks --------------------------------------
    def update(self):
        if mouse.left:  # panning
            win_w, win_h = window.size
            dx = mouse.delta[0] / win_w * self.scale * window.aspect_ratio
            dy = mouse.delta[1] / win_h * self.scale
            self.center -= Vec2(dx, dy) * self.pan_speed
            self._dirty = True
        if self._dirty:
            self._render_to_texture()

    def input(self, key):
        if key == 'scroll up':
            self.zoom(self.zoom_speed)
        elif key == 'scroll down':
            self.zoom(1 / self.zoom_speed)
        elif key == 'left mouse down':
            self.save_state()
        elif key == 'c':
            self.palette_idx = (self.palette_idx + 1) % 4
            self.palette = build_palette(self.palette_idx)
            self._dirty = True
        elif key == 'b':
            self.go_back()
        elif key == 'r':
            self.reset_view()

    # ---------------- public -------------------------------------------------
    def set_fractal(self, name: str):
        if name != self.fractal_name:
            self.fractal_name = name
            self._dirty = True

# -----------------------------------------------------------------------------
#  UI helpers ------------------------------------------------------------------
# -----------------------------------------------------------------------------

def create_set_buttons(explorer: CPUFractalExplorer):
    y = 0.45
    for name in ('Mandelbrot', 'Burning Ship', 'Tricorn'):
        btn = Button(text=name, position=(-0.86, y), scale=0.12, color=color.azure)
        btn.on_click = lambda n=name: explorer.set_fractal(n)
        y -= 0.12

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    #  Scene setup -----------------------------------------------------------------
    # -----------------------------------------------------------------------------
    # Detect headless environments and use an offscreen window if no display is available
    
    import os
    import sys
    window_type="onscreen"
    if not os.environ.get("DISPLAY"):
        print("No display available; cannot create graphical window.", file=sys.stderr)
        sys.exit(0)
    
    app = Ursina(window_type=window_type, borderless=False, title='Fractal Explorer CPU – 2-D')
    window.color = color.black
    
    explorer = CPUFractalExplorer()
    create_set_buttons(explorer)
    
    Text('Scroll – Zoom | Drag – Pan | C – Palette | B – Back | R – Reset', origin=(0, -0.5), position=(0, -0.48), scale=1.0, color=color.white)
    info_text = Text(origin=(-0.5, 0.5), position=(-window.aspect_ratio / 2 + 0.02, 0.46), scale=1.0)
    
    app.run()
