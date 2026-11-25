"""Monta o SUPER do Luba ("SÓ DEPENDE DE LUBA") a partir das imagens originais (fundo branco).

Uso (dentro da pasta Luta):
    python tools/montar_super_luba.py

Entrada (assets/images/Sprites/raw/):
    luba_super_original.png        -> pai: parado, preparando, empurrando, parado
    luba_tubarao_original.png      -> pai + água: redemoinho, jato, tubarão, tubarão desfazendo, guarda
    luba_super_fx_original.png     -> teletransporte: estrela, explosão, coluna, dissipando, fiapos
    luba_agua_original/frame1..5   -> água: onda baixa, onda alta, tudo água, onda descendo, respingos

Saída (assets/images/Sprites/):
    luba_super.png         -> frames do SUPER (linha 7), todos do mesmo tamanho e com o pé no chão:
                              Luba, pai parado, preparando, empurrando, redemoinho, jato, tubarão,
                              tubarão, guarda, guarda, Luba
    luba_super_fx.png      -> teletransporte (5 frames, centro e chão alinhados)
    luba_tubarao_fx.png    -> água separada do pai: redemoinho, jato, tubarão, tubarão desfazendo
    lubaAgua/frame1..5.png -> água sem o fundo (frame3 é a textura de "tudo água", sem transparência)

No fim imprime os números para colar no "super" do Luba em CHARACTERS (fighter.py).
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from fighter import CHARACTERS_BY_ID  # noqa: E402
from remover_fundo import remove_background  # noqa: E402

SPRITES = os.path.join(ROOT, "assets", "images", "Sprites")
RAW = os.path.join(SPRITES, "raw")

FATHER_HEIGHT = 330        # pai em pé na tela (o Luba tem ~317)
TELEPORT_HEIGHT = 440      # altura da coluna do teletransporte na tela
WATER_WIDTH = 1100         # água um pouco mais larga que a tela (1000) para balançar de lado
WATER_DEPTH = 640          # textura de "tudo água": cobre a tela (600) com folga
WATER_FADE = 90            # a onda some aos poucos embaixo (o jogo põe a textura por baixo)
# pulso do pai em cada frame com água (x na imagem original): à direita dele, só pele e roupa
# escura são do pai; o resto (água, espuma) vai para o efeito
WRIST_X = (206, 540, 860, 1136)
SKIN = 12                  # pele: vermelho passa do azul por pelo menos isso
DARK_LUM = 95              # paletó, calça, sapato...
DARK_BLUE = 40             # ... pouco azulados (o azul-escuro do tubarão passa disso)
FX_BOTTOM = 400            # a água das mãos não desce até aqui (abaixo é a perna do pai)
FAINT = 110                # pedaço de efeito que não passa disso de alfa é resto do contorno do pai
FX_FADE = 45               # o tubarão desfazendo foi cortado no pulso: a ponta de trás some aos poucos
BAND = 3                   # borda suave (px) que acompanha o corpo recortado
WATER_SOLID = 45           # água: pixel que se afasta do branco mais que isso é água "cheia"


def luminance(rgb):
    return rgb[..., 0] * 0.3 + rgb[..., 1] * 0.59 + rgb[..., 2] * 0.11


def load_rgb(path):
    return np.array(Image.open(path).convert("RGB")).astype(float)


def without_background(rgb):
    """RGBA sem o fundo branco. Área branca fechada pelo corpo que não é branco puro (crachá)
    volta a ser opaca: o remover_fundo tira o branco grande fechado, que quase sempre é o vão
    entre o braço e o corpo."""
    out, _ = remove_background(rgb)
    solid = out[..., 3] > 128
    holes = ndimage.binary_fill_holes(solid) & ~solid
    labels, count = ndimage.label(holes)
    for idx, box in enumerate(ndimage.find_objects(labels), start=1):
        region = labels[box] == idx
        pure_white = (rgb[box][region].min(axis=1) >= 250).mean()
        if pure_white < 0.5:
            out[box][region, :3] = rgb[box][region]
            out[box][region, 3] = 255
    return out


def bodies(alpha):
    """Corpos opacos (um por frame), da esquerda para a direita: lista de máscaras."""
    labels, count = ndimage.label(alpha >= 250, structure=np.ones((3, 3)))
    sizes = ndimage.sum(np.ones_like(alpha), labels, index=np.arange(1, count + 1))
    big = [i + 1 for i in range(count) if sizes[i] >= 0.2 * sizes.max()]
    boxes = ndimage.find_objects(labels)
    big.sort(key=lambda i: boxes[i - 1][1].start)
    return [labels == i for i in big]


def with_band(core, alpha, keep=None):
    """O corpo e a borda suave dele (pixels semitransparentes encostados)."""
    band = ndimage.binary_dilation(core, iterations=BAND) & (alpha > 0) & (alpha < 250)
    if keep is not None:
        band &= keep
    return core | band


def feet(mask):
    """(chão, calcanhar de trás): linha mais baixa do corpo e o x mais à esquerda perto dela."""
    ys, xs = np.nonzero(mask)
    ground = ys.max()
    return ground, xs[ys >= ground - 25].min()


def crop(rgba, mask):
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    piece = rgba[y0:y1, x0:x1].copy()
    piece[..., 3] = np.where(mask[y0:y1, x0:x1], piece[..., 3], 0)
    return Image.fromarray(piece, "RGBA"), x0, y0


def head_width(mask):
    """Largura da cabeça (careca, de lado): a linha mais larga logo abaixo do topo
    (faixa proporcional à altura do corpo, para não pegar o ombro)."""
    ys, _ = np.nonzero(mask)
    top, height = ys.min(), ys.max() - ys.min()
    return max(mask[y].sum() for y in range(top + int(0.03 * height), top + int(0.09 * height)))


def unmultiply_white(rgb, floor=0.04):
    """Efeito desenhado sobre o branco -> cor e transparência (fumaça fica translúcida)."""
    alpha = (255 - rgb.min(axis=2)) / 255
    color = (rgb - (1 - alpha[..., None]) * 255) / np.maximum(alpha, 1e-6)[..., None]
    alpha = np.clip((alpha - floor) / (1 - floor), 0, 1)
    out = np.zeros(rgb.shape[:2] + (4,), dtype=np.uint8)
    out[..., :3] = np.clip(color, 0, 255)
    out[..., 3] = np.round(alpha * 255)
    return out


def water_rgba(rgb):
    """Água sobre fundo branco: o corpo d'água (e a espuma dentro dele) fica opaco; respingo e
    borda ficam semitransparentes; o branco puro ligado à borda de cima/lados é fundo."""
    distance = 255 - rgb.min(axis=2)
    solid = ndimage.binary_closing(distance > WATER_SOLID, structure=np.ones((3, 3)), iterations=3)
    solid = ndimage.binary_fill_holes(solid)
    white = rgb.min(axis=2) >= 246
    labels, _ = ndimage.label(white)
    edges = np.concatenate([labels[0], labels[:, 0], labels[:, -1]])
    background = np.isin(labels, np.unique(edges[edges > 0]))
    alpha = np.where(solid, 1.0, np.clip(distance / WATER_SOLID, 0, 1))
    alpha[background & ~solid] = 0
    color = (rgb - (1 - alpha[..., None]) * 255) / np.maximum(alpha, 1e-6)[..., None]
    color = np.where(solid[..., None], rgb, color)
    out = np.zeros(rgb.shape[:2] + (4,), dtype=np.uint8)
    out[..., :3] = np.clip(color, 0, 255)
    out[..., 3] = np.round(alpha * 255)
    return out


def split_columns(alpha, min_gap=10, min_width=40):
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


def resize(img, scale):
    return img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)


# ---------------- PAI ----------------
def father_poses():
    """Poses do pai (luba_super) e do pai com a água (luba_tubarao, com a água separada), sem fundo.
    Retorna (poses, poses com água, efeitos, escala do luba_super, escala do luba_tubarao).
    Cada pose: (imagem, x0, y0, chão, calcanhar); cada efeito: (imagem, x0, y0) na imagem original."""
    rgb = load_rgb(os.path.join(RAW, "luba_super_original.png"))
    rgba = without_background(rgb)
    alpha = rgba[..., 3]
    poses, heads = [], []
    cores = bodies(alpha)
    for core in cores:
        mask = with_band(core, alpha)
        poses.append((*crop(rgba, mask), *feet(core)))
        heads.append(head_width(core))
    stand_height = poses[0][3] - np.nonzero(cores[0])[0].min()
    super_scale = FATHER_HEIGHT / stand_height

    rgb_t = load_rgb(os.path.join(RAW, "luba_tubarao_original.png"))
    rgba_t = without_background(rgb_t)
    alpha_t = rgba_t[..., 3]
    lum = luminance(rgb_t)
    skin = (rgb_t[..., 0] - rgb_t[..., 2] >= SKIN) & (rgb_t[..., 0] >= rgb_t[..., 1])
    fatherly = skin | ((lum < DARK_LUM) & (rgb_t[..., 2] - rgb_t[..., 0] < DARK_BLUE))
    water_colored = ~fatherly
    xs = np.arange(rgb_t.shape[1])[None, :]

    cores = bodies(alpha_t)
    fathers = []
    for i, core in enumerate(cores):
        if i < len(WRIST_X):  # à frente do pulso, o que não é pele nem roupa escura é água
            core = core & ~((xs > WRIST_X[i]) & water_colored)
            # pedaços soltos que sobraram da água (espuma clara) não são do pai
            labels, count = ndimage.label(core, structure=np.ones((3, 3)))
            sizes = ndimage.sum(core, labels, index=np.arange(1, count + 1))
            keep = [j + 1 for j in range(count) if sizes[j] >= 0.6 * sizes.max()
                    or (sizes[j] >= 30 and skin[labels == j + 1].mean() > 0.5)]
            core = np.isin(labels, keep)
        fathers.append(core)
    father_any = np.zeros_like(alpha_t, dtype=bool)
    masks = []
    for i, core in enumerate(fathers):
        # a borda suave é do pai, menos à frente do pulso (lá só a pele: o resto é água)
        keep = fatherly | (xs <= WRIST_X[i]) if i < len(WRIST_X) else None
        mask = with_band(core, alpha_t, keep=keep)
        masks.append(mask)
        father_any |= mask

    # efeitos: o que sobrou, cada pedaço no frame do pai à esquerda dele (a guarda não tem água).
    # Pedaço sem cor de água (beirada da calça que o remover_fundo achou fina demais) volta ao pai.
    fx_all = (alpha_t > 0) & ~father_any
    lefts = [np.nonzero(m.any(axis=0))[0].min() for m in masks]
    labels, count = ndimage.label(fx_all, structure=np.ones((3, 3)))
    owner = np.zeros(count + 1, dtype=int)
    index = np.arange(1, count + 1)
    strongest = ndimage.maximum(alpha_t, labels, index=index)
    watery = (ndimage.sum(alpha_t * water_colored, labels, index=index)
              / np.maximum(ndimage.sum(alpha_t, labels, index=index), 1))
    for idx, box in enumerate(ndimage.find_objects(labels), start=1):
        region = labels[box] == idx
        left = box[1].start
        frame = max(i for i, x in enumerate(lefts) if x <= left) if left >= lefts[0] else 0
        if strongest[idx - 1] < FAINT or watery[idx - 1] < 0.4:
            fx_all[box] &= ~region
            if strongest[idx - 1] >= FAINT:
                masks[frame][box] |= region
            continue
        owner[idx] = min(frame, len(WRIST_X) - 1)
    owners = owner[labels]
    # restos fracos do contorno do pai bem atrás do pulso não são água
    wrist = np.array(WRIST_X)[owners]
    fx_all &= ~(xs < wrist - 30)
    # perto do pulso, pixel com cor de roupa/pele grudado na água por pixels quase invisíveis
    # (beirada da calça) também é do pai
    sat = rgb_t.max(axis=2) - rgb_t.min(axis=2)
    grey = (sat < 25) & (lum < 170)   # sombra da calça (a água é azul ou espuma bem clara)
    ys = np.arange(rgb_t.shape[0])[:, None]
    stray = fx_all & (((fatherly | grey) & (alpha_t > 40) & (xs < wrist + 15)) | (ys > FX_BOTTOM))
    for i in range(len(WRIST_X)):
        masks[i] |= stray & (owners == i)
    fx_all &= ~stray
    effects = []
    for i in range(len(WRIST_X)):
        effects.append(crop(rgba_t, fx_all & (owners == i)))
    img, x0, y0 = effects[-1]
    arr = np.array(img)
    arr[..., 3] = (arr[..., 3] * np.clip(np.arange(arr.shape[1]) / FX_FADE, 0, 1)[None, :]).astype(np.uint8)
    effects[-1] = (Image.fromarray(arr, "RGBA"), x0, y0)

    tub_poses = []
    tub_heads = []
    for core, mask in zip(fathers, masks):
        tub_poses.append((*crop(rgba_t, mask), *feet(core)))
        tub_heads.append(head_width(core))
    # mesma pessoa nas duas imagens: a cabeça (careca, de lado) mede igual na tela
    clean = [h for i, h in enumerate(tub_heads) if i in (2, 4)]  # sem água encostando na cabeça
    tub_scale = super_scale * np.median(heads) / np.median(clean)
    return poses, tub_poses, effects, super_scale, tub_scale


def main():
    char = CHARACTERS_BY_ID["luba"]
    size, luba_scale, _ = char["data"]
    frame = int(size * luba_scale)
    sheet = Image.open(os.path.join(ROOT, char["sheet_path"])).convert("RGBA")
    luba_idle = sheet.crop((0, 0, size, size)).resize((frame, frame), Image.LANCZOS)
    idle_alpha = np.array(luba_idle)[..., 3]
    ys, xs = np.nonzero(idle_alpha > 200)
    ground = ys.max()                    # pé do Luba no frame normal
    center = (xs.min() + xs.max()) / 2   # meio do corpo do Luba

    poses, tub_poses, effects, s_super, s_tub = father_poses()
    stand_img, sx0, _, _, stand_heel = poses[0]
    stand_center = sx0 + stand_img.width / 2
    heel_x = center - (stand_center - stand_heel) * s_super   # o pai aparece no lugar do Luba

    def place(pose, scale):
        img, x0, y0, floor, heel = pose
        return resize(img, scale), heel_x + (x0 - heel) * scale, ground + (y0 - floor) * scale

    placed = [(luba_idle, 0, 0)]
    placed += [place(p, s_super) for p in poses[:3]]
    tub_placed = [place(p, s_tub) for p in tub_poses]
    placed += [tub_placed[i] for i in (0, 1, 2, 2, 4, 4)]
    placed.append((luba_idle, 0, 0))

    # efeitos da água no mesmo sistema de coordenadas (canto do frame normal)
    fx_placed = []
    for i, (img, x0, y0) in enumerate(effects):
        _, _, _, floor, heel = tub_poses[i]
        fx_placed.append((resize(img, s_tub), heel_x + (x0 - heel) * s_tub, ground + (y0 - floor) * s_tub))

    left = int(np.floor(min(x for _, x, _ in placed))) - 2
    top = int(np.floor(min(y for _, _, y in placed))) - 2
    right = int(np.ceil(max(x + img.width for img, x, _ in placed))) + 2
    bottom = int(np.ceil(max(y + img.height for img, _, y in placed))) + 2
    width, height = right - left, bottom - top
    strip = Image.new("RGBA", (width * len(placed), height), (0, 0, 0, 0))
    for i, (img, x, y) in enumerate(placed):
        strip.alpha_composite(img, (i * width + round(x - left), round(y - top)))
    strip.save(os.path.join(SPRITES, "luba_super.png"))
    # sombra: meio entre os pés de cada frame (a parte de baixo do corpo)
    shadows = []
    for i in range(len(placed)):
        a = np.array(strip.crop((i * width, 0, (i + 1) * width, height)))[..., 3]
        ys_, xs_ = np.nonzero(a > 200)
        low = xs_[ys_ >= ys_.max() - 0.15 * (ys_.max() - ys_.min())]
        shadows.append(round((low.min() + low.max()) / 2))
    print(f"luba_super.png -> rect=({left}, {top}, {width}, {height})  frames={len(placed)}  "
          f"escala pai={s_super:.3f} / {s_tub:.3f}  sombra={tuple(shadows)}")

    # efeitos da água: uma linha de frames do mesmo tamanho; cada um com a posição no frame do SUPER
    fx_w = max(img.width for img, _, _ in fx_placed) + 2
    fx_h = max(img.height for img, _, _ in fx_placed) + 2
    fx_sheet = Image.new("RGBA", (fx_w * len(fx_placed), fx_h), (0, 0, 0, 0))
    spots = []
    for i, (img, x, y) in enumerate(fx_placed):
        fx_sheet.alpha_composite(img, (i * fx_w + 1, 1))
        spots.append((round(x - left) - 1, round(y - top) - 1))
    fx_sheet.save(os.path.join(SPRITES, "luba_tubarao_fx.png"))
    # miolo do redemoinho (onde ele gira): centro dos pixels mais claros do frame 0
    vortex = np.array(fx_placed[0][0]).astype(float)
    bright = (vortex[..., 3] > 200) & (luminance(vortex[..., :3]) > 225)
    by, bx = np.nonzero(bright)
    core = (round(bx.mean()) + 1, round(by.mean()) + 1) if len(bx) else (fx_w // 2, fx_h // 2)
    print(f"luba_tubarao_fx.png -> size=({fx_w}, {fx_h})  spots={spots}  miolo do redemoinho={core}")

    # teletransporte: efeito sobre o branco (fumaça translúcida), frames alinhados pelo meio e pelo chão
    rgb_fx = load_rgb(os.path.join(RAW, "luba_super_fx_original.png"))
    fx_rgba = unmultiply_white(rgb_fx)
    runs = split_columns(fx_rgba[..., 3])
    alpha_fx = fx_rgba[..., 3]
    tallest = max(np.ptp(np.nonzero((alpha_fx[:, x0:x1] > 60).any(axis=1))[0]) for x0, x1 in runs)
    t_scale = TELEPORT_HEIGHT / tallest
    rows = np.nonzero((alpha_fx > 20).any(axis=1))[0]
    y0, y1 = rows.min(), rows.max() + 1
    t_w = round(max(x1 - x0 for x0, x1 in runs) * t_scale) + 2
    t_h = round((y1 - y0) * t_scale) + 2
    t_sheet = Image.new("RGBA", (t_w * len(runs), t_h), (0, 0, 0, 0))
    for i, (x0, x1) in enumerate(runs):
        piece = resize(Image.fromarray(fx_rgba[y0:y1, x0:x1], "RGBA"), t_scale)
        t_sheet.alpha_composite(piece, (i * t_w + (t_w - piece.width) // 2, 1))
    t_sheet.save(os.path.join(SPRITES, "luba_super_fx.png"))
    # chão do teletransporte: a linha mais clara na metade de baixo da coluna (frame do meio)
    mid_x0, mid_x1 = runs[len(runs) // 2]
    bright = (luminance(rgb_fx[:, mid_x0:mid_x1]) > 200) & (alpha_fx[:, mid_x0:mid_x1] > 60)
    counts = bright.sum(axis=1)
    counts[: (y0 + y1) // 2] = 0
    floor_row = int(np.argmax(counts))
    print(f"luba_super_fx.png -> size=({t_w}, {t_h})  frames={len(runs)}  escala={t_scale:.3f}  "
          f"meio do Luba no frame do SUPER=({round(center - left)}, {round(ground - top)})  "
          f"base da coluna~{round((floor_row - y0) * t_scale)}")

    # água: onda sem o fundo (embaixo some aos poucos: o jogo completa com a textura)
    agua_out = os.path.join(SPRITES, "lubaAgua")
    for n in (1, 2, 4, 5):
        rgb_w = load_rgb(os.path.join(RAW, "luba_agua_original", f"frame{n}.png"))
        img = resize(Image.fromarray(water_rgba(rgb_w), "RGBA"), WATER_WIDTH / rgb_w.shape[1])
        arr = np.array(img)
        ramp = np.clip((img.height - 1 - np.arange(img.height)) / WATER_FADE, 0, 1)
        arr[..., 3] = (arr[..., 3] * ramp[:, None]).astype(np.uint8)
        a = arr[..., 3]
        surface = int(np.median([np.argmax(a[:, x] > 230) for x in range(0, a.shape[1], 8)]))
        solid = next((y for y in range(a.shape[0]) if (a[y] >= 250).mean() >= 0.98), None)
        Image.fromarray(arr, "RGBA").save(os.path.join(agua_out, f"frame{n}.png"))
        print(f"lubaAgua/frame{n}.png -> {img.size}  superfície~{surface}  opaca a partir de {solid}")
    texture = Image.open(os.path.join(RAW, "luba_agua_original", "frame3.png")).convert("RGB")
    scale = max(WATER_WIDTH / texture.width, WATER_DEPTH / texture.height)
    texture = resize(texture, scale)
    x0 = (texture.width - WATER_WIDTH) // 2
    texture.crop((x0, 0, x0 + WATER_WIDTH, WATER_DEPTH)).save(os.path.join(agua_out, "frame3.png"))
    print(f"lubaAgua/frame3.png -> ({WATER_WIDTH}, {WATER_DEPTH})  textura")


if __name__ == "__main__":
    main()
