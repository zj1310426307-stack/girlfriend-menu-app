from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
import schemas


def list_dishes(db: Session, category: str | None = None):
    query = db.query(models.Dish).filter(models.Dish.is_active.is_(True))
    if category:
        query = query.filter(models.Dish.category == category)
    return query.order_by(models.Dish.id.desc()).all()


def get_dish(db: Session, dish_id: int):
    dish = (
        db.query(models.Dish)
        .filter(models.Dish.id == dish_id, models.Dish.is_active.is_(True))
        .first()
    )
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
    # Keep historical order items intact. A physical delete can fail on
    # PostgreSQL once the dish has been ordered because of the foreign key.
    dish.is_active = False
    db.commit()


def list_favorite_dishes(db: Session, customer_id: str):
    return (
        db.query(models.Dish)
        .join(models.FavoriteDish, models.FavoriteDish.dish_id == models.Dish.id)
        .filter(
            models.FavoriteDish.customer_id == customer_id,
            models.Dish.is_active.is_(True),
        )
        .order_by(models.FavoriteDish.created_at.desc())
        .all()
    )


def add_favorite_dish(db: Session, customer_id: str, dish_id: int):
    dish = get_dish(db, dish_id)
    existing = (
        db.query(models.FavoriteDish)
        .filter(
            models.FavoriteDish.customer_id == customer_id,
            models.FavoriteDish.dish_id == dish_id,
        )
        .first()
    )
    if existing:
        return dish
    db.add(models.FavoriteDish(customer_id=customer_id, dish_id=dish_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return dish


def remove_favorite_dish(db: Session, customer_id: str, dish_id: int):
    favorite = (
        db.query(models.FavoriteDish)
        .filter(
            models.FavoriteDish.customer_id == customer_id,
            models.FavoriteDish.dish_id == dish_id,
        )
        .first()
    )
    if favorite:
        db.delete(favorite)
        db.commit()


def create_order(db: Session, data: schemas.OrderCreate):
    dish_ids = {item.dish_id for item in data.items}
    dishes = (
        db.query(models.Dish)
        .filter(models.Dish.id.in_(dish_ids), models.Dish.is_active.is_(True))
        .all()
    )
    dish_map = {dish.id: dish for dish in dishes}
    missing = dish_ids - dish_map.keys()
    if missing:
        raise HTTPException(status_code=400, detail=f"菜品不存在或已经下架：{sorted(missing)}")

    if data.source_order_id:
        source_order = get_order(db, data.source_order_id)
        if not data.customer_id or source_order.customer_id != data.customer_id:
            raise HTTPException(status_code=403, detail="不能再次点其他人的订单")

    order = models.Order(
        note=data.note,
        desired_time=data.desired_time,
        customer_id=data.customer_id,
        source_order_id=data.source_order_id,
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


def repeat_order_draft(db: Session, order_id: int, customer_id: str):
    """Build an editable cart draft without creating a submitted order."""
    order = get_order(db, order_id)
    if not order.customer_id or order.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="这张点菜单不属于当前设备")

    dish_ids = {item.dish_id for item in order.items}
    current_dishes = db.query(models.Dish).filter(models.Dish.id.in_(dish_ids)).all()
    dish_map = {dish.id: dish for dish in current_dishes}
    items = []
    unavailable_names = []
    for item in order.items:
        dish = dish_map.get(item.dish_id)
        available = bool(dish and dish.is_active)
        if not available:
            unavailable_names.append(item.dish_name)
        items.append(
            {
                "dish_id": item.dish_id,
                "name": dish.name if dish else item.dish_name,
                "description": dish.description if dish else "",
                "category": dish.category if dish else "",
                "price": dish.price if dish else item.price,
                "image_url": dish.image_url if dish else "",
                "quantity": item.quantity,
                "available": available,
            }
        )
    return {
        "source_order_id": order.id,
        "note": order.note,
        "items": items,
        "unavailable_names": unavailable_names,
    }


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


def get_favorite_ranking(db: Session, customer_id: str, limit: int = 5):
    """Rank this device's dishes from submitted orders, reviews and favorites.

    A review belongs to an order, so its rating contributes to every dish in that
    order. Repeat orders receive a modest boost without overwhelming actual order
    frequency. This keeps the ranking useful even before many reviews exist.
    """
    rows = (
        db.query(
            models.Dish.id.label("dish_id"),
            models.Dish.name.label("name"),
            func.sum(models.OrderItem.quantity).label("count"),
            func.avg(models.Review.rating).label("rating"),
        )
        .join(models.OrderItem, models.OrderItem.dish_id == models.Dish.id)
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .outerjoin(models.Review, models.Review.order_id == models.Order.id)
        .filter(
            models.Order.customer_id == customer_id,
            models.Dish.is_active.is_(True),
        )
        .group_by(models.Dish.id, models.Dish.name)
        .all()
    )
    repeat_rows = (
        db.query(
            models.OrderItem.dish_id,
            func.count(func.distinct(models.Order.id)).label("repeat_count"),
        )
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .filter(
            models.Order.customer_id == customer_id,
            models.Order.source_order_id.is_not(None),
        )
        .group_by(models.OrderItem.dish_id)
        .all()
    )
    repeat_counts = {row.dish_id: int(row.repeat_count or 0) for row in repeat_rows}
    favorite_ids = {
        row.dish_id
        for row in db.query(models.FavoriteDish.dish_id)
        .filter(models.FavoriteDish.customer_id == customer_id)
        .all()
    }

    ranking = []
    for row in rows:
        count = int(row.count or 0)
        rating = round(float(row.rating), 1) if row.rating is not None else None
        repeat_count = repeat_counts.get(row.dish_id, 0)
        is_favorite = row.dish_id in favorite_ids
        rating_basis = rating if rating is not None else 3.0
        score = rating_basis * count * (1 + repeat_count * 0.25)
        if is_favorite:
            score += 2
        ranking.append(
            {
                "dish_id": row.dish_id,
                "name": row.name,
                "count": count,
                "rating": rating,
                "repeat_count": repeat_count,
                "is_favorite": is_favorite,
                "score": round(score, 2),
            }
        )

    ranking.sort(key=lambda item: (item["score"], item["count"]), reverse=True)
    return ranking[:limit]
