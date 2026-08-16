from PIL import Image, ImageDraw

BG = (13, 17, 23, 255)
FG = (88, 211, 164, 255)

NODES = [(15, 16), (15, 48), (49, 32)]
EDGES = [((15, 16), (49, 32)), ((15, 48), (49, 32))]
NODE_R = 8.5
EDGE_W = 4.0
RADIUS = 14


def render(size):
    ss = 8  # supersample
    S = size * ss
    scale = S / 64.0
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=RADIUS * scale, fill=BG)
    for a, b in EDGES:
        d.line(
            [a[0] * scale, a[1] * scale, b[0] * scale, b[1] * scale],
            fill=FG,
            width=max(1, int(EDGE_W * scale)),
        )
    for x, y in NODES:
        r = NODE_R * scale
        d.ellipse([x * scale - r, y * scale - r, x * scale + r, y * scale + r], fill=FG)
    return img.resize((size, size), Image.Resampling.LANCZOS)


big = render(512)
big.save("public/favicon-512.png")
render(180).save("public/apple-touch-icon.png")
big.save(
    "public/favicon.ico",
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)

for n in (16, 32):
    render(n).resize((160, 160), Image.Resampling.NEAREST).save(f"/tmp/fav{n}-preview.png")
print("ok")
