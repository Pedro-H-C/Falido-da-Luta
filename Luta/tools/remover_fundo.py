"""Tira o fundo "falso" de um sprite gerado sem transparência de verdade.

Uso (dentro da pasta Luta):
    python tools/remover_fundo.py entrada.png saida.png

Reconhece sozinho dois tipos de fundo:
- XADREZ desenhado (cinza/branco, claro ou escuro, mesmo irregular): personagem com contorno
  escuro fica opaco; aura/brilho fica semitransparente;
- BRANCO liso (render 3D sem contorno): o corpo (pele, roupa, cabelo) fica opaco com a borda
  recortada suave; linhas de efeito cinza (vibração, ondas) ficam semitransparentes.

O ideal continua sendo gerar já com fundo transparente de verdade (PNG); use isto quando não der.
"""
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

# ---- xadrez ----
OUTLINE_LUM = 110      # contornos/roupa escura: abaixo disso conta como "personagem"
AURA_SAT = 140         # cor muito forte (aura vermelha, azul...) não conta como contorno
OUTLINE_CLOSE = 5      # quanto fechar o contorno para achar o que ele cerca
AURA_BLUE = 40         # azul acima do vermelho/verde por mais que isso = aura azul
GREY_SAT = 12          # o xadrez é cinza (quase sem saturação)
CHECKER_STD = 4.5      # ... e quadriculado (varia bastante numa janela pequena)
CHECKER_NEAR = 40      # ... e perto do cinza médio do xadrez
HOLE_CHECKER = 0.5     # buraco do contorno com mais que isso de xadrez é fundo (não personagem)
HOLE_BLUE = 0.5        # buraco com mais que isso de cor de aura...
HOLE_BLUE_SIZE = 150   # ... e maior que isso (px) é aura, não reflexo na roupa
AURA_BLUR = 7          # média da aura (apaga o quadriculado por baixo do brilho)
ALPHA_FLOOR = 0.10     # alfa abaixo disso vira 0 (resto do quadriculado)
TWO_TONES = 15         # tons do fundo mais distantes que isso = xadrez; senão é fundo liso

# ---- branco liso ----
WHITE_MIN = 235        # fundo branco: todos os canais acima disso...
WHITE_SAT = 12         # ... e sem cor
WHITE_HOLE = 400       # área branca fechada maior que isso também é fundo (vão entre braço e corpo)
BODY_THICK = 4         # parte mais fina que ~2x isso (px) é linha de efeito, não corpo
BODY_MIN = 200         # pedaço de corpo menor que isso (px) é sujeira
EDGE = 2               # borda do corpo (px) recortada com transparência suave
FX_FLOOR = 0.06        # linhas de efeito: alfa abaixo disso vira 0


def box_mean(arr, size):
    return ndimage.uniform_filter(arr, size=size, mode="nearest")


def luminance(rgb):
    return rgb[..., 0] * 0.3 + rgb[..., 1] * 0.59 + rgb[..., 2] * 0.11


def color_to_alpha(rgb, background):
    """Menor alfa que explica rgb como uma cor por cima de background, e essa cor."""
    up = np.where(rgb > background, (rgb - background) / np.maximum(255 - background, 1), 0)
    down = np.where(rgb < background, (background - rgb) / np.maximum(background, 1), 0)
    alpha = np.maximum(up, down).max(axis=2)
    color = (rgb - (1 - alpha[..., None]) * background) / np.maximum(alpha, 1e-6)[..., None]
    return alpha, color


def background_tones(rgb):
    """Os dois tons do fundo (escuro, claro), iguais na imagem toda. No fundo liso saem quase iguais.

    Agrupa os pixels cinza claros em dois tons (k-médias). Média local não serve: o cinza de
    muleta, metal e sombra perto do personagem puxaria o tom do fundo.
    """
    lum = rgb.mean(axis=2)
    grey = ((rgb.max(axis=2) - rgb.min(axis=2)) < GREY_SAT) & (lum > 140)
    values = lum[grey]
    if values.size < 100:
        return np.array([255.0] * 3), np.array([255.0] * 3)
    low, high = np.percentile(values, 25), np.percentile(values, 75)
    for _ in range(15):
        middle = (low + high) / 2
        lower, upper = values[values < middle], values[values >= middle]
        if not lower.size or not upper.size:
            break
        low, high = lower.mean(), upper.mean()
    dark = np.median(rgb[grey & (np.abs(lum - low) < 10)], axis=0)
    light = np.median(rgb[grey & (np.abs(lum - high) < 10)], axis=0)
    return dark, light


# ---------------- XADREZ ----------------
def checker_patches(rgb, lum, dark, light, inside):
    """Pedaços de xadrez que sobraram dentro do personagem (ex.: vão entre a perna e a muleta).
    Xadrez = região cinza com os DOIS tons; muleta/metal cinza tem um tom só e fica."""
    grey = (rgb.max(axis=2) - rgb.min(axis=2)) < GREY_SAT * 2
    is_dark = grey & (np.abs(lum - dark.mean()) < 12)
    is_light = grey & (np.abs(lum - light.mean()) < 12)
    candidate = ndimage.binary_dilation(is_dark | is_light) & inside
    labels, count = ndimage.label(candidate)
    if not count:
        return np.zeros_like(inside)
    index = np.arange(1, count + 1)
    dark_frac = ndimage.mean(is_dark, labels, index=index)
    light_frac = ndimage.mean(is_light, labels, index=index)
    size = ndimage.sum(candidate, labels, index=index)
    keep = (dark_frac > 0.15) & (light_frac > 0.15) & (size > 60)
    return np.isin(labels, index[keep])


def remove_checker(rgb, dark, light):
    lum = luminance(rgb)
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    ref_lum = (dark.mean() + light.mean()) / 2
    std = np.sqrt(np.maximum(0, box_mean(lum ** 2, 9) - box_mean(lum, 9) ** 2))
    checker = (sat < GREY_SAT * 2) & (np.abs(lum - ref_lum) < CHECKER_NEAR) & (std > CHECKER_STD)

    # personagem: contornos escuros fechados + os buracos que eles cercam. Buraco que é quase
    # todo xadrez (ex.: vão entre o braço e o corpo) é fundo; reflexo no rosto continua personagem.
    # Buraco grande e quase todo cor de aura é o miolo de um "fantasma" da aura: fica translúcido.
    dark_line = (lum < OUTLINE_LUM) & (sat < AURA_SAT)
    outline = ndimage.binary_closing(dark_line, structure=np.ones((3, 3)), iterations=2)
    # para achar o que o contorno cerca, fecha mais forte (rosto/perna com contorno aberto)
    closed = ndimage.binary_closing(dark_line, structure=np.ones((3, 3)), iterations=OUTLINE_CLOSE)
    holes = ndimage.binary_fill_holes(closed) & ~outline
    aura = (rgb[..., 2] - np.maximum(rgb[..., 0], rgb[..., 1]) > AURA_BLUE) | (sat > AURA_SAT)
    labels, count = ndimage.label(holes)
    if count:
        index = np.arange(1, count + 1)
        checker_frac = ndimage.mean(checker, labels, index=index)
        aura_frac = ndimage.mean(aura, labels, index=index)
        size = ndimage.sum(holes, labels, index=index)
        drop = (checker_frac > HOLE_CHECKER) | ((aura_frac > HOLE_BLUE) & (size > HOLE_BLUE_SIZE))
        holes &= ~np.isin(labels, index[drop])
        holes &= ~checker_patches(rgb, lum, dark, light, holes)
    solid = ndimage.binary_opening(outline | holes, structure=np.ones((2, 2)))

    # aura: "cor para alfa" contra o tom do quadrado de trás. Não se sabe se é o claro ou o
    # escuro, então fica o que exige menos alfa (o próprio fundo dá ~0 nos dois casos).
    alpha_d, color_d = color_to_alpha(rgb, dark)
    alpha_l, color_l = color_to_alpha(rgb, light)
    use_light = alpha_l < alpha_d
    alpha = np.where(use_light, alpha_l, alpha_d)
    color = np.where(use_light[..., None], color_l, color_d)
    # leve média (sem o personagem) para apagar o quadriculado que ainda passa pelo brilho
    free = (~solid).astype(float)
    weight = np.maximum(box_mean(free, AURA_BLUR), 1e-6)
    alpha_s = box_mean(alpha * free, AURA_BLUR) / weight
    color = (np.stack([box_mean(color[..., c] * alpha * free, AURA_BLUR) for c in range(3)], axis=2)
             / np.maximum(alpha_s * weight, 1e-6)[..., None])
    alpha = np.clip((alpha_s - ALPHA_FLOOR) / (1 - ALPHA_FLOOR), 0, 1)

    out = np.zeros(rgb.shape[:2] + (4,), dtype=np.uint8)
    out[..., :3] = np.where(solid[..., None], rgb, np.clip(color, 0, 255))
    out[..., 3] = np.where(solid, 255, np.round(alpha * 255))
    return out


# ---------------- BRANCO LISO ----------------
def remove_white(rgb):
    lum = luminance(rgb)
    sat = rgb.max(axis=2) - rgb.min(axis=2)

    # fundo: o branco ligado à borda da imagem + áreas brancas grandes fechadas pelo corpo
    white = (rgb.min(axis=2) > WHITE_MIN) & (sat < WHITE_SAT)
    labels, count = ndimage.label(white)
    index = np.arange(1, count + 1)
    sizes = ndimage.sum(white, labels, index=index)
    edges = np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])
    keep = np.union1d(np.unique(edges[edges > 0]), index[sizes > WHITE_HOLE])
    background = np.isin(labels, keep)

    # corpo: o que não é branco e forma mancha larga; linhas de efeito são finas e ficam de fora.
    # (cor não serve: o jeans tem partes cinza quase sem cor, iguais às linhas de efeito)
    not_white = ~background & ((rgb.min(axis=2) < WHITE_MIN) | (sat > WHITE_SAT))
    disk = ndimage.generate_binary_structure(2, 1)
    blobs = ndimage.binary_opening(not_white, structure=disk, iterations=BODY_THICK)
    body = ndimage.binary_dilation(blobs, structure=disk, iterations=BODY_THICK + EDGE) & not_white
    solid = ndimage.binary_fill_holes(ndimage.binary_closing(body, structure=np.ones((3, 3)), iterations=2))
    solid &= ~background
    labels, count = ndimage.label(solid)
    if count:
        index = np.arange(1, count + 1)
        sizes = ndimage.sum(solid, labels, index=index)
        solid = np.isin(labels, index[sizes > BODY_MIN])

    # borda do corpo: a cor vem de dentro; o alfa é o quanto o pixel se afastou do branco
    # em direção a essa cor (recorte suave, sem auréola branca)
    inner = ndimage.binary_erosion(solid, iterations=EDGE)
    _, (iy, ix) = ndimage.distance_transform_edt(~inner, return_indices=True)
    inside_color = rgb[iy, ix]
    band = ndimage.binary_dilation(solid, iterations=EDGE) & ~inner & ~background
    to_pixel, to_body = 255 - rgb, 255 - inside_color
    alpha_band = np.clip((to_pixel * to_body).sum(axis=2) / np.maximum((to_body ** 2).sum(axis=2), 1), 0, 1)

    # linhas de efeito (vibração, ondas): "cor para alfa" contra o branco
    alpha_fx, color_fx = color_to_alpha(rgb, np.full(3, 255.0))
    alpha_fx = np.clip((alpha_fx - FX_FLOOR) / (1 - FX_FLOOR), 0, 1)

    alpha = np.where(inner, 1.0, np.where(band, alpha_band, np.where(background, 0.0, alpha_fx)))
    color = np.where((inner | band)[..., None], np.where(inner[..., None], rgb, inside_color), color_fx)
    out = np.zeros(rgb.shape[:2] + (4,), dtype=np.uint8)
    out[..., :3] = np.clip(color, 0, 255)
    out[..., 3] = np.round(alpha * 255)
    return out


def is_checker(rgb, dark, light):
    """Xadrez: os dois tons são bem diferentes E cada um cobre uma parte grande do fundo.
    (No fundo liso, o "tom escuro" é só o cinza das linhas de efeito, bem pouco.)"""
    if light.mean() - dark.mean() <= TWO_TONES:
        return False
    lum = rgb.mean(axis=2)
    grey = ((rgb.max(axis=2) - rgb.min(axis=2)) < GREY_SAT) & (lum > 140)
    near_dark = (grey & (np.abs(lum - dark.mean()) < 8)).sum()
    near_light = (grey & (np.abs(lum - light.mean()) < 8)).sum()
    return min(near_dark, near_light) > 0.2 * max(near_dark, near_light)


def remove_background(rgb):
    """Retorna (RGBA, tipo de fundo encontrado)."""
    dark, light = background_tones(rgb)
    if is_checker(rgb, dark, light):
        return remove_checker(rgb, dark, light), "xadrez"
    return remove_white(rgb), "branco liso"


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    rgb = np.array(Image.open(sys.argv[1]).convert("RGB")).astype(float)
    out, kind = remove_background(rgb)
    Image.fromarray(out, "RGBA").save(sys.argv[2])
    print(f"fundo: {kind} | salvo: {sys.argv[2]}")


if __name__ == "__main__":
    main()
