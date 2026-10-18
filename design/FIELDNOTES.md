# Footnote / Meeting Fieldnotes

Editable Paper file: https://app.paper.design/file/01M56HH1VJ2BSH57HAFMAF1RED/p-1-0

## Direction

The phone is a field notebook for an unfamiliar meeting: quiet paper, strong ink,
short labels, and ruled entries. The glasses remain a separate green text display.
The phone borrows its sense of focus, but reserves phosphor green for the display
preview and digest memory strip. The first Paper page compares Field notes with
Night desk and Service manual; Field notes is the chosen direction.

## Tokens and type

| Role | Value | Use |
| --- | --- | --- |
| Paper | `#E6ECE3` | Main canvas |
| Ink | `#17362A` | Text, primary action, desktop spine |
| Muted | `#536A5B` | Help and secondary text |
| Rule | `#A8B8A9` | Ledger dividers |
| Mark | `#3E7B51` | Live status and question number |
| Display | `#07160D` | G2 preview and digest memory strip |
| Phosphor | `#B8EDB2` | Main text within display preview |

Bahnschrift carries the short headings; Segoe UI carries controls and prose.
Consolas appears only in the simulated G2 display. The physical G2 uses its
firmware font, so the browser preview is an approximation of layout and copy.
Buttons are square, with a minimum 48px touch height on the phone. Ruled rows
and space group information. There are no gradients, decorative badges, or cards.

## Interaction and hierarchy

1. The meeting action is above the fold. Status, G2 preview, and current term
   follow it. The phone exposes queue, mute, and next controls only when a term
   is present. The end action stays available throughout an active meeting.
2. Saved questions form a numbered ledger. Ending brings draft review to the
   top of the page, with To, Subject, full body, and an explicit approval action.
3. The digest opens with a compact G2 memory strip and separates learned words,
   people, and sent messages with rules. The mobile layout keeps the same order.
4. G2 uses three text containers at 576 × 288: status at y=12, term at y=78,
   detail at y=144. The term is brightest (15 of 15), detail is 11, and status
   is 6. Only the term container captures events. Listening, term, queued,
   empty/ready, and error artboards remain in the original G2 Paper file:
   https://app.paper.design/file/01M56GD0RYAQWQJM4X2MFXNWRR/p-1-0

## Paper frames and review images

The Meeting Fieldnotes file contains a direction study, three 390 × 844 phone
frames (ready, listening and queued, draft approval), a 1440 × 900 digest, and
a 390 × 844 digest. Editable Paper content is the visual source; the code in
`glasses/src` and `web/src` implements the same hierarchy and tokens.

Paper exports: `evidence/paper-directions.jpg`, `paper-phone-ready.jpg`,
`paper-phone-live.jpg`, `paper-phone-draft.jpg`, `paper-digest-desktop.jpg`, and
`paper-digest-mobile.jpg`.

Local implementation screenshots: `evidence/phone-fieldnotes-ready-full.jpg`,
`phone-fieldnotes-live.jpg`, `phone-fieldnotes-queued.jpg`,
`phone-fieldnotes-draft.jpg`, `digest-fieldnotes-desktop.jpg`, and
`digest-fieldnotes-mobile.jpg`. The earlier `phone-before.png` and
`digest-before.png` show the baseline for the before/after comparison.

## Check before the demo

Browser screenshots and simulated controls were reviewed in demo mode; the
physical G2 was not available for a brightness or text fit check. Check the
three live containers on device, especially long inferred meanings and owner
names. Keep `BACKEND_URL=http://localhost:8000` for the local integration.
