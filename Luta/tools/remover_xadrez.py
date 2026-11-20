"""Tira o fundo xadrez "falso" (desenhado na imagem) de um sprite gerado sem transparência de verdade.

Uso (dentro da pasta Luta):
    python tools/remover_xadrez.py entrada.jpg saida.png

Como funciona:
- personagem: tudo que está dentro dos contornos escuros vira opaco, com a cor original;
- aura/brilho: vira semitransparente ("cor para alfa" contra o branco do xadrez), então o
  brilho aparece por cima de qualquer cenário;
- o xadrez some (dentro de buracos do contorno ele é reconhecido pela textura quadriculada).

O ideal continua sendo gerar já com fundo transparente de verdade (PNG); use isto quando não der.
"""
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

OUTLINE_LUM = 110      # contornos/roupa escura: abaixo disso conta como "personagem"
AURA_BLUE = 40         # azul acima do vermelho/verde por mais que isso = aura (troque se a aura for de outra cor)
CHECKER_SAT = 22       # o xadrez é cinza (quase sem saturação)
CHECKER_LUM = 200      # ... e claro
CHECKER_STD = 4.5      # ... e quadriculado (varia bastante numa janela pequena)
HOLE_CHECKER = 0.5     # buraco do contorno com mais que isso de xadrez é fundo (não personagem)
HOLE_BLUE = 0.5        # buraco com mais que isso de azul da aura...
HOLE_BLUE_SIZE = 150   # ... e maior que isso (px) é aura, não reflexo na roupa
AURA_BLUR = 7          # média da aura (apaga o quadriculado por baixo do brilho)
ALPHA_FLOOR = 0.10     # alfa abaixo disso vira 0 (o xadrez, já borrado, dá ~0.07)


def box_mean(arr, size):
    return ndimage.uniform_filter(arr, size=size, mode="nearest")


def remove_checker(rgb):
    lum = rgb[..., 0] * 0.3 + rgb[..., 1] * 0.59 + rgb[..., 2] * 0.11
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    std = np.sqrt(np.maximum(0, box_mean(lum ** 2, 9) - box_mean(lum, 9) ** 2))
    checker = (sat < CHECKER_SAT) & (lum > CHECKER_LUM) & (std > CHECKER_STD)

    # personagem: contornos escuros fechados + os buracos que eles cercam. Buraco que é quase
    # todo xadrez (ex.: vão entre o braço e o corpo) é fundo; reflexo no rosto continua personagem.
    # Buraco grande e quase todo azul é o miolo de um "fantasma" da aura: fica translúcido.
    outline = ndimage.binary_closing(lum < OUTLINE_LUM, structure=np.ones((3, 3)), iterations=2)
    holes = ndimage.binary_fill_holes(outline) & ~outline
    aura_blue = rgb[..., 2] - np.maximum(rgb[..., 0], rgb[..., 1]) > AURA_BLUE
    labels, count = ndimage.label(holes)
    if count:
        index = np.arange(1, count + 1)
        checker_frac = ndimage.mean(checker, labels, index=index)
        blue_frac = ndimage.mean(aura_blue, labels, index=index)
        size = ndimage.sum(holes, labels, index=index)
        drop = (checker_frac > HOLE_CHECKER) | ((blue_frac > HOLE_BLUE) & (size > HOLE_BLUE_SIZE))
        holes &= ~np.isin(labels, index[drop])
    solid = ndimage.binary_opening(outline | holes, structure=np.ones((2, 2)))

    # aura: média local sem o personagem (apaga o quadriculado) e "cor para alfa" contra o branco
    free = (~solid).astype(float)
    weight = box_mean(free, AURA_BLUR)
    smooth = (np.stack([box_mean(rgb[..., c] * free, AURA_BLUR) for c in range(3)], axis=2)
              / np.maximum(weight, 1e-6)[..., None])
    alpha = (255 - smooth.min(axis=2)) / 255
    color = (smooth - (1 - alpha[..., None]) * 255) / np.maximum(alpha, 1e-6)[..., None]
    alpha = np.clip((alpha - ALPHA_FLOOR) / (1 - ALPHA_FLOOR), 0, 1)

    out = np.zeros(rgb.shape[:2] + (4,), dtype=np.uint8)
    out[..., :3] = np.where(solid[..., None], rgb, np.clip(color, 0, 255))
    out[..., 3] = np.where(solid, 255, np.round(alpha * 255))
    return out


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    rgb = np.array(Image.open(sys.argv[1]).convert("RGB")).astype(float)
    Image.fromarray(remove_checker(rgb), "RGBA").save(sys.argv[2])
    print("salvo:", sys.argv[2])


if __name__ == "__main__":
    main()
