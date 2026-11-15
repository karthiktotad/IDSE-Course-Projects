# Asset credits and licenses

## Used at runtime

### Kenney Tiny City (version 1.0)

- Source: https://kenney.nl/assets/tiny-city
- Creator: Kenney Vleugels / Kenney.nl
- License: Creative Commons Zero (CC0), verified in the archive's `License.txt`.
- Included source download: `frontend/kenney_tiny-city.zip` (preserved as downloaded).
- Inspected tile sheet: `Tilemap/tilemap.png`, 203×186 px, 12 columns × 11 rows, 16×16 px frames with 1 px spacing. The archive's `Tilesheet.txt` documents those frame dimensions and 132 total tiles; individual PNGs are 16×16.
- Runtime copy: `frontend/public/assets/eastbank/kenney-tiny-city/tilemap.png` plus the included license and tile sheet information.
- Usage: small city roof tiles, trees, street lights and vehicles. The current map renders them at 2× for the 32×32 world grid. Frame positions used by the renderer were checked against the packed tile sheet preview.
- Attribution is optional; Kenney is credited here as provenance.

## Inspected but not used

| Pack | Source and license | Inspected file dimensions / contents | Why it is not used in the Eastbank renderer |
|---|---|---|---|
| (12×12) City Tiles - Top Down, FisherG | [OpenGameArt source](https://opengameart.org/content/12x12-city-tiles-top-down); CC0 listed on the source page and permission reiterated in `TopDownCityPack/Readme.txt`. Optional attribution: FisherG. | `sTiles.png` is 360×360 px, corresponding to a 30×30 sheet of 12 px sprites; mockup is 600×546 px. | Its palette and sprite proportions differ from Tiny City. |
| Road Tile Set, Chasersgaming | [OpenGameArt source](https://opengameart.org/content/road-tile-set-0); CC0 listed on the source page. Optional attribution: Chasersgaming. | Downloaded `sprite25_0.png`: 440×512 px, RGBA. | Its isolated road graphics do not match the selected city pack closely enough to combine. |
| Smooth tileset, Matvey | [OpenGameArt source](https://opengameart.org/content/smooth-tileset); CC0 listed on the source page. | Downloaded `smooth.png`: 192×384 px RGBA; page describes 32×32 tiles. | Its textured, smooth water and grass style differs from Tiny City's crisp pixel art. |
| Kenney 3D Road Tiles | CC0, verified in the archive's `License.txt`. | `3D Road pack.zip` contains 302 OBJ models and a Unity package, with 918×515 px preview/sample images. | 3D mesh content is not used in this orthogonal 2D Phaser map. |

The supplied archives and images remain in `frontend/`; the renderer loads only the selected Kenney Tiny City atlas. There are no network asset requests at runtime.
