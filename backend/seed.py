from sqlalchemy.orm import Session

import models


SAMPLE_DISHES = [
    {
        "name": "番茄炒蛋",
        "description": "酸甜下饭，鸡蛋嫩嫩的，永远不会出错的家常味。",
        "category": "家常菜",
        "price": 18,
        "image_url": "https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=900&q=80",
    },
    {
        "name": "可乐鸡翅",
        "description": "酱汁浓郁，甜咸刚好，每一只都认真收汁。",
        "category": "肉肉",
        "price": 32,
        "image_url": "https://images.unsplash.com/photo-1527477396000-e27163b481c2?auto=format&fit=crop&w=900&q=80",
    },
    {
        "name": "蒜蓉西兰花",
        "description": "清爽脆嫩，蒜香十足，负责给今天补一点绿色。",
        "category": "蔬菜",
        "price": 16,
        "image_url": "https://images.unsplash.com/photo-1459411621453-7b03977f4bfc?auto=format&fit=crop&w=900&q=80",
    },
    {
        "name": "鱼香肉丝",
        "description": "酸甜微辣，肉丝嫩滑，配米饭特别香。",
        "category": "肉肉",
        "price": 28,
        "image_url": "",
    },
    {
        "name": "爱心水果酸奶杯",
        "description": "当季水果、浓稠酸奶和一点点蜂蜜。",
        "category": "甜品",
        "price": 15,
        "image_url": "https://images.unsplash.com/photo-1488477181946-6428a0291777?auto=format&fit=crop&w=900&q=80",
    },
    {
        "name": "紫菜蛋花汤",
        "description": "轻盈鲜香，暖胃又舒服。",
        "category": "汤",
        "price": 10,
        "image_url": "https://images.unsplash.com/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=900&q=80",
    },
    {
        "name": "蒜蓉娃娃菜",
        "description": "清甜爽口，铺满香香的蒜蓉。",
        "category": "蔬菜",
        "price": 16,
        "image_url": "",
    },
    {
        "name": "油焖虾",
        "description": "虾肉鲜嫩，酱汁浓郁，甜咸刚刚好。",
        "category": "海鲜",
        "price": 38,
        "image_url": "",
    },
    {
        "name": "糖醋肉",
        "description": "外酥里嫩，酸甜开胃，是快乐的下饭菜。",
        "category": "肉肉",
        "price": 32,
        "image_url": "",
    },
    {
        "name": "松鼠鱼",
        "description": "酥脆鱼肉裹上酸甜酱汁，好看又好吃。",
        "category": "海鲜",
        "price": 58,
        "image_url": "",
    },
    {
        "name": "番茄牛腩",
        "description": "牛腩软烂入味，番茄汤汁浓郁暖胃。",
        "category": "肉肉",
        "price": 42,
        "image_url": "",
    },
    {
        "name": "麻辣香锅",
        "description": "丰富食材一锅炒香，麻辣过瘾又下饭。",
        "category": "肉肉",
        "price": 48,
        "image_url": "",
    },
    {
        "name": "咖喱鸡",
        "description": "鸡肉软嫩，咖喱浓香，拌米饭特别满足。",
        "category": "肉肉",
        "price": 32,
        "image_url": "",
    },
    {
        "name": "干锅花菜",
        "description": "花菜爽脆入味，锅气十足，微辣更香。",
        "category": "蔬菜",
        "price": 22,
        "image_url": "",
    },
    {
        "name": "干锅豆角",
        "description": "豆角煸得焦香，咸香微辣很下饭。",
        "category": "蔬菜",
        "price": 22,
        "image_url": "",
    },
    {
        "name": "烧茄子",
        "description": "茄子软糯入味，酱香浓郁。",
        "category": "蔬菜",
        "price": 20,
        "image_url": "",
    },
    {
        "name": "地三鲜",
        "description": "土豆、茄子和青椒，经典东北家常味。",
        "category": "蔬菜",
        "price": 22,
        "image_url": "",
    },
    {
        "name": "酸辣汤",
        "description": "酸辣鲜香，开胃又暖身。",
        "category": "汤",
        "price": 16,
        "image_url": "",
    },
    {
        "name": "香菜牛肉",
        "description": "牛肉滑嫩，香菜清香，鲜辣爽口。",
        "category": "肉肉",
        "price": 36,
        "image_url": "",
    },
]

GAME_CATALOG = [
    {"name": "大话骰", "icon": "骰", "type": "dice", "status": "available"},
    {"name": "五子棋", "icon": "棋", "type": "gomoku", "status": "available"},
    {"name": "飞行棋", "icon": "飞", "type": "aeroplane", "status": "coming_soon"},
    {"name": "斗地主", "icon": "牌", "type": "landlord", "status": "coming_soon"},
    {"name": "斗兽棋", "icon": "兽", "type": "jungle", "status": "coming_soon"},
    {"name": "中国象棋", "icon": "象", "type": "chinese_chess", "status": "coming_soon"},
]


def seed_dishes(db: Session):
    existing_names = {name for (name,) in db.query(models.Dish.name).all()}
    default_tags = {
        "家常菜": ["家常", "下饭"],
        "肉肉": ["下饭", "满足"],
        "蔬菜": ["清爽", "家常"],
        "甜品": ["甜甜", "饭后"],
        "汤": ["暖胃", "舒服"],
        "海鲜": ["鲜香", "认真做"],
    }
    missing_dishes = [
        models.Dish(
            **dish,
            cook_time=35 if dish["category"] not in {"汤", "甜品"} else 20,
            difficulty=2,
            spicy_level=1 if any(word in dish["name"] for word in ("辣", "鱼香", "干锅")) else 0,
            tags=default_tags.get(dish["category"], ["今日推荐"]),
        )
        for dish in SAMPLE_DISHES
        if dish["name"] not in existing_names
    ]
    if missing_dishes:
        db.add_all(missing_dishes)
        db.commit()


def seed_games(db: Session):
    existing_types = {game_type for (game_type,) in db.query(models.Game.type).all()}
    missing_games = [
        models.Game(**game)
        for game in GAME_CATALOG
        if game["type"] not in existing_types
    ]
    if missing_games:
        db.add_all(missing_games)
    changed = bool(missing_games)
    gomoku = db.query(models.Game).filter(models.Game.type == "gomoku").first()
    if gomoku and gomoku.status != "available":
        gomoku.status = "available"
        changed = True
    if changed:
        db.commit()


if __name__ == "__main__":
    from database import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_dishes(session)
        seed_games(session)
    print("测试菜品数据已准备好。")
