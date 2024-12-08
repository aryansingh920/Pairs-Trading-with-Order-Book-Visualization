import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging
from datetime import datetime


@dataclass
class Trade:
    entry_time: datetime
    exit_time: Optional[datetime]
    pair: str
    direction: str
    entry_prices: Dict[str, float]
    exit_prices: Optional[Dict[str, float]]
    positions: Dict[str, float]
    pnl: float
    return_pct: float
    trade_duration: Optional[pd.Timedelta]
    entry_z_score: float
    exit_z_score: Optional[float]


class PairsBacktester:
    def __init__(self, config: Dict):
        self.initial_capital = config.get('initial_capital', 1000000)
        self.position_size = config.get('position_size', 0.1)  # 10% of capital
        self.transaction_costs = config.get(
            'transaction_costs', 0.001)  # 10 bps
        self.z_score_threshold = config.get('z_score_threshold', 2.0)
        self.logger = logging.getLogger(__name__)

        # Initialize tracking variables
        self.current_capital = self.initial_capital
        self.trades: List[Trade] = []
        self.current_positions: Dict[str, Dict] = {}
        self.equity_curve = []

    def run_backtest(
        self,
        signals_df: pd.DataFrame,
        price_data: Dict[str, pd.DataFrame],
        hedge_ratios: Dict[str, float]
    ) -> Dict:
        """
        Run backtest using generated signals and price data
        """
        try:
            # Sort signals by timestamp
            signals_df = signals_df.sort_values('timestamp')

            # Process each signal
            for _, signal in signals_df.iterrows():
                self._process_signal(signal, price_data, hedge_ratios)

                # Update equity curve
                self.equity_curve.append({
                    'timestamp': signal.timestamp,
                    'equity': self._calculate_current_equity(price_data, signal.timestamp)
                })

            # Close any remaining positions at the end
            self._close_all_positions(
                price_data, signals_df.iloc[-1].timestamp)

            # Calculate backtest results
            results = self._calculate_backtest_results()

            return results

        except Exception as e:
            self.logger.error(f"Error in backtest: {e}")
            raise

    def _process_signal(
        self,
        signal: pd.Series,
        price_data: Dict[str, pd.DataFrame],
        hedge_ratios: Dict[str, float]
    ) -> None:
        """
        Process individual trading signal
        """
        pair = signal.pair
        assets = pair.split('_')

        if signal.signal_type == 'entry':
            # Calculate position sizes
            position_value = self.current_capital * self.position_size
            hedge_ratio = hedge_ratios[pair]

            if signal.direction == 'long':
                positions = {
                    # Short first asset
                    assets[0]: -position_value / signal.asset1_price,
                    assets[1]: position_value / \
                    signal.asset2_price    # Long second asset
                }
            else:  # short
                positions = {
                    # Long first asset
                    assets[0]: position_value / signal.asset1_price,
                    assets[1]: -position_value / \
                    signal.asset2_price   # Short second asset
                }

            # Record trade
            self.current_positions[pair] = {
                'direction': signal.direction,
                'positions': positions,
                'entry_prices': {
                    assets[0]: signal.asset1_price,
                    assets[1]: signal.asset2_price
                },
                'entry_time': signal.timestamp,
                'entry_z_score': signal.z_score
            }

            # Deduct transaction costs
            self.current_capital -= (position_value *
                                     2 * self.transaction_costs)

        elif signal.signal_type == 'exit' and pair in self.current_positions:
            # Close position and calculate PnL
            entry_data = self.current_positions[pair]

            # Calculate PnL
            pnl = self._calculate_trade_pnl(
                entry_data,
                {assets[0]: signal.asset1_price,
                    assets[1]: signal.asset2_price},
                pair
            )

            # Record completed trade
            self.trades.append(
                Trade(
                    entry_time=entry_data['entry_time'],
                    exit_time=signal.timestamp,
                    pair=pair,
                    direction=entry_data['direction'],
                    entry_prices=entry_data['entry_prices'],
                    exit_prices={
                        assets[0]: signal.asset1_price,
                        assets[1]: signal.asset2_price
                    },
                    positions=entry_data['positions'],
                    pnl=pnl,
                    return_pct=pnl / self.initial_capital,
                    trade_duration=signal.timestamp - entry_data['entry_time'],
                    entry_z_score=entry_data['entry_z_score'],
                    exit_z_score=signal.z_score
                )
            )

            # Update capital
            self.current_capital += pnl

            # Remove position
            del self.current_positions[pair]

    def _calculate_trade_pnl(
        self,
        entry_data: Dict,
        exit_prices: Dict[str, float],
        pair: str
    ) -> float:
        """
        Calculate PnL for a completed trade
        """
        pnl = 0
        assets = pair.split('_')

        for asset in assets:
            position = entry_data['positions'][asset]
            entry_price = entry_data['entry_prices'][asset]
            exit_price = exit_prices[asset]

            # Calculate PnL for this leg
            asset_pnl = position * (exit_price - entry_price)
            pnl += asset_pnl

        # Deduct transaction costs
        position_value = abs(
            entry_data['positions'][assets[0]] *
            entry_data['entry_prices'][assets[0]]
        )
        pnl -= position_value * 2 * self.transaction_costs

        return pnl

    def _calculate_current_equity(
        self,
        price_data: Dict[str, pd.DataFrame],
        timestamp: datetime
    ) -> float:
        """
        Calculate current equity including open positions
        """
        equity = self.current_capital

        for pair, position_data in self.current_positions.items():
            assets = pair.split('_')
            for asset in assets:
                position = position_data['positions'][asset]
                current_price = price_data[asset].loc[timestamp, 'close']
                entry_price = position_data['entry_prices'][asset]
                equity += position * (current_price - entry_price)

        return equity

    def _close_all_positions(
        self,
        price_data: Dict[str, pd.DataFrame],
        timestamp: datetime
    ) -> None:
        """
        Close all open positions at the end of backtest
        """
        for pair, position_data in list(self.current_positions.items()):
            assets = pair.split('_')
            exit_prices = {
                assets[0]: price_data[assets[0]].loc[timestamp, 'close'],
                assets[1]: price_data[assets[1]].loc[timestamp, 'close']
            }

            # Calculate and record final trade
            pnl = self._calculate_trade_pnl(position_data, exit_prices, pair)

            self.trades.append(
                Trade(
                    entry_time=position_data['entry_time'],
                    exit_time=timestamp,
                    pair=pair,
                    direction=position_data['direction'],
                    entry_prices=position_data['entry_prices'],
                    exit_prices=exit_prices,
                    positions=position_data['positions'],
                    pnl=pnl,
                    return_pct=pnl / self.initial_capital,
                    trade_duration=timestamp - position_data['entry_time'],
                    entry_z_score=position_data['entry_z_score'],
                    exit_z_score=None
                )
            )

            self.current_capital += pnl
            del self.current_positions[pair]

    def _calculate_backtest_results(self) -> Dict:
        """
        Calculate comprehensive backtest results and statistics
        """
        equity_df = pd.DataFrame(self.equity_curve)
        returns = equity_df['equity'].pct_change()

        results = {
            'total_trades': len(self.trades),
            'profitable_trades': len([t for t in self.trades if t.pnl > 0]),
            'win_rate': len([t for t in self.trades if t.pnl > 0]) / len(self.trades),
            'total_pnl': sum(t.pnl for t in self.trades),
            'total_return': (self.current_capital - self.initial_capital) / self.initial_capital,
            'sharpe_ratio': self._calculate_sharpe_ratio(returns),
            'max_drawdown': self._calculate_max_drawdown(equity_df['equity']),
            'avg_trade_duration': pd.Series([t.trade_duration for t in self.trades]).mean(),
            'profit_factor': self._calculate_profit_factor(),
            'trades': self.trades,
            'equity_curve': equity_df
        }

        return results

    def _calculate_sharpe_ratio(self, returns: pd.Series) -> float:
        """
        Calculate annualized Sharpe ratio
        """
        if len(returns) < 2:
            return 0.0

        # Assume daily data, annualize with sqrt(252)
        return np.sqrt(252) * (returns.mean() / returns.std())

    def _calculate_max_drawdown(self, equity_curve: pd.Series) -> float:
        """
        Calculate maximum drawdown
        """
        rolling_max = equity_curve.expanding().max()
        drawdowns = (equity_curve - rolling_max) / rolling_max
        return drawdowns.min()

    def _calculate_profit_factor(self) -> float:
        """
        Calculate profit factor (gross profits / gross losses)
        """
        gross_profits = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_losses = abs(sum(t.pnl for t in self.trades if t.pnl < 0))

        return gross_profits / gross_losses if gross_losses != 0 else float('inf')
