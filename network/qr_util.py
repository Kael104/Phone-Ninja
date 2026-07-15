"""QR code rendering helpers for the connection screen."""

from __future__ import annotations

import io

import pygame
import qrcode


def make_qr_surface(url: str, box_size: int = 6, border: int = 2) -> pygame.Surface:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return pygame.image.load(buf, "qr.png").convert()
