import pandas as pd
import numpy as np
from binance.client import Client
from alpha_vantage.timeseries import TimeSeries
from typing import Dict, List, Tuple
import logging


class DataFetcher:
    def __init__(self, config: Dict):
        self.binance_client = Client(
            config['binance']['api_key'],
            config['binance']['api_secret']
        )
        self.alpha_vantage = TimeSeries(
            key=config['alpha_vantage']['api_key']
        )
        self.logger = logging.getLogger(__name__)

    async def fetch_historical_data(
        self,
        symbol: str,
        interval: str,
        start_time: str,
        end_time: str
    ) -> pd.DataFrame:
        """
        Fetch historical price data for a given symbol
        """
        try:
            klines = self.binance_client.get_historical_klines(
                symbol,
                interval,
                start_time,
                end_time
            )

            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close',
                'volume', 'close_time', 'quote_volume',
                'trades', 'taker_buy_base', 'taker_buy_quote', 'ignored'
            ])

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            return df[['open', 'high', 'low', 'close', 'volume']]

        except Exception as e:
            self.logger.error(f"Error fetching historical data: {e}")
            raise

    async def fetch_stock_data(
        self,
        symbol: str,
        interval: str = 'daily'
    ) -> pd.DataFrame:
        """
        Fetch stock data from Alpha Vantage
        """
        try:
            data, _ = self.alpha_vantage.get_daily(
                symbol=symbol,
                outputsize='full'
            )

            df = pd.DataFrame(data).astype(float)
            df.index = pd.to_datetime(df.index)

            return df

        except Exception as e:
            self.logger.error(f"Error fetching stock data: {e}")
            raise

    async def get_pairs_data(
        self,
        pairs: List[Tuple[str, str]],
        interval: str,
        start_time: str,
        end_time: str
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical data for multiple pairs
        """
        pairs_data = {}

        for asset1, asset2 in pairs:
            try:
                df1 = await self.fetch_historical_data(
                    asset1, interval, start_time, end_time
                )
                df2 = await self.fetch_historical_data(
                    asset2, interval, start_time, end_time
                )

                # Ensure both dataframes have the same index
                common_idx = df1.index.intersection(df2.index)
                pairs_data[f"{asset1}_{asset2}"] = {
                    'asset1': df1.loc[common_idx],
                    'asset2': df2.loc[common_idx]
                }

            except Exception as e:
                self.logger.error(f"Error fetching pair data: {e}")
                continue

        return pairs_data
