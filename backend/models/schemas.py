from typing import Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str


class DocumentOut(BaseModel):
    id: int
    original_name: str
    stored_name: str
    file_path: str
    file_url: str | None = None
    content_type: str | None = None
    size_bytes: int
    created_at: str


class DocumentPageInfo(BaseModel):
    page: int
    width: float
    height: float
    unit: str = "pdf_point"


class DocumentPreview(BaseModel):
    document: DocumentOut
    file_url: str
    pages: list[DocumentPageInfo]


class DocumentMetadata(BaseModel):
    document_id: int
    page_count: int
    pages: list[DocumentPageInfo]


class CheckAssetOut(BaseModel):
    id: str
    filename: str
    path: str
    image_url: str
    source: str
    size_bytes: int
    created_at: str | None = None


class CheckAssetUploadResponse(BaseModel):
    source_id: str
    created_count: int
    assets: list[CheckAssetOut]


class JamoSourceUploadResponse(BaseModel):
    source_id: str
    filename: str
    image_url: str


class JamoCrop(BaseModel):
    x: int
    y: int
    width: int
    height: int


class JamoAssetCreate(BaseModel):
    source_id: str
    category: str
    jamo: str
    crop: JamoCrop


class JamoAssetPatch(BaseModel):
    active: bool | None = None


class JamoAssetOut(BaseModel):
    id: str
    category: str
    jamo: str
    filename: str
    path: str
    image_url: str
    active: bool = True
    size_bytes: int
    created_at: str | None = None


class JamoSignaturePreviewRequest(BaseModel):
    customer_name: str
    mode: str = "jamo_composed_signature"


class JamoSignaturePreviewResponse(BaseModel):
    success: bool
    preview_url: str
    used_jamo: list[str] = Field(default_factory=list)
    missing_jamo: list[str] = Field(default_factory=list)
    output_path: str


class SignatureAssetOut(BaseModel):
    id: str
    category: str
    label: str
    filename: str
    path: str
    image_url: str
    active: bool = True
    size_bytes: int
    created_at: str | None = None


class SignatureAssetPatch(BaseModel):
    active: bool | None = None
    label: str | None = None


class ConfigPayload(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class MergeRequest(BaseModel):
    document_id: int | None = None
    template_id: int | None = None
    pdf_path: str | None = None
    overlay_config_path: str | None = None
    form_data_path: str | None = None


class MergeResponse(BaseModel):
    status: str
    output_path: str | None = None
    message: str


class ExtractFieldRequest(BaseModel):
    field_key: str
    page: int
    x: float
    y: float
    width: float
    height: float
    unit: str = "pdf_point"


class ExtractFieldsPayload(BaseModel):
    fields: list[ExtractFieldRequest] = Field(default_factory=list)


class ExtractFieldsResponse(BaseModel):
    fields: dict[str, str] = Field(default_factory=dict)
    raw_fields: dict[str, str] = Field(default_factory=dict)
    warnings: dict[str, str] = Field(default_factory=dict)


class TemplateMergeOptions(BaseModel):
    auto_extract: bool = True
    generate_signature: bool = True
    use_check_assets: bool = True
    auto_filename: bool = True


class TemplateMergeRequest(BaseModel):
    form_data: dict[str, Any] = Field(default_factory=dict)
    options: TemplateMergeOptions = Field(default_factory=TemplateMergeOptions)


class TemplateMergeResponse(BaseModel):
    success: bool
    output_filename: str
    output_path: str
    message: str
    extracted_fields: dict[str, str] = Field(default_factory=dict)
    applied_style_profile: dict[str, Any] = Field(default_factory=dict)


class TemplatePublicOut(BaseModel):
    id: int
    name: str
    description: str
    document_name: str | None = None


class ProcessPdfResponse(BaseModel):
    success: bool
    process_id: int | None = None
    extracted_fields: dict[str, str] = Field(default_factory=dict)
    raw_fields: dict[str, str] = Field(default_factory=dict)
    warnings: dict[str, str] = Field(default_factory=dict)
    page_count: int | None = None
    group_page_count: int | None = None
    batch_count: int | None = None
    batch_items: list[dict[str, Any]] = Field(default_factory=list)
    output_filename: str
    output_path: str
    download_url: str
    message: str
    applied_style_profile: dict[str, Any] = Field(default_factory=dict)


class ProcessExtractResponse(BaseModel):
    document_id: int
    original_name: str
    extracted_fields: dict[str, str] = Field(default_factory=dict)
    raw_fields: dict[str, str] = Field(default_factory=dict)
    warnings: dict[str, str] = Field(default_factory=dict)
    page_count: int | None = None
    group_page_count: int | None = None
    batch_count: int | None = None
    batch_items: list[dict[str, Any]] = Field(default_factory=list)


class ProcessMergeRequest(BaseModel):
    template_id: int
    document_id: int
    form_data: dict[str, Any] = Field(default_factory=dict)


class ProcessUploadResponse(BaseModel):
    document_id: int
    status: str


class ProcessRunRequest(BaseModel):
    template_id: int | None = None
    template_version_id: int | None = None
    send_kakao: bool = False


class ProcessStatusResponse(BaseModel):
    document_id: int
    status: str
    customer_name: str | None = None
    manager_name: str | None = None
    manager_code: str | None = None
    final_pdf_path: str | None = None
    failed_step: str | None = None
    failed_reason: str | None = None


class AdminTemplateCreate(BaseModel):
    template_key: str
    template_name: str
    insurer_name: str | None = None
    description: str = ""


class AdminTemplateOut(BaseModel):
    id: int
    template_key: str
    template_name: str
    insurer_name: str | None = None
    description: str | None = None
    is_active: bool
    created_at: str
    updated_at: str


class TemplateVersionCreate(BaseModel):
    version: str
    pdf_sample_path: str | None = None
    overlay_config: dict[str, Any] = Field(default_factory=lambda: {"pages": {}})
    extract_config: dict[str, Any] = Field(default_factory=lambda: {"fields": []})


class TemplateVersionOut(BaseModel):
    id: int
    template_id: int
    version: str
    pdf_sample_path: str | None = None
    overlay_config_path: str
    extract_config_path: str
    is_active: bool
    created_at: str
    updated_at: str


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    document_id: int | None = None
    overlay_config: dict[str, Any] = Field(default_factory=lambda: {"pages": {}})
    form_data: dict[str, Any] = Field(default_factory=dict)
    render_style: dict[str, Any] = Field(
        default_factory=lambda: {
            "font_family": "random",
            "pen_texture": "random",
            "randomize": True,
            "pdf_level_style": True,
            "page_group_size": 3,
            "signature_generation_modes": [
                "jamo_composed_signature",
                "first_korean_char",
                "english_cursive_full",
                "english_initials",
                "last_korean_char",
                "full_korean_name",
                "neat_korean_name",
            ],
            "check_stroke_profiles": ["normal", "dark", "light"],
            "keep_style_consistency_per_pdf": True,
            "fax_effect": True,
            "fax_effect_config": {
                "dpi": 170,
                "rotation": [-0.35, 0.35],
                "contrast": 1.18,
                "brightness": 1.02,
                "noise": 7,
                "blur": 0.18,
            },
            "random_range": {
                "rotation": [-3, 3],
                "offset_x": [-2, 2],
                "offset_y": [-2, 2],
                "scale": [0.95, 1.05],
                "opacity": [0.85, 1.0],
            },
        }
    )


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    document_id: int | None = None
    overlay_config: dict[str, Any] | None = None
    form_data: dict[str, Any] | None = None
    render_style: dict[str, Any] | None = None


class TemplateOut(BaseModel):
    id: int
    name: str
    description: str
    document_id: int | None = None
    document_name: str | None = None
    overlay_config: dict[str, Any]
    form_data: dict[str, Any]
    render_style: dict[str, Any]
    created_at: str
    updated_at: str
