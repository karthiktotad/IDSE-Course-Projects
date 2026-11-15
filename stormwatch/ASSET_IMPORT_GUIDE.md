# Asset import notes

Kenney Tiny City is now used by the Eastbank renderer. The archive was inspected before import; its CC0 license is included beside the runtime atlas at `frontend/public/assets/eastbank/kenney-tiny-city/`.

The renderer loads its verified 203×186 px tile sheet as 16×16 px frames with one pixel of spacing. No external URL or download is needed at runtime. The rest of the downloaded packs remain in `frontend/` and are intentionally not mixed into this district's tile style. License and dimension notes are in [ASSET_CREDITS.md](ASSET_CREDITS.md).

If another art pack is selected for a later area, inspect its archive and license first, record its real image dimensions, and keep that area's tiles visually consistent.
