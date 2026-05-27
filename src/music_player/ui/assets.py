def draw_bluetooth_icon(draw, x, y):
    """
    Draws a standard pixel-art Bluetooth logo at position x, y.
    Bounding box is roughly 7x11 pixels.
    """
    draw.line((x + 3, y, x + 3, y + 10), fill="white")
    draw.line((x + 3, y, x + 6, y + 3), fill="white")
    draw.line((x + 6, y + 3, x + 3, y + 5), fill="white")
    draw.line((x + 3, y + 5, x + 6, y + 7), fill="white")
    draw.line((x + 6, y + 7, x + 3, y + 10), fill="white")
    draw.line((x + 3, y + 2, x, y + 5), fill="white")
    draw.line((x, y + 5, x + 3, y + 8), fill="white")
