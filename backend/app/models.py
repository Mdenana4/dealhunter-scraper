import enum
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Boolean, DateTime, ForeignKey,
    Text, Enum as SAEnum, func,
)
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class SubscriptionTier(str, enum.Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class Source(str, enum.Enum):
    amazon = "amazon"
    noon = "noon"
    jumia = "jumia"
    carrefour = "carrefour"
    other = "other"


class FakeProbability(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    subscription_tier = Column(SAEnum(SubscriptionTier), default=SubscriptionTier.free)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Deal(Base):
    __tablename__ = "deals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    original_price = Column(Float)
    discounted_price = Column(Float)
    discount_percent = Column(Float)
    url = Column(Text, nullable=False)
    image_url = Column(Text)
    source = Column(SAEnum(Source), nullable=False)
    category = Column(String(100))
    fake_probability = Column(SAEnum(FakeProbability), default=FakeProbability.low)
    is_active = Column(Boolean, default=True)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))


class SavedItem(Base):
    __tablename__ = "saved_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    deal_id = Column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False)
    saved_at = Column(DateTime(timezone=True), server_default=func.now())
