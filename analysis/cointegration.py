import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint
from typing import List, Tuple, Dict
import logging
from scipy import stats


class CointegrationAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def test_cointegration(
        self,
        series1: pd.Series,
        series2: pd.Series
    ) -> Tuple[float, float, Dict]:
        """
        Test for cointegration between two price series
        Returns: t-statistic, p-value, and cointegration parameters
        """
        try:
            # Perform cointegration test
            t_stat, p_value, critical_values = coint(series1, series2)

            # Calculate cointegration ratio
            model = np.polyfit(series1, series2, 1)
            ratio = model[0]
            intercept = model[1]

            # Calculate spread
            spread = series2 - (ratio * series1 + intercept)

            # Calculate spread statistics
            spread_mean = spread.mean()
            spread_std = spread.std()

            results = {
                'ratio': ratio,
                'intercept': intercept,
                'spread_mean': spread_mean,
                'spread_std': spread_std,
                'critical_values': critical_values
            }

            return t_stat, p_value, results

        except Exception as e:
            self.logger.error(f"Error in cointegration test: {e}")
            raise

    def find_cointegrated_pairs(
        self,
        price_data: Dict[str, pd.DataFrame],
        p_value_threshold: float = 0.05
    ) -> List[Dict]:
        """
        Find all cointegrated pairs in a set of price series
        """
        n = len(price_data)
        cointegrated_pairs = []

        # Get all unique combinations of assets
        symbols = list(price_data.keys())

        for i in range(n):
            for j in range(i+1, n):
                try:
                    series1 = price_data[symbols[i]]['close']
                    series2 = price_data[symbols[j]]['close']

                    t_stat, p_value, results = self.test_cointegration(
                        series1, series2
                    )

                    if p_value < p_value_threshold:
                        pair_info = {
                            'asset1': symbols[i],
                            'asset2': symbols[j],
                            't_statistic': t_stat,
                            'p_value': p_value,
                            'hedge_ratio': results['ratio'],
                            'intercept': results['intercept'],
                            'spread_mean': results['spread_mean'],
                            'spread_std': results['spread_std']
                        }
                        cointegrated_pairs.append(pair_info)

                except Exception as e:
                    self.logger.error(
                        f"Error analyzing pair {symbols[i]}-{symbols[j]}: {e}"
                    )
                    continue

        return cointegrated_pairs

    def calculate_zscore(
        self,
        series1: pd.Series,
        series2: pd.Series,
        hedge_ratio: float,
        intercept: float,
        window: int = 20
    ) -> pd.Series:
        """
        Calculate rolling z-score for a pair
        """
        spread = series2 - (hedge_ratio * series1 + intercept)

        rolling_mean = spread.rolling(window=window).mean()
        rolling_std = spread.rolling(window=window).std()

        zscore = (spread - rolling_mean) / rolling_std

        return zscore

    def calculate_half_life(self, spread: pd.Series) -> float:
        """
        Calculate half-life of mean reversion
        """
        spread_lag = spread.shift(1)
        spread_diff = spread - spread_lag
        spread_lag = spread_lag[1:]
        spread_diff = spread_diff[1:]

        model = np.polyfit(spread_lag, spread_diff, 1)
        lambda_param = -model[0]

        half_life = np.log(2) / lambda_param

        return half_life
