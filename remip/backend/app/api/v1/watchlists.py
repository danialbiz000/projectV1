from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.models import AdministrativeArea, PropertyListing, Watchlist, WatchlistItem
from app.schemas.listing import WatchlistItemIn, WatchlistItemOut, WatchlistOut

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


def _owned_watchlist(db, user_id: str, watchlist_id: str) -> Watchlist:
    watchlist = db.get(Watchlist, watchlist_id)
    # 404 (not 403) for other users' watchlists: do not leak their existence.
    if watchlist is None or watchlist.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Watchlist not found")
    return watchlist


@router.get("", response_model=list[WatchlistOut])
def list_watchlists(user: CurrentUser, db: DbDep) -> list[Watchlist]:
    return list(db.scalars(select(Watchlist).where(Watchlist.user_id == user.id)))


@router.post("", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
def create_watchlist(user: CurrentUser, db: DbDep, name: str = "Nuova watchlist") -> Watchlist:
    watchlist = Watchlist(user_id=user.id, name=name[:200])
    db.add(watchlist)
    db.commit()
    return watchlist


@router.post(
    "/{watchlist_id}/items", response_model=WatchlistItemOut, status_code=status.HTTP_201_CREATED
)
def add_item(
    watchlist_id: str, body: WatchlistItemIn, user: CurrentUser, db: DbDep
) -> WatchlistItem:
    watchlist = _owned_watchlist(db, user.id, watchlist_id)
    initial_price = None
    if body.kind == "listing":
        if not body.listing_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "listing_id required")
        listing = db.get(PropertyListing, body.listing_id)
        if listing is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
        initial_price = listing.current_price
    elif body.kind == "area":
        if not body.area_id or db.get(AdministrativeArea, body.area_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Area not found")
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "kind must be 'listing' or 'area'")

    item = WatchlistItem(
        watchlist_id=watchlist.id,
        kind=body.kind,
        listing_id=body.listing_id,
        area_id=body.area_id,
        note=body.note[:1000],
        initial_price=initial_price,
        thresholds=body.thresholds,
        notify=body.notify,
    )
    db.add(item)
    db.commit()
    return item


@router.delete("/{watchlist_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(watchlist_id: str, item_id: str, user: CurrentUser, db: DbDep) -> None:
    watchlist = _owned_watchlist(db, user.id, watchlist_id)
    item = db.get(WatchlistItem, item_id)
    if item is None or item.watchlist_id != watchlist.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    db.delete(item)
    db.commit()
