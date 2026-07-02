from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
import schemas


def list_dishes(db: Session, category: str | None = None):
    query = db.query(models.Dish)
    if category:
        query = query.filter(models.Dish.category == category)
    return query.order_by(models.Dish.id.desc()).all()


def get_dish(db: Session, dish_id: int):
    dish = db.get(models.Dish, dish_id)
    if not dish:
        raise HTTPException(status_code=404, detail="菜品不存在")
    return dish


def create_dish(db: Session, data: schemas.DishCreate):
    dish = models.Dish(**data.model_dump())
    db.add(dish)
    db.commit()
    db.refresh(dish)
    return dish


def update_dish(db: Session, dish_id: int, data: schemas.DishUpdate):
    dish = get_dish(db, dish_id)
    for key, value in data.model_dump().items():
        setattr(dish, key, value)
    db.commit()
    db.refresh(dish)
    return dish


def delete_dish(db: Session, dish_id: int):
    dish = get_dish(db, dish_id)
    db.delete(dish)
    db.commit()


def create_order(db: Session, data: schemas.OrderCreate):
    dish_ids = {item.dish_id for item in data.items}
    dishes = db.query(models.Dish).filter(models.Dish.id.in_(dish_ids)).all()
    dish_map = {dish.id: dish for dish in dishes}
    missing = dish_ids - dish_map.keys()
    if missing:
        raise HTTPException(status_code=400, detail=f"菜品不存在：{sorted(missing)}")

    order = models.Order(
        note=data.note,
        desired_time=data.desired_time,
        customer_id=data.customer_id,
    )
    db.add(order)
    db.flush()
    for item in data.items:
        dish = dish_map[item.dish_id]
        order.items.append(
            models.OrderItem(
                dish_id=dish.id,
                dish_name=dish.name,
                price=dish.price,
                quantity=item.quantity,
            )
        )
    db.commit()
    db.refresh(order)
    return order


def list_orders(db: Session):
    return db.query(models.Order).order_by(models.Order.created_at.desc()).all()


def list_customer_orders(db: Session, customer_id: str):
    return (
        db.query(models.Order)
        .filter(models.Order.customer_id == customer_id)
        .order_by(models.Order.created_at.desc())
        .all()
    )


def get_order(db: Session, order_id: int):
    order = db.get(models.Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


def update_order_status(db: Session, order_id: int, status: str):
    order = get_order(db, order_id)
    order.status = status
    db.commit()
    db.refresh(order)
    return order


def get_review(db: Session, order_id: int):
    get_order(db, order_id)
    review = (
        db.query(models.Review)
        .filter(models.Review.order_id == order_id)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="该订单还没有评价")
    return review


def create_review(db: Session, order_id: int, data: schemas.ReviewCreate):
    order = get_order(db, order_id)
    if order.status != "已完成":
        raise HTTPException(status_code=400, detail="订单完成后才能评价")
    if order.review:
        raise HTTPException(status_code=409, detail="该订单已经评价过了")

    review = models.Review(order_id=order_id, **data.model_dump())
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该订单已经评价过了")
    db.refresh(review)
    return review


def get_stats_summary(db: Session):
    total_orders = db.query(func.count(models.Order.id)).scalar() or 0
    completed_orders = (
        db.query(func.count(models.Order.id))
        .filter(models.Order.status == "已完成")
        .scalar()
        or 0
    )
    last_order_at = db.query(func.max(models.Order.created_at)).scalar()
    return {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "last_order_at": last_order_at,
    }


def get_dish_stats(db: Session):
    rows = (
        db.query(
            models.OrderItem.dish_id,
            models.OrderItem.dish_name,
            func.sum(models.OrderItem.quantity).label("total_quantity"),
            func.max(models.Order.created_at).label("last_ordered_at"),
        )
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .group_by(models.OrderItem.dish_id, models.OrderItem.dish_name)
        .order_by(
            func.sum(models.OrderItem.quantity).desc(),
            func.max(models.Order.created_at).desc(),
        )
        .all()
    )
    return [
        {
            "dish_id": row.dish_id,
            "dish_name": row.dish_name,
            "total_quantity": row.total_quantity,
            "last_ordered_at": row.last_ordered_at,
        }
        for row in rows
    ]


def get_recent_orders(db: Session):
    return (
        db.query(models.Order)
        .order_by(models.Order.created_at.desc())
        .limit(10)
        .all()
    )
