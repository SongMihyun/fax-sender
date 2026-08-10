export type SignatureStyle = {
  rotation: number;
  opacity: number;
  scale: number;
};

type JamoAsset = {
  category: "initial" | "medial" | "final";
  jamo: string;
  path: string;
};

const initials = ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"];
const medials = ["ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ", "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ"];
const finals = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"];
const horizontalMedials = new Set(["ㅗ", "ㅛ", "ㅜ", "ㅠ", "ㅡ"]);
const mixedMedials = new Set(["ㅘ", "ㅙ", "ㅚ", "ㅝ", "ㅞ", "ㅟ", "ㅢ"]);
const compositeJamo: Record<string, string[]> = {
  "ㄲ": ["ㄱ", "ㄱ"],
  "ㄸ": ["ㄷ", "ㄷ"],
  "ㅃ": ["ㅂ", "ㅂ"],
  "ㅆ": ["ㅅ", "ㅅ"],
  "ㅉ": ["ㅈ", "ㅈ"],
  "ㅘ": ["ㅗ", "ㅏ"],
  "ㅙ": ["ㅗ", "ㅐ"],
  "ㅚ": ["ㅗ", "ㅣ"],
  "ㅝ": ["ㅜ", "ㅓ"],
  "ㅞ": ["ㅜ", "ㅔ"],
  "ㅟ": ["ㅜ", "ㅣ"],
  "ㅢ": ["ㅡ", "ㅣ"],
  "ㄳ": ["ㄱ", "ㅅ"],
  "ㄵ": ["ㄴ", "ㅈ"],
  "ㄶ": ["ㄴ", "ㅎ"],
  "ㄺ": ["ㄹ", "ㄱ"],
  "ㄻ": ["ㄹ", "ㅁ"],
  "ㄼ": ["ㄹ", "ㅂ"],
  "ㄽ": ["ㄹ", "ㅅ"],
  "ㄾ": ["ㄹ", "ㅌ"],
  "ㄿ": ["ㄹ", "ㅍ"],
  "ㅀ": ["ㄹ", "ㅎ"],
  "ㅄ": ["ㅂ", "ㅅ"],
};
const similarJamo: Record<string, string[]> = {
  "ㄲ": ["ㄱ"],
  "ㄸ": ["ㄷ"],
  "ㅃ": ["ㅂ"],
  "ㅆ": ["ㅅ"],
  "ㅉ": ["ㅈ"],
  "ㅋ": ["ㄱ"],
  "ㅌ": ["ㄷ"],
  "ㅍ": ["ㅂ"],
  "ㅊ": ["ㅈ"],
  "ㅎ": ["ㅇ"],
  "ㅐ": ["ㅏ", "ㅣ"],
  "ㅔ": ["ㅓ", "ㅣ"],
  "ㅑ": ["ㅏ"],
  "ㅕ": ["ㅓ"],
  "ㅛ": ["ㅗ"],
  "ㅠ": ["ㅜ"],
};

// Compound vowels must not fall back to a visually similar single vowel.
// For example, ㅖ needs the ㅕ handwriting plus one fixed ㅣ on its right.
const medialICompounds: Record<string, { base: string; side: "left" | "right" }> = {
  "\u3150": { base: "\u314f", side: "left" },
  "\u3152": { base: "\u3151", side: "left" },
  "\u3154": { base: "\u3153", side: "left" },
  "\u3156": { base: "\u3155", side: "right" },
  "\u315a": { base: "\u3161", side: "right" },
};

let jamoManifestPromise: Promise<JamoAsset[]> | null = null;
const imageCache = new Map<string, Promise<HTMLImageElement>>();

export function createRandomSignatureStyle(enabled: boolean): SignatureStyle {
  if (!enabled) {
    return { rotation: 0, opacity: 1, scale: 1 };
  }
  return {
    rotation: Math.random() * 7 - 3.5,
    opacity: 0.96 + Math.random() * 0.04,
    scale: 0.94 + Math.random() * 0.14,
  };
}

function cleanKoreanName(name: string): string {
  return (name || "").replace(/[^가-힣]/g, "");
}

function decomposeSyllable(char: string): [string, string, string] | null {
  const code = char.charCodeAt(0) - 0xac00;
  if (code < 0 || code > 11171) return null;
  return [initials[Math.floor(code / 588)], medials[Math.floor((code % 588) / 28)], finals[code % 28]];
}

function pick<T>(items: T[]): T | null {
  if (items.length === 0) return null;
  return items[Math.floor(Math.random() * items.length)];
}

async function loadJamoManifest(): Promise<JamoAsset[]> {
  if (!jamoManifestPromise) {
    jamoManifestPromise = fetch(`${import.meta.env.BASE_URL}assets/jamo/manifest.json`)
      .then((response) => (response.ok ? response.json() : []))
      .catch(() => []);
  }
  return jamoManifestPromise;
}

function assetUrl(path: string): string {
  return `${import.meta.env.BASE_URL}assets/jamo/${path.split("/").map(encodeURIComponent).join("/")}`;
}

async function loadImage(path: string): Promise<HTMLImageElement> {
  if (!imageCache.has(path)) {
    imageCache.set(
      path,
      new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error(`자모 이미지를 불러오지 못했습니다: ${path}`));
        image.src = assetUrl(path);
      }),
    );
  }
  return imageCache.get(path)!;
}

function composeMedialICompound(base: HTMLImageElement, stroke: HTMLImageElement, side: "left" | "right"): HTMLCanvasElement {
  const scale = Math.min(72 / Math.max(1, base.naturalHeight), 48 / Math.max(1, base.naturalWidth));
  const baseWidth = Math.max(1, Math.round(base.naturalWidth * scale));
  const baseHeight = Math.max(1, Math.round(base.naturalHeight * scale));
  const strokeScale = Math.min(72 / Math.max(1, stroke.naturalHeight), 14 / Math.max(1, stroke.naturalWidth));
  const strokeWidth = Math.max(1, Math.round(stroke.naturalWidth * strokeScale));
  const strokeHeight = Math.max(1, Math.round(stroke.naturalHeight * strokeScale));
  const gap = Math.max(1, Math.round(baseWidth / 12));
  const canvas = document.createElement("canvas");
  canvas.width = baseWidth + strokeWidth + gap;
  canvas.height = Math.max(baseHeight, strokeHeight);
  const context = canvas.getContext("2d");
  if (!context) return canvas;
  const baseY = Math.round((canvas.height - baseHeight) / 2);
  const strokeY = Math.round((canvas.height - strokeHeight) / 2);
  if (side === "left") {
    context.drawImage(stroke, 0, strokeY, strokeWidth, strokeHeight);
    context.drawImage(base, strokeWidth + gap, baseY, baseWidth, baseHeight);
  } else {
    context.drawImage(base, 0, baseY, baseWidth, baseHeight);
    context.drawImage(stroke, baseWidth + gap, strokeY, strokeWidth, strokeHeight);
  }
  return canvas;
}

async function pickJamoImage(category: JamoAsset["category"], jamo: string, seen = new Set<string>()): Promise<CanvasImageSource | null> {
  const key = `${category}:${jamo}`;
  if (seen.has(key)) return null;
  seen.add(key);

  const manifest = await loadJamoManifest();
  const direct = pick(manifest.filter((asset) => asset.category === category && asset.jamo === jamo));
  if (direct) return loadImage(direct.path);

  const compound = category === "medial" ? medialICompounds[jamo] : undefined;
  if (compound) {
    const base = await pickJamoImage("medial", compound.base, new Set(seen));
    const fixedStrokeAsset = manifest
      .filter((asset) => asset.category === "medial" && asset.jamo === "\u3163")
      .sort((left, right) => left.path.localeCompare(right.path))[0];
    const stroke = fixedStrokeAsset ? await loadImage(fixedStrokeAsset.path) : null;
    if (base instanceof HTMLImageElement && stroke) return composeMedialICompound(base, stroke, compound.side);
  }

  const finalAsInitial = category === "final" && initials.includes(jamo) ? pick(manifest.filter((asset) => asset.category === "initial" && asset.jamo === jamo)) : null;
  if (finalAsInitial) return loadImage(finalAsInitial.path);

  for (const component of compositeJamo[jamo] ?? []) {
    const image = await pickJamoImage(category, component, new Set(seen));
    if (image) return image;
  }

  for (const similar of similarJamo[jamo] ?? []) {
    const image = await pickJamoImage(category, similar, new Set(seen));
    if (image) return image;
  }

  return null;
}

function drawFittedImage(context: CanvasRenderingContext2D, image: CanvasImageSource, x: number, y: number, maxWidth: number, maxHeight: number) {
  const sourceWidth = image instanceof HTMLImageElement ? image.naturalWidth : image instanceof HTMLCanvasElement ? image.width : maxWidth;
  const sourceHeight = image instanceof HTMLImageElement ? image.naturalHeight : image instanceof HTMLCanvasElement ? image.height : maxHeight;
  const ratio = Math.min(maxWidth / Math.max(1, sourceWidth), maxHeight / Math.max(1, sourceHeight));
  const width = sourceWidth * ratio;
  const height = sourceHeight * ratio;
  context.drawImage(image, x + (maxWidth - width) / 2, y + (maxHeight - height) / 2, width, height);
}

function syllableBoxes(medial: string, hasFinal: boolean) {
  if (hasFinal && horizontalMedials.has(medial)) {
    return { initial: [18, 4, 80, 46], medial: [18, 43, 80, 30], final: [20, 72, 76, 44] };
  }
  if (hasFinal && mixedMedials.has(medial)) {
    return { initial: [6, 8, 48, 58], medial: [42, 10, 66, 66], final: [20, 74, 78, 42] };
  }
  if (hasFinal) {
    return { initial: [4, 10, 48, 56], medial: [42, 10, 56, 60], final: [16, 64, 76, 48] };
  }
  if (horizontalMedials.has(medial)) {
    return { initial: [18, 8, 80, 60], medial: [18, 62, 80, 54], final: [20, 78, 76, 40] };
  }
  if (mixedMedials.has(medial)) {
    return { initial: [6, 14, 48, 78], medial: [44, 12, 66, 104], final: [20, 78, 78, 40] };
  }
  return { initial: [8, 14, 50, 94], medial: [52, 14, 60, 98], final: [20, 78, 78, 40] };
}

function strengthenSignatureInk(canvas: HTMLCanvasElement) {
  const context = canvas.getContext("2d");
  if (!context) return;

  const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
  const pixels = imageData.data;
  for (let index = 0; index < pixels.length; index += 4) {
    if (pixels[index + 3] < 8) continue;
    pixels[index] = 0;
    pixels[index + 1] = 0;
    pixels[index + 2] = 0;
    pixels[index + 3] = Math.min(255, pixels[index + 3] * 1.35 + 24);
  }
  context.putImageData(imageData, 0, 0);
}

async function drawSyllable(context: CanvasRenderingContext2D, char: string, x: number, y: number): Promise<boolean> {
  const decomposed = decomposeSyllable(char);
  if (!decomposed) return false;

  const [initial, medial, final] = decomposed;
  const boxes = syllableBoxes(medial, Boolean(final));
  const initialImage = await pickJamoImage("initial", initial);
  const medialImage = await pickJamoImage("medial", medial);
  const finalImage = final ? await pickJamoImage("final", final) : null;
  if (!initialImage || !medialImage || (final && !finalImage)) return false;

  context.save();
  context.translate(x, y);
  context.rotate((Math.random() * 5 - 2.5) * Math.PI / 180);
  drawFittedImage(context, initialImage, boxes.initial[0], boxes.initial[1], boxes.initial[2], boxes.initial[3]);
  drawFittedImage(context, medialImage, boxes.medial[0], boxes.medial[1], boxes.medial[2], boxes.medial[3]);
  if (final && finalImage) drawFittedImage(context, finalImage, boxes.final[0], boxes.final[1], boxes.final[2], boxes.final[3]);
  context.restore();
  return true;
}

async function createJamoSignaturePng(name: string, style: SignatureStyle): Promise<ArrayBuffer | null> {
  const koreanName = cleanKoreanName(name);
  if (!koreanName) return null;

  const canvas = document.createElement("canvas");
  canvas.width = Math.max(240, koreanName.length * 120 + 24);
  canvas.height = 150;
  const context = canvas.getContext("2d");
  if (!context) return null;
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.globalAlpha = style.opacity;

  let cursor = 12;
  for (const char of koreanName) {
    const ok = await drawSyllable(context, char, cursor, 14 + Math.random() * 6);
    if (!ok) return null;
    cursor += 112 + Math.random() * 6;
  }

  const output = document.createElement("canvas");
  output.width = canvas.width + 30;
  output.height = canvas.height + 30;
  const outputContext = output.getContext("2d");
  if (!outputContext) return null;
  outputContext.translate(output.width / 2, output.height / 2);
  outputContext.rotate((style.rotation * Math.PI) / 180);
  outputContext.scale(style.scale, style.scale);
  outputContext.drawImage(canvas, -canvas.width / 2, -canvas.height / 2);
  strengthenSignatureInk(output);

  const blob = await new Promise<Blob>((resolve, reject) => {
    output.toBlob((value) => (value ? resolve(value) : reject(new Error("자모 서명 PNG 변환 실패"))), "image/png");
  });
  return blob.arrayBuffer();
}

async function createTextSignaturePng(name: string, style: SignatureStyle): Promise<ArrayBuffer> {
  const canvas = document.createElement("canvas");
  canvas.width = 620;
  canvas.height = 240;
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("서명 이미지를 생성할 수 없습니다.");
  }

  context.clearRect(0, 0, canvas.width, canvas.height);
  context.translate(canvas.width / 2, canvas.height / 2);
  context.rotate((style.rotation * Math.PI) / 180);
  context.scale(style.scale, style.scale);
  context.translate(-canvas.width / 2, -canvas.height / 2);

  context.globalAlpha = style.opacity;
  context.fillStyle = "#020608";
  context.lineWidth = 3;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.font = "96px 'Segoe Script', 'Brush Script MT', 'Malgun Gothic', cursive";
  context.textBaseline = "middle";
  context.fillText(name || "서명", 42, 118);

  context.beginPath();
  context.moveTo(54, 165);
  context.bezierCurveTo(150, 184, 285, 176, 430, 158);
  context.strokeStyle = "rgba(2, 6, 8, 0.88)";
  context.stroke();
  strengthenSignatureInk(canvas);

  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((value) => (value ? resolve(value) : reject(new Error("서명 PNG 변환 실패"))), "image/png");
  });
  return blob.arrayBuffer();
}

export async function createSignaturePng(name: string, style: SignatureStyle): Promise<ArrayBuffer> {
  const jamoSignature = await createJamoSignaturePng(name, style);
  if (jamoSignature) return jamoSignature;
  return createTextSignaturePng(name, style);
}

export async function createNamePng(name: string, widthInPoints: number, heightInPoints: number): Promise<ArrayBuffer> {
  const jamoName = await createJamoSignaturePng(name, {
    rotation: Math.random() * 2 - 1,
    opacity: 0.92,
    scale: 1,
  });
  if (jamoName) return jamoName;

  const scale = 5;
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(80, Math.ceil(widthInPoints * scale));
  canvas.height = Math.max(60, Math.ceil(heightInPoints * scale));
  const context = canvas.getContext("2d");
  if (!context) throw new Error("이름 이미지를 생성할 수 없습니다.");

  const text = (name || "").trim();
  const maxWidth = canvas.width - Math.max(8, Math.round(canvas.width / 16));
  let fontSize = Math.max(12, Math.floor(canvas.height * 0.72));
  context.fillStyle = "#080c0e";
  context.textAlign = "center";
  context.textBaseline = "middle";
  do {
    context.font = `700 ${fontSize}px 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif`;
    if (context.measureText(text).width <= maxWidth || fontSize <= 8) break;
    fontSize -= 1;
  } while (fontSize > 8);
  context.fillText(text, canvas.width / 2, canvas.height / 2 + canvas.height * 0.03, maxWidth);

  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((value) => (value ? resolve(value) : reject(new Error("이름 PNG 변환 실패"))), "image/png");
  });
  return blob.arrayBuffer();
}
