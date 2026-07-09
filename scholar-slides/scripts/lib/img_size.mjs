// img_size.mjs — build-time PNG dimension probe (M8a true-wide sizing).
// Crops are always PNG (crop_figure.py / make_chart.py); anything else returns null and the
// figure simply renders with the default height-driven sizing. 26 bytes read, no decoder.
import fs from "node:fs";

const PNG_SIG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

export function probeImageSize(filePath) {
  let fd;
  try {
    fd = fs.openSync(filePath, "r");
    const head = Buffer.alloc(24);
    if (fs.readSync(fd, head, 0, 24, 0) < 24) return null;
    if (!head.subarray(0, 8).equals(PNG_SIG)) return null;
    if (head.toString("ascii", 12, 16) !== "IHDR") return null;
    const w = head.readUInt32BE(16);
    const h = head.readUInt32BE(20);
    return w > 0 && h > 0 ? { w, h } : null;
  } catch {
    return null;
  } finally {
    if (fd !== undefined) fs.closeSync(fd);
  }
}
