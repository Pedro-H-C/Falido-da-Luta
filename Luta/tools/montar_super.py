"""Monta as sheets do SUPER a partir das imagens geradas (uma linha de frames, fundo transparente).

Uso (dentro da pasta Luta):
    python tools/montar_super.py igor

Entrada (assets/images/Sprites/raw/):
    <id>_super_raw.png     -> linha com os frames do personagem, olhando para a DIREITA
    <id>_super_fx_raw.png  -> (opcional) linha com os frames do efeito, sem o personagem

Saída (assets/images/Sprites/):
    <id>_super.png     -> frames do personagem já na escala do jogo, todos do mesmo tamanho
    <id>_super_fx.png  -> frames do efeito, alinhados pelo canto esquerdo e pelo chão

No fim imprime os números para colar no "super" do personagem em CHARACTERS (fighter.py).

Como alinha:
- escala: o ÚLTIMO frame (de volta à base) fica com a mesma altura do idle da sheet principal;
- âncora: o pé de trás (o mais à esquerda) fica no mesmo lugar do pé de trás do idle, e todos
  os pés na mesma linha do chão. Os pés são achados pelos pixels escuros (roupa e tênis pretos);
  se o personagem usar roupa clara, aumente DARK_LUM.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from fighter import CHARACTERS_BY_ID  # noqa: E402

DARK_LUM = 60          # pixel "escuro" (roupa/tênis) para achar os corpos e os pés
DARK_SAT = 60          # ... e sem muita cor (aura azul-escura não conta)
FEET_BAND = 30         # altura (px da imagem gerada) da faixa dos pés
FEET_SAT = 120         # contorno do tênis pode estar tingido pela aura
PART_ALPHA = 60        # aura com alfa a partir disso forma "partes" que não são divididas entre frames
PART_MAJORITY = 0.7    # parte vai inteira para um frame se 70% dela já for dele
FX_SCALE_REL = 1.1     # efeito um pouco maior que a escala do personagem


def luminance(arr):
    return arr[..., 0] * 0.3 + arr[..., 1] * 0.59 + arr[..., 2] * 0.11


def split_frames(alpha, min_gap=10, min_width=40):
    """Separa os frames pelas colunas vazias entre eles."""
    cols = (alpha > 20).any(axis=0)
    runs, start = [], None
    for x, filled in enumerate(cols):
        if filled and start is None:
            start = x
        elif not filled and start is not None:
            runs.append([start, x])
            start = None
    if start is not None:
        runs.append([start, len(cols)])
    merged = []
    for run in runs:
        if merged and run[0] - merged[-1][1] < min_gap:
            merged[-1][1] = run[1]
        else:
            merged.append(run)
    return [r for r in merged if r[1] - r[0] >= min_width]


def split_by_bodies(body, alpha):
    """Acha os corpos (colunas com roupa/contorno) e diz de qual frame é cada pixel.
    Assim a aura de um frame que invade o espaço do vizinho continua no frame certo.
    Retorna (trechos de coluna de cada corpo, mapa dono[y, x] = 1..n)."""
    bodies = split_frames(body.astype(np.uint8) * 255)
    labels = np.zeros(body.shape, dtype=np.int32)
    for i, (x0, x1) in enumerate(bodies, start=1):
        labels[:, x0:x1][body[:, x0:x1]] = i
    # 1) cada pixel vai para o corpo mais próximo
    _, (iy, ix) = ndimage.distance_transform_edt(labels == 0, return_indices=True)
    owner = labels[iy, ix]
    # 2) partes conectadas inteiras (tênis + perna, um arco de aura) ficam com o frame da maioria
    #    dos seus pixels; primeiro o personagem opaco, depois a aura mais forte
    for threshold in (250, PART_ALPHA):
        parts, _ = ndimage.label(alpha >= threshold, structure=np.ones((3, 3)))
        for idx, box in enumerate(ndimage.find_objects(parts), start=1):
            region = parts[box] == idx
            votes = np.bincount(owner[box][region], minlength=len(bodies) + 1)
            best = votes.argmax()
            if votes[best] >= PART_MAJORITY * region.sum():
                owner[box][region] = best
    # 3) o brilho fraco segue a parte forte mais próxima
    strong = alpha >= PART_ALPHA
    _, (iy, ix) = ndimage.distance_transform_edt(~strong, return_indices=True)
    owner = np.where(strong, owner, owner[iy, ix])
    return bodies, owner


def idle_reference(char):
    """Topo, pé de trás e chão do idle (frame 0), em pixels do jogo."""
    size, scale, _ = char["data"]
    sheet = Image.open(os.path.join(ROOT, char["sheet_path"])).convert("RGBA")
    alpha = np.array(sheet.crop((0, 0, size, size)))[..., 3]
    ys, xs = np.nonzero(alpha > 200)
    return {"top": ys.min() * scale, "feet": ys.max() * scale, "back": xs.min() * scale,
            "frame": int(size * scale)}


def build_character(char, raw_path, out_path):
    ref = idle_reference(char)
    img = Image.open(raw_path).convert("RGBA")
    arr = np.array(img).astype(int)
    alpha = arr[..., 3]
    saturation = arr[..., :3].max(axis=2) - arr[..., :3].min(axis=2)
    # escuro e sem cor = roupa/contorno; azul-escuro forte de aura não conta
    dark = (alpha > 200) & (luminance(arr) < DARK_LUM) & (saturation < DARK_SAT)
    bodies, owner = split_by_bodies(dark, alpha)

    # pés: contorno escuro do tênis; tolera um pouco de cor (a luz da aura tinge o contorno)
    feet = (alpha > 200) & (luminance(arr) < DARK_LUM) & (saturation < FEET_SAT)
    mine = [feet & (owner == i) for i in range(1, len(bodies) + 1)]
    baseline = int(np.median([np.nonzero(m.any(axis=1))[0].max() for m in mine]))
    back_feet = [np.nonzero(m[baseline - FEET_BAND:baseline + 4].any(axis=0))[0].min() for m in mine]

    last_x0, last_x1 = bodies[-1]
    last_top = np.nonzero(dark[:, last_x0:last_x1].any(axis=1))[0].min()
    scale = (ref["feet"] - ref["top"]) / (baseline - last_top)

    # posição de cada frame em coordenadas do frame padrão do jogo (0,0 = canto do frame normal)
    pixels = np.array(img)
    placed = []
    for i, foot in enumerate(back_feet, start=1):
        mine = (owner == i) & (alpha > 10)
        ys, xs = np.nonzero(mine)
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        piece = pixels[y0:y1, x0:x1].copy()
        piece[..., 3] = np.where(mine[y0:y1, x0:x1], piece[..., 3], 0)
        w, h = max(1, round((x1 - x0) * scale)), max(1, round((y1 - y0) * scale))
        crop = Image.fromarray(piece, "RGBA").resize((w, h), Image.LANCZOS)
        x = ref["back"] + (x0 - foot) * scale
        y = ref["feet"] + (y0 - baseline) * scale
        placed.append((crop, x, y))

    left = int(np.floor(min(x for _, x, _ in placed))) - 2
    top = int(np.floor(min(y for _, _, y in placed))) - 2
    right = int(np.ceil(max(x + c.width for c, x, _ in placed))) + 2
    bottom = int(np.ceil(max(y + c.height for c, _, y in placed))) + 2
    width, height = right - left, bottom - top

    sheet = Image.new("RGBA", (width * len(placed), height), (0, 0, 0, 0))
    for i, (crop, x, y) in enumerate(placed):
        sheet.alpha_composite(crop, (i * width + round(x - left), round(y - top)))
    sheet.save(out_path)

    # ponto de impacto aproximado: pixels mais claros na parte de baixo do frame do meio
    mid = len(bodies) // 2
    region = slice(baseline - 160, baseline + 10)
    bright = (owner[region] == mid + 1) & (alpha[region] > 200) & (luminance(arr)[region] > 235)
    by, bx = np.nonzero(bright)
    impact = None
    if len(bx):
        impact = (round(ref["back"] + (bx.mean() - back_feet[mid]) * scale),
                  round(ref["feet"] + (by.mean() - 160) * scale))
    return {"rect": (left, top, width, height), "steps": len(placed), "scale": scale, "impact": impact}


def build_fx(raw_path, out_path, scale):
    img = Image.open(raw_path).convert("RGBA")
    alpha = np.array(img)[..., 3]
    frames = split_frames(alpha)
    boxes = []
    for x0, x1 in frames:
        ys, xs = np.nonzero(alpha[:, x0:x1] > 10)
        boxes.append((x0 + xs.min(), x0 + xs.max() + 1, ys.max() + 1))
    y_top = min(np.nonzero((alpha[:, x0:x1] > 10).any(axis=1))[0].min() for x0, x1 in frames)
    y_bottom = max(b for _, _, b in boxes)
    ground = int(np.median([b for _, _, b in boxes]))

    width = max(round((x1 - x0) * scale) for x0, x1, _ in boxes) + 2
    height = round((y_bottom - y_top) * scale) + 2
    sheet = Image.new("RGBA", (width * len(boxes), height), (0, 0, 0, 0))
    for i, (x0, x1, _) in enumerate(boxes):
        crop = img.crop((x0, y_top, x1, y_bottom))
        crop = crop.resize((max(1, round((x1 - x0) * scale)), height - 2), Image.LANCZOS)
        sheet.alpha_composite(crop, (i * width, 0))
    sheet.save(out_path)
    return {"size": (width, height), "steps": len(boxes), "ground": round((ground - y_top) * scale)}


def main():
    char_id = sys.argv[1] if len(sys.argv) > 1 else "igor"
    char = CHARACTERS_BY_ID[char_id]
    sprites = os.path.join(ROOT, "assets", "images", "Sprites")
    raw = os.path.join(sprites, "raw")

    info = build_character(char, os.path.join(raw, f"{char_id}_super_raw.png"),
                           os.path.join(sprites, f"{char_id}_super.png"))
    print(f"{char_id}_super.png  ->  rect={info['rect']}  steps={info['steps']}  "
          f"escala={info['scale']:.3f}  impacto~{info['impact']}")

    fx_raw = os.path.join(raw, f"{char_id}_super_fx_raw.png")
    if os.path.exists(fx_raw):
        fx = build_fx(fx_raw, os.path.join(sprites, f"{char_id}_super_fx.png"), info["scale"] * FX_SCALE_REL)
        print(f"{char_id}_super_fx.png  ->  size={fx['size']}  steps={fx['steps']}  chão={fx['ground']}")


if __name__ == "__main__":
    main()
