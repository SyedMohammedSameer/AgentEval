from inventory.ledger import Entry, InsufficientStock


class Store:
    def __init__(self, stock: dict):
        self._items = {sku: Entry(on_hand=qty) for sku, qty in stock.items()}

    def available(self, sku: str) -> int:
        entry = self._items.get(sku)
        return entry.available if entry else 0

    def reserve(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        entry = self._items.get(sku)
        if entry is None:
            raise InsufficientStock(sku)
        # Reserve against what is still free, not against gross stock.
        if qty > entry.available:
            raise InsufficientStock(sku)
        entry.reserved += qty

    def release(self, sku: str, qty: int) -> None:
        entry = self._items.get(sku)
        if entry is None:
            return
        # Floor at zero: you cannot un-reserve more than was reserved.
        entry.reserved = max(0, entry.reserved - qty)

    def commit(self, sku: str, qty: int) -> None:
        """Ship reserved units: they leave both reserved and on_hand."""
        entry = self._items[sku]
        entry.reserved -= qty
        entry.on_hand -= qty
