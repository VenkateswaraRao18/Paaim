"""
Seed two real tenants — the demo's whole point.

Two factories that share a process and share nothing else: different industry,
different vocabulary, different plant, different users. If PAAIM is a product,
these two coexist. If it is one plant's demo with a config screen, they corrupt
each other — which is exactly what happened until the vocabulary, mappings,
monitors and watchers stopped being global.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import delete, select

from paaim.auth.deps import get_auth_service
from paaim.models import (
    AsyncSessionLocal, FactoryModel, UserModel, create_tables,
)

TENANTS = [
    {
        "id": "northfield_foods",
        "name": "Northfield Foods",
        "location": "Madison, WI",
        "industry": "food_beverage",
        "vocabulary_pack": "food_processing",
        "users": [
            ("ops@northfield.example", "northfield123", "Dana Reyes", "supervisor"),
        ],
    },
    {
        "id": "precision_parts",
        "name": "Precision Parts Co",
        "location": "Sheffield, UK",
        "industry": "automotive",
        "vocabulary_pack": "cnc_machining",
        "users": [
            ("ops@precision.example", "precision123", "Sam Okafor", "supervisor"),
        ],
    },
]


async def main(reset: bool = False) -> None:
    await create_tables()
    auth = get_auth_service()

    async with AsyncSessionLocal() as db:
        if reset:
            await db.execute(delete(UserModel))
            await db.execute(delete(FactoryModel))
            await db.commit()

        for t in TENANTS:
            f = (await db.execute(
                select(FactoryModel).where(FactoryModel.id == t["id"])
            )).scalar_one_or_none()
            if not f:
                f = FactoryModel(id=t["id"])
                db.add(f)
            f.name, f.location = t["name"], t["location"]
            f.industry, f.vocabulary_pack = t["industry"], t["vocabulary_pack"]
            f.is_active = True

            for email, password, full_name, role in t["users"]:
                u = (await db.execute(
                    select(UserModel).where(UserModel.email == email)
                )).scalar_one_or_none()
                if not u:
                    u = UserModel(id=f"user_{email.split('@')[0]}_{t['id'][:6]}", email=email)
                    db.add(u)
                # Hashed, always. The old login compared `password == "password"`
                # in an if/elif and there were no users at all.
                u.password_hash = auth.hash_password(password)
                u.full_name, u.role, u.factory_id, u.is_active = full_name, role, t["id"], True

        await db.commit()

    # Each tenant's vocabulary is created from its own pack, in its own file.
    from paaim.normalization.vocabulary import get_vocabulary_store
    for t in TENANTS:
        store = get_vocabulary_store(t["id"])
        store.apply_pack(t["vocabulary_pack"])
        print(f"  {t['id']:18} vocabulary={t['vocabulary_pack']:16} "
              f"({len(store.as_dict())} signals) -> {store.path}")

    print("\nTenants seeded:\n")
    for t in TENANTS:
        print(f"  {t['name']}  ({t['id']})")
        for email, password, full_name, role in t["users"]:
            print(f"     {email:28} / {password:14} {role}")
    print("\nThese two share nothing: separate vocabularies, mappings, monitors,")
    print("watchers, machines, costs, orders and incidents.")


if __name__ == "__main__":
    asyncio.run(main(reset="--reset" in sys.argv))
