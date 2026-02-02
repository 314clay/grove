"""SQLAlchemy models for the todo system."""

from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    ARRAY,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Area(Base):
    """Life domains (Health, Career, etc.)."""
    __tablename__ = "areas"
    __table_args__ = {"schema": "todos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    color: Mapped[Optional[str]] = mapped_column(String(7))
    icon: Mapped[Optional[str]] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    initiatives: Mapped[list["Initiative"]] = relationship(back_populates="area")
    projects: Mapped[list["Project"]] = relationship(back_populates="area")
    tasks: Mapped[list["Task"]] = relationship(back_populates="area")


class Initiative(Base):
    """Strategic goals within an area."""
    __tablename__ = "initiatives"
    __table_args__ = {"schema": "todos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    area_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.areas.id"))
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.initiatives.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    target_date: Mapped[Optional[date]] = mapped_column(Date)
    labels: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    area: Mapped[Optional["Area"]] = relationship(back_populates="initiatives")
    parent: Mapped[Optional["Initiative"]] = relationship(remote_side=[id], backref="children")
    key_results: Mapped[list["KeyResult"]] = relationship(back_populates="initiative")
    projects: Mapped[list["Project"]] = relationship(back_populates="initiative")
    tasks: Mapped[list["Task"]] = relationship(back_populates="initiative")


class KeyResult(Base):
    """Measurable outcomes for initiatives."""
    __tablename__ = "key_results"
    __table_args__ = {"schema": "todos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    initiative_id: Mapped[int] = mapped_column(ForeignKey("todos.initiatives.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    target_value: Mapped[Optional[int]] = mapped_column(Integer)
    current_value: Mapped[int] = mapped_column(Integer, default=0)
    unit: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    initiative: Mapped["Initiative"] = relationship(back_populates="key_results")


class Project(Base):
    """Finite deliverables linked to initiatives."""
    __tablename__ = "projects"
    __table_args__ = {"schema": "todos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    initiative_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.initiatives.id"))
    area_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.areas.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    target_date: Mapped[Optional[date]] = mapped_column(Date)
    labels: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    done_when: Mapped[Optional[str]] = mapped_column(Text)
    beads_repo: Mapped[Optional[str]] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    initiative: Mapped[Optional["Initiative"]] = relationship(back_populates="projects")
    area: Mapped[Optional["Area"]] = relationship(back_populates="projects")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project")


class Task(Base):
    """Individual actionable items."""
    __tablename__ = "tasks"
    __table_args__ = {"schema": "todos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.projects.id"))
    initiative_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.initiatives.id"))
    area_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.areas.id"))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="inbox")
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    story_points: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    assignee: Mapped[Optional[str]] = mapped_column(String(100))
    context: Mapped[Optional[str]] = mapped_column(String(100))
    energy_level: Mapped[Optional[str]] = mapped_column(String(10))
    time_spent_minutes: Mapped[int] = mapped_column(Integer, default=0)
    cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    scheduled_date: Mapped[Optional[date]] = mapped_column(Date)
    defer_until: Mapped[Optional[date]] = mapped_column(Date)
    labels: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    session_id: Mapped[Optional[str]] = mapped_column(UUID)
    source_message_id: Mapped[Optional[int]] = mapped_column(Integer)
    beads_id: Mapped[Optional[str]] = mapped_column(String(64))
    beads_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    clarified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    project: Mapped[Optional["Project"]] = relationship(back_populates="tasks")
    initiative: Mapped[Optional["Initiative"]] = relationship(back_populates="tasks")
    area: Mapped[Optional["Area"]] = relationship(back_populates="tasks")
    blocked_by: Mapped[list["TaskDependency"]] = relationship(
        foreign_keys="TaskDependency.task_id",
        back_populates="task"
    )
    blocks: Mapped[list["TaskDependency"]] = relationship(
        foreign_keys="TaskDependency.depends_on_id",
        back_populates="depends_on"
    )


class TaskDependency(Base):
    """Dependencies between tasks."""
    __tablename__ = "task_dependencies"
    __table_args__ = {"schema": "todos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("todos.tasks.id"), nullable=False)
    depends_on_id: Mapped[int] = mapped_column(ForeignKey("todos.tasks.id"), nullable=False)
    dependency_type: Mapped[str] = mapped_column(String(32), default="blocks")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    task: Mapped["Task"] = relationship(foreign_keys=[task_id], back_populates="blocked_by")
    depends_on: Mapped["Task"] = relationship(foreign_keys=[depends_on_id], back_populates="blocks")


class Habit(Base):
    """Recurring habits separate from tasks."""
    __tablename__ = "habits"
    __table_args__ = {"schema": "todos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    area_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.areas.id"))
    frequency: Mapped[str] = mapped_column(String(32), default="daily")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    logs: Mapped[list["HabitLog"]] = relationship(back_populates="habit")


class HabitLog(Base):
    """Log entries for habit completions."""
    __tablename__ = "habit_log"
    __table_args__ = {"schema": "todos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    habit_id: Mapped[int] = mapped_column(ForeignKey("todos.habits.id"), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    habit: Mapped["Habit"] = relationship(back_populates="logs")
