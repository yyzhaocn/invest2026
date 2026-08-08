# Chapter 7: Object-Oriented Programming

## Core Idea
Design for **responsibilities, not hierarchies**: small focused classes with shallow hierarchies, composition over deep inheritance, and interfaces (ABC) where pluggability matters — the foundation for portfolio/position/price-source models in later chapters.

## Frameworks Introduced
- **Composition-first class design**: group attributes+behavior that belong to one concept; hierarchies stay shallow; classes stay focused; inheritance only when classes share a common interface.
- **PriceSource Interface pattern**: `ABC` + `@abstractmethod get_price(symbol)` lets file loader and API client plug into the same strategy/analytics code without changing callers (dependency on interface, not implementation).
- **Dataclass for record types**: `@dataclass` auto-generates `__init__`/`__repr__` from type annotations — ideal for simple financial records (Position, Quote) with a few methods.
- **Property invariants**: `@property` + setter guards state (e.g. reject negative quantity) while callers still use plain attribute syntax.

## Key Concepts
- **self**: instance reference inside methods; attributes attach to self.
- **`__repr__`**: concise machine-oriented representation for REPL/logs — worth the small investment for debugging.
- **PEP 8 naming**: CamelCase classes (`Position`), snake_case methods/attrs (`market_value()`), `_qty` underscore for internal state.
- **Delegation**: `Portfolio.total_value()` sums `p.market_value()` — small objects calling each other.
- **Invariant self-checks**: `assert portfolio.total_value() == 10*180.0 + 5*350.0` catches unintended logic changes.

## Mental Models
- Think of classes as *bundles of data + behavior with a discoverable interface*, not taxonomy.
- Use X when Y: *dataclass when* the class is mostly stored fields; *ABC when* multiple providers must satisfy one contract; *property when* state needs invariants.
- Prefer composition (Portfolio holds a list of Positions) over inheritance chains.

## Anti-patterns
- **Deep class hierarchies** nobody can trace — use composition.
- **Boilerplate classes** with hand-written `__init__`/`__repr__` where `@dataclass` suffices.
- **Letting callers mutate internal state directly** when a property can enforce invariants.
- **Over-OOP**: don't turn analytics code into hierarchy for its own sake.

## Code Examples
```python
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class Position:
    symbol: str
    qty: float
    price: float
    def market_value(self) -> float:
        return self.qty * self.price

class Portfolio:
    def __init__(self, positions: list[Position]):
        self.positions = positions
    def total_value(self) -> float:
        return sum(p.market_value() for p in self.positions)
    def value_by_symbol(self, symbol: str) -> float:
        return sum(p.market_value() for p in self.positions if p.symbol == symbol)

class PriceSource(ABC):
    @abstractmethod
    def get_price(self, symbol: str) -> float: ...

class DictPriceSource(PriceSource):
    def __init__(self, prices: dict[str, float]): self.prices = prices
    def get_price(self, symbol: str) -> float: return self.prices[symbol]

# property invariant
@dataclass
class SafePosition:
    symbol: str
    _qty: float
    price: float
    @property
    def qty(self) -> float: return self._qty
    @qty.setter
    def qty(self, value: float) -> None:
        if value < 0: raise ValueError("quantity cannot be negative")
        self._qty = value
```
- **What it demonstrates**: dataclass records, delegation, ABC interface, property invariant.

## Worked Example
Portfolio = [Position("AAPL",10,180.0), Position("MSFT",5,350.0)] → `total_value() == 3550.0`; `value_by_symbol("AAPL")` sums across multiple AAPL lots (e.g. 10×180 + 5×182 = 2710). `SafePosition.qty = -5` raises ValueError — invariant enforced at assignment.

## Key Takeaways
1. Small focused classes that call each other beat deep hierarchies.
2. `@dataclass` removes boilerplate for record types.
3. ABC interfaces make data providers pluggable without changing callers.
4. Properties enforce invariants while preserving attribute syntax.
5. `assert` self-checks catch logic drift early.

## Connects To
- **Ch 21**: the small asset management library (portfolios, positions) builds on these patterns
- **Ch 24**: market/broker objects for trading simulations
