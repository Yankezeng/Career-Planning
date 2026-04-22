from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import BASE_DIR
from app.models.persona import PersonaImageAsset


PERSONA_ASSET_ROUTE_PREFIX = "/api/students/profile/persona-images"

CBTI_ASSET_FILE_MAP: tuple[tuple[str, str, str], ...] = (
    ("TLIS", "技术探索稳健型", "CBTI (1).png"),
    ("TLIG", "技术探索跃迁型", "CBTI (2).png"),
    ("TLCS", "技术协作稳健型", "CBTI (3).png"),
    ("TLCG", "技术协作成长型", "CBTI (4).png"),
    ("TEIS", "技术执行稳健型", "CBTI (5).png"),
    ("TEIG", "技术执行冲刺型", "CBTI (6).png"),
    ("TECS", "技术交付稳健型", "CBTI (7).png"),
    ("TECG", "技术交付高潜型", "CBTI (8).png"),
    ("PLIS", "实践探索稳健型", "CBTI (9).png"),
    ("PLIG", "实践探索跃迁型", "CBTI (10).png"),
    ("PLCS", "实践协作稳健型", "CBTI (11).png"),
    ("PLCG", "实践协作成长型", "CBTI (12).png"),
    ("PEIS", "实践执行稳健型", "CBTI (13).png"),
    ("PEIG", "实践执行冲刺型", "CBTI (14).png"),
    ("PECS", "实践交付稳健型", "CBTI (15).png"),
    ("PECG", "实践交付高潜型", "CBTI (16).png"),
)


class PersonaImageAssetService:
    def __init__(self, db: Session):
        self.db = db

    def import_cbti_assets(self, source_dir: Path | None = None) -> list[dict[str, Any]]:
        root = source_dir or (BASE_DIR / "CBTI")
        imported: list[dict[str, Any]] = []
        for code, name, file_name in CBTI_ASSET_FILE_MAP:
            path = root / file_name
            image_data = path.read_bytes()
            digest = sha256(image_data).hexdigest()
            asset = (
                self.db.query(PersonaImageAsset)
                .filter(PersonaImageAsset.code == code)
                .first()
            )
            if asset:
                asset.name = name
                asset.file_name = file_name
                asset.mime_type = "image/png"
                asset.image_data = image_data
                asset.image_size = len(image_data)
                asset.sha256 = digest
                asset.is_active = True
            else:
                asset = PersonaImageAsset(
                    code=code,
                    name=name,
                    file_name=file_name,
                    mime_type="image/png",
                    image_data=image_data,
                    image_size=len(image_data),
                    sha256=digest,
                    is_active=True,
                )
                self.db.add(asset)
            imported.append(
                {
                    "code": code,
                    "name": name,
                    "file_name": file_name,
                    "sha256": digest,
                    "image_size": len(image_data),
                }
            )
        self.db.commit()
        return imported

    def ensure_cbti_assets(self) -> list[dict[str, Any]]:
        count = (
            self.db.query(PersonaImageAsset)
            .filter(PersonaImageAsset.is_active.is_(True))
            .count()
        )
        if count == len(CBTI_ASSET_FILE_MAP):
            return []
        return self.import_cbti_assets()

    def get_asset(self, code: str) -> PersonaImageAsset:
        return (
            self.db.query(PersonaImageAsset)
            .filter(
                PersonaImageAsset.code == str(code or "").strip().upper(),
                PersonaImageAsset.is_active.is_(True),
            )
            .one()
        )

    @staticmethod
    def get_image_url(code: str) -> str:
        return f"{PERSONA_ASSET_ROUTE_PREFIX}/{str(code or '').strip().upper()}"

    @staticmethod
    def to_public_dict(asset: PersonaImageAsset) -> dict[str, Any]:
        return {
            "code": asset.code,
            "name": asset.name,
            "file_name": asset.file_name,
            "mime_type": asset.mime_type,
            "image_size": asset.image_size,
            "sha256": asset.sha256,
            "image_url": PersonaImageAssetService.get_image_url(asset.code),
        }
