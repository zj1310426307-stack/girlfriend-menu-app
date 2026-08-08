from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
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
