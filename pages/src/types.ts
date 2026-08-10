export type TemplatePositionType = "check" | "name" | "date" | "signature" | "extract_text";

export type TemplateField = "customerName" | "managerName" | "managerCode" | "date";

export type TemplatePosition = {
  id: string;
  type: TemplatePositionType;
  field?: TemplateField;
  fieldKey?: string;
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
  unit?: "pdf_point";
  sourceType?: string;
};

export type PdfTemplate = {
  id: string;
  name: string;
  description: string;
  coordinateOrigin?: "top_left" | "bottom_left";
  groupPageCount?: number;
  positions: TemplatePosition[];
};

export type FormValues = {
  customerName: string;
  managerName: string;
  managerCode: string;
  date: string;
};

export type CheckDarkness = "light" | "normal" | "dark";

export type ProcessingOptions = {
  insertChecks: boolean;
  generateSignature: boolean;
  randomStyle: boolean;
  checkDarkness: CheckDarkness;
};

export type ProcessedPdf = {
  bytes: Uint8Array;
  blobUrl: string;
  filename: string;
};
