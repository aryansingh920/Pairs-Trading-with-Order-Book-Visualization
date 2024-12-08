import pandas as pd
import numpy as np
from typing import Dict, Tuple
from dataclasses import dataclass
import logging


@dataclass
class TradingSignal:
    timestamp: pd.Timestamp
    pair: str
    signal_type: str  # 'entry' or 'exit'
    direction: str    # 'long' or 'short'
    z_score: float
    asset1_price: float
    asset2_price: float
    hedge_ratio: float
    confidence: float


class SignalGenerator:
    def __init__(self, config: Dict):
        self.z_score_threshold = config['z_score_threshold']
        self.stop_loss_multiplier = config['stop_loss_multiplier']
        self.take_profit_multiplier = config['take_profit_multiplier']
        self.logger = logging.getLogger(__name__)

    def generate_trading_signals(
        self,
        asset1_prices: pd.Series,
        asset2_prices: pd.Series,
        z_scores: pd.Series,
        hedge_ratio: float,
        min_confidence: float = 0.7
    ) -> pd.DataFrame:
        """
        Generate trading signals based on z-scores and price data
        """
        signals = []
        position = 0  # -1: short, 0: neutral, 1: long

        for timestamp, z_score in z_scores.items():
            try:
                # Skip if we don't have price data for this timestamp
                if timestamp not in asset1_prices.index or \
                   timestamp not in asset2_prices.index:
                    continue

                asset1_price = asset1_prices[timestamp]
                asset2_price = asset2_prices[timestamp]

                # Calculate signal confidence based on z-score magnitude
                confidence = self._calculate_confidence(z_score)

                if position == 0:  # No position, look for entry
                    if z_score < -self.z_score_threshold and \
                       confidence >= min_confidence:
                        # Long asset2, short asset1
                        signals.append(
                            TradingSignal(
                                timestamp=timestamp,
                                pair=f"{asset1_prices.name}_{asset2_prices.name}",
                                signal_type='entry',
                                direction='long',
                                z_score=z_score,
                                asset1_price=asset1_price,
                                asset2_price=asset2_price,
                                hedge_ratio=hedge_ratio,
                                confidence=confidence
                            )
                        )
                        position = 1

                    elif z_score > self.z_score_threshold and \
                            confidence >= min_confidence:
                        # Short asset2, long asset1
                        signals.append(
                            TradingSignal(
                                timestamp=timestamp,
                                pair=f"{asset1_prices.name}_{asset2_prices.name}",
                                signal_type='entry',
                                direction='short',
                                z_score=z_score,
                                asset1_price=asset1_price,
                                asset2_price=asset2_price,
                                hedge_ratio=hedge_ratio,
                                confidence=confidence
                            )
                        )
                        position = -1

                elif position == 1:  # Long position, look for exit
                    if self._check_exit_conditions(
                        z_score,
                        'long',
                        confidence
                    ):
                        signals.append(
                            TradingSignal(
                                timestamp=timestamp,
                                pair=f"{asset1_prices.name}_{asset2_prices.name}",
                                signal_type='exit',
                                direction='long',
                                z_score=z_score,
                                asset1_price=asset1_price,
                                asset2_price=asset2_price,
                                hedge_ratio=hedge_ratio,
                                confidence=confidence
                            )
                        )
                        position = 0

                elif position == -1:  # Short position, look for exit
                    if self._check_exit_conditions(
                        z_score,
                        'short',
                        confidence
                    ):
                        signals.append(
                            TradingSignal(
                                timestamp=timestamp,
                                pair=f"{asset1_prices.name}_{asset2_prices.name}",
                                signal_type='exit',
                                direction='short',
                                z_score=z_score,
                                asset1_price=asset1_price,
                                asset2_price=asset2_price,
                                hedge_ratio=hedge_ratio,
                                confidence=confidence
                            )
                        )
                        position = 0

            except Exception as e:
                self.logger.error(f"Error generating signals: {e}")
                continue

        return pd.DataFrame([vars(s) for s in signals])

    def _calculate_confidence(self, z_score: float) -> float:
        """
        Calculate confidence score based on z-score magnitude
        """
        # Use sigmoid function to map z-score to confidence
        confidence = 1 / (1 + np.exp(-abs(z_score) + self.z_score_threshold))
        return min(max(confidence, 0), 1)  # Clip between 0 and 1

    def _check_exit_conditions(
        self,
        z_score: float,
        position_type: str,
        confidence: float
    ) -> bool:
        """
        Check if position should be exited based on various conditions
        """
        # Stop loss check
        if position_type == 'long' and \
           z_score < -self.z_score_threshold * self.stop_loss_multiplier:
            return True

        if position_type == 'short' and \
           z_score > self.z_score_threshold * self.stop_loss_multiplier:
            return True

        # Take profit check
        if position_type == 'long' and \
           z_score > -self.z_score_threshold / self.take_profit_multiplier:
            return True

        if position_type == 'short' and \
           z_score < self.z_score_threshold / self.take_profit_multiplier:
            return True

        # Additional exit conditions based on confidence
        if confidence < 0.3:  # Exit if confidence drops significantly
            return True

        return False

    def calculate_position_sizes(
        self,
        signal: TradingSignal,
        available_capital: float,
        max_position_size: float
    ) -> Tuple[float, float]:
        """
        Calculate position sizes for both assets in the pair
        """
        # Base position size on confidence and available capital
        base_position = min(
            available_capital * signal.confidence,
            max_position_size
        )

        # Calculate individual position sizes
        asset1_position = base_position
        asset2_position = base_position * signal.hedge_ratio

        return asset1_position, asset2_position

    def get_signal_metrics(self, signals_df: pd.DataFrame) -> Dict:
        """
        Calculate various metrics for generated signals
        """
        metrics = {
            'total_signals': len(signals_df),
            'entry_signals': len(signals_df[signals_df['signal_type'] == 'entry']),
            'exit_signals': len(signals_df[signals_df['signal_type'] == 'exit']),
            'long_entries': len(signals_df[
                (signals_df['signal_type'] == 'entry') &
                (signals_df['direction'] == 'long')
            ]),
            'short_entries': len(signals_df[
                (signals_df['signal_type'] == 'entry') &
                (signals_df['direction'] == 'short')
            ]),
            'avg_confidence': signals_df['confidence'].mean(),
            'avg_z_score': abs(signals_df['z_score']).mean()
        }

        return metrics
