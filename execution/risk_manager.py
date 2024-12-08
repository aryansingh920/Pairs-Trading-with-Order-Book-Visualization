from typing import Dict, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass
import logging


@dataclass
class RiskMetrics:
    value_at_risk: float
    expected_shortfall: float
    position_size_limit: float
    max_leverage: float
    correlation_risk: float
    liquidity_risk: float


class RiskManager:
    def __init__(self, config: Dict):
        self.max_position_size = config['max_position_size']
        self.max_leverage = config.get('max_leverage', 2.0)
        self.max_concentration = config.get('max_concentration', 0.2)
        self.min_liquidity_ratio = config.get('min_liquidity_ratio', 3.0)
        self.var_confidence = config.get('var_confidence', 0.99)
        self.risk_free_rate = config.get('risk_free_rate', 0.02)
        self.logger = logging.getLogger(__name__)

    def check_trade_risk(
        self,
        pair: str,
        direction: str,
        position_sizes: Dict[str, float],
        current_positions: Dict[str, Dict],
        order_book_data: Dict[str, Dict],
        price_history: Dict[str, pd.DataFrame]
    ) -> Tuple[bool, Dict[str, str]]:
        """
        Comprehensive risk check for a potential trade
        """
        try:
            risk_checks = {}

            # Position size check
            size_check = self._check_position_size(
                position_sizes,
                current_positions
            )
            risk_checks['position_size'] = size_check

            # Liquidity check
            liquidity_check = self._check_liquidity(
                pair,
                position_sizes,
                order_book_data
            )
            risk_checks['liquidity'] = liquidity_check

            # Portfolio risk check
            portfolio_check = self._check_portfolio_risk(
                pair,
                position_sizes,
                current_positions,
                price_history
            )
            risk_checks['portfolio_risk'] = portfolio_check

            # All checks must pass
            trade_allowed = all(
                check == "pass" for check in risk_checks.values())

            return trade_allowed, risk_checks

        except Exception as e:
            self.logger.error(f"Error in trade risk check: {e}")
            return False, {"error": str(e)}

    def _check_position_size(
        self,
        new_positions: Dict[str, float],
        current_positions: Dict[str, Dict]
    ) -> str:
        """
        Check if position sizes are within limits
        """
        # Calculate total position including existing positions
        total_position = 0
        for asset, size in new_positions.items():
            total_position += abs(size)

            # Add existing positions for the same asset
            for position in current_positions.values():
                if asset in position['positions']:
                    total_position += abs(position['positions'][asset])

        if total_position > self.max_position_size:
            return "fail: position size exceeds limit"

        return "pass"

    def _check_liquidity(
        self,
        pair: str,
        position_sizes: Dict[str, float],
        order_book_data: Dict[str, Dict]
    ) -> str:
        """
        Check if there's sufficient liquidity for the trade
        """
        for asset, size in position_sizes.items():
            if asset not in order_book_data:
                return f"fail: no order book data for {asset}"

            order_book = order_book_data[asset]

            # Check if we're buying or selling
            if size > 0:  # Buying
                liquidity = sum(level['quantity']
                                for level in order_book['asks'])
                required_ratio = abs(size) * self.min_liquidity_ratio

                if liquidity < required_ratio:
                    return f"fail: insufficient ask liquidity for {asset}"
            else:  # Selling
                liquidity = sum(level['quantity']
                                for level in order_book['bids'])
                required_ratio = abs(size) * self.min_liquidity_ratio

                if liquidity < required_ratio:
                    return f"fail: insufficient bid liquidity for {asset}"

        return "pass"

    def _check_portfolio_risk(
        self,
        pair: str,
        new_positions: Dict[str, float],
        current_positions: Dict[str, Dict],
        price_history: Dict[str, pd.DataFrame]
    ) -> str:
        """
        Check portfolio-level risk metrics
        """
        # Calculate portfolio VaR including new positions
        portfolio_risk = self.calculate_portfolio_risk(
            new_positions,
            current_positions,
            price_history
        )

        # Check Value at Risk
        if portfolio_risk.value_at_risk > self.max_position_size * 0.1:
            return "fail: VaR exceeds limit"

        # Check leverage
        if portfolio_risk.max_leverage > self.max_leverage:
            return "fail: leverage exceeds limit"

        # Check correlation risk
        if portfolio_risk.correlation_risk > 0.8:
            return "fail: high correlation risk"

        return "pass"

    def calculate_portfolio_risk(
        self,
        new_positions: Dict[str, float],
        current_positions: Dict[str, Dict],
        price_history: Dict[str, pd.DataFrame]
    ) -> RiskMetrics:
        """
        Calculate comprehensive portfolio risk metrics
        """
        # Combine new and existing positions
        all_positions = {}
        for asset, size in new_positions.items():
            all_positions[asset] = size

        for position in current_positions.values():
            for asset, size in position['positions'].items():
                if asset in all_positions:
                    all_positions[asset] += size
                else:
                    all_positions[asset] = size

        # Calculate returns
        returns_dict = {}
        for asset in all_positions:
            if asset in price_history:
                prices = price_history[asset]['close']
                returns_dict[asset] = prices.pct_change().dropna()

        returns_df = pd.DataFrame(returns_dict)

        # Calculate portfolio returns
        portfolio_weights = {
            asset: size / sum(abs(v) for v in all_positions.values())
            for asset, size in all_positions.items()
        }

        portfolio_returns = sum(
            returns_df[asset] * weight
            for asset, weight in portfolio_weights.items()
            if asset in returns_df
        )

        # Calculate VaR
        var = np.percentile(portfolio_returns, (1 - self.var_confidence) * 100)

        # Calculate Expected Shortfall (CVaR)
        es = portfolio_returns[portfolio_returns <= var].mean()

        # Calculate max leverage
        leverage = sum(abs(v) for v in all_positions.values()) / \
            self.max_position_size

        # Calculate correlation risk
        correlation_matrix = returns_df.corr()
        max_correlation = correlation_matrix.max().max()

        # Calculate liquidity risk score (simplified)
        liquidity_risk = 0.5  # Placeholder - should be calculated based on order book

        return RiskMetrics(
            value_at_risk=abs(var),
            expected_shortfall=abs(es),
            position_size_limit=self.max_position_size,
            max_leverage=leverage,
            correlation_risk=max_correlation,
            liquidity_risk=liquidity_risk
        )

    def adjust_position_sizes(
        self,
        position_sizes: Dict[str, float],
        risk_metrics: RiskMetrics
    ) -> Dict[str, float]:
        """
        Adjust position sizes based on risk metrics
        """
        # Calculate scaling factor based on risk metrics
        var_scale = self.max_position_size * 0.1 / risk_metrics.value_at_risk
        leverage_scale = self.max_leverage / risk_metrics.max_leverage
        liquidity_scale = 1 / risk_metrics.liquidity_risk

        # Use the most conservative scaling factor
        scale = min(var_scale, leverage_scale, liquidity_scale, 1.0)

        # Apply scaling to position sizes
        adjusted_positions = {
            asset: size * scale
            for asset, size in position_sizes.items()
        }

        return adjusted_positions
