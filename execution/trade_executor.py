import asyncio
from typing import Dict, List, Optional, Tuple
import pandas as pd
from datetime import datetime
import logging
from dataclasses import dataclass


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    status: str
    timestamp: datetime
    filled_quantity: float = 0.0
    average_price: float = 0.0
    fees: float = 0.0


class TradeExecutor:
    def __init__(self, config: Dict, exchange_client: any):
        self.client = exchange_client
        self.max_slippage = config.get('max_slippage', 0.001)  # 10 bps
        self.order_timeout = config.get('order_timeout', 30)  # seconds
        self.retry_attempts = config.get('retry_attempts', 3)
        self.logger = logging.getLogger(__name__)

    async def execute_pairs_trade(
        self,
        pair: str,
        direction: str,
        position_sizes: Dict[str, float],
        prices: Dict[str, float],
        order_book_data: Dict[str, Dict]
    ) -> Tuple[bool, List[OrderResult]]:
        """
        Execute a pairs trade with both legs simultaneously
        """
        try:
            orders: List[OrderResult] = []
            assets = pair.split('_')

            # Prepare orders for both legs
            asset1_side = "sell" if direction == "long" else "buy"
            asset2_side = "buy" if direction == "long" else "sell"

            # Execute orders concurrently
            async with asyncio.TaskGroup() as tg:
                order1_task = tg.create_task(
                    self._execute_single_order(
                        symbol=assets[0],
                        side=asset1_side,
                        quantity=abs(position_sizes[assets[0]]),
                        price=prices[assets[0]],
                        order_book=order_book_data[assets[0]]
                    )
                )

                order2_task = tg.create_task(
                    self._execute_single_order(
                        symbol=assets[1],
                        side=asset2_side,
                        quantity=abs(position_sizes[assets[1]]),
                        price=prices[assets[1]],
                        order_book=order_book_data[assets[1]]
                    )
                )

            # Get results
            order1_result = await order1_task
            order2_result = await order2_task

            orders.extend([order1_result, order2_result])

            # Check if both orders were successful
            success = all(
                order.status == "FILLED" and
                order.filled_quantity == order.quantity
                for order in orders
            )

            if not success:
                # Attempt to cancel any unfilled orders
                await self._cleanup_unfilled_orders(orders)

            return success, orders

        except Exception as e:
            self.logger.error(f"Error executing pairs trade: {e}")
            return False, []

    async def _execute_single_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        order_book: Dict
    ) -> OrderResult:
        """
        Execute a single order with smart order routing
        """
        for attempt in range(self.retry_attempts):
            try:
                # Calculate optimal order type and price
                order_strategy = self._determine_order_strategy(
                    side, quantity, price, order_book
                )

                # Place the order
                order_id = await self.client.create_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    **order_strategy
                )

                # Monitor order until filled or timeout
                start_time = datetime.now()
                while True:
                    order_status = await self.client.get_order(symbol, order_id)

                    if order_status['status'] == 'FILLED':
                        return OrderResult(
                            order_id=order_id,
                            symbol=symbol,
                            side=side,
                            quantity=quantity,
                            price=price,
                            status='FILLED',
                            timestamp=datetime.now(),
                            filled_quantity=float(order_status['executedQty']),
                            average_price=float(order_status['avgPrice']),
                            fees=float(order_status.get('fees', 0.0))
                        )

                    if (datetime.now() - start_time).seconds > self.order_timeout:
                        # Cancel order and retry
                        await self.client.cancel_order(symbol, order_id)
                        break

                    await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.error(
                    f"Error in order execution attempt {attempt}: {e}")
                if attempt == self.retry_attempts - 1:
                    return OrderResult(
                        order_id="",
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        price=price,
                        status='FAILED',
                        timestamp=datetime.now()
                    )

                await asyncio.sleep(1)  # Wait before retrying

    def _determine_order_strategy(
        self,
        side: str,
        quantity: float,
        price: float,
        order_book: Dict
    ) -> Dict:
        """
        Determine optimal order type and price based on order book
        """
        # Calculate available liquidity at each price level
        liquidity = self._analyze_order_book_liquidity(side, order_book)

        # If we can get good fill at market, use market order
        if self._can_execute_market(side, quantity, price, liquidity):
            return {
                'type': 'MARKET'
            }

        # Otherwise, use limit order with smart pricing
        limit_price = self._calculate_limit_price(side, price, order_book)
        return {
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'price': limit_price
        }

    def _analyze_order_book_liquidity(
        self,
        side: str,
        order_book: Dict
    ) -> pd.DataFrame:
        """
        Analyze liquidity available at each price level
        """
        # Get relevant side of order book
        levels = order_book['asks'] if side == 'buy' else order_book['bids']

        # Create DataFrame with cumulative quantities
        df = pd.DataFrame(levels)
        df['cumulative_quantity'] = df['quantity'].cumsum()

        return df
    

    def _can_execute_market(
        self,
        side: str,
        quantity: float,
        price: float,
        liquidity: pd.DataFrame
    ) -> bool:
        """
        Check if market order is feasible based on expected slippage
        """
        # Find the weighted average price for the desired quantity
        executable_levels = liquidity[
            liquidity['cumulative_quantity'] <= quantity
        ]

        if executable_levels.empty:
            return False

        weighted_price = (
            (executable_levels['price'] * executable_levels['quantity']).sum() /
            executable_levels['quantity'].sum()
        )

        # Calculate expected slippage
        slippage = abs(weighted_price - price) / price

        return slippage <= self.max_slippage

    def _calculate_limit_price(
        self,
        side: str,
        price: float,
        order_book: Dict
    ) -> float:
        """
        Calculate optimal limit price based on order book
        """
        if side == 'buy':
            # Find best ask and place limit slightly higher
            best_ask = min(level['price'] for level in order_book['asks'])
            return min(price * (1 + self.max_slippage), best_ask * 1.001)
        else:
            # Find best bid and place limit slightly lower
            best_bid = max(level['price'] for level in order_book['bids'])
            return max(price * (1 - self.max_slippage), best_bid * 0.999)

    async def _cleanup_unfilled_orders(
        self,
        orders: List[OrderResult]
    ) -> None:
        """
        Cancel unfilled orders and handle cleanup
        """
        for order in orders:
            if order.status != "FILLED":
                try:
                    await self.client.cancel_order(
                        symbol=order.symbol,
                        order_id=order.order_id
                    )
                except Exception as e:
                    self.logger.error(f"Error cancelling order: {e}")

    async def close_position(
        self,
        position: Dict,
        order_book_data: Dict[str, Dict]
    ) -> Tuple[bool, List[OrderResult]]:
        """
        Close an existing position
        """
        try:
            orders = []

            # Close each leg of the position
            for symbol, quantity in position['positions'].items():
                side = "sell" if quantity > 0 else "buy"
                price = self._get_current_price(
                    symbol, side, order_book_data[symbol])

                order_result = await self._execute_single_order(
                    symbol=symbol,
                    side=side,
                    quantity=abs(quantity),
                    price=price,
                    order_book=order_book_data[symbol]
                )

                orders.append(order_result)

            success = all(
                order.status == "FILLED"
                for order in orders
            )

            return success, orders

        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            return False, []

    def _get_current_price(
        self,
        symbol: str,
        side: str,
        order_book: Dict
    ) -> float:
        """
        Get current price for a symbol based on order book
        """
        if side == 'buy':
            return min(level['price'] for level in order_book['asks'])
        else:
            return max(level['price'] for level in order_book['bids'])

    async def monitor_orders(
        self,
        orders: List[OrderResult]
    ) -> Dict[str, Dict]:
        """
        Monitor status of multiple orders
        """
        order_updates = {}

        for order in orders:
            try:
                status = await self.client.get_order(
                    symbol=order.symbol,
                    order_id=order.order_id
                )

                order_updates[order.order_id] = {
                    'symbol': order.symbol,
                    'status': status['status'],
                    'filled_quantity': float(status['executedQty']),
                    'average_price': float(status['avgPrice']),
                    'fees': float(status.get('fees', 0.0))
                }

            except Exception as e:
                self.logger.error(
                    f"Error monitoring order {order.order_id}: {e}")
                order_updates[order.order_id] = {
                    'symbol': order.symbol,
                    'status': 'ERROR',
                    'error': str(e)
                }

        return order_updates

    async def calculate_execution_metrics(
        self,
        orders: List[OrderResult]
    ) -> Dict[str, float]:
        """
        Calculate execution quality metrics
        """
        metrics = {
            'total_slippage': 0.0,
            'total_fees': 0.0,
            'average_fill_rate': 0.0,
            'execution_time': 0.0
        }

        for order in orders:
            if order.status == 'FILLED':
                # Calculate slippage
                slippage = abs(order.average_price - order.price) / order.price
                metrics['total_slippage'] += slippage

                # Add fees
                metrics['total_fees'] += order.fees

                # Calculate fill rate
                metrics['average_fill_rate'] += (
                    order.filled_quantity / order.quantity
                )

        # Calculate averages
        num_orders = len([o for o in orders if o.status == 'FILLED'])
        if num_orders > 0:
            metrics['total_slippage'] /= num_orders
            metrics['average_fill_rate'] /= num_orders

            # Calculate total execution time
            start_time = min(order.timestamp for order in orders)
            end_time = max(order.timestamp for order in orders)
            metrics['execution_time'] = (end_time - start_time).total_seconds()

        return metrics

    def validate_order_parameters(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float
    ) -> Tuple[bool, str]:
        """
        Validate order parameters before execution
        """
        try:
            # Check symbol is valid
            symbol_info = self.client.get_symbol_info(symbol)
            if not symbol_info:
                return False, f"Invalid symbol: {symbol}"

            # Check quantity meets minimum
            min_qty = float(symbol_info['minQty'])
            if quantity < min_qty:
                return False, f"Quantity below minimum: {min_qty}"

            # Check quantity precision
            qty_precision = symbol_info['quantityPrecision']
            if not self._check_precision(quantity, qty_precision):
                return False, f"Invalid quantity precision. Must be {qty_precision} decimals"

            # Check price precision
            price_precision = symbol_info['pricePrecision']
            if not self._check_precision(price, price_precision):
                return False, f"Invalid price precision. Must be {price_precision} decimals"

            return True, "Valid order parameters"

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def _check_precision(self, value: float, precision: int) -> bool:
        """
        Check if a value meets required decimal precision
        """
        str_val = f"{value:.10f}".rstrip('0')
        decimal_places = len(str_val.split('.')[-1]) if '.' in str_val else 0
        return decimal_places <= precision
