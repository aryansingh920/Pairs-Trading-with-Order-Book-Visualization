import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import asyncio
import websockets
import json
import logging


class OrderBook:
    def __init__(self, symbol: str, depth: int = 10):
        self.symbol = symbol
        self.depth = depth
        self.bids: Dict[float, float] = {}
        self.asks: Dict[float, float] = {}
        self.last_update_id = None
        self.logger = logging.getLogger(__name__)

    async def update(self, data: Dict) -> None:
        """
        Update the order book with new data
        """
        if self.last_update_id is None:
            # First update, initialize the order book
            self.bids = {float(price): float(qty)
                         for price, qty in data['bids']}
            self.asks = {float(price): float(qty)
                         for price, qty in data['asks']}
            self.last_update_id = data['lastUpdateId']
        else:
            # Process incremental updates
            for price, qty in data['bids']:
                price, qty = float(price), float(qty)
                if qty == 0:
                    self.bids.pop(price, None)
                else:
                    self.bids[price] = qty

            for price, qty in data['asks']:
                price, qty = float(price), float(qty)
                if qty == 0:
                    self.asks.pop(price, None)
                else:
                    self.asks[price] = qty

    def get_order_book_snapshot(self) -> Dict[str, pd.DataFrame]:
        """
        Get current order book snapshot as DataFrame
        """
        bids_df = pd.DataFrame(
            [[price, qty] for price, qty in sorted(
                self.bids.items(), reverse=True
            )[:self.depth]],
            columns=['price', 'quantity']
        )

        asks_df = pd.DataFrame(
            [[price, qty] for price, qty in sorted(
                self.asks.items()
            )[:self.depth]],
            columns=['price', 'quantity']
        )

        return {
            'bids': bids_df,
            'asks': asks_df
        }

    def get_market_depth(self, levels: int = None) -> Tuple[float, float]:
        """
        Calculate total market depth up to specified levels
        """
        if levels is None:
            levels = self.depth

        bid_depth = sum(
            qty for _, qty in sorted(
                self.bids.items(), reverse=True
            )[:levels]
        )
        ask_depth = sum(
            qty for _, qty in sorted(
                self.asks.items()
            )[:levels]
        )

        return bid_depth, ask_depth

    def get_weighted_mid_price(self, volume_weight: float = 0.5) -> float:
        """
        Calculate volume-weighted mid price
        """
        best_bid = max(self.bids.keys()) if self.bids else 0
        best_ask = min(self.asks.keys()) if self.asks else 0

        if best_bid == 0 or best_ask == 0:
            return 0

        weighted_price = (
            best_bid * (1 - volume_weight) +
            best_ask * volume_weight
        )

        return weighted_price

    def estimate_slippage(
        self,
        side: str,
        quantity: float,
        price_tolerance: float = 0.01
    ) -> float:
        """
        Estimate slippage for a given order size
        """
        if side.lower() not in ['buy', 'sell']:
            raise ValueError("Side must be 'buy' or 'sell'")

        orders = sorted(self.asks.items()) if side.lower() == 'buy' else \
            sorted(self.bids.items(), reverse=True)

        remaining_qty = quantity
        total_cost = 0

        for price, available_qty in orders:
            executable_qty = min(remaining_qty, available_qty)
            total_cost += executable_qty * price
            remaining_qty -= executable_qty

            if remaining_qty <= 0:
                break

        if remaining_qty > 0:
            return float('inf')  # Not enough liquidity

        avg_price = total_cost / quantity
        reference_price = min(self.asks.keys()) if side.lower() == 'buy' else \
            max(self.bids.keys())

        return (avg_price - reference_price) / reference_price
