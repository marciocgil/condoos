import { deflateSync } from "node:zlib";

/** A small real PNG whose colour depends on ``seed``: a new file on every run. File triage
 * (D95) opens and saves images again, so signature-only fakes are refused. */
export function uniquePng(seed: number = Date.now()): Buffer {
  const width = 8;
  const height = 8;
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (buf: Buffer) => {
    let c = 0xffffffff;
    for (const byte of buf) c = (crcTable[(c ^ byte) & 0xff] ?? 0) ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type: string, data: Buffer) => {
    const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const sum = Buffer.alloc(4);
    sum.writeUInt32BE(crc(body));
    return Buffer.concat([len, body, sum]);
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header.writeUInt8(8, 8); // bit depth
  header.writeUInt8(2, 9); // truecolour RGB
  const rgb = [seed & 0xff, (seed >>> 8) & 0xff, (seed >>> 16) & 0xff];
  const rows = Buffer.concat(
    Array.from({ length: height }, () => Buffer.from([0, ...Array(width).fill(rgb).flat()])),
  );
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(rows)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

/** A valid fictitious CNPJ for a test condominium (check digits computed; ``seed`` makes it
 * new on every run). Only for condominiums: their CNPJ is never looked up at BrasilAPI
 * (only suppliers are), and suppliers in E2E come from the seed. */
export function fictitiousCnpj(seed: number = Date.now()): string {
  const base = String(seed % 100_000_000)
    .padStart(8, "0")
    .concat("0001")
    .split("")
    .map(Number);
  const digit = (nums: number[]) => {
    const weights =
      nums.length === 12
        ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    const sum = nums.reduce((s, n, i) => s + n * (weights[i] ?? 0), 0);
    const r = sum % 11;
    return r < 2 ? 0 : 11 - r;
  };
  const d1 = digit(base);
  const d2 = digit([...base, d1]);
  return [...base, d1, d2].join("");
}
