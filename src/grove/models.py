"""SQLAlchemy models for the Grove task system.

Botanical naming scheme:
- Groves: Life domains (Health, Career, etc.)
- Trunks: Strategic initiatives within a grove
- Fruits: Measurable outcomes (OKRs) for trunks
- Branches: Projects within a trunk
- Buds: Individual tasks/work items
- Seeds: Unprocessed buds (status='seed')

Bud status lifecycle: seed → dormant → budding → bloomed/mulch
"""

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


class Grove(Base):
    """Life domains (Health, Career, etc.) - the forests where your work grows."""
    __tablename__ = "groves"
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

    trunks: Mapped[list["Trunk"]] = relationship(back_populates="grove")
    branches: Mapped[list["Branch"]] = relationship(back_populates="grove")
    buds: Mapped[list["Bud"]] = relationship(back_populates="grove")


class Trunk(Base):
    """Strategic goals within a grove - the main stems that support your branches."""
    __tablename__ = "trunks"
    __table_args__ = {"schema": "todos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grove_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.groves.id"))
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.trunks.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    target_date: Mapped[Optional[date]] = mapped_column(Date)
    labels: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    grove: Mapped[Optional["Grove"]] = relationship(back_populates="trunks")
    parent: Mapped[Optional["Trunk"]] = relationship(remote_side=[id], backref="children")
    fruits: Mapped[list["Fruit"]] = relationship(back_populates="trunk")
    branches: Mapped[list["Branch"]] = relationship(back_populates="trunk")
    buds: Mapped[list["Bud"]] = relationship(back_populates="trunk")


class Fruit(Base):
    """Measurable outcomes for trunks (OKR-style) - the fruits that ripen as you progress."""
    __tablename__ = "fruits"
    __table_args__ = {"schema": "todos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trunk_id: Mapped[int] = mapped_column(ForeignKey("todos.trunks.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    target_value: Mapped[Optional[int]] = mapped_column(Integer)
    current_value: Mapped[int] = mapped_column(Integer, default=0)
    unit: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    trunk: Mapped["Trunk"] = relationship(back_populates="fruits")


class Branch(Base):
    """Projects - branches that hold your buds."""
    __tablename__ = "branches"
    __table_args__ = {"schema": "todos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trunk_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.trunks.id"))
    grove_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.groves.id"))
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

    trunk: Mapped[Optional["Trunk"]] = relationship(back_populates="branches")
    grove: Mapped[Optional["Grove"]] = relationship(back_populates="branches")
    buds: Mapped[list["Bud"]] = relationship(back_populates="branch")


class Bud(Base):
    """Individual work items - buds that bloom into completed work.

    Status lifecycle:
    - seed: Raw capture, unprocessed (inbox)
    - dormant: Clarified, ready to work on
    - budding: Actively being worked on
    - bloomed: Completed
    - mulch: Dropped/abandoned (feeds future growth)
    """
    __tablename__ = "buds"
    __table_args__ = {"schema": "todos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.branches.id"))
    trunk_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.trunks.id"))
    grove_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.groves.id"))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="seed")
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

    branch: Mapped[Optional["Branch"]] = relationship(back_populates="buds")
    trunk: Mapped[Optional["Trunk"]] = relationship(back_populates="buds")
    grove: Mapped[Optional["Grove"]] = relationship(back_populates="buds")
    blocked_by: Mapped[list["BudDependency"]] = relationship(
        foreign_keys="BudDependency.bud_id",
        back_populates="bud"
    )
    blocks: Mapped[list["BudDependency"]] = relationship(
        foreign_keys="BudDependency.depends_on_id",
        back_populates="depends_on"
    )


class BudDependency(Base):
    """Dependencies between buds - which buds must bloom first."""
    __tablename__ = "bud_dependencies"
    __table_args__ = {"schema": "todos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bud_id: Mapped[int] = mapped_column(ForeignKey("todos.buds.id"), nullable=False)
    depends_on_id: Mapped[int] = mapped_column(ForeignKey("todos.buds.id"), nullable=False)
    dependency_type: Mapped[str] = mapped_column(String(32), default="blocks")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    bud: Mapped["Bud"] = relationship(foreign_keys=[bud_id], back_populates="blocked_by")
    depends_on: Mapped["Bud"] = relationship(foreign_keys=[depends_on_id], back_populates="blocks")


class Habit(Base):
    """Recurring habits separate from buds."""
    __tablename__ = "habits"
    __table_args__ = {"schema": "todos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    grove_id: Mapped[Optional[int]] = mapped_column(ForeignKey("todos.groves.id"))
    frequency: Mapped[str] = mapped_column(String(20), default="daily")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
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
