# User Web Tool - Scaffolding Guide

## Overview
A separate user-facing web interface for Axehead FM, distinct from the admin dashboard. This tool is designed to be clean, minimalist, and user-friendly—inspired by the Teenage Engineering EP sample tool aesthetic.

## Architecture

### Route
- **Endpoint**: `/api/user`
- **Template**: `templates/user.html`
- **Base Template**: `templates/user_base.html`
- **Stylesheet**: `static/css/user.css`

### File Structure
```
src/music_player/
├── web/
│   ├── routes.py          (Added /api/user route)
│   └── templates/
│       ├── base.html      (Admin dashboard base - unchanged)
│       ├── user_base.html (NEW - User tool base template)
│       └── user.html      (NEW - User tool home page)
└── static/
    └── css/
        └── user.css       (NEW - User tool stylesheet)
```

## Adding Features

### 1. Create a New Feature Component

Add a card or section to `user.html`:

```html
<div class="card">
    <div class="card-header">
        <h3 class="card-title">Feature Name</h3>
    </div>
    <div class="card-content">
        <!-- Your feature content -->
    </div>
    <div class="card-footer">
        <button class="btn-primary">Action</button>
    </div>
</div>
```

### 2. Add Backend Route

In `routes.py`, add a new endpoint:

```python
@api_bp.route('/user/feature-name', methods=['GET', 'POST'])
def user_feature():
    """User feature endpoint."""
    if request.method == 'POST':
        data = request.json
        # Process data
        return jsonify({'status': 'success'})
    
    # Return data for GET
    return jsonify({...})
```

### 3. Add JavaScript Handler

In the `user.html` script block:

```javascript
async function handleFeature() {
    try {
        const response = await fetchJSON('/user/feature-name', {
            method: 'POST',
            body: JSON.stringify({ /* data */ })
        });
        showSuccess('Feature completed');
    } catch (error) {
        showError(`Error: ${error.message}`);
    }
}
```

## CSS Classes & Components

### Layout
- `.welcome-card` - Hero section
- `.features-grid` - Responsive grid layout
- `.card` - Content card
- `.container` - Max-width wrapper (1200px)

### Forms
- `.form-group` - Group inputs with labels
- Input types: `text`, `number`, `password`, `email`, `file`, `select`, `textarea`

### Buttons
- `.btn-primary` - Main action button
- `.btn-secondary` - Secondary action
- `.btn-danger` - Destructive action
- `.btn-success` - Positive action
- `.btn-small` - Compact button

### Alerts
- `.alert.alert-info` - Info message
- `.alert.alert-success` - Success message
- `.alert.alert-warning` - Warning message
- `.alert.alert-danger` - Error message

### Utilities
- `.text-center`, `.text-right` - Text alignment
- `.mt-8`, `.mt-16`, `.mt-24` - Margin top
- `.mb-8`, `.mb-16`, `.mb-24` - Margin bottom
- `.gap-8`, `.gap-16` - Gap between flex items

## Helper Functions (Built-in)

All functions are available in the `user_base.html` script block:

```javascript
// Fetch JSON from API
fetchJSON(endpoint, options)

// Show notifications
showNotification(message, type)
showSuccess(message)
showError(message)
```

## Design Philosophy

- **Clean**: Minimal visual complexity, focus on functionality
- **Minimalist**: Plenty of whitespace, clear hierarchy
- **Responsive**: Mobile-first design, works on all screen sizes
- **Accessible**: High contrast, readable fonts, clear interactions
- **Fast**: Optimized CSS, minimal dependencies

## Color Palette

- **Primary**: Blue (#007bff)
- **Success**: Green (#28a745)
- **Warning**: Amber (#ffc107)
- **Danger**: Red (#dc3545)
- **Background**: White & Light Gray
- **Text**: Dark Gray & Black

## Responsive Breakpoints

- Desktop: 1200px+
- Tablet: 768px - 1199px
- Mobile: < 768px
- Small Mobile: < 480px

## API Integration

The user tool integrates with existing Axehead FM endpoints:

- `/api/catalog` - Get media catalog
- `/api/audio/devices` - Audio device list
- `/api/system/info` - System information
- `/api/wifi/connections` - WiFi networks

Create new endpoints in `routes.py` as needed for user-specific features.

## Example: Adding a Simple Feature

**1. Update `user.html`:**
```html
<div class="card">
    <div class="card-header">
        <h3 class="card-title">Now Playing</h3>
    </div>
    <div id="now-playing" class="card-content">
        Loading...
    </div>
</div>
```

**2. Add JavaScript:**
```javascript
async function loadNowPlaying() {
    const data = await fetchJSON('/catalog');
    document.getElementById('now-playing').innerHTML = 
        `<p>${data[Object.keys(data)[0]].title}</p>`;
}

document.addEventListener('DOMContentLoaded', loadNowPlaying);
```

**3. Optional: Create backend endpoint** (if existing API isn't sufficient)
```python
@api_bp.route('/user/now-playing', methods=['GET'])
def get_now_playing():
    # Return current track info
    return jsonify({...})
```

## Next Steps

1. Access the user tool at: `http://<device>:5000/api/user`
2. Start adding features following the patterns above
3. Use browser developer tools to debug and test
4. Add CSS classes as needed for custom styling
