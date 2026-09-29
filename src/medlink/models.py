from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from medlink.config import DIMENSIONS


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    checksum: Mapped[str] = mapped_column(String(64))
    embedding_key: Mapped[str] = mapped_column(String(300))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100))


class Encounter(Base):
    __tablename__ = "encounters"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    admitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ward: Mapped[str] = mapped_column(String(40))
    __table_args__ = (CheckConstraint("discharged_at IS NULL OR discharged_at >= admitted_at"),)


class Lab(Base):
    __tablename__ = "labs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    encounter_id: Mapped[str] = mapped_column(ForeignKey("encounters.id"))
    code: Mapped[str] = mapped_column(String(30))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_value: Mapped[float] = mapped_column(Float)
    source_unit: Mapped[str] = mapped_column(String(20))
    __table_args__ = (
        Index("ix_lab_encounter_code_time", "encounter_id", "code", "collected_at"),
        CheckConstraint("value >= 0"),
        CheckConstraint("available_at >= collected_at"),
    )


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    encounter_id: Mapped[str] = mapped_column(ForeignKey("encounters.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    text: Mapped[str] = mapped_column(Text)


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    note_id: Mapped[str] = mapped_column(ForeignKey("notes.id"), index=True)
    position: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    # SQLite variant is used only for unit tests; production always requires PostgreSQL.
    embedding: Mapped[list[float]] = mapped_column(Vector(DIMENSIONS).with_variant(JSON, "sqlite"))
    embedding_key: Mapped[str] = mapped_column(String(300))
