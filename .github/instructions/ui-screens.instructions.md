---
description: "Read before creating or changing any KeyTune screen: dialog, panel, tab, preferences page or group of controls. Rules for labels, groups, help text, layout and the audit that verifies them."
name: "Building Screens"
applyTo:
  - "src/player/**/*dialog*.py"
  - "src/player/**/*panel*.py"
  - "src/player/widgets.py"
  - "src/player/reading_dialog.py"
  - "src/player/frames/ui.py"
  - "scripts/audit_ui_accessibility.py"
---
# Building screens

KeyTune is used with a screen reader. A screen can look finished and still be
unusable, because what the reader announces does not come from what the code
*says* (`SetName`, a caption drawn nearby) but from what Windows exposes through
MSAA. Every rule below was a real bug found by measuring that, not a matter of
taste. General behavior rules (focus, shortcuts, announcements) stay in
[player-ui-a11y.instructions](player-ui-a11y.instructions.md).

## Finish with the audit

```
uv run python scripts/audit_ui_accessibility.py
```

It builds every screen and asks Windows for the accessible name of each control.
It must pass before a screen change is done. Add `-v` to print every name and
description and **read them**: the audit cannot tell that a name is wrong, only
that it is missing (a list once passed while being named by a whole intro
sentence).

A new `wx.Dialog` or `wx.Panel` subclass must be added to `SCREENS` in that
script; the audit fails until it is. `tests/test_ui_accessibility_audit.py` runs
the same audit with the test suite.

## Rules

### 1. Every input has a visible label, created immediately before it

For edits, lists and choices Windows takes the name from the static text that
comes right before the control in creation (z) order — not sizer order, and not
`SetName`, which by itself reaches the screen reader as nothing.

```python
label = wx.StaticText(parent, label=_("Nome do preset:"))
self.name_ctrl = wx.TextCtrl(parent)          # created right after its label
```

- Do not create anything between a label and its control.
- Do not let an intro paragraph be the last static text before a list: it
  becomes the list's name.
- Read-only text (details, comments, logs, help) follows the same rule, and is
  always built by `reading_dialog`: `create_reading_field` (the field alone),
  `add_reading_field` (label + field) or `show_reading_dialog`; from a frame,
  `self._show_reading_dialog(...)`. Never a bare `wx.TextCtrl(...TE_READONLY)`:
  the standard field does not wrap, so each arrow press reads a whole line of
  the text instead of the fragment that fit the window, and the audit rejects
  one that wraps. Never `wx.MessageBox` for item details.

### 2. Number fields and label-less controls need an explicit name

`wx.SpinCtrl` is a composite and does **not** inherit the label next to it. The
same goes for any control with no label directly before it (a list under a
toolbar, a status text that must be read as "name: value").

```python
attach_named_accessible(self.limit_ctrl, name=_("Número máximo de itens"))
# or, with help text:
describe_control(control, _("Volume padrão"), _("Volume ao abrir o player."))
```

`wx.SpinCtrlDouble` cannot be named at all (wx wraps it in a window that hides
the name). Speak "label: value" on focus and on change instead, as
`equalizer/dialog.py` does.

### 3. A group is real only if its controls are its children

A `wx.StaticBox` announces its name when focus enters it only when the controls
are created **with the box as parent**. With the box as a sibling it is just a
drawing, and wx itself logs a warning.

```python
box, sizer = create_group(page, _("Critérios"))     # widgets.create_group
self.favorites_checkbox = wx.CheckBox(box, label=_("Somente &favoritos"))
sizer.Add(self.favorites_checkbox, 0, wx.ALL | wx.EXPAND, ROW_BORDER)
```

Controls added later (rows built on demand) also take the box as parent — keep
a reference to it.

- Group related options under a short noun title ("Volume", "Idioma e região").
  No loose controls next to groups on the same page.
- Do not put a box around a single control whose label already says the same.

### 4. Help text is a description, not a paragraph on the screen

- A tooltip alone is mouse-only. Help goes through `describe_control`, which
  sets tooltip, help text and accessible description together.
- Keep it to one short sentence: the reader speaks it every time the control
  gets focus. No restating the label, no "Escolha…/Selecione…".
- Avoid visible help paragraphs inside a form; they are read in full when the
  dialog opens. One short intro line at the top is the limit.
- Frequently focused controls on main tabs (search fields, lists) get a name
  only, no description.

### 5. Where an option lives

- A page that grows past one screen is split into tabs, not compressed.
- Preferences: feature tabs (KeyTube, Rádios online, Download…) hold options for
  *using* the feature; "Recursos adicionais" holds only what is downloaded or
  enabled. The app and the manual send users to "Preferências > Recursos
  adicionais" for components — keep that true.
- Options are disabled, never hidden, when they do not apply; announce the
  change through `_announce`.

### 6. Layout

- Short controls (choice, number) go on one row: label left, control right —
  `add_choice_row`, or `add_labeled_row` for a control you created. Long
  controls (text, folder, list) go under their label.
- Call `equalize_row_controls(root)` once the form is built so the right-hand
  column has one width.
- Sizes go through `FromDIP`; the screen may be at 125% or more. A notebook
  with many tabs uses `wx.NB_MULTILINE`; long pages are `wx.ScrolledWindow`.
- Use `ROW_BORDER` between rows of a group instead of ad-hoc numbers.

### 7. Keyboard

- Tab order is creation order: create controls in reading order.
- Every dialog closes with Esc (`SetEscapeId`), and has a default button where
  Enter should confirm.
- Mnemonics (`&`) must be unique within the dialog, including the standard
  buttons.
- Do not move focus on open, tab switch or refresh beyond the dialog's natural
  first control.

### 8. Text

Portuguese, wrapped in `_()`. After changing strings run
`python scripts/i18n.py extract` then `compile` (see
[i18n.instructions](i18n.instructions.md)), and update `docs/manual.md` when an
option moves or is renamed.

## Helpers

| Need | Use |
| --- | --- |
| Group with a real box | `widgets.create_group(parent, label)` |
| Name + help on a control | `widgets.describe_control(control, name, help_text)` |
| Name only | `accessibility.attach_named_accessible(control, name=...)` |
| Label + choice on a row | `widgets.add_choice_row(...)` |
| Label + any control on a row | `widgets.add_labeled_row(sizer, label, control)` |
| Folder field with button | `widgets.add_directory_row(...)` |
| Uniform right column | `widgets.equalize_row_controls(root)` |
| Read-only text | `reading_dialog.create_reading_field` / `add_reading_field` / `show_reading_dialog` |

`preferences/dialog.py` and `smart_library/smart_playlist_dialog.py` are the
reference forms.

## Before calling a screen done

1. `uv run python scripts/audit_ui_accessibility.py -v` passes and the names
   read well.
2. Walk the screen with Tab and Shift+Tab; order matches the visual order.
3. Look at it at 125% scaling: nothing cut off, right column aligned.
4. With NVDA when possible: entering each group announces its title; each field
   announces label, type, value and its short description.
5. `python -m compileall src` and `python -m unittest discover -s tests`.

## Why these rules hold

- Windows names an edit or list from the static text immediately before it in
  z-order, and stops searching at the first one it finds:
  <https://learn.microsoft.com/en-us/windows/win32/winauto/ensure-that-ui-elements-are-named-correctly>
- Since wxWidgets 2.9.1, windows inside a `wxStaticBoxSizer` should be children
  of the `wxStaticBox`; siblings trigger a debug warning:
  <https://docs.wxwidgets.org/3.3/classwx_static_box_sizer.html>
- `wxSpinCtrlDouble` exposing no label to screen readers is a known wx
  limitation: <https://groups.google.com/g/wx-dev/c/nEaCaK6vHZU>
