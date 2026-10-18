# Afterimage design pass

[Paper file — final screens](https://app.paper.design/file/01M56HH1VJ2BSH57HAFMAF1RED/p-5-0)

**Direction.** Afterimage carries the G2's green-on-black character into the
phone and digest. Space Grotesk makes the main action and term easy to scan;
IBM Plex Mono keeps device status and counts quiet. A single lit edge marks the
current item. The result stays legible without gradients, decoration, or a grid
of rounded cards.

**What changed from v1.** The phone now leads with the current term and one
primary action. Drafts are reviewed one person at a time, with Send and a
five-second Undo window for Discard. The digest uses numbered terms and a
clear people column. The G2 uses one thin outline, then term, meaning, person
to ask, and one short action hint. Empty and error copy is brief on G2; the
phone carries the detail.

`before/` contains the earlier Paper phone, digest, and G2 frames. `after/`
contains the chosen Paper frames and local browser/simulator captures. Sent,
Undo, and offline phone frames are new states, so there are no matching v1
screens. The live app captures have `-app` in the filename; official simulator
captures have `g2-simulator` in the filename. The simulator's transparent
framebuffer was also captured on black for easier review.

**Checks.** The local browser flow reached a backend term, saved a question,
ended a meeting, reviewed a draft, used Undo, and completed Discard. The digest
was checked at desktop and 375 px. The official simulator showed the 576 × 288
term, brief saved confirmation, and return to listening. SDK text brightness is
0–4. Border brightness and the longest text still need Sohail's physical G2
check before merging this branch.
