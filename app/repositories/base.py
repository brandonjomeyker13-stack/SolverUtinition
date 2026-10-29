from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], db: Session):
        self.model = model
        self.db = db

    def create(self, obj_in: ModelType) -> ModelType:
        self.db.add(obj_in)
        self.db.flush()
        self.db.refresh(obj_in)
        return obj_in

    def get_by_id(self, id: int) -> ModelType | None:
        return self.db.get(self.model, id)
