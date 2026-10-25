# Map packages and place lookups

This repository defines a JSON format used to bundle offline map layers into a
zip file (a *map package*) and to attach renderable content to places matched
on those layers (*place lookups*).

The format has two parts:

1. **Map package** — a zip file holding map layers, with an optional
   `layers.json` describing them and an optional `package.json` identifying the
   package as a whole.
2. **Place lookups** — for any layer that opts in, sibling lookup geometry
   (a `<basename>.shp` bundle or a `<basename>.geojson`) and a sibling
   `<basename>.json` carrying the renderable content.

The content side is **render-first**: each row carries a `view` describing
what to draw, so consumers do not need hard-coded field ordering.

The schema is in [package-schema.json](package-schema.json) (JSON Schema draft
2020-12).

> **Status.** This document describes the target format. Some files in
> [demos/](demos/) and [legal_atlas/](legal_atlas/) still use the older top-level
> wrapper key `package` (instead of `content`) and the older join key
> `feature.id` (instead of `feature.properties.featureId`). They will be
> migrated; the spec below is the canonical target.

---

## 1. Map packages

A map package is a zip file with **all files at the archive root** — there is
no enclosing directory inside the archive.

### 1.1 Package forms

Three forms are supported, in increasing order of capability:

| Form                                       | When to use                                                                |
| ------------------------------------------ | -------------------------------------------------------------------------- |
| **Layers only**                            | Quick packaging; the runtime discovers layers from the archive contents.   |
| **Layers + `layers.json`**                 | Layer ordering, metadata, or place-lookup participation matters.           |
| **Layers + `layers.json` + `package.json`** | **Preferred.** The package will be distributed and serviced over time.    |

`package.json` requires `layers.json` to also be present.

### 1.2 Archive layout and layer bundles

A layer is a group of files sharing a basename. Common bundles:

- Shapefile bundle: `layer1.shp`, `layer1.dbf`, `layer1.shx`, `layer1.prj`,
  `layer1.cpg`, `layer1.qmd`.
- Lookup bundle: `layer1.geojson`, `layer1.json`, or `layer1.shp`,
  `layer1.shx`, `layer1.dbf`, `layer1.json`.

For place lookup, the runtime locates companions by **basename + extension
swap** in the same archive root:

- `<basename>.shp` (+ `.shx`, `.dbf`, optional `.prj`) — lookup geometry,
  used in preference when present (see §2.2).
- `<basename>.geojson` — lookup geometry, used only when there is no
  `<basename>.shp`.
- `<basename>.json` — renderable content.

If the primary layer file is itself a GeoJSON or a shapefile, that same file
may serve as both the display layer and the lookup geometry; the companion
content file is still `<basename>.json`.

### 1.3 `layers.json`

A top-level JSON **array** of layer objects, in the order they should be
drawn:

```json
[
  {
    "filename": "weather.geojson",
    "name": "Weather",
    "active": true,
    "opacity": 0.0,
    "lookup": true
  }
]
```

| Field      | Type    | Purpose |
| ---------- | ------- | ------- |
| `filename` | string  | A filename belonging to the layer — typically the primary display file (`.geojson`, `.shp`, `.mbtiles`, `.tif`, `.kml`, etc.). The runtime takes the **basename** to locate companion lookup files. |
| `name`     | string  | Human-readable layer name shown in the UI. |
| `active`   | boolean | Whether the layer is visible when the package is first loaded. |
| `opacity`  | number  | Optional layer opacity from `0.0` (transparent) to `1.0` (opaque). |
| `lookup`   | boolean | Whether the layer participates in place lookup (see §2). |
| `symbol`   | object  | Optional symbol description for vector layers (see §1.6). Typically irrelevant for KML and raster formats. |

When `lookup` is `true`, the runtime expects sibling lookup geometry
(`<basename>.shp` bundle or `<basename>.geojson`) and a `<basename>.json`
content file.

### 1.4 `package.json`

`package.json` identifies the package as a whole and powers the update flow:

```json
{
  "id": "LegalAtlas",
  "name": "Legal Atlas Mongolia",
  "version": "2026.04.21",
  "language": "en"
}
```

| Field      | Type   | Purpose |
| ---------- | ------ | ------- |
| `id`       | string | Stable package identifier. The runtime uses it for deduplication. |
| `name`     | string | Human-readable package name. |
| `version`  | string | Package version. Versions are compared **lexically** — choose values whose string ordering gives the intended semantic ordering (e.g. ISO-style `2026.04.21`, or zero-padded numeric). |
| `language` | string | Optional language identifier such as `en` or `mn`. Used to disambiguate localized packages with the same `id`. |

### 1.5 Distribution — building an applink URL

A package is distributed by hosting the zip at a stable URL and giving users
an **applink** that opens CyberTracker and downloads it.

The applink shape is `https://cybertrackerwiki.org/applink/?x=<payload>`,
where `<payload>` is the base64 encoding of a small JSON object:

```json
{ "webUpdateUrl": "https://ctwiki.blob.core.windows.net/bin/LegalAtlasMongoliaTest.zip" }
```

To build one:

```bash
python3 -c '
import base64, json
payload = {"webUpdateUrl": "https://ctwiki.blob.core.windows.net/bin/LegalAtlasMongoliaTest.zip"}
print("https://cybertrackerwiki.org/applink/?x=" + base64.b64encode(json.dumps(payload).encode()).decode())
'
```

The CyberTracker app intercepts `cybertrackerwiki.org/applink/` URLs, decodes
the `x` parameter, fetches `webUpdateUrl`, and installs the package. Anything
that hands a user a clickable URL works (chat, email, QR codes, NFC).

For SMART Mobile, use the `applink-smart` prefix instead — the URL shape is
`https://cybertrackerwiki.org/applink-smart/?x=<payload>`.

Encoding the applink as a QR code also works — CyberTracker and SMART Mobile
will read the QR code and install the package the same way.

To package a demo locally, run [demos/build.py](demos/build.py); it zips
every subdirectory of `demos/` into a sibling `<name>.zip`.

### 1.6 Runtime behavior

- If `layers.json` is present, it defines the layers and their draw order.
- If `layers.json` is absent, the runtime discovers layers from the archive
  files directly.
- If `package.json` is present, `layers.json` should also be present.
- If `package.json` is present, the runtime uses `id` and `version` to decide
  whether an installed package should be replaced.
- All package files are expected at the archive root.

### 1.7 Symbol examples

Symbols are optional and primarily relevant for shapefile / vector layers.

Point symbol:

```json
{ "marker-style": "circle", "marker-size": 5.5, "marker-color": "#ffff00", "outline-color": "#ff0000" }
```

Line symbol:

```json
{ "stroke-style": "dashdot", "stroke-size": 4.4, "stroke-color": "#ffff00" }
```

Area symbol (with outline sub-symbol):

```json
{
  "fill-style": "solid",
  "fill-color": "#ff00ff",
  "outline-symbol": {
    "stroke-style": "dashdot",
    "stroke-size": 1.0,
    "stroke-color": "#ffff00"
  }
}
```

Allowed enum values:

- `marker-style`: `circle`, `cross`, `diamond`, `square`, `triangle`, `x`
- `stroke-style`: `solid`, `dash`, `dashdot`, `dashdotdot`, `dot`
- `fill-style`: `none`, `solid`, `horizontal`, `vertical`,
  `forwardDiagonal`, `backwardDiagonal`, `cross`, `diagonalCross`

---

## 2. Place lookups

A place lookup answers the question:

> the user selected or tapped at `(x, y)` — what content applies here?

The answer is computed entirely from the per-layer lookup pair
(lookup geometry + `<basename>.json`). The map-package layer in §1 is
about deployment and servicing; the content JSON is only related to its
companion geometry.

### 2.1 Lookup participation

A layer participates in place lookup when its `layers.json` entry has:

```json
{ "lookup": true }
```

When `lookup` is `true`, the runtime expects:

- Companion lookup geometry: `<basename>.shp` (with `.shx` and `.dbf`), or
  `<basename>.geojson`. If both are present the shapefile is used and the
  GeoJSON is never opened.
- `<basename>.json` — companion content file.

If the geometry or the content file is missing, the lookup layer is
incomplete.

### 2.2 Lookup geometry and the join key

The lookup geometry is the file the point-in-polygon test runs against. It
produces a set of **matched feature ids**, which the content file's
`filter.featureIds` (§2.5) is then evaluated against. Two geometry formats
are supported; the join key is the same string in both.

#### GeoJSON lookup geometry

Each feature used for matching must carry a string property named
**`featureId`** inside `properties`:

```json
{
  "type": "Feature",
  "properties": {
    "featureId": "country:MN",
    "name": "Mongolia"
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [[ ... ]]
  }
}
```

The content file matches against `properties.featureId`. The property name
is matched case-insensitively (`FEATUREID`, as a shapefile conversion often
spells it, works). A numeric value is coerced to its string form, so `12`
matches `"12"`. If no `featureId` property exists the runtime falls back to a
property named `fid`, and only then to the standard top-level GeoJSON `id`,
which is a legacy path: it is a record number and should not be relied on.

`featureId` is an opaque string. Conventional namespacing (`country:MN`,
`region:MN-073`, `world`) keeps ids legible across packages but is not
required.

Only `Polygon` and `MultiPolygon` geometries are tested; other geometry
types never match. The whole file is parsed on every lookup, so GeoJSON is
suited to small layers.

#### Shapefile lookup geometry

A lookup layer may ship its geometry as a shapefile bundle instead of, or as
well as, a GeoJSON. When `<basename>.shp` exists the runtime uses it and the
GeoJSON is ignored. The shapefile is preferred because it is binary and
self-indexing: only records whose bounding box contains the point are read,
so large layers stay fast.

The runtime requires `.shp`, `.shx` and `.dbf`. `.prj` is optional but
honoured. `.cpg`, `.sbn`, `.sbx`, `.qix` and `.qmd` are ignored.

A shapefile has no intrinsic feature id. The only built-in identity is a
record's position, which changes whenever the file is edited or re-exported,
so it is not usable as a stable key. The join key is therefore an attribute
column in the `.dbf` named **`featureId`**, or failing that `fid`, the same
names and order the GeoJSON reader uses. Names are matched
case-insensitively, because many shapefile writers uppercase field names;
dBASE limits names to 10 characters, which both fit. If neither column is
present the layer logs an error and yields no matches — it does **not** fall
back to the GeoJSON.

How a lookup at `(x, y)` produces the matched feature ids:

1. **Project the point.** If `<basename>.prj` names a coordinate system
   other than WGS84, the WGS84 point is projected into it. Without a `.prj`
   the shapefile is assumed to hold WGS84 longitude/latitude.
2. **Check the file.** The `.shp` header shape type must be Polygon (5),
   PolygonZ (15) or PolygonM (25), and the header bounding box must contain
   the point. Otherwise there are no matches.
3. **Find the key column.** Walk the `.dbf` field descriptors to locate
   `featureId` and its byte offset within a row.
4. **Scan records.** For each record index `i`:
   - Use `.shx` entry `i` to find record `i` in `.shp`.
   - Skip it unless its shape type is a polygon variant and its record
     bounding box contains the point. This is the step that avoids reading
     most of the file.
   - Skip it if `.dbf` row `i` carries the deletion flag.
   - Read `featureId` from `.dbf` row `i` and trim surrounding whitespace
     (dBASE pads fields to a fixed width). A numeric (`N` or `F`) field is
     normalized to the same string a JSON number would give, so `12`,
     `12.0` and `"12"` all match. Skip it if that id has already matched:
     an id only needs to match once.
   - Decode the record's parts into rings and run an even-odd
     point-in-polygon test across all rings together. Z and M values are
     ignored.
   - On a hit, add the `featureId` to the matched set.
5. **Evaluate content.** The matched set is tested against each dataset's
   `filter.featureIds` exactly as for GeoJSON.

Row `i` of the `.dbf` is paired with record `i` of the `.shp` purely by
position. The two files must have the same record count and order; this is
guaranteed by any standard shapefile writer but is broken by editing one file
without the other.

Even-odd testing means holes are handled by ring nesting rather than winding
order: a point inside an inner ring is outside the feature regardless of ring
direction. A multipart record (several outer rings) matches if the point lies
in any part.

#### Keeping the two formats equivalent

The content file is written once and must work against whichever geometry
the runtime picks. When a layer ships both a `.shp` and a `.geojson`:

- Every feature must carry the same value in `properties.featureId`
  (GeoJSON) and the `featureId` column (`.dbf`).
- Prefer a **character** field in the `.dbf` and a **string** property in
  the GeoJSON. Numeric ids are accepted and normalized identically in both
  readers, but strings avoid any formatting surprises.
- Keep ids ASCII, or make sure the `.dbf` is UTF-8 encoded. The runtime
  decodes the column as UTF-8 regardless of any `.cpg`.
- Avoid leading or trailing whitespace in ids. The `.dbf` value is trimmed;
  the GeoJSON value is used verbatim.
- Converting with `ogr2ogr` carries attribute columns in both directions, so
  a `featureId` column round-trips. The top-level GeoJSON `id` and OGR's
  `fid` are record numbers and are not used by the runtime.

### 2.3 Content JSON structure

A content package looks like this:

```json
{
  "content": {
    "id": "Seasons",
    "language": "en",
    "defaultLocale": "en-US"
  },
  "datasets": [
    {
      "id": "northern-spring",
      "filter": {
        "featureIds": ["hemisphere:north"],
        "when": {
          "start": "2026-03-01T00:00:00Z",
          "end":   "2026-05-31T23:59:59Z"
        }
      },
      "rows": [
        {
          "path": ["Northern Hemisphere", "Spring"],
          "view": {
            "title": "Spring in the Northern Hemisphere",
            "subtitle": "March – May",
            "blocks": [
              {
                "type": "body",
                "label": "Description",
                "format": "text",
                "value": "Days lengthen, temperatures rise, plants leaf out."
              }
            ]
          }
        }
      ]
    }
  ]
}
```

Top-level fields:

- `content` — metadata for this content file (distinct from the map-package
  `package.json` in §1.4).
- `datasets` — ordered array of datasets.

`content` fields:

| Field           | Type   | Purpose |
| --------------- | ------ | ------- |
| `id`            | string | Stable identifier for this content file. |
| `language`      | string | Language identifier such as `en` or `mn`. |
| `defaultLocale` | string | Optional locale identifier such as `en-US` or `mn-MN`. |

### 2.4 Datasets

A dataset groups rows that share the same applicability filter. Every
dataset has:

- `id` — stable identifier.
- `filter` — when this dataset applies (see §2.5).
- `rows` — non-empty ordered array of renderable rows (see §2.6).

Datasets render in declaration order; multiple matching datasets in the same
content file all contribute their rows.

### 2.5 Dataset filters

`filter` controls whether a dataset applies to the current lookup:

```json
"filter": {
  "featureIds": ["country:MN"],
  "when": {
    "start": "2026-07-11T00:00:00+08:00",
    "end":   "2026-07-15T23:59:59+08:00"
  }
}
```

It has two parts: spatial (`featureIds`) and temporal (`when`).

#### `filter.featureIds`

An array of strings matched against the `featureId` property of the selected
GeoJSON feature(s). The dataset applies if any element matches.

```json
{ "featureIds": ["country:MN", "region:MN-073"] }
```

Special value:

- `["*"]` — wildcard, matches any selected feature.

If neither the wildcard nor the matched feature's id appears in
`featureIds`, the dataset is skipped.

#### `filter.when`

`when` is optional. When present, both `start` and `end` are required RFC
3339 date-times:

```json
{
  "when": {
    "start": "2026-07-11T00:00:00+08:00",
    "end":   "2026-07-15T23:59:59+08:00"
  }
}
```

Optional fields:

- `allDay` (boolean) — the window covers full local days.
- `timezone` (string) — IANA timezone identifier (e.g. `Asia/Ulaanbaatar`).

```json
{
  "when": {
    "start":    "2026-07-11T00:00:00+08:00",
    "end":      "2026-07-15T23:59:59+08:00",
    "allDay":   true,
    "timezone": "Asia/Ulaanbaatar"
  }
}
```

To express disjoint windows (e.g. winter as Dec–Feb of every year), emit
multiple datasets that share the same `featureIds`. Datasets without `when`
are always eligible from a time perspective.

#### Default time behavior

The default is **no filter**:

- If the runtime has no active date/time, datasets are not filtered by time.
- If the runtime has an active date/time, `filter.when` decides whether the
  dataset overlaps the selected range.

### 2.6 Rows

Rows are the renderable items inside a dataset. Each row has:

- `path` — full localized browse path shown in the UI (array of strings, in
  parent-to-child order).
- `view` — renderable content (see §2.7).

Optionally, a row may carry its own `filter` to override the dataset-level
filter at row scope.

```json
{
  "path": ["Mongolia", "National Holidays"],
  "view": {
    "title": "Naadam Festival",
    "subtitle": "July 11 – 15",
    "blocks": [
      { "type": "body", "label": "About", "format": "text",
        "value": "Mongolia's largest national holiday: wrestling, horse racing, and archery." }
    ]
  }
}
```

### 2.7 Views

A `view` is the renderable content of a row. Fields:

| Field      | Required | Notes |
| ---------- | -------- | ----- |
| `title`    | yes      | Short heading. |
| `subtitle` | no       | Optional secondary heading. |
| `name`     | no       | Optional short label used in browse lists when distinct from `title`. |
| `blocks`   | yes      | Non-empty ordered array of render blocks (see §2.8). |

Blocks render top-to-bottom and the consumer must preserve their order.

### 2.8 View block types

Six block types are defined. Consumers should silently skip blocks of unknown
types, allowing forward-compatible additions.

#### Labels

Every block type accepts an optional `label` field that the UI renders as a
heading above the block. One exception: for `attributes` blocks the label is
**required** because it heads the items table.

Labels are short, human-readable strings. They are not identifiers.

#### `body` — large text content

```json
{ "type": "body", "label": "Details", "format": "html",
  "value": "<p>The purpose of this law is to regulate ...</p>" }
```

| Field    | Required | Notes |
| -------- | -------- | ----- |
| `type`   | yes      | constant `"body"` |
| `format` | yes      | one of `text`, `html` |
| `value`  | yes      | the string content |
| `label`  | no       | optional heading |

Static offline HTML content is represented as a `body` block with
`format: "html"`.

#### `attributes` — labelled list of label/value pairs

```json
{ "type": "attributes", "label": "Penalties",
  "items": [
    { "label": "Fine Min",  "format": "text", "value": "900000" },
    { "label": "Fine Max",  "format": "text", "value": "10800000" },
    { "label": "Currency",  "format": "text", "value": "Tugrik-MNT" }
  ]
}
```

Each item has `label`, `format` (one of `text`, `html`, `markdown`, `json`),
and `value`. The `label` on the block itself is **required**.

#### `web` — embedded web view

```json
{ "type": "web", "label": "More info",
  "url": "https://wttr.in/<latitude>,<longitude>?0",
  "orientation": "landscape" }
```

| Field         | Required | Notes |
| ------------- | -------- | ----- |
| `type`        | yes      | constant `"web"` |
| `url`         | yes      | absolute URL |
| `label`       | no       | optional heading |
| `orientation` | no       | `portrait` or `landscape`; hint to the embedding container |

The runtime substitutes the tokens `<latitude>` and `<longitude>` in `url`
with the matched point before opening the URL.

#### `image` — embedded image

```json
{ "type": "image", "label": "Photo", "source": "https://example.org/image.jpg" }
```

| Field    | Required | Notes |
| -------- | -------- | ----- |
| `type`   | yes      | constant `"image"` |
| `source` | yes      | image source, typically a URL |
| `label`  | no       | optional heading |

#### `link` — clickable link

```json
{ "type": "link", "label": "Reference",
  "url": "https://example.org/regulation",
  "text": "View full regulation" }
```

| Field   | Required | Notes |
| ------- | -------- | ----- |
| `type`  | yes      | constant `"link"` |
| `url`   | yes      | link target URL |
| `text`  | yes      | visible link text |
| `label` | no       | optional heading |

#### `notice` — highlighted callout

```json
{ "type": "notice", "label": "Important", "tone": "restriction",
  "text": "Hunting is prohibited in this zone." }
```

| Field   | Required | Notes |
| ------- | -------- | ----- |
| `type`  | yes      | constant `"notice"` |
| `tone`  | yes      | one of `note`, `important`, `caution`, `restriction` |
| `text`  | yes      | notice text |
| `label` | no       | optional heading |

### 2.9 Runtime lookup flow

A typical lookup against an active package proceeds as:

1. Identify layers whose `layers.json` entries have `lookup: true`.
2. For each such layer, locate the lookup geometry and `<basename>.json`.
   The geometry is `<basename>.shp` if present, otherwise
   `<basename>.geojson`.
3. Run the point-in-polygon test against the geometry (§2.2). For a
   shapefile only records whose bounding box contains the point are read.
4. Collect each selected feature's id: `properties.featureId` for GeoJSON,
   or the `featureId` column of the `.dbf` row for a shapefile.
5. Load the companion content JSON.
6. Evaluate every dataset's `filter.featureIds` against the selected ids.
7. If the runtime has an active date/time filter, evaluate `filter.when`.
8. Render the matching rows in declaration order.

---

## 3. End-to-end example

A minimal one-feature world weather package illustrates every moving part.

### 3.1 `package.json`

```json
{
  "id": "WeatherDemo",
  "name": "Weather Demo",
  "version": "2026.04.21",
  "language": "en"
}
```

### 3.2 `layers.json`

```json
[
  {
    "filename": "weather.geojson",
    "name": "Weather",
    "active": true,
    "opacity": 0.0,
    "lookup": true
  }
]
```

### 3.3 `weather.geojson`

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": { "featureId": "world" },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[
          [-180.0, -90.0], [180.0, -90.0], [180.0, 90.0], [-180.0, 90.0], [-180.0, -90.0]
        ]]
      }
    }
  ]
}
```

### 3.4 `weather.json`

```json
{
  "content": {
    "id": "weather-en",
    "language": "en",
    "defaultLocale": "en-US"
  },
  "datasets": [
    {
      "id": "world-weather",
      "filter": { "featureIds": ["world"] },
      "rows": [
        {
          "path": ["Weather"],
          "view": {
            "title": "Local weather",
            "subtitle": "wttr.in",
            "blocks": [
              {
                "type": "notice", "label": "Note", "tone": "note",
                "text": "Open the embedded view for live conditions at the tapped location."
              },
              {
                "type": "web",
                "url": "https://wttr.in/<latitude>,<longitude>?0",
                "orientation": "portrait"
              }
            ]
          }
        }
      ]
    }
  ]
}
```

This example uses a single world polygon and a single content dataset. More
specific packages use many features, many datasets, and time-scoped content
— see [demos/seasons/](demos/seasons/), [demos/holidays/](demos/holidays/),
and [legal_atlas/new_format_data/](legal_atlas/new_format_data/) for
progressively richer examples.
