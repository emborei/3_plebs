# Navigation data: stage maps + visual labels

## Recommendation

Use **both**, for different jobs:

- **Static stage map data** is a prior for global orientation, corridors, walls, and named objectives.
- **Labels/detections from live screenshots** are necessary for moving enemies, projectiles, telegraphs, XP, bosses, UI state, and determining where the player currently is.

A mined map cannot tell the bot that a projectile is about to hit. A detector cannot tell it where a faraway relic is. The navigation policy should combine them, with immediate threat avoidance always allowed to override the global route.

## What research found

- [VampireUnpacker](https://github.com/SurvivatonsAndMore/VampireUnpacker) documents exporting a 1:1 stage-tilemap image from a stage prefab, plus merged game data and language strings. Its current instructions use AssetRipper and local game files. It also warns that its selected output/assets folder is cleared during a rip; only use a disposable copy/scratch folder and do not point it at saves or the installed game directory.
- The in-game [Milky Way Map](https://vampire.survivors.wiki/w/Milky_Way_Map) reveals a pause-menu map with the player marker and stage pickups/objectives after the relic is unlocked. That gives us a possible screen-only localization/goal source without reading memory. Some DLC stages have their own map relics, so map coverage is stage-dependent.
- A public enemy-detection dataset exists, but the reported v3 model was trained on only 59 images, with 49.8 mAP@50 and 48.5% recall ([dataset/model card](https://universe.roboflow.com/vampire-survivors/vampire-survivors-enemies-detection/model/3)). That is useful for experimentation, not a safe production detector; a missed threat is more important than a pretty confidence score.

## First navigation milestone

Pick **one stage and one game version**—prefer a simple/open or corridor-style map—and get these pieces working before broad DLC support:

1. Export its tilemap to an image from a disposable local asset copy. Record exact game version, stage/mode, DLC, and a hash for the export.
2. Add a matching Milky Way pause-map screenshot. Detect the player marker and one or two known landmarks/POIs; this anchors the tilemap to screen-map coordinates.
3. Capture normal gameplay on the same stage at a fixed resolution. Build a labelled set for `enemy`, `projectile`, `telegraph`, `xp`, `boss`, `boss_health_bar`, `pickup`, and `level_up_ui`. Start with a few hundred varied frames as a feasibility test, then measure recall on held-out clips before deciding whether more labels/training are needed.
4. Implement a **debug-only** localization overlay first: stage map, estimated player position, confidence, recognized threats and goals. Do not allow it to steer until its estimates stay aligned while the character moves in all eight directions.
5. Add a cost grid / A* route to static objectives, then blend its desired direction with the current evasive policy. Threat avoidance wins; when localization confidence is low, fall back to local screen-only dodging/orbit movement.

## Coordinate problem to solve

The exported image is a static map; the live game camera follows/centers the player, and scrolling screenshots do not directly reveal world coordinates. We must establish an external anchor. Best initial option: detect the player marker on the pause map and map screenshot-visible objective markers to exported landmarks. During play, maintain position using visual landmarks/odometry only while confidence remains high, then periodically re-anchor from the pause map if the user enables it. If that proves too brittle, use the game’s visible edge arrows for objectives as local bearings and treat the tilemap only as an objective/obstacle reference.

Do not assume every mode/map has the same extent or orientation. Validate normal/Hyper/Inverse, zoom/resolution, DLC, and patch versions separately. Keep a versioned profile per stage rather than silently applying an old map.

## Proposed local profile (no extracted assets are committed)

```json
{
  "schema_version": 1,
  "stage_id": "inlaid_library",
  "game_version": "user-verified-version",
  "mode": "normal",
  "map_image": "maps/inlaid_library.png",
  "map_sha256": "...",
  "world_bounds": null,
  "orientation": "unverified",
  "landmarks": [],
  "walkable_mask": null,
  "source": "user-local VampireUnpacker export"
}
```

`world_bounds`, orientation, and landmarks must be calibrated against visible game captures; a raw tilemap image alone is not enough to plan a route. Keep maps/models in user data or user-selected folders, not in Git or the installer, unless redistribution rights are clear.

## What we need from a test setup

- Windows + Steam game version and selected stage/DLC/mode.
- Resolution, display scaling, and whether Milky Way Map is unlocked (plus relevant DLC map relics).
- A short capture of: stage start, ordinary movement in four/eight directions, one pause map, an enemy-heavy moment, a boss/telegraph moment, and one level-up screen. Redact anything personal outside the game window.
- If available, a local tilemap export and stage metadata, generated in a scratch copy of the game files. Do not upload proprietary game files; a map screenshot/export and metadata are enough for the first prototype.
- GPU model/driver to verify the selected ONNX provider, although capture and map calibration are independent of GPU vendor.
