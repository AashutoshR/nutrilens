// Downscale photos in the browser before upload: phone photos are often >5 MB (the
// Claude API limit) and in HEIC, which the browser can decode but the API cannot.
async function decode(file) {
  if ("createImageBitmap" in window) {
    try {
      return await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch {
      /* fall through to <img> decoding */
    }
  }
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    return img;
  } finally {
    URL.revokeObjectURL(url);
  }
}

function draw(source, maxSide) {
  const w = source.width;
  const h = source.height;
  const scale = Math.min(1, maxSide / Math.max(w, h));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(w * scale);
  canvas.height = Math.round(h * scale);
  canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
  return canvas;
}

export async function prepareImage(file) {
  if (!file.type.startsWith("image/")) throw new Error("That file isn't an image.");
  const source = await decode(file);
  const canvas = draw(source, 1568);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
  const thumbnail = draw(canvas, 240).toDataURL("image/jpeg", 0.7);
  return { blob, previewUrl: URL.createObjectURL(blob), thumbnail };
}
