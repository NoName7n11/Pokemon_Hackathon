**Design QA — catalog-confined card inspector**

- Source visual truth: the latest deck-builder screenshot attached in the user
  conversation; its attachment path is not exposed as a local file.
- Implementation: `deck_builder/index.html`.
- Intended viewport: desktop, approximately 1919 x 991 based on the supplied
  reference.
- State: a card is expanded over only the center Card Catalog while the filter
  panel and current deck panel remain visible.
- Source pixel dimensions: 1919 x 991.
- Implementation screenshot: unavailable.
- Density normalization: not performed because no browser-rendered implementation
  capture could be produced.

**Findings**

- [P1] Rendered containment and viewport proportions could not be verified.
  Location: catalog-confined focus overlay.
  Evidence: the integrated browser runtime failed during initialization, so the
  implementation could not be captured and compared side by side with the source.
  Impact: static inspection confirms the overlay is positioned inside the catalog,
  but it cannot prove final card scale, control placement, or clipping in a real
  browser.
  Fix: capture the expanded-card state at the source viewport in a functioning
  browser and correct any remaining P1/P2 differences.

**Required Fidelity Surfaces**

- Fonts and typography: the existing builder typography is preserved; rendering
  remains unverified.
- Spacing and layout rhythm: the overlay now uses the catalog panel as its containing
  block, preserving the left filter and right deck columns; rendered proportions
  remain unverified.
- Colors and visual tokens: the original catalog remains visible beneath a
  semi-transparent dimming layer; the neutral inspector bar and red adjustment
  buttons remain consistent with the source direction.
- Image quality and asset fidelity: real packaged card previews are used; all 1,267
  manifest paths exist.
- Copy and content: the center inspector keeps Card Library/category context while
  the original live deck panel supplies deck composition and selected-card rows.

**Primary Interactions**

- Static implementation inspection confirms handlers remain for gallery arrow-key
  movement, focused previous/next navigation, keyboard and visible `+` / `-`, and
  Escape-to-close.
- Add/remove still invokes the shared deck rendering path, so the visible right deck
  panel is refreshed immediately.
- Browser interaction execution and console inspection remain blocked.

**Implementation Checklist**

- Capture the catalog-confined expanded-card state in a functioning browser.
- Confirm filters and the right deck panel remain visible and independently scrollable.
- Test arrows, `+`, `-`, visible controls, and Escape.
- Check console errors and compare against the supplied reference.

**Comparison History**

- Previous pass: the focus layer covered the entire viewport, hiding deck visibility.
- Current pass: the focus layer is reparented into `.catalogPanel`, uses absolute
  panel-relative bounds, no longer locks body overflow, and disables the redundant
  internal deck drawer.
- Transition refinement: removed the separately rendered backdrop card grid so
  opening the inspector preserves the exact existing catalog, with a 150 ms dim
  and card-entry transition instead of an abrupt background replacement.
- Post-fix visual evidence: blocked because the integrated browser runtime could not
  initialize.

final result: blocked
