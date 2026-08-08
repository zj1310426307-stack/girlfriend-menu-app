from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


OrderStatus = Literal["待接单", "已接单", "制作中", "已完成", "暂时做不了"]


class AdminLogin(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    invite_code: str = Field(min_length=1, max_length=100)


class AdminLoginOut(BaseModel):
    token: str


class DiceRoomCreate(BaseModel):
    invite_code: str = Field(min_length=1, max_length=100)


class DiceRoomOut(BaseModel):
    room_code: str


class DishBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    category: str = Field(min_length=1, max_length=50)
    price: float = Field(ge=0)
    image_url: str = Field(default="", max_length=500)


class DishCreate(DishBase):
    pass


class DishUpdate(DishBase):
    pass


class DishOut(DishBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class OrderItemCreate(BaseModel):
    dish_id: int
    quantity: int = Field(default=1, ge=1, le=99)


class OrderCreate(BaseModel):
    items: list[OrderItemCreate] = Field(min_length=1, max_length=30)
    note: str = Field(default="", max_length=500)
    desired_time: str = Field(default="", max_length=50)
    customer_id: str | None = Field(default=None, max_length=100)
    source_order_id: int | None = Field(default=None, ge=1)


class OrderRepeatItem(BaseModel):
    dish_id: int
    name: str
    description: str = ""
    category: str = ""
    price: float
    image_url: str = ""
    quantity: int
    available: bool


class OrderRepeatDraft(BaseModel):
    source_order_id: int
    note: str = ""
    items: list[OrderRepeatItem]
    unavailable_names: list[str]


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dish_id: int
    dish_name: str
    price: float
    quantity: int


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    want_again: Literal["想吃", "一般", "暂时不想"]
    comment: str = Field(default="", max_length=500)


class ReviewOut(ReviewCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    created_at: datetime


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: OrderStatus
    note: str
    desired_time: str
    customer_id: str | None = None
    source_order_id: int | None = None
    created_at: datetime
    items: list[OrderItemOut]
    review: ReviewOut | None = None
    has_review: bool


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class StatsSummary(BaseModel):
    total_orders: int
    completed_orders: int
    last_order_at: datetime | None


class DishStats(BaseModel):
    dish_id: int
    dish_name: str
    total_quantity: int
    last_ordered_at: datetime
