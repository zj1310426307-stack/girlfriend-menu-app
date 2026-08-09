from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class Dish(Base):
    __tablename__ = "dishes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    category = Column(String(50), nullable=False, index=True)
    price = Column(Float, nullable=False, default=0)
    image_url = Column(String(500), default="")
    cook_time = Column(Integer, nullable=True)
    difficulty = Column(Integer, nullable=True)
    spicy_level = Column(Integer, nullable=True, default=0)
    tags = Column(JSON, nullable=True, default=list)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(20), nullable=False, default="待接单", index=True)
    note = Column(Text, default="")
    desired_time = Column(String(50), default="")
    customer_id = Column(String(100), nullable=True, index=True)
    source_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    review = relationship(
        "Review",
        back_populates="order",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    @property
    def has_review(self):
        return self.review is not None


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    dish_id = Column(Integer, ForeignKey("dishes.id"), nullable=False)
    dish_name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False, default=1)

    order = relationship("Order", back_populates="items")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True, index=True)
    rating = Column(Integer, nullable=False)
    want_again = Column(String(20), nullable=False)
    comment = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    order = relationship("Order", back_populates="review")


class FavoriteDish(Base):
    __tablename__ = "favorite_dishes"
    __table_args__ = (
        UniqueConstraint("customer_id", "dish_id", name="uq_favorite_customer_dish"),
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)
    dish_id = Column(Integer, ForeignKey("dishes.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    icon = Column(String(20), nullable=False, default="玩")
    type = Column(String(50), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default="coming_soon", index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class GameRoom(Base):
    __tablename__ = "game_rooms"

    id = Column(Integer, primary_key=True, index=True)
    room_code = Column(String(12), nullable=False, unique=True, index=True)
    game_type = Column(String(50), nullable=False, index=True)
    creator = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="waiting", index=True)
    max_players = Column(Integer, nullable=False, default=2)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)


class LoveScore(Base):
    __tablename__ = "love_scores"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "type",
            "related_id",
            name="uq_love_score_source",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)
    score = Column(Integer, nullable=False)
    type = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=False, default="")
    related_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    @property
    def time(self):
        return self.created_at
