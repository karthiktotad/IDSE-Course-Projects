import Phaser from 'phaser';
import type { FloodOverlay, GameState, MapCell } from './types';

const W = 32, H = 24, TILE = 32;
const at = (x: number, y: number) => y * W + x;
const hash = (x: number, y: number) => ((x * 73856093) ^ (y * 19349663) ^ 0x45a31) >>> 0;
const rgb = (r: number, g: number, b: number) => Phaser.Display.Color.GetColor(r, g, b);
const mix = (a: number, b: number, t: number) => Math.round(a + (b - a) * Phaser.Math.Clamp(t, 0, 1));
const waterTint = (depth: number) => {
  const from = depth < 15 ? 0x87dce7 : depth < 60 ? 0x3d9dbb : 0x21698b;
  const to = depth < 15 ? 0x3d9dbb : depth < 60 ? 0x21698b : 0x102e56;
  const t = depth < 15 ? depth / 15 : depth < 60 ? (depth - 15) / 45 : Math.min(1, (depth - 60) / 100);
  const a = Phaser.Display.Color.IntegerToColor(from), b = Phaser.Display.Color.IntegerToColor(to);
  return rgb(mix(a.red, b.red, t), mix(a.green, b.green, t), mix(a.blue, b.blue, t));
};

export type EastbankCallbacks = {
  onCellSelected: (cell: MapCell) => void;
  onCellHovered: (cell: MapCell | null, pointer: Phaser.Input.Pointer | null) => void;
  onPlacementTarget: (cell: MapCell) => void;
  onPlacementHover: (cell: MapCell | null) => void;
};

export class EastbankScene extends Phaser.Scene {
  map?: GameState;
  private overlay: FloodOverlay = null;
  private hovered: MapCell | null = null;
  private selected: MapCell | null = null;
  private dragStart = { x: 0, y: 0, scrollX: 0, scrollY: 0 };
  private dragged = false;
  private deployed: Array<{ x: number; y: number; resourceId: 'pump' | 'barrier' | 'rescue-boat'; direction?: 'N' | 'E' | 'S' | 'W'; radius?: number }> = [];
  private displayedWaterDepth: number[] = [];
  private waterDepthStart: number[] = [];
  private waterDepthTarget: number[] = [];
  private waterAnimationElapsed = 0;
  private waterAnimationActive = false;
  private floodFront: Array<{ x: number; y: number; startedAt: number }> = [];
  private staticRendered = false;
  private visualElapsed = 0;
  private dynamicDrawElapsed = 0;
  private overlayGraphics?: Phaser.GameObjects.Graphics;
  private waterSurfaceGraphics?: Phaser.GameObjects.Graphics;
  private atmosphereGraphics?: Phaser.GameObjects.Graphics;
  private flowGraphics?: Phaser.GameObjects.Graphics;
  private weatherGraphics?: Phaser.GameObjects.Graphics;
  private effectGraphics?: Phaser.GameObjects.Graphics;
  private deploymentGraphics?: Phaser.GameObjects.Graphics;
  private focusGraphics?: Phaser.GameObjects.Graphics;
  private kenneyReady = false;
  private placementMode = false;
  private readyCallback?: () => void;
  private tutorialFocusId: string | null = null;
  private placementPreview: { cell: MapCell; valid: boolean; resourceId: 'pump' | 'barrier' | 'rescue-boat'; direction: 'N' | 'E' | 'S' | 'W' } | null = null;
  private placementGraphics?: Phaser.GameObjects.Graphics;

  constructor(private readonly callbacks: EastbankCallbacks) { super('eastbank'); }

  setReadyCallback(callback: () => void) { this.readyCallback = callback; }

  preload() {
    this.load.spritesheet(
      'kenney-tiny-city',
      '/assets/eastbank/kenney-tiny-city/tilemap.png',
      { frameWidth: 16, frameHeight: 16, margin: 0, spacing: 1 },
    );
    this.load.on('loaderror', (file: Phaser.Loader.File) => console.error('Asset load failed:', file.key, file.src));
  }

  create() {
    this.kenneyReady = this.textures.exists('kenney-tiny-city');
    const camera = this.cameras.main;
    camera.setBounds(0, 0, W * TILE, H * TILE);
    camera.setZoom(1);
    camera.centerOn(W * TILE / 2, H * TILE / 2);
    camera.roundPixels = true;
    this.input.on('pointerdown', (p: Phaser.Input.Pointer) => {
      this.dragged = false;
      this.dragStart = { x: p.x, y: p.y, scrollX: camera.scrollX, scrollY: camera.scrollY };
    });
    this.input.on('pointermove', (p: Phaser.Input.Pointer) => {
      if (p.isDown) {
        const dx = p.x - this.dragStart.x, dy = p.y - this.dragStart.y;
        if (Math.abs(dx) + Math.abs(dy) > 3) this.dragged = true;
        if (this.dragged && !this.placementMode) {
          camera.scrollX = this.dragStart.scrollX - dx / camera.zoom;
          camera.scrollY = this.dragStart.scrollY - dy / camera.zoom;
        }
      }
      const world = camera.getWorldPoint(p.x, p.y);
      const x = Math.floor(world.x / TILE), y = Math.floor(world.y / TILE);
      const cell = x >= 0 && y >= 0 && x < W && y < H && this.map ? this.map.cells[at(x, y)] : null;
      if (cell !== this.hovered) { this.hovered = cell; this.drawFocus(); }
      if (this.placementMode) this.callbacks.onPlacementHover(cell);
      this.callbacks.onCellHovered(cell, cell ? p : null);
    });
    this.input.on('pointerup', (p: Phaser.Input.Pointer) => {
      if (!this.map) return;
      const world = camera.getWorldPoint(p.x, p.y);
      const x = Math.floor(world.x / TILE), y = Math.floor(world.y / TILE);
      if (x < 0 || y < 0 || x >= W || y >= H) return;
      if (this.placementMode) {
        this.callbacks.onPlacementTarget(this.map.cells[at(x, y)]);
        return;
      }
      if (this.dragged) return;
      this.selected = this.map.cells[at(x, y)];
      this.drawFocus();
      this.callbacks.onCellSelected(this.selected);
    });
    this.input.on('pointerout', () => { this.hovered = null; this.drawFocus(); this.callbacks.onCellHovered(null, null); if (this.placementMode) this.callbacks.onPlacementHover(null); });
    this.input.on('wheel', (_p: Phaser.Input.Pointer, _objects: unknown[], _dx: number, dy: number) => {
      const next = Phaser.Math.Clamp(camera.zoom * (dy > 0 ? 0.9 : 1.1), 1, 2.8);
      camera.zoomTo(next, 170);
    });
    this.readyCallback?.();
    this.readyCallback = undefined;
  }

  setMapData(data: GameState, initial = false) {
    if (data.columns !== W || data.rows !== H || data.cells.length !== W * H) {
      throw new Error('Eastbank map grid must be exactly 32 x 24 cells');
    }
    if (!this.map || initial || this.displayedWaterDepth.length !== data.cells.length) {
      this.displayedWaterDepth = data.cells.map(cell => cell.water_depth_mm);
      this.waterDepthStart = [...this.displayedWaterDepth];
      this.waterDepthTarget = [...this.displayedWaterDepth];
      this.waterAnimationActive = false;
    } else {
      this.waterDepthStart = [...this.displayedWaterDepth];
      this.waterDepthTarget = data.cells.map(cell => cell.water_depth_mm);
      this.waterAnimationElapsed = 0;
      this.waterAnimationActive = true;
      const newFront = data.cells.filter((cell, index) => {
        const before = this.displayedWaterDepth[index] ?? 0;
        return cell.water_depth_mm - before > 5 && (before < 3 || cell.water_depth_mm - before > 25);
      }).map(cell => ({ x: cell.x, y: cell.y, startedAt: this.visualElapsed }));
      this.floodFront = [...this.floodFront.filter(item => this.visualElapsed - item.startedAt < 1500), ...newFront].slice(-180);
      if (newFront.some(item => data.cells[at(item.x, item.y)]?.is_road)) this.cameras.main.shake(180, 0.0012);
    }
    this.map = data;
    this.deployed = [
      ...data.resources.pumps.map(item => ({ x: item.grid_position.x, y: item.grid_position.y, resourceId: 'pump' as const, radius: item.operating_radius_cells })),
      ...data.resources.barriers.map(item => ({ x: item.position.x, y: item.position.y, resourceId: 'barrier' as const, direction: item.direction })),
      ...data.resources.rescue_boats.map(item => ({ x: item.grid_position.x, y: item.grid_position.y, resourceId: 'rescue-boat' as const, radius: item.operating_radius_cells })),
    ];
    this.renderMap();
  }

  update(_time: number, delta: number) {
    if (!this.map) return;
    this.visualElapsed += delta;
    if (this.waterAnimationActive) {
      this.waterAnimationElapsed = Math.min(620, this.waterAnimationElapsed + delta);
      const progress = this.waterAnimationElapsed / 620;
      const eased = progress * progress * (3 - 2 * progress);
      for (let index = 0; index < this.displayedWaterDepth.length; index += 1) {
        this.displayedWaterDepth[index] = this.waterDepthStart[index]
          + (this.waterDepthTarget[index] - this.waterDepthStart[index]) * eased;
      }
      if (progress >= 1) this.waterAnimationActive = false;
    }
    // Dynamic 32x24 layers redraw at 16x20 fps; terrain and building art remains cached.
    this.dynamicDrawElapsed += delta;
    if (this.dynamicDrawElapsed >= 55) {
      this.dynamicDrawElapsed = 0;
      this.drawWeather();
      this.drawAnimatedWater();
      this.drawAnimatedCityEffects();
      this.drawDeployments(this.deploymentGraphics);
      this.drawPlacementPreview();
      if (this.tutorialFocusId) this.drawFocus();
      this.drawFocus();
    }
  }

  setOverlay(layer: FloodOverlay) { this.overlay = layer === this.overlay ? null : layer; this.renderMap(); return this.overlay; }
  setPlacementMode(active: boolean) { this.placementMode = active; if (!active) this.setPlacementPreview(null); }
  setPlacementPreview(preview: { cell: MapCell; valid: boolean; resourceId: 'pump' | 'barrier' | 'rescue-boat'; direction: 'N' | 'E' | 'S' | 'W' } | null) {
    this.placementPreview = preview;
    this.drawPlacementPreview();
  }

  private drawPlacementPreview() {
    this.placementGraphics?.clear();
    const preview = this.placementPreview;
    if (!preview || !this.map) return;
    const g = this.placementGraphics ??= this.add.graphics().setDepth(9);
    const color = preview.valid ? 0x7be0a2 : 0xf17d77;
    const x = preview.cell.x * TILE, y = preview.cell.y * TILE;
    const pulse = 0.55 + 0.4 * (0.5 + 0.5 * Math.sin(this.visualElapsed / 160));
    g.fillStyle(color, 0.13 + pulse * 0.12); g.fillRect(x + 1, y + 1, TILE - 2, TILE - 2);
    g.lineStyle(1.5 + pulse, color, pulse); g.strokeRect(x + 1, y + 1, TILE - 2, TILE - 2);
    if (preview.resourceId === 'pump') {
      g.lineStyle(1, color, 0.75); g.strokeCircle(x + 16, y + 16, 2.5 * TILE);
      g.fillStyle(color, 1); g.fillCircle(x + 16, y + 16, 5);
    } else if (preview.resourceId === 'rescue-boat') {
      g.lineStyle(1, color, 0.75); g.strokeCircle(x + 16, y + 16, 5 * TILE);
      g.fillStyle(color, 1); g.fillTriangle(x + 8, y + 20, x + 24, y + 20, x + 16, y + 9);
    } else {
      g.lineStyle(5, color, 1);
      const edge = preview.direction;
      if (edge === 'N') g.lineBetween(x, y, x + TILE, y);
      if (edge === 'S') g.lineBetween(x, y + TILE, x + TILE, y + TILE);
      if (edge === 'W') g.lineBetween(x, y, x, y + TILE);
      if (edge === 'E') g.lineBetween(x + TILE, y, x + TILE, y + TILE);
    }
  }
  getOverlay() { return this.overlay; }
  resetCamera() { this.cameras.main.pan(W * TILE / 2, H * TILE / 2, 250, 'Sine.easeOut'); this.cameras.main.zoomTo(1, 220); }
  zoomBy(delta: number) { this.cameras.main.zoomTo(Phaser.Math.Clamp(this.cameras.main.zoom + delta, 1, 2.8), 180); }

  setTutorialFocus(locationId: string | null) {
    this.tutorialFocusId = locationId;
    this.drawFocus();
  }

  getTutorialLocationRect(locationId: string): DOMRect | null {
    const location = this.map?.locations.find(place => place.id === locationId);
    const canvas = this.game?.canvas;
    if (!location || !canvas) return null;
    const bounds = canvas.getBoundingClientRect();
    const camera = this.cameras.main;
    const scaleX = bounds.width / camera.width;
    const scaleY = bounds.height / camera.height;
    const left = bounds.left + (location.x * TILE - camera.scrollX) * camera.zoom * scaleX;
    const top = bounds.top + (location.y * TILE - camera.scrollY) * camera.zoom * scaleY;
    const width = location.width * TILE * camera.zoom * scaleX;
    const height = location.height * TILE * camera.zoom * scaleY;
    if (left + width < bounds.left || top + height < bounds.top || left > bounds.right || top > bounds.bottom) return null;
    return new DOMRect(left, top, width, height);
  }

  private renderMap() {
    if (!this.map) return;
    if (!this.staticRendered) {
      const g = this.add.graphics().setDepth(0);
      this.drawTerrain(g);
      this.drawChannels(g);
      this.drawRoads(g);
      this.drawBuildings(g);
      if (!this.kenneyReady) this.drawGreenery(g);
      this.drawInteractiveObjects(g);
      if (this.kenneyReady) this.drawKenneyAssets();
      this.drawPlaceLabels();
      this.staticRendered = true;
    }
    this.overlayGraphics ??= this.add.graphics().setDepth(4);
    this.waterSurfaceGraphics ??= this.add.graphics().setDepth(4.2);
    this.atmosphereGraphics ??= this.add.graphics().setDepth(3.6);
    this.flowGraphics ??= this.add.graphics().setDepth(3.7);
    this.deploymentGraphics ??= this.add.graphics().setDepth(5);
    this.effectGraphics ??= this.add.graphics().setDepth(6);
    this.weatherGraphics ??= this.add.graphics().setDepth(7);
    this.placementGraphics ??= this.add.graphics().setDepth(9);
    this.focusGraphics ??= this.add.graphics().setDepth(8);
    this.overlayGraphics.clear();
    this.overlayGraphics.setVisible(Boolean(this.overlay));
    if (this.overlay) this.drawOverlay(this.overlayGraphics);
    this.drawWeather();
    this.drawAnimatedWater();
    this.drawAnimatedCityEffects();
    this.drawDeployments(this.deploymentGraphics);
    this.drawPlacementPreview();
    this.drawFocus();
  }

  private drawKenneyAssets() {
    const city = this.map!;
    const places = new Map(city.locations.map(place => [place.id, place]));
    // These frames were read from the included 12 x 11 tile sheet: brown/blue roof tiles,
    // trees and road props. The source uses 16px cells separated by one transparent pixel.
    for (const cell of city.cells) {
      if (cell.building_id) {
        const place = places.get(cell.building_id);
        const seed = hash(cell.x, cell.y);
        const roofFrame = place?.kind === 'hospital' || place?.kind === 'control_centre' ? 6
          : place?.kind === 'school' ? 0 : seed % 3 === 0 ? 6 : 0;
        this.add.image(cell.x * TILE + 16, cell.y * TILE + 16, 'kenney-tiny-city', roofFrame)
          .setScale(2).setDepth(2);
      } else if (!cell.is_road && cell.terrain_type !== 'river' && cell.terrain_type !== 'canal'
          && !cell.interactive_object_id) {
        const seed = hash(cell.x, cell.y);
        const chance = cell.terrain_type === 'park' ? 35 : 8;
        if (seed % 100 < chance) {
          const frame = seed % 2 ? 68 : 80;
          this.add.image(cell.x * TILE + 16, cell.y * TILE + 16, 'kenney-tiny-city', frame)
            .setScale(2).setDepth(2);
        }
      }
    }
    const streetLights: Array<[number, number, number]> = [
      [8, 5, 86], [23, 5, 86], [29, 5, 85], [8, 12, 86],
      [23, 12, 85], [29, 17, 86], [15, 17, 85],
    ];
    for (const [x, y, frame] of streetLights) {
      this.add.image(x * TILE + 16, y * TILE + 16, 'kenney-tiny-city', frame).setScale(2).setDepth(2.5);
    }
    const cars: Array<[number, number, number]> = [[10, 5, 122], [19, 12, 124], [6, 17, 110], [25, 17, 122]];
    for (const [x, y, frame] of cars) {
      this.add.image(x * TILE + 16, y * TILE + 16, 'kenney-tiny-city', frame).setScale(2).setDepth(3);
    }
    const facilities = this.add.graphics().setDepth(3.2);
    for (const place of city.locations.filter(item => item.kind === 'hospital')) {
      const cx = place.x * TILE + place.width * TILE / 2;
      const cy = place.y * TILE + 17;
      facilities.fillStyle(0xb84443, 1); facilities.fillRect(cx - 3, cy - 10, 6, 20); facilities.fillRect(cx - 10, cy - 3, 20, 6);
    }
  }

  private drawTerrain(g: Phaser.GameObjects.Graphics) {
    for (const c of this.map!.cells) {
      const x = c.x * TILE, y = c.y * TILE, seed = hash(c.x, c.y);
      g.fillStyle(c.terrain_type === 'park' ? 0x658c58 : 0x527b50, 1); g.fillRect(x, y, TILE, TILE);
      g.fillStyle(c.terrain_type === 'park' ? 0x789961 : 0x5c8555, 0.72);
      g.fillRect(x + 3 + seed % 17, y + 3 + (seed >>> 4) % 17, 5, 3);
      g.fillStyle(0x456f49, 0.6); g.fillRect(x + 19 + (seed >>> 8) % 8, y + 22, 3, 2);
      if (c.terrain_type === 'park') {
        g.fillStyle(0x8da66a, 0.5); g.fillCircle(x + 16, y + 16, 7);
        g.lineStyle(1, 0xa6b478, 0.7); g.strokeCircle(x + 16, y + 16, 6);
      }
    }
  }

  private drawChannels(g: Phaser.GameObjects.Graphics) {
    for (const c of this.map!.cells) if (c.terrain_type === 'river' || c.terrain_type === 'canal') {
      const x = c.x * TILE, y = c.y * TILE, river = c.terrain_type === 'river', seed = hash(c.x, c.y);
      g.fillStyle(river ? 0x334c42 : 0x667a50, 1); g.fillRect(x, y, TILE, TILE);
      g.fillStyle(river ? 0x256b80 : 0x2c7480, 1); g.fillRect(x + 3, y + 2, 26, 28);
      g.fillStyle(0x88c3c5, 0.52); g.fillRect(x + 5 + seed % 14, y + 7 + (seed >>> 7) % 15, 8, 2);
      g.fillStyle(0xc5d9ca, 0.3); g.fillRect(x + 18, y + 21, 5, 1);
    }
  }

  private drawRoads(g: Phaser.GameObjects.Graphics) {
    for (const c of this.map!.cells) if (c.is_road) {
      const x = c.x * TILE, y = c.y * TILE, bridge = c.is_bridge;
      g.fillStyle(bridge ? 0xb1aa8d : 0x9b987f, 1); g.fillRect(x, y, TILE, TILE);
      g.fillStyle(bridge ? 0x6c7775 : 0x505c61, 1); g.fillRect(x + (bridge ? 2 : 1), y + (bridge ? 3 : 2), 30, 28);
      g.fillStyle(0x77847e, 0.65); g.fillRect(x + 3, y + 4, 26, 1); g.fillRect(x + 3, y + 27, 26, 1);
      const horizontal = [5, 12, 17].includes(c.y);
      if (!bridge && horizontal && c.x % 2 === 0) {
        g.fillStyle(0xe5d9a9, 0.92); g.fillRect(x + 5, y + 15, 8, 1); g.fillRect(x + 20, y + 15, 7, 1);
      } else if (!bridge && !horizontal && c.y % 2 === 0) {
        g.fillStyle(0xe5d9a9, 0.88); g.fillRect(x + 15, y + 5, 1, 7); g.fillRect(x + 15, y + 20, 1, 7);
      }
      if (bridge) {
        g.fillStyle(0xd3caa6, 1); g.fillRect(x + 2, y + 2, 28, 2); g.fillRect(x + 2, y + 28, 28, 2);
        for (let px = x + 5; px < x + 29; px += 8) { g.fillStyle(0xe0d7b6, 1); g.fillRect(px, y + 1, 2, 4); g.fillRect(px, y + 27, 2, 4); }
      }
    }
  }

  private drawBuildings(g: Phaser.GameObjects.Graphics) {
    const boxes = new Map<string, { minX: number; minY: number; maxX: number; maxY: number }>();
    for (const c of this.map!.cells) if (c.building_id) {
      const box = boxes.get(c.building_id) ?? { minX: c.x, minY: c.y, maxX: c.x, maxY: c.y };
      box.minX = Math.min(box.minX, c.x); box.minY = Math.min(box.minY, c.y); box.maxX = Math.max(box.maxX, c.x); box.maxY = Math.max(box.maxY, c.y); boxes.set(c.building_id, box);
    }
    const locations = new Map(this.map!.locations.map(place => [place.id, place]));
    for (const [id, box] of boxes) {
      const location = locations.get(id), type = location?.kind ?? 'residential';
      const x = box.minX * TILE + 3, y = box.minY * TILE + 3;
      const w = (box.maxX - box.minX + 1) * TILE - 6, h = (box.maxY - box.minY + 1) * TILE - 6;
      const roof = type === 'hospital' ? 0xd5d4c4 : type === 'school' ? 0xc98a52 : type === 'control_centre' ? 0x56727b : type === 'clinic' ? 0x8a9b8b : (hash(box.minX, box.minY) % 2 ? 0x986b58 : 0x777c79);
      g.fillStyle(0x273a39, 0.8); g.fillRect(x + 3, y + 4, w, h);
      g.fillStyle(0xd2c4a2, 1); g.fillRect(x, y + 4, w, h - 3);
      g.fillStyle(roof, 1); g.fillRect(x + 2, y, w - 4, h - 3);
      g.fillStyle(0xe7d7b7, 0.54); g.fillRect(x + 4, y + 3, w - 8, 2);
      g.lineStyle(1, 0x343d3b, 0.9); g.strokeRect(x + 2, y, w - 4, h - 3);
      for (let px = x + 8; px < x + w - 5; px += 12) { g.lineStyle(1, 0xf0e2c5, 0.25); g.lineBetween(px, y + 5, px, y + h - 9); }
      g.fillStyle(0x46565a, 0.9); g.fillRect(x + w * 0.55, y + h * 0.4, 7, 6); g.fillRect(x + w * 0.27, y + h * 0.68, 6, 4);
      if (type === 'hospital') { g.fillStyle(0xb84443, 1); g.fillRect(x + w / 2 - 2, y + 5, 4, 13); g.fillRect(x + w / 2 - 7, y + 10, 14, 4); }
      if (type === 'school') { g.fillStyle(0x3a5d70, 1); for (let px = x + 7; px < x + w - 6; px += 12) g.fillRect(px, y + h - 10, 6, 6); }
    }
  }

  private drawGreenery(g: Phaser.GameObjects.Graphics) {
    for (const c of this.map!.cells) {
      if (c.terrain_type !== 'grass' && c.terrain_type !== 'park') continue;
      const seed = hash(c.x, c.y);
      if (seed % 17 < (c.terrain_type === 'park' ? 8 : 3)) {
        const x = c.x * TILE + 8 + (seed >>> 5) % 12, y = c.y * TILE + 8 + (seed >>> 12) % 12;
        g.fillStyle(0x345b42, 0.95); g.fillRect(x + 2, y + 7, 10, 3);
        g.fillStyle(seed % 2 ? 0x34734b : 0x43804f, 1); g.fillCircle(x + 7, y + 6, 6);
        g.fillStyle(0x8cad62, 0.9); g.fillRect(x + 3, y + 2, 3, 2);
      }
    }
  }

  private drawInteractiveObjects(g: Phaser.GameObjects.Graphics) {
    for (const c of this.map!.cells) if (c.interactive_object_id?.startsWith('drain-')) {
      const x = c.x * TILE, y = c.y * TILE;
      g.fillStyle(0x202f31, 1); g.fillRoundedRect(x + 10, y + 10, 12, 11, 2);
      g.fillStyle(0xaeb7a6, 1); for (let yy = y + 12; yy < y + 20; yy += 3) g.fillRect(x + 12, yy, 8, 1);
    }
    for (const station of this.map!.locations.filter(place => place.kind === 'weather_station')) {
      const x = station.x * TILE, y = station.y * TILE;
      g.fillStyle(0xe0ca83, 1); g.fillRect(x + 5, y + 5, 22, 22);
      g.fillStyle(0x263d45, 1); g.fillRect(x + 14, y + 8, 3, 16); g.fillRect(x + 10, y + 11, 11, 2);
      g.lineStyle(1, 0x24383b, 1); g.strokeCircle(x + 15, y + 9, 5);
    }
  }

  private drawOverlay(g: Phaser.GameObjects.Graphics) {
    const cells = this.map!.cells;
    const getValue = (c: MapCell) => this.overlay === 'elevation' ? c.elevation_mm
      : this.overlay === 'rainfall' ? c.rainfall_intensity_mm_hr
      : this.overlay === 'water' ? this.displayedWaterDepth[at(c.x, c.y)] ?? c.water_depth_mm
          : this.overlay === 'risk' ? c.flood_risk_index : c.drainage_capacity_mm_hr;
    const values = cells.map(getValue), min = Math.min(...values), max = Math.max(...values);
    for (const c of cells) {
      const value = getValue(c), t = (value - min) / Math.max(1, max - min);
      if (this.overlay === 'water') {
        const depth = this.displayedWaterDepth[at(c.x, c.y)] ?? c.water_depth_mm;
        if (depth < 0.5) continue;
        const x = c.x * TILE, y = c.y * TILE;
        const tint = waterTint(depth);
        const alpha = depth < 15 ? 0.25 + depth / 100 : depth < 60 ? 0.42 : 0.58;
        g.fillStyle(tint, alpha); g.fillRect(x, y, TILE, TILE);
        if (depth >= 100) {
          const pulse = 0.45 + 0.45 * (0.5 + 0.5 * Math.sin(this.visualElapsed / 180 + hash(c.x, c.y) % 9));
          g.lineStyle(1.5, 0xf3a17f, pulse); g.strokeRect(x + 1, y + 1, TILE - 2, TILE - 2);
        }
        continue;
      }
      if (this.overlay === 'drainage') {
        const waterway = c.terrain_type === 'river' || c.terrain_type === 'canal';
        const inlet = c.interactive_object_id?.startsWith('drain-');
        if (!waterway && !inlet && c.drainage_capacity_mm_hr < 15) continue;
        g.fillStyle(inlet ? 0xffdb67 : waterway ? 0x58d5df : 0x78bf91, inlet ? 0.82 : 0.28 + t * 0.48);
      } else {
        const color = this.overlay === 'elevation'
          ? rgb(mix(27, 211, t), mix(98, 178, t), mix(126, 93, t))
          : this.overlay === 'rainfall' ? rgb(mix(36, 212, t), mix(121, 91, t), mix(174, 42, t))
            : rgb(mix(37, 226, t), mix(163, 60, t), mix(98, 51, t));
        g.fillStyle(color, 0.28 + t * 0.4);
      }
      g.fillRect(c.x * TILE, c.y * TILE, TILE, TILE);
    }
  }

  private drawAnimatedWater() {
    if (!this.waterSurfaceGraphics || !this.map) return;
    const surface = this.waterSurfaceGraphics;
    surface.clear();
    for (const cell of this.map.cells) {
      const depth = this.displayedWaterDepth[at(cell.x, cell.y)] ?? cell.water_depth_mm;
      if (depth < 1) continue;
      const x = cell.x * TILE, y = cell.y * TILE;
      const tint = waterTint(depth);
      const alpha = this.overlay === 'water' ? 0.28 : Math.min(0.7, 0.22 + depth / 145);
      surface.fillStyle(tint, alpha); surface.fillRect(x + 1, y + 1, TILE - 2, TILE - 2);
      const phase = ((this.visualElapsed / 95) + hash(cell.x, cell.y)) % 25;
      surface.lineStyle(1, 0xa8e5e5, Math.min(0.62, 0.18 + depth / 260));
      surface.lineBetween(x + phase, y + 7 + (hash(cell.x, cell.y) % 16), x + Math.min(30, phase + 6), y + 7 + (hash(cell.x, cell.y) % 16));
      if (depth >= 100) {
        const pulse = 0.3 + 0.35 * (0.5 + 0.5 * Math.sin(this.visualElapsed / 180 + hash(cell.x, cell.y) % 9));
        surface.lineStyle(1, 0xe89579, pulse); surface.strokeRect(x + 1, y + 1, TILE - 2, TILE - 2);
      }
    }
    if (this.overlay === 'water' && this.overlayGraphics) {
      this.overlayGraphics.clear(); this.drawOverlay(this.overlayGraphics);
    }
    this.flowGraphics?.clear();
    if (this.flowGraphics) {
      for (const cell of this.map.cells) {
        if (cell.terrain_type !== 'river' && cell.terrain_type !== 'canal') continue;
        const x = cell.x * TILE, y = cell.y * TILE;
        const vertical = cell.terrain_type === 'river';
        const phase = (this.visualElapsed / 60 + hash(cell.x, cell.y) % 21) % 25;
        this.flowGraphics.lineStyle(1, 0xb4e5db, 0.5);
        if (vertical) this.flowGraphics.lineBetween(x + 9 + (hash(cell.x, cell.y) % 8), y + phase, x + 14 + (hash(cell.x, cell.y) % 8), y + Math.min(30, phase + 7));
        else this.flowGraphics.lineBetween(x + phase, y + 12 + (hash(cell.x, cell.y) % 7), x + Math.min(30, phase + 8), y + 13 + (hash(cell.x, cell.y) % 7));
      }
    }
  }

  private drawWeather() {
    if (!this.weatherGraphics || !this.atmosphereGraphics || !this.map) return;
    const rain = this.map.rainfall_mm_per_hour;
    this.weatherGraphics.clear(); this.atmosphereGraphics.clear();
    if (rain <= 0.5) return;
    const severity = Phaser.Math.Clamp(rain / 100, 0, 1);
    this.atmosphereGraphics.fillStyle(0x0d1a29, severity * 0.2);
    this.atmosphereGraphics.fillRect(0, 0, W * TILE, H * TILE);
    const count = Math.round(18 + severity * 190);
    const drift = (this.visualElapsed * (0.035 + severity * 0.08)) % (W * TILE + 60);
    this.weatherGraphics.lineStyle(severity > 0.55 ? 1 : 0.7, severity > 0.55 ? 0xc2e2ea : 0xb5d9df, 0.18 + severity * 0.3);
    for (let index = 0; index < count; index += 1) {
      const seed = hash(index, 7);
      const x = (seed % (W * TILE) + drift) % (W * TILE);
      const y = (Math.floor(seed / 997) * 17 + this.visualElapsed * (0.12 + severity * 0.34)) % (H * TILE);
      const length = 3 + severity * 8;
      this.weatherGraphics.lineBetween(x, y, x - 2 - severity * 3, y + length);
    }
    if (severity > 0.56 && Math.sin(this.visualElapsed / 1700) > 0.985) {
      this.atmosphereGraphics.fillStyle(0xd7eff2, 0.19);
      this.atmosphereGraphics.fillRect(0, 0, W * TILE, H * TILE);
    }
  }

  private drawAnimatedCityEffects() {
    if (!this.effectGraphics || !this.map) return;
    const g = this.effectGraphics; g.clear();
    for (const station of this.map.locations.filter(place => place.kind === 'weather_station')) {
      const x = station.x * TILE + 16, y = station.y * TILE + 16;
      const pulse = 0.5 + 0.5 * Math.sin(this.visualElapsed / 420 + station.x);
      g.lineStyle(1.5, 0xf0d982, 0.2 + pulse * 0.48);
      g.strokeCircle(x, y, 12 + pulse * 4);
      g.fillStyle(0xffe6a1, 0.22 + pulse * 0.3); g.fillCircle(x + 8, y - 8, 2);
    }
    // Emergency traffic becomes visible once the scripted storm is running.
    // It follows the cross-town arterial as a small flashing ambulance sprite.
    if (this.map.scenario_progress.active) {
      const routeY = 17 * TILE + 16;
      const travel = (this.visualElapsed / 22) % (W * TILE + 60);
      const x = travel - 30;
      const siren = Math.sin(this.visualElapsed / 78) > 0 ? 0xe65d52 : 0x5f9dd2;
      g.fillStyle(0x203b39, 0.22); g.fillEllipse(x, routeY + 10, 27, 5);
      g.fillStyle(0x29423e, 1); g.fillRoundedRect(x - 11, routeY - 7, 22, 13, 3);
      g.fillStyle(0xf3eee0, 1); g.fillRoundedRect(x - 9, routeY - 8, 19, 10, 2);
      g.fillStyle(0xa7c7bd, 1); g.fillRect(x - 7, routeY - 6, 5, 4); g.fillRect(x + 2, routeY - 6, 5, 4);
      g.fillStyle(0xc94f49, 1); g.fillRect(x - 1, routeY - 6, 2, 5); g.fillRect(x - 3, routeY - 4, 6, 2);
      g.fillStyle(0x293533, 1); g.fillCircle(x - 6, routeY + 4, 2); g.fillCircle(x + 6, routeY + 4, 2);
      g.fillStyle(siren, 0.95); g.fillCircle(x, routeY - 10, 2);
      g.fillStyle(siren, 0.16); g.fillCircle(x, routeY - 10, 8);
    }
    const hospital = this.map.locations.find(place => place.kind === 'hospital');
    if (hospital && this.map.simulation.location_accessibility[hospital.id] === 'inaccessible') {
      const x = hospital.x * TILE + hospital.width * TILE / 2;
      const y = hospital.y * TILE - 4;
      const pulse = 0.5 + 0.5 * Math.sin(this.visualElapsed / 180);
      g.fillStyle(0x351f24, 0.85); g.fillCircle(x, y, 8 + pulse * 3);
      g.lineStyle(2, 0xf27d73, 0.5 + pulse * 0.5); g.strokeCircle(x, y, 8 + pulse * 3);
      g.fillStyle(0xffdfd1, 1); g.fillRect(x - 1, y - 4, 2, 5); g.fillCircle(x, y + 3, 1.2);
    }
    for (const cell of this.map.cells) {
      if (!cell.interactive_object_id?.startsWith('drain-')) continue;
      const depth = this.displayedWaterDepth[at(cell.x, cell.y)] ?? cell.water_depth_mm;
      if (depth < 3) continue;
      const x = cell.x * TILE + 16, y = cell.y * TILE + 16;
      const ripple = (this.visualElapsed / 100 + hash(cell.x, cell.y)) % 8;
      g.lineStyle(1, 0x91e1df, 0.65 - ripple * 0.05); g.strokeCircle(x, y, 4 + ripple);
      g.fillStyle(0xbce9de, 0.65); g.fillCircle(x + (ripple % 3), y - 3, 1.3);
    }
    this.floodFront = this.floodFront.filter(front => this.visualElapsed - front.startedAt < 1500);
    for (const front of this.floodFront) {
      const age = this.visualElapsed - front.startedAt;
      const progress = age / 1500;
      const x = front.x * TILE + 16, y = front.y * TILE + 16;
      g.lineStyle(2, 0x9ce8ee, 0.8 * (1 - progress));
      g.strokeCircle(x, y, 7 + progress * 24);
    }
  }

  private drawDeployments(g = this.add.graphics()) {
    g.clear();
    for (const item of this.deployed) {
      const bob = item.resourceId === 'rescue-boat' ? Math.sin(this.visualElapsed / 240 + item.x) * 1.5 : 0;
      const x = item.x * TILE + 16, y = item.y * TILE + 16 + bob;
      const color = item.resourceId === 'pump' ? 0x59e5e0 : item.resourceId === 'barrier' ? 0xffd36e : 0xf28970;
      if (item.resourceId === 'pump') {
        const pulse = 0.25 + 0.45 * (0.5 + 0.5 * Math.sin(this.visualElapsed / 180));
        g.lineStyle(1.5, color, pulse); g.strokeCircle(x, y, 13 + pulse * 4);
        const spin = this.visualElapsed / 180;
        g.lineStyle(1.5, 0xa8ffff, 0.85);
        for (let ray = 0; ray < 4; ray += 1) {
          const angle = spin + ray * Math.PI / 2;
          g.lineBetween(x + Math.cos(angle) * 5, y + Math.sin(angle) * 5, x + Math.cos(angle) * 9, y + Math.sin(angle) * 9);
        }
      }
      if (this.selected?.x === item.x && this.selected?.y === item.y && item.radius) {
        g.lineStyle(2, color, 0.8); g.strokeCircle(x, y, item.radius * TILE);
      }
      if (item.resourceId === 'rescue-boat') {
        g.fillStyle(0x122022, 0.92); g.fillEllipse(x, y, 23, 17);
        g.lineStyle(2, color, 1); g.strokeEllipse(x, y, 23, 17);
        g.fillStyle(0xf4d498, 1); g.fillTriangle(x - 2, y - 6, x + 7, y, x - 2, y + 6);
        g.lineStyle(1, 0xffdfb2, 0.7); g.lineBetween(x - 13, y + 7, x - 19, y + 10);
      } else {
        g.fillStyle(0x122022, 0.92); g.fillCircle(x, y, 11); g.lineStyle(2, color, 1); g.strokeCircle(x, y, 9);
      }
      if (item.resourceId === 'barrier') {
        const direction = item.direction ?? 'N';
        const pulse = 0.72 + 0.28 * Math.sin(this.visualElapsed / 260);
        g.lineStyle(3, color, pulse);
        if (direction === 'N' || direction === 'S') g.lineBetween(x - 8, y, x + 8, y);
        else g.lineBetween(x, y - 8, x, y + 8);
      } else {
        if (item.resourceId !== 'rescue-boat') {
          g.fillStyle(color, 1); g.fillRect(x - 2, y - 5, 4, 10); g.fillRect(x - 5, y - 2, 10, 4);
        }
      }
    }
    const evacuated = this.map?.response_outcome.residential_locations.filter(home => home.evacuated) ?? [];
    evacuated.forEach((home, index) => {
      const boat = this.deployed.filter(item => item.resourceId === 'rescue-boat')
        .sort((a, b) => Phaser.Math.Distance.Between(a.x, a.y, home.x, home.y) - Phaser.Math.Distance.Between(b.x, b.y, home.x, home.y))[0];
      if (!boat) return;
      const hx = home.x * TILE + 16, hy = home.y * TILE + 16;
      const bx = boat.x * TILE + 16, by = boat.y * TILE + 16;
      for (let point = 1; point <= 5; point += 1) {
        const t = point / 6;
        g.fillStyle(0xa5e4b1, 0.4); g.fillCircle(Phaser.Math.Linear(hx, bx, t), Phaser.Math.Linear(hy, by, t), 1.5);
      }
      const travel = (this.visualElapsed / 1500 + index * 0.23) % 1;
      g.fillStyle(0xffedaa, 0.95); g.fillCircle(Phaser.Math.Linear(hx, bx, travel), Phaser.Math.Linear(hy, by, travel), 3);
      const pulse = 0.35 + 0.3 * (0.5 + 0.5 * Math.sin(this.visualElapsed / 220));
      g.lineStyle(1.5, 0x8de0a4, pulse); g.strokeCircle(hx, hy, 11 + pulse * 6);
    });
  }

  private drawPlaceLabels() {
    this.add.text(42, 310, 'WEST RIVER', { fontFamily: 'monospace', fontSize: '13px', color: '#e0e6c5', backgroundColor: '#184553', padding: { x: 4, y: 3 } }).setDepth(5);
    this.add.text(255, 302, 'EASTBANK DRAINAGE CANAL', { fontFamily: 'monospace', fontSize: '12px', color: '#e1e8ca', backgroundColor: '#244851', padding: { x: 4, y: 3 } }).setDepth(5);
    this.add.text(366, 525, 'HOSPITAL ACCESS x LOW', { fontFamily: 'monospace', fontSize: '13px', color: '#f5d598', backgroundColor: '#473b2c', padding: { x: 4, y: 3 } }).setDepth(5);
    for (const station of this.map!.locations.filter(place => place.kind === 'weather_station')) {
      this.add.text(station.x * TILE + 16, station.y * TILE - 3, 'WX', { fontFamily: 'monospace', fontSize: '12px', color: '#f7e5aa', backgroundColor: '#394335', padding: { x: 3, y: 2 } }).setOrigin(0.5, 1).setDepth(5);
    }
    for (const place of this.map!.locations.filter(item => ['hospital', 'school', 'control_centre'].includes(item.kind))) {
      const label = place.kind === 'hospital' ? 'EASTBANK GENERAL' : place.kind === 'school' ? 'EASTBANK SCHOOL' : 'FLOOD CONTROL';
      this.add.text(place.x * TILE, place.y * TILE - 13, label, {
        fontFamily: 'monospace', fontSize: '13px', color: '#fff0c5', backgroundColor: '#182b2a',
        padding: { x: 4, y: 3 },
      }).setDepth(6);
    }
  }

  private drawFocus() {
    if (!this.map) return;
    const graphics = this.focusGraphics ??= this.add.graphics().setDepth(8);
    graphics.clear();
    const drawCell = (cell: MapCell, name: string, color: number, width: number) => {
      graphics.lineStyle(width, color, 1); graphics.strokeRect(cell.x * TILE + 1, cell.y * TILE + 1, TILE - 2, TILE - 2);
      graphics.fillStyle(color, 0.13); graphics.fillRect(cell.x * TILE + 1, cell.y * TILE + 1, TILE - 2, TILE - 2);
    };
    if (this.selected) {
      drawCell(this.selected, 'selected-cell', 0xffdf83, 2);
      if (this.selected.building_id) {
        const footprint = this.map.cells.filter(cell => cell.building_id === this.selected!.building_id);
        const minX = Math.min(...footprint.map(cell => cell.x)), minY = Math.min(...footprint.map(cell => cell.y));
        const maxX = Math.max(...footprint.map(cell => cell.x)), maxY = Math.max(...footprint.map(cell => cell.y));
        const pulse = 0.45 + 0.45 * (0.5 + 0.5 * Math.sin(this.visualElapsed / 200));
        graphics.lineStyle(2, 0xffe28a, pulse); graphics.strokeRoundedRect(minX * TILE + 2, minY * TILE + 2, (maxX - minX + 1) * TILE - 4, (maxY - minY + 1) * TILE - 4, 5);
        graphics.lineStyle(1, 0xfff1bd, pulse * 0.5); graphics.strokeRoundedRect(minX * TILE - 2, minY * TILE - 2, (maxX - minX + 1) * TILE + 4, (maxY - minY + 1) * TILE + 4, 6);
      }
    }
    if (this.hovered) drawCell(this.hovered, 'hover-cell', 0xf1f0dd, 1);
    if (this.tutorialFocusId) {
      const location = this.map.locations.find(place => place.id === this.tutorialFocusId);
      if (location) {
        const pulse = 0.55 + 0.4 * (0.5 + 0.5 * Math.sin(this.visualElapsed / 170));
        const width = location.width * TILE, height = location.height * TILE;
        graphics.lineStyle(4, 0x9fe2c3, pulse); graphics.strokeRoundedRect(location.x * TILE - 3, location.y * TILE - 3, width + 6, height + 6, 8);
        graphics.lineStyle(1, 0xffe28a, 1); graphics.strokeRoundedRect(location.x * TILE - 7, location.y * TILE - 7, width + 14, height + 14, 10);
      }
    }
  }
}
