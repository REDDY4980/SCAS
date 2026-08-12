"""Farm repository — pure CRUD, no business logic (AIB v1.0 Vol 12.6)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.farm import Farm


class FarmRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, farm_id: uuid.UUID) -> Farm | None:
        return self.db.get(Farm, farm_id)

    def list_for_user(self, user_id: uuid.UUID) -> list[Farm]:
        return list(
            self.db.execute(
                select(Farm).where(Farm.user_id == user_id).order_by(Farm.created_at.desc())
            ).scalars()
        )

    def create(self, *, user_id: uuid.UUID, **fields) -> Farm:
        farm = Farm(user_id=user_id, **fields)
        self.db.add(farm)
        self.db.commit()
        self.db.refresh(farm)
        return farm

    def update(self, farm: Farm, **fields) -> Farm:
        for key, value in fields.items():
            if value is not None:
                setattr(farm, key, value)
        self.db.commit()
        self.db.refresh(farm)
        return farm

    def delete(self, farm: Farm) -> None:
        self.db.delete(farm)
        self.db.commit()
