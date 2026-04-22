from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    users: Mapped[List["User"]] = relationship("User", back_populates="role")


class Department(Base, TimestampMixin):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    classes: Mapped[List["Classroom"]] = relationship("Classroom", back_populates="department")
    users: Mapped[List["User"]] = relationship("User", back_populates="department")


class Classroom(Base, TimestampMixin):
    __tablename__ = "classes"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    grade: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("departments.id"), nullable=True)

    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="classes")
    users: Mapped[List["User"]] = relationship("User", back_populates="classroom", foreign_keys="User.class_id")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    real_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("roles.id"), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("departments.id"), nullable=True)
    class_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("classes.id"), nullable=True)

    role: Mapped[Optional["Role"]] = relationship("Role", back_populates="users")
    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="users")
    classroom: Mapped[Optional["Classroom"]] = relationship("Classroom", back_populates="users", foreign_keys=[class_id])
    student: Mapped[Optional["Student"]] = relationship("Student", back_populates="user", uselist=False)
    enterprise_profile: Mapped[Optional["EnterpriseProfile"]] = relationship(
        "EnterpriseProfile",
        back_populates="user",
        uselist=False,
    )


class EnterpriseProfile(Base, TimestampMixin):
    __tablename__ = "enterprise_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True, unique=True)
    company_name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    company_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    company_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company_size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_doc_ids: Mapped[list] = mapped_column(JSON, default=list)

    user: Mapped[Optional["User"]] = relationship("User", back_populates="enterprise_profile")
    deliveries: Mapped[List["ResumeDelivery"]] = relationship(
        "ResumeDelivery",
        back_populates="enterprise_profile",
        cascade="all, delete-orphan",
    )
