export type Gesture = 'click' | 'up' | 'down' | 'end' | 'exit' | 'foreground' | 'background' | 'closed';
interface Envelope { eventType?: number }
export function gestureOf(event: { sysEvent?: Envelope; textEvent?: Envelope; listEvent?: Envelope; audioEvent?: unknown }): Gesture | null {
  const envelopes = [event.sysEvent, event.textEvent, event.listEvent].filter((e): e is Envelope => !!e);
  // Protobuf omits CLICK_EVENT=0, but only an existing envelope can be a click.
  const types = envelopes.map(e => e.eventType ?? 0);
  if (types.includes(3)) return 'exit';
  if (types.includes(6) || types.includes(7)) return 'closed';
  if (types.includes(5)) return 'background';
  if (types.includes(4)) return 'foreground';
  if (types.includes(9) || types.includes(10)) return 'end';
  if (types.includes(1)) return 'up';
  if (types.includes(2)) return 'down';
  if (types.includes(0)) return 'click';
  return null;
}
