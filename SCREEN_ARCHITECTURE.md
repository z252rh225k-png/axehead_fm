# More Powerful Screen Architecture Suggestions

Your screens are now modular and organized! Here are several approaches to make them even more powerful:

## 1. **Theme/Style System** (Recommended - Easy to implement)

Create a `theme.py` file that centralizes all styling:

```python
# src/music_player/ui/theme.py
class Theme:
    # Colors
    FOREGROUND = "white"
    BACKGROUND = "black"
    
    # Fonts & Typography
    TITLE_X = 34
    TITLE_Y = 4
    CONTENT_X = 30
    CONTENT_Y = 16
    
    # Layout Constants
    SCREEN_WIDTH = 128
    SCREEN_HEIGHT = 64
    HEADER_HEIGHT = 14
    FOOTER_HEIGHT = 10
    
    # Spacing
    PADDING = 4
    MARGIN = 2

# Then use in screens:
class MusicScreen(BaseScreen):
    def draw(self, draw, state, bt_manager):
        from music_player.ui.theme import Theme
        draw.text((Theme.TITLE_X, Theme.TITLE_Y), "NOW PLAYING", fill=Theme.FOREGROUND)
```

**Benefits:**
- Single place to change all colors/spacing
- Supports light/dark mode easily
- Easy to create new themes

## 2. **Component-Based UI** (More powerful)

Create reusable UI components:

```python
# src/music_player/ui/components.py
class UIComponent:
    def draw(self, draw, x, y):
        pass

class TextLabel(UIComponent):
    def __init__(self, text, x, y, fill="white"):
        self.text = text
        self.x = x
        self.y = y
        self.fill = fill
    
    def draw(self, draw):
        draw.text((self.x, self.y), self.text, fill=self.fill)

class VUMeter(UIComponent):
    def __init__(self, x, y, bars=10, height=24):
        self.x = x
        self.y = y
        self.bars = bars
        self.height = height
    
    def draw(self, draw, state):
        for i in range(self.bars):
            bar_h = random.randint(2, self.height)
            draw.rectangle((
                self.x + i*10,
                self.y - bar_h,
                self.x + i*10 + 7,
                self.y
            ), fill="white")

class ProgressBar(UIComponent):
    def __init__(self, x, y, width, height, value=0.5):
        self.x, self.y = x, y
        self.width, self.height = width, height
        self.value = value
    
    def draw(self, draw):
        # Draw background
        draw.rectangle((self.x, self.y, self.x+self.width, self.y+self.height), outline="white")
        # Draw fill
        fill_width = int(self.width * self.value)
        draw.rectangle((self.x, self.y, self.x+fill_width, self.y+self.height), fill="white")

# Use in screens:
class MusicScreen(BaseScreen):
    def __init__(self):
        self.title = TextLabel("NOW PLAYING", 34, 4)
        self.vu_meter = VUMeter(14, 58, bars=10)
    
    def draw(self, draw, state, bt_manager):
        self.title.draw(draw)
        if should_show_vu_meter(state):
            self.vu_meter.draw(draw, state)
```

**Benefits:**
- Reusable across multiple screens
- Easy to position/layout elements
- Cleaner code
- Testable components

## 3. **Layout Manager** (For complex UIs)

```python
# src/music_player/ui/layout.py
class Layout:
    def __init__(self, width=128, height=64):
        self.width = width
        self.height = height
        self.components = []
    
    def add(self, component, x, y):
        self.components.append((component, x, y))
        return self
    
    def grid(self, rows, cols, start_x=0, start_y=0, width=None, height=None):
        """Add components in a grid layout"""
        pass
    
    def draw(self, draw, state):
        for component, x, y in self.components:
            component.draw(draw, x, y, state)

# Usage:
class MenuScreen(BaseScreen):
    def __init__(self):
        self.layout = Layout()
        self.layout.add(TextLabel("MENU"), 40, 2)
        self.layout.add(Divider(horizontal=True), 0, 14)
        # Add menu items in a list...
    
    def draw(self, draw, state, bt_manager):
        self.layout.draw(draw, state)
```

## 4. **Data-Driven Screens** (Most declarative)

Define screens via configuration:

```python
# src/music_player/ui/screen_config.py
MUSIC_SCREEN_CONFIG = {
    "name": "music",
    "components": [
        {"type": "text", "text": "NOW PLAYING", "x": 34, "y": 4},
        {"type": "text", "ref": "title", "x": 30, "y": 16},
        {"type": "vu_meter", "x": 14, "y": 58, "bars": 10},
        {"type": "cassette", "x": 36, "y": 32},
    ]
}

class DynamicScreen(BaseScreen):
    def __init__(self, config):
        self.config = config
        self.components = self._build_components(config)
    
    def _build_components(self, config):
        components = []
        for comp_config in config["components"]:
            comp_type = comp_config.pop("type")
            components.append(COMPONENT_REGISTRY[comp_type](**comp_config))
        return components
    
    def draw(self, draw, state, bt_manager):
        for component in self.components:
            component.draw(draw, state)
```

## 5. **Recommended Path Forward**

Start with **#1 (Theme System)** - it requires minimal refactoring but gives big benefits.

Then move to **#2 (Components)** - extract common patterns like meters, labels, borders, etc.

Example quick win - create `UIComponents`:

```python
# src/music_player/ui/components.py
class Header(UIComponent):
    """Reusable header with title and divider"""
    def draw(self, draw, title):
        draw.text((40, 2), title, fill="white")
        draw.line((0, 13, 128, 13), fill="white")

class Bluetooth Indicator(UIComponent):
    """Shows BT icon in corner"""
    def draw(self, draw, is_connected):
        if is_connected:
            draw_bluetooth_icon(draw, 115, 4)
```

Then simplify all screens:

```python
class MusicScreen(BaseScreen):
    def __init__(self):
        self.header = Header()
        self.bt_icon = BluetoothIndicator()
    
    def draw(self, draw, state, bt_manager):
        self.header.draw(draw, "NOW PLAYING")
        self.bt_icon.draw(draw, bt_manager.connected_device is not None)
        # ... rest of screen-specific logic
```

## Quick Refactor: Extract 3 Reusable Components

These would reduce code duplication across screens:

```python
class Header:
    def draw(self, draw, title, show_bt=False):
        draw.text((40, 2), title, fill="white")
        draw.line((0, 13, 128, 13), fill="white")
        if show_bt:
            draw_bluetooth_icon(draw, 115, 2)

class VerticalBars:
    """Generic bar chart/meter"""
    def __init__(self, x, y, bar_count, bar_width, spacing):
        self.x, self.y = x, y
        self.bar_count = bar_count
        self.bar_width = bar_width
        self.spacing = spacing
    
    def draw(self, draw, values):
        for i, val in enumerate(values):
            h = int(val * 30)
            bx = self.x + (i * self.spacing)
            draw.rectangle((bx, self.y - h, bx + self.bar_width, self.y), fill="white")

class Divider:
    def __init__(self, y=14):
        self.y = y
    
    def draw(self, draw):
        draw.line((0, self.y, 128, self.y), fill="white")
```

This would let you clean up VolumeScreen, MusicScreen, etc. immediately!
