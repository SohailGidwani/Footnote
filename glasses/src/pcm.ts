export class PcmBuffer {
  private buffer: Uint8Array;
  private used = 0;
  constructor(chunkBytes = 128_000) {
    if (chunkBytes <= 0 || chunkBytes % 2) throw new Error('PCM chunks must contain whole 16-bit samples.');
    this.buffer = new Uint8Array(chunkBytes);
  }
  push(frame: Uint8Array): Uint8Array[] {
    const chunks: Uint8Array[] = [];
    let offset = 0;
    while (offset < frame.length) {
      const take = Math.min(frame.length - offset, this.buffer.length - this.used);
      this.buffer.set(frame.subarray(offset, offset + take), this.used);
      this.used += take;
      offset += take;
      if (this.used === this.buffer.length) {
        chunks.push(this.buffer.slice());
        this.used = 0;
      }
    }
    return chunks;
  }
  flush(): Uint8Array | null {
    const length = this.used - (this.used % 2);
    const result = length ? this.buffer.slice(0, length) : null;
    this.used = 0;
    return result;
  }
  clear() { this.used = 0; }
}
