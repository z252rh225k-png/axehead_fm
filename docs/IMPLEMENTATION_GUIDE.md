# Axehead FM - Feature Implementation Guide

## Overview

This document outlines the phased implementation of four major features to enhance Axehead FM with network connectivity, media management, and over-the-air updates. Each phase is designed to be independent, with clear deliverables and integration points.

**Total Estimated Effort**: 2-3 weeks of development
**Key Constraint**: Work in phases to survive Copilot usage limits

---

## Phase 1: Web UI Scaffold + Media Management (Priority: HIGH)

**Goal**: Build a functional web interface for uploading/managing media and editing the catalog

**Deliverables**:
- Flask web app running on port 5000
- Dashboard showing media catalog
- Upload forms for audio/video/images
- CRUD operations for catalog entries
- Integration with existing catalog.json

**Dependencies**: Flask, werkzeug (for file handling)
**Effort**: 3-4 days
**Status**: Not Started
**Detailed Plan**: See [phase-1-web-ui.md](phase-1-web-ui.md)

**Key Files to Create**:
- `src/music_player/web/__init__.py`
- `src/music_player/web/app.py`
- `src/music_player/web/routes.py`
- `src/music_player/web/models.py`
- `src/music_player/web/utils.py`
- `src/music_player/web/templates/base.html`
- `src/music_player/web/templates/dashboard.html`
- `src/music_player/static/css/dashboard.css`
- `src/music_player/static/js/dashboard.js`

**Integration Points**:
- Add Flask startup to `player.py` main loop (optional: separate systemd service)
- Modify `catalog.json` loading to watch for changes
- Use existing media paths from deployment notes

---

## Phase 2: WiFi Setup via NFC (Priority: HIGH)

**Goal**: Enable scanning NFC tags to provision WiFi credentials

**Deliverables**:
- Extended NFC reader to detect NDEF WiFi messages
- NetworkManager wrapper for WiFi connection
- WiFi status screen in UI
- Configuration storage for WiFi settings

**Dependencies**: nmcli (pre-installed), ndeflib (optional)
**Effort**: 2-3 days
**Status**: Not Started
**Detailed Plan**: See [phase-2-wifi-nfc.md](phase-2-wifi-nfc.md)

**Key Files to Create/Modify**:
- `src/music_player/hardware/network_manager.py` (NEW)
- `src/music_player/hardware/nfc_reader.py` (EXTEND)
- `src/music_player/ui/screens/wifi_setup_screen.py` (NEW)
- `src/music_player/state/config.py` (EXTEND)

**Integration Points**:
- Hook into main player loop before media handlers
- Add WiFi status to renderer priority
- Store WiFi credentials securely (env var or encrypted config)

---

## Phase 3: GitHub OTA Updates (Priority: MEDIUM)

**Goal**: Enable deploying new versions directly from GitHub releases via web interface

**Deliverables**:
- Web endpoint to upload/apply update packages
- Rollback mechanism (keep previous version)
- Version tracking and update history
- Integration with systemd service restart

**Dependencies**: Flask (from Phase 1), zipfile (stdlib), subprocess (stdlib)
**Effort**: 2-3 days
**Status**: Not Started
**Detailed Plan**: See [phase-3-github-updates.md](phase-3-github-updates.md)

**Key Files to Create**:
- `src/music_player/web/update_handler.py` (NEW)
- Web UI routes for update management

**Integration Points**:
- Extend Phase 1 web routes
- Requires Phase 1 to be complete
- Works alongside existing systemd services

---

## Phase 4: Web Terminal Access (Priority: NICE TO HAVE)

**Goal**: Access Linux terminal via web interface for debugging/admin tasks

**Deliverables**:
- Web-based terminal emulator (xterm.js)
- Authenticated shell subprocess
- Command history and logging
- Basic security measures (rate limiting, command blacklist)

**Dependencies**: Flask (Phase 1), pyxterm or similar, xterm.js
**Effort**: 2-3 days (optional feature)
**Status**: Not Started
**Detailed Plan**: See [phase-4-web-terminal.md](phase-4-web-terminal.md)

**Warning**: Security-sensitive feature - requires careful implementation

---

## Architecture Overview

### Web Server Architecture

```
┌─────────────────────────────────────────┐
│   Browser (10.0.0.X:8080+)             │
└──────────────┬──────────────────────────┘
               │ HTTP
        ┌──────▼──────┐
        │   Flask     │ (Port 5000)
        │   Web App   │
        └──────┬──────┘
     ┌─────────┴──────────────────┐
     │                            │
┌────▼────────┐         ┌────────▼─────┐
│  Routes     │         │  File I/O    │
│ (Phase 1-3) │         │  Media Dir   │
└─────────────┘         └──────────────┘
     │
     └─────► catalog.json (read/write)

```

### Integration with Main Player

```
┌──────────────────────────────────┐
│   player.py Main Loop            │
│  (100ms cycle)                   │
└──────────────┬───────────────────┘
     ┌────────┴─────────────────────┐
     │                              │
 ┌───▼────┐               ┌────────▼────┐
 │  NFC   │               │   Web App   │
 │ Reader │────────────── │  (Background│
 └────────┘ Phase 2       │   Thread)   │
     │                    │  Phase 1    │
     │                    └─────────────┘
     │
  ┌──▼─────────┐
  │  Handlers   │
  │ (Media)     │
  └─────────────┘
```

---

## Implementation Strategy to Handle Usage Limits

Each phase is designed as a **complete, self-contained module**:

1. **Phase 1** (Web UI) can run in isolation without Phase 2-4
2. **Phase 2** (WiFi) is independent of Phase 1 but enhances it
3. **Phase 3** (Updates) depends on Phase 1 but extends it
4. **Phase 4** (Terminal) is purely optional

**If interrupted by usage limits**:
- Save work at end of each phase
- Next session can pick up at Phase N+1
- All phases include comprehensive documentation
- Each phase has a clear integration checklist

**Token-saving strategies**:
- Use detailed phase documents instead of long chat explanations
- Implement each phase in dedicated functions/modules (no large rewrites)
- Test locally before deployment instructions
- Keep code modular and well-commented

---

## File Organization

```
docs/
├── IMPLEMENTATION_GUIDE.md (this file)
├── phase-1-web-ui.md       (Full Phase 1 guide + code)
├── phase-2-wifi-nfc.md     (Full Phase 2 guide + code)
├── phase-3-github-updates.md (Full Phase 3 guide + code)
└── phase-4-web-terminal.md (Full Phase 4 guide + code)

src/music_player/
├── web/                    (Phase 1-3)
│   ├── __init__.py
│   ├── app.py
│   ├── routes.py
│   ├── models.py
│   ├── utils.py
│   ├── update_handler.py   (Phase 3)
│   └── templates/
│       ├── base.html
│       ├── dashboard.html
│       ├── updates.html    (Phase 3)
│       └── terminal.html   (Phase 4)
├── static/
│   ├── css/dashboard.css
│   ├── js/dashboard.js
│   ├── js/terminal.js      (Phase 4)
│   └── js/xterm/          (Phase 4)
├── hardware/
│   ├── network_manager.py  (Phase 2)
│   └── nfc_reader.py       (Phase 2 - extend)
└── ui/screens/
    └── wifi_setup_screen.py (Phase 2)
```

---

## Quick Reference: Which Phase to Start?

**For basic media management only**: Start Phase 1
**For automatic WiFi setup**: Start Phase 1, then Phase 2
**For cloud deployment/CI-CD**: Start Phase 1, then Phase 3
**For full admin interface**: All phases in order

---

## Testing Strategy

Each phase includes:
- Unit tests for core logic
- Integration tests with existing player code
- Manual testing checklist
- Rollback/error handling procedures

See individual phase documents for test procedures.

---

## Security Considerations

- Phase 1: File upload validation (mime types, max size)
- Phase 2: WiFi credential storage (encrypted config file)
- Phase 3: Update signature verification (optional)
- Phase 4: Command blacklist and rate limiting (critical)

---

## Next Steps

1. Read [phase-1-web-ui.md](phase-1-web-ui.md) for implementation details
2. Create directory structure: `src/music_player/web/`
3. Implement Phase 1 following the detailed guide
4. Test locally with Flask development server
5. Deploy to Raspberry Pi and test with actual media

Good luck! 🚀
