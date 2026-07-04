"""Іконки, намальовані в коді (щоб не тягти бінарні файли).

Символ — білі смужки-еквалайзер на кольоровому колі (синє у спокої, червоне
під час запису). Жирно й контрастно, щоб читалось навіть у 16px трею.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap


def _icon_pixmap(size=256, recording=False):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    # Кольорове коло-фон (синє у спокої, червоне під час запису).
    bg = QColor("#ff3b30") if recording else QColor("#2f8cff")
    p.setPen(Qt.NoPen)
    p.setBrush(bg)
    p.drawEllipse(0, 0, size, size)

    # Білі смужки-еквалайзер (як у оверлеї).
    p.setBrush(QColor("#ffffff"))
    heights = [0.34, 0.54, 0.42]
    bw = size * 0.13
    gap = size * 0.10
    total = len(heights) * bw + (len(heights) - 1) * gap
    x = (size - total) / 2
    for h in heights:
        bh = size * h
        p.drawRoundedRect(QRectF(x, (size - bh) / 2, bw, bh), bw / 2, bw / 2)
        x += bw + gap

    p.end()
    return pm


def tray_icon(recording=False):
    return QIcon(_icon_pixmap(256, recording=recording))


def mic_icon():
    return QIcon(_icon_pixmap(256, recording=False))
