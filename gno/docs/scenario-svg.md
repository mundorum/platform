# gnō Scenario SVG

This document describes the SVG files that hold the graphic design of a
narrative's scenarios, in version 1.1 of the gnō language: every element the
files contain, what it is for, how it is written, and examples. A scenario
SVG is a standard SVG file, which any browser or SVG viewer can open; gnō
extends it with `data-gno-*` attributes and with IDs that have a role in the
Player.

The editor writes these files from **Presentation → Scenarios**, so authors
rarely need to read them. This document is for those who read them,
generate them with other tools, or edit them by hand. What the Player does
with a design is described in the [README](../README.md#graphic-play); how to
build one in the editor, in the [scenario tutorial](scenario-tutorial.md);
the syntax of the narrative text, in the [syntax reference](syntax.md).

- [Notation](#notation)
- [The file in the package](#the-file-in-the-package)
- [Canvas](#canvas)
- [Background](#background)
- [Items](#items): [entity image](#entity-image), [anchor](#anchor), [text area](#text-area), [stack](#stack), [group](#group)
- [Role IDs](#role-ids): [anchors](#anchor-ids), [controls](#controls), [speech](#speech), [subscene places](#subscene-places), [pairs](#pairs)
- [What is hidden](#what-is-hidden)
- [How a file is read](#how-a-file-is-read)
- [Grammar at a glance](#grammar-at-a-glance)
- [Complete example](#complete-example)

## Notation

The grammar uses the same minimal subset of Extended BNF as the
[syntax reference](syntax.md#notation):

| Notation | Meaning |
|---|---|
| `a = …` | the rule that defines `a` |
| `"…"` | written exactly as shown |
| `a b` | `a` followed by `b` |
| `a \| b` | either `a` or `b` |
| `[ a ]` | `a` is optional |
| `{ a }` | `a` repeated zero or more times |
| `<…>` | a description in words, where a rule would say less than the words do |

Two conventions are added for XML:

- `name=value` stands for the attribute `name="value"`: the rule `value`
  gives what goes between the quotes. `name=""` is an attribute whose value
  is empty, which marks the kind of an element.
- Attributes can be written in any order, and spaces between them are
  free, as in any XML file.

Each rule comes with a concrete example on the line below it, marked `▸`:

```text
anchor = "<g" id=anchor-id data-gno-anchor=anchor-id size translate ">" "</g>"
         ▸ <g id="left" data-gno-anchor="left" data-gno-width="180" data-gno-height="320" transform="translate(180,330)"></g>
```

Each structure is then shown in use, as it is written in a file.

## The file in the package

Each scenario with a design has one SVG file. In a downloaded zip, the files
are in the `scene/` folder, named after their scenario: the name in lower
case, without accents, with every run of other characters written as `_`
(`Sala de Exames` → `scene/sala_de_exames.svg`). If two scenario names come
out the same, the second file gets `_2`, the next `_3`, and so on.

The presentation YAML lists the files under `scenarios`, from the scenario
name to its file. A scenario missing from this list has no design and plays
as text.

```yaml
scenarios:
  Hospital: scene/hospital.svg
  Radiology: scene/radiology.svg
```

The SVG files carry no version: the version of the whole package is in its
manifest (see the [README](../README.md#versions)).

## Canvas

The root `<svg>` element sets the size of the scenario's stage, in pixels.
Everything in the design is placed in that coordinate system, with the
origin at the top-left corner.

```text
scenario-svg = "<svg" namespaces width=number height=number viewBox=view-box ">"
               [ background ] { item } "</svg>"
               ▸ <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="960" height="540" viewBox="0 0 960 540">
namespaces   = xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
               ▸ xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
view-box     = "0 0 " number " " number
               ▸ 0 0 960 540
number       = [ "-" ] <digits> [ "." <digits> ]
               ▸ 960
```

- `width` and `height` give the size of the stage; `viewBox` repeats them.
  Without a size, the stage is 960 × 540.
- The items are direct children of `<svg>`, never nested in each other.
  [Stacks](#stack) and [groups](#group) list the items they hold by ID
  instead of containing them.
- The order of the elements in the file is the drawing order: each element
  is drawn over the ones before it.

## Background

The background is the image behind the whole scenario: a room, a landscape,
a hospital corridor. It covers the stage, cropped to fill it.

```text
background = "<image" id="background" "x=" "0" "y=" "0" width=number height=number
             href=url xlink:href=url preserveAspectRatio="xMidYMid slice"
             data-gno-library=library-id data-gno-image=image-id "/>"
             ▸ <image id="background" x="0" y="0" width="960" height="540" href="https://example.org/hospital/emergency-room.jpg" xlink:href="https://example.org/hospital/emergency-room.jpg" preserveAspectRatio="xMidYMid slice" data-gno-library="hospital" data-gno-image="emergency-room" />
library-id = <the ID of an image library in the presentation YAML>
             ▸ hospital
image-id   = <the ID of an image in that library>
             ▸ emergency-room
```

- The ID `background` is reserved for it: an `<image>` with this ID is the
  background, wherever it is in the file.
- `href` is the image's address. `xlink:href` repeats it for viewers that
  only know the SVG 1.1 form; the editor reads `href`.
- `data-gno-library` and `data-gno-image` say which image of which library
  (**Presentation → Image libraries**) the background came from.
- `width` and `height` are those of the canvas.

## Items

Items are what the design places on the stage. There are five kinds, each
written with its own element:

```text
item = entity-image | anchor | text-area | stack | group
       ▸ <g id="left" data-gno-anchor="left" data-gno-width="180" data-gno-height="320" transform="translate(180,330)"></g>
```

Every item has an `id`, unique in the file. An ID either just names the item
or gives it a [role](#role-ids) in the Player. Positions and sizes are in
pixels of the canvas.

### Entity image

An entity image is a picture placed on the design: furniture, a prop, a
speech bubble, a button. It is called an entity image because it is one of
the images of an entity in **Presentation → Entity**, often an entity
declared for the design only (`@bubble`, `@button`). It is always shown,
unless its ID gives it a role that hides it at times (see
[What is hidden](#what-is-hidden)).

```text
entity-image = "<image" id=item-id x=number y=number width=number height=number
               href=url xlink:href=url
               data-gno-entity=entity data-gno-library=library-id data-gno-image=image-id "/>"
               ▸ <image id="stretcher" x="600" y="380" width="240" height="120" href="https://example.org/hospital/stretcher.png" xlink:href="https://example.org/hospital/stretcher.png" data-gno-entity="@stretcher" data-gno-library="hospital" data-gno-image="stretcher" />
entity       = <an entity as written in the narrative, with its "@">
               ▸ @stretcher
```

- `x` and `y` are its top-left corner.
- `data-gno-entity` names the entity the image belongs to; with
  `data-gno-library` and `data-gno-image`, it lets the editor find the image
  again.
- The entities of the narrative are **not** entity images: they enter and
  leave the stage at [anchors](#anchor), as the narrative says. An entity
  image is part of the design, and stays where it is placed.

### Anchor

An anchor is a place on the stage where the narrative's entities stand: the
left of the room, the bed, the doorway. An entity whose state words name an
anchor stands there, its image fitted into the anchor's box (see
[Anchor IDs](#anchor-ids)). The anchor itself draws nothing.

```text
anchor    = "<g" id=anchor-id data-gno-anchor=anchor-id size translate ">" "</g>"
            ▸ <g id="left" data-gno-anchor="left" data-gno-width="180" data-gno-height="320" transform="translate(180,330)"></g>
size      = data-gno-width=number data-gno-height=number
            ▸ data-gno-width="180" data-gno-height="320"
translate = transform="translate(" number "," number ")"
            ▸ transform="translate(180,330)"
```

- `data-gno-anchor` marks the element as an anchor and repeats its ID.
- `translate` gives the **center** of the anchor's box, and `size` its
  width and height. Without a size, the box is 36 × 36.
- The `<g>` is empty: the image the editor shows while placing an anchor is
  only an aid, and is not written.

### Text area

A text area is a box of text on the stage. It can hold fixed text (a title,
a sign), or, depending on its ID, the narrative's speech, the label of a
choice, or the label of a control (see [Role IDs](#role-ids)). It is a
`<foreignObject>` holding an XHTML `<div>`, since SVG text can't wrap long
lines by itself.

```text
text-area = "<foreignObject" id=text-id x=number y=number width=number height=number
            data-gno-text="" data-gno-font=font data-gno-font-size=number data-gno-color=color ">"
            text-div "</foreignObject>"
            ▸ <foreignObject id="speech_text" x="60" y="395" width="560" height="90" data-gno-text="" data-gno-font="Lora, Georgia, serif" data-gno-font-size="18" data-gno-color="#1a1610">
text-id   = role-or-name "_text"
            ▸ speech_text
text-div  = "<div" xmlns="http://www.w3.org/1999/xhtml" style=css ">" <plain text> "</div>"
            ▸ <div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Lora, Georgia, serif;font-size:18px;color:#1a1610;">Text</div>
font      = <a CSS font-family list>
            ▸ Outfit, Arial, sans-serif
color     = "#" <six hexadecimal digits>
            ▸ #7a3e1a
```

- `data-gno-text` marks the element as a text area.
- The ID of a text area always ends in `_text`. The rest of it, the ID the
  editor shows, is the one that gives the area its role (`speech_text` is
  the area of `speech`); see [Pairs](#pairs).
- `x` and `y` are its top-left corner.
- The `<div>` holds the area's own text, as plain text. Its `style` writes
  the font, size and color as CSS, so that other viewers show them; the
  editor reads them from the `data-gno-*` attributes instead.
- The font size is between 6 and 300. A font or color the editor can't
  accept is replaced by the default: Lora, 18, `#1a1610`.

### Stack

A stack places items in a line, the way a CSS flexbox does: a vertical
stack lines them up from top to bottom, a horizontal one from left to
right. Items keep their own size; the stack decides where they go. Items
hidden at the current pause take no room, so the others close up: speech
stacked above the choices moves down when no choices are on offer.

```text
stack     = "<g" id=item-id data-gno-layout=direction data-gno-justify=justify
            data-gno-align=align data-gno-gap=number data-gno-children=item-ids
            size translate ">" "</g>"
            ▸ <g id="talk" data-gno-layout="column" data-gno-justify="end" data-gno-align="start" data-gno-gap="8" data-gno-children="bubble action_1_text action_2_text" data-gno-width="640" data-gno-height="500" transform="translate(20,20)"></g>
direction = "column" | "row"
            ▸ column
justify   = "start" | "center" | "end" | "space-between"
            ▸ end
align     = "start" | "center" | "end"
            ▸ start
item-ids  = item-id { " " item-id }
            ▸ bubble action_1_text action_2_text
```

- `data-gno-layout` marks the element as a stack and gives its direction:
  `column` (top to bottom) or `row` (left to right).
- `data-gno-justify` places the line of items along the direction: at the
  start, the center or the end of the stack's box, or spread out over it
  (`space-between`).
- `data-gno-align` places each item across the direction: at the start
  (left, or top), the center or the end.
- `data-gno-gap` is the space between two items, from 0 to 1000.
- `data-gno-children` lists the IDs of the items in the stack, in the order
  they are placed. They can be stacks or groups themselves.
- `translate` gives the **top-left corner** of the stack's box, and `size`
  its width and height.
- A stack with no visible item is hidden too. Its defaults are `start`,
  `start`, a gap of 8, and a box of 200 × 200.

### Group

A group keeps items together exactly where they were placed, such as a
speech area over the bubble image behind it. A group has no area of its
own: it moves as one, and a stack places it as any other item, its items
following along. A group is hidden when all the items in it that can be
hidden are, and its plain images go with it: the bubble shows only while
there is speech.

```text
group = "<g" id=item-id data-gno-group="" data-gno-children=item-ids size translate ">" "</g>"
        ▸ <g id="bubble" data-gno-group="" data-gno-children="speech speech_text" data-gno-width="600" data-gno-height="120" transform="translate(40,380)"></g>
```

- `data-gno-group` marks the element as a group.
- `data-gno-children` lists the IDs of the items in the group, from back to
  front, in their drawing order.
- `translate` and `size` give the box around the group's items (its
  top-left corner, then its size), which the editor keeps up to date. The
  items keep their own positions in the file; when a stack moves the group,
  they move by the same amount.
- A group holding only plain images is always shown.

## Role IDs

The ID of an item can give it a part in the Player: where entities stand,
which buttons continue, go back and choose, where speech is shown, where a
subscene opens. Role IDs are compared ignoring case and accents. An item
whose ID has no role is shown as it is, all the time.

```text
role-id      = anchor-id | control-id | speech-id | subscene-id
               ▸ action_1
role-or-name = role-id | item-id
               ▸ speech
item-id      = <a name without spaces, unique in the file>
               ▸ stretcher
```

### Anchor IDs

An anchor's ID is the word the narrative uses to place an entity there. Of
the state words written after an entity, those that don't choose its image
are compared with the anchors' IDs, and the first that names one says where
the entity stands.

```text
anchor-id = <a name without spaces>
            ▸ left
```

With anchors `left`, `middle` and `right`, the line `@Lucinda left concerned`
places Lucinda at `left`, in her `concerned` image if she has one.

### Controls

Controls are the items the reader clicks to move through the narrative.
Each can be an entity image, a text area, or both (a [pair](#pairs)).

```text
control-id = "action_proceed" | "action_regress" | "action_" choice-number
             ▸ action_2
choice-number = <a whole number from 1>
             ▸ 2
```

| ID | Shown | Does |
|---|---|---|
| `action_proceed` | while the scene is paused | continues to the next beat; a text area shows its own text ("Continue") |
| `action_regress` | once past the first beat; always in a subscene | goes back one beat; in a subscene, closes it; a text area shows its own text ("Back") |
| `action_N` | while choice N is on offer | takes the Nth choice of the scene (`* Label -> Target`); a text area shows the choice's label |

When the design lacks a control, the Player shows its own button in its
place, so a scene can never get stuck.

### Speech

Speech areas are the text areas where the narrative's text is shown, beat
by beat. An entity image with the same ID (a speech bubble) is shown only
while its area has something to show.

```text
speech-id = [ speaker "." ] "speech"
            ▸ Lucinda.speech
speaker   = "_" | <an entity's name, without "@">
            ▸ Lucinda
```

| Text | Goes to | Otherwise to |
|---|---|---|
| Text outside dialogs | `_.speech` | `speech` |
| A dialog of `@Lucinda` | `Lucinda.speech` | `speech` |
| A dialog of the group `@Lucinda + @Jacinto` | `speech` | the area of its first member (`Lucinda.speech`) |

In a shared area (`speech`, and always for a group), each dialog starts with
the speaker's name. Text with no area to go to is not shown.

### Subscene places

A subscene place is where a subscene (`~>`) opens over this scenario's
stage. The subscene is fitted into the place's box, keeping its proportion,
and centered in it.

```text
subscene-id   = "subscene" [ "." scenario-name ]
                ▸ subscene.radiology
scenario-name = <a scenario's name, with "_" for each space>
                ▸ sala_de_exames
```

- `subscene.<scenario>` places the subscenes of that scenario; plain
  `subscene` places any other subscene.
- A text area or an anchor with this ID is an invisible box: it takes room
  in a stack while its subscene is open, and draws nothing. An empty text
  area is the usual way to draw one.
- An entity image with this ID is a frame: it is shown only while that
  subscene is open, such as a border or a shadow around it. When a box and a
  frame share the ID, the box places the subscene.
- Without a place, the subscene is centered at the size of its own design,
  scaled down if it doesn't fit.

### Pairs

A text area and an entity image can share an ID, and then play the same
role together: the text area shows the text, the entity image is its
picture (a button, a speech bubble). Since every `id` in an SVG file must be
unique, the text area's `id` carries the suffix `_text`:

| Role | Entity image `id` | Text area `id` |
|---|---|---|
| choice 1 | `action_1` | `action_1_text` |
| continue | `action_proceed` | `action_proceed_text` |
| speech | `speech` | `speech_text` |
| a subscene box and its frame | `subscene.radiology` | `subscene.radiology_text` |

A text area without a partner still carries the suffix: an area named
`title` in the editor is `title_text` in the file.

## What is hidden

At each beat, the Player shows the design's items, hiding those with nothing
to do at that moment. A hidden item takes no room in a stack.

| Item | Hidden while |
|---|---|
| speech area | it has no text at this beat |
| speech bubble (entity image with a speech ID) | its speech area has no text |
| `action_N` | choice N is not on offer |
| `action_proceed` | the scene is not paused (its choices are on offer, or it ended) |
| `action_regress` | at the scene's first beat, outside a subscene |
| anchor | no entity stands on it |
| subscene place (box or frame) | its subscene is not open |
| stack | none of its items is shown |
| group | none of its items that can be hidden is shown; its plain images go with it |
| any other entity image or text area | never |

## How a file is read

When a package is opened, the editor rebuilds each design from its SVG file.
These rules matter when a file is written or edited by other tools:

- Only the direct children of `<svg>` are read. An element is an item only
  when it is one of the forms above: an `<image>`, a `<g>` with
  `data-gno-anchor`, `data-gno-layout` or `data-gno-group`, or a
  `<foreignObject>` with `data-gno-text`. Any other element is ignored, and
  is not written back when the narrative is saved.
- Of an image's address, `href` is read; `xlink:href` is not.
- Of a text area, the text is read from its `<div>`, as plain text, and the
  font, size and color from its `data-gno-*` attributes, not from its
  `style`.
- An ID listed in `data-gno-children` that names no item is skipped. A
  stack or group that ends up containing itself is hidden.
- Missing sizes take defaults: 80 × 80 for an entity image, 36 × 36 for an
  anchor, 200 × 80 for a text area, 200 × 200 for a stack.

## Grammar at a glance

```text
scenario-svg  = "<svg" namespaces width=number height=number viewBox=view-box ">"
                [ background ] { item } "</svg>"
namespaces    = xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
view-box      = "0 0 " number " " number
number        = [ "-" ] <digits> [ "." <digits> ]

background    = "<image" id="background" "x=" "0" "y=" "0" width=number height=number
                href=url xlink:href=url preserveAspectRatio="xMidYMid slice"
                data-gno-library=library-id data-gno-image=image-id "/>"
library-id    = <the ID of an image library in the presentation YAML>
image-id      = <the ID of an image in that library>

item          = entity-image | anchor | text-area | stack | group

entity-image  = "<image" id=item-id x=number y=number width=number height=number
                href=url xlink:href=url
                data-gno-entity=entity data-gno-library=library-id data-gno-image=image-id "/>"
entity        = <an entity as written in the narrative, with its "@">

anchor        = "<g" id=anchor-id data-gno-anchor=anchor-id size translate ">" "</g>"
size          = data-gno-width=number data-gno-height=number
translate     = transform="translate(" number "," number ")"

text-area     = "<foreignObject" id=text-id x=number y=number width=number height=number
                data-gno-text="" data-gno-font=font data-gno-font-size=number data-gno-color=color ">"
                text-div "</foreignObject>"
text-id       = role-or-name "_text"
text-div      = "<div" xmlns="http://www.w3.org/1999/xhtml" style=css ">" <plain text> "</div>"
font          = <a CSS font-family list>
color         = "#" <six hexadecimal digits>

stack         = "<g" id=item-id data-gno-layout=direction data-gno-justify=justify
                data-gno-align=align data-gno-gap=number data-gno-children=item-ids
                size translate ">" "</g>"
direction     = "column" | "row"
justify       = "start" | "center" | "end" | "space-between"
align         = "start" | "center" | "end"
item-ids      = item-id { " " item-id }

group         = "<g" id=item-id data-gno-group="" data-gno-children=item-ids size translate ">" "</g>"

role-id       = anchor-id | control-id | speech-id | subscene-id
role-or-name  = role-id | item-id
item-id       = <a name without spaces, unique in the file>
anchor-id     = <a name without spaces>
control-id    = "action_proceed" | "action_regress" | "action_" choice-number
choice-number = <a whole number from 1>
speech-id     = [ speaker "." ] "speech"
speaker       = "_" | <an entity's name, without "@">
subscene-id   = "subscene" [ "." scenario-name ]
scenario-name = <a scenario's name, with "_" for each space>
```

| Attribute | On | Meaning |
|---|---|---|
| `data-gno-library`, `data-gno-image` | background, entity image | the library and image it came from |
| `data-gno-entity` | entity image | the entity the image belongs to |
| `data-gno-anchor` | `<g>` | marks an anchor; repeats its ID |
| `data-gno-text` | `<foreignObject>` | marks a text area |
| `data-gno-font`, `data-gno-font-size`, `data-gno-color` | text area | its font, size and color |
| `data-gno-layout` | `<g>` | marks a stack; its direction |
| `data-gno-justify`, `data-gno-align`, `data-gno-gap` | stack | how it places its items |
| `data-gno-group` | `<g>` | marks a group |
| `data-gno-children` | stack, group | the IDs of the items it holds |
| `data-gno-width`, `data-gno-height` | anchor, stack, group | the size of its box |

## Complete example

A design for the `Hospital` scenario of the complete example in the
[syntax reference](syntax.md#complete-example), in `scene/hospital.svg`:

- three anchors, `left`, `middle` and `right`, where the entities stand;
- a stretcher, always shown;
- a speech bubble: the `speech` text area over the `speech` bubble image,
  in the group `bubble`;
- the labels of choices 1 and 2;
- a vertical stack, `talk`, holding the bubble and the choices, aligned at
  the bottom: the bubble sits at the bottom of the stage and moves up when
  the choices appear;
- a continue button, `action_proceed`, and a back button made of text,
  `action_regress`;
- a place for subscenes of the `Radiology` scenario, with a frame, and one
  for any other subscene.

```xml
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="960" height="540" viewBox="0 0 960 540">
  <image id="background" x="0" y="0" width="960" height="540" href="https://example.org/hospital/emergency-room.jpg" xlink:href="https://example.org/hospital/emergency-room.jpg" preserveAspectRatio="xMidYMid slice" data-gno-library="hospital" data-gno-image="emergency-room" />
  <image id="stretcher" x="600" y="380" width="240" height="120" href="https://example.org/hospital/stretcher.png" xlink:href="https://example.org/hospital/stretcher.png" data-gno-entity="@stretcher" data-gno-library="hospital" data-gno-image="stretcher" />
  <g id="left" data-gno-anchor="left" data-gno-width="180" data-gno-height="320" transform="translate(180,330)"></g>
  <g id="middle" data-gno-anchor="middle" data-gno-width="180" data-gno-height="320" transform="translate(480,330)"></g>
  <g id="right" data-gno-anchor="right" data-gno-width="180" data-gno-height="320" transform="translate(780,330)"></g>
  <image id="speech" x="40" y="380" width="600" height="120" href="https://example.org/ui/bubble.png" xlink:href="https://example.org/ui/bubble.png" data-gno-entity="@bubble" data-gno-library="ui" data-gno-image="bubble" />
  <foreignObject id="speech_text" x="60" y="395" width="560" height="90" data-gno-text="" data-gno-font="Lora, Georgia, serif" data-gno-font-size="18" data-gno-color="#1a1610">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Lora, Georgia, serif;font-size:18px;color:#1a1610;width:100%;height:100%;box-sizing:border-box;overflow:hidden;line-height:1.3;white-space:pre-wrap;overflow-wrap:anywhere;">Text</div>
  </foreignObject>
  <g id="bubble" data-gno-group="" data-gno-children="speech speech_text" data-gno-width="600" data-gno-height="120" transform="translate(40,380)"></g>
  <foreignObject id="action_1_text" x="40" y="0" width="600" height="40" data-gno-text="" data-gno-font="Outfit, Arial, sans-serif" data-gno-font-size="18" data-gno-color="#7a3e1a">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Outfit, Arial, sans-serif;font-size:18px;color:#7a3e1a;width:100%;height:100%;box-sizing:border-box;overflow:hidden;line-height:1.3;white-space:pre-wrap;overflow-wrap:anywhere;">Choice 1</div>
  </foreignObject>
  <foreignObject id="action_2_text" x="40" y="48" width="600" height="40" data-gno-text="" data-gno-font="Outfit, Arial, sans-serif" data-gno-font-size="18" data-gno-color="#7a3e1a">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Outfit, Arial, sans-serif;font-size:18px;color:#7a3e1a;width:100%;height:100%;box-sizing:border-box;overflow:hidden;line-height:1.3;white-space:pre-wrap;overflow-wrap:anywhere;">Choice 2</div>
  </foreignObject>
  <g id="talk" data-gno-layout="column" data-gno-justify="end" data-gno-align="start" data-gno-gap="8" data-gno-children="bubble action_1_text action_2_text" data-gno-width="640" data-gno-height="500" transform="translate(20,20)"></g>
  <image id="action_proceed" x="880" y="460" width="56" height="56" href="https://example.org/ui/next.png" xlink:href="https://example.org/ui/next.png" data-gno-entity="@button" data-gno-library="ui" data-gno-image="next" />
  <foreignObject id="action_regress_text" x="800" y="470" width="70" height="36" data-gno-text="" data-gno-font="Outfit, Arial, sans-serif" data-gno-font-size="16" data-gno-color="#6b6050">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Outfit, Arial, sans-serif;font-size:16px;color:#6b6050;width:100%;height:100%;box-sizing:border-box;overflow:hidden;line-height:1.3;white-space:pre-wrap;overflow-wrap:anywhere;">Back</div>
  </foreignObject>
  <image id="subscene.radiology" x="660" y="20" width="280" height="180" href="https://example.org/ui/lightbox-frame.png" xlink:href="https://example.org/ui/lightbox-frame.png" data-gno-entity="@frame" data-gno-library="ui" data-gno-image="lightbox-frame" />
  <foreignObject id="subscene.radiology_text" x="672" y="32" width="256" height="156" data-gno-text="" data-gno-font="Lora, Georgia, serif" data-gno-font-size="18" data-gno-color="#1a1610">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Lora, Georgia, serif;font-size:18px;color:#1a1610;width:100%;height:100%;box-sizing:border-box;overflow:hidden;line-height:1.3;white-space:pre-wrap;overflow-wrap:anywhere;"></div>
  </foreignObject>
  <g id="subscene" data-gno-anchor="subscene" data-gno-width="720" data-gno-height="405" transform="translate(480,270)"></g>
</svg>
```

Played with the `Emergency Room` scene of that example:

- `@Lucinda left concerned` places Lucinda at the `left` anchor, and
  `-- @patient right pale: …` places the patient at `right`.
- The text and the dialogs go to `speech_text`: the scenario has no
  `_.speech` or `Lucinda.speech` area. Since the area is shared, each
  dialog starts with the speaker's name. The bubble shows while there is
  speech.
- At the end of the scene, `action_1_text` and `action_2_text` show
  "Examine the patient" and "Read the triage notes". The `talk` stack moves
  the bubble up above them.
- The entity divert `@xray_film middle ~> X-Ray` opens the `X-Ray` scene,
  of the `Radiology` scenario, in the box of `subscene.radiology_text`, with
  the lightbox frame around it. The choice `Read the triage notes` opens
  `Triage Notes`, of the `Hospital` scenario, at the plain `subscene`
  anchor.
