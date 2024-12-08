import asyncio
import logging
from typing import Dict
from datetime import datetime, timedelta
import yaml
from pathlib import Path

from data.data_fetcher import DataFetcher
from data.order_book import OrderBook
from analysis.cointegration import CointegrationAnalyzer
from analysis.signals import SignalGenerator
from execution.risk_manager import RiskManager
from execution.trade_executor import TradeExecutor
from backtesting.backtest import PairsBacktester


class TradingSystem:
    def __init__(self, config_path: str):
        # Load configuration
        self.config = self._load_config(config_path)

        # Setup logging
        self._setup_logging()

        # Initialize components
        self.data_fetcher = DataFetcher(self.config)
        self.cointegration_analyzer = CointegrationAnalyzer()
        self.signal_generator = SignalGenerator(self.config['trading'])
        self.risk_manager = RiskManager(self.config['risk'])
        self.trade_executor = TradeExecutor(
            self.config['execution'],
            self.config['exchange_client']
        )
        self.backtest = PairsBacktester(self.config['backtesting'])

        # Trading state
        self.pairs = {}
        self.positions = {}
        self.order_books = {}

        self.logger = logging.getLogger(__name__)

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def _setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=self.config.get('log_level', 'INFO'),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('trading.log'),
                logging.StreamHandler()
            ]
        )

    async def initialize(self):
        """Initialize the trading system"""
        try:
            # Fetch initial historical data
            start_date = (datetime.now() - timedelta(days=365)
                          ).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')

            self.pairs = await self.data_fetcher.get_pairs_data(
                self.config['pairs'],
                'daily',
                start_date,
                end_date
            )

            # Find cointegrated pairs
            cointegrated_pairs = self.cointegration_analyzer.find_cointegrated_pairs(
                self.pairs,
                self.config['cointegration']['p_value_threshold']
            )

            # Initialize order books
            for pair in cointegrated_pairs:
                self.order_books[pair['asset1']] = OrderBook(pair['asset1'])
                self.order_books[pair['asset2']] = OrderBook(pair['asset2'])

            self.logger.info(
                f"Found {len(cointegrated_pairs)} cointegrated pairs")
            return cointegrated_pairs

        except Exception as e:
            self.logger.error(f"Error initializing trading system: {e}")
            raise

    async def run_trading_loop(self):
        """Main trading loop"""
        while True:
            try:
                # Update data
                await self._update_market_data()

                # Generate signals
                signals = await self._generate_trading_signals()

                # Execute trades
                await self._execute_trades(signals)

                # Update positions
                await self._manage_positions()

                # Sleep for interval
                await asyncio.sleep(self.config['trading']['update_interval'])

            except Exception as e:
                self.logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def _update_market_data(self):
        """Update market data and order books"""
        for symbol, order_book in self.order_books.items():
            try:
                data = await self.data_fetcher.fetch_order_book(symbol)
                await order_book.update(data)
            except Exception as e:
                self.logger.error(
                    f"Error updating order book for {symbol}: {e}")

    async def _generate_trading_signals(self):
        """Generate trading signals for all pairs"""
        signals = []
        for pair in self.pairs:
            try:
                zscore = self.cointegration_analyzer.calculate_zscore(
                    self.pairs[pair]['asset1']['close'],
                    self.pairs[pair]['asset2']['close'],
                    self.pairs[pair]['hedge_ratio']
                )

                pair_signals = self.signal_generator.generate_trading_signals(
                    self.pairs[pair]['asset1']['close'],
                    self.pairs[pair]['asset2']['close'],
                    zscore,
                    self.pairs[pair]['hedge_ratio']
                )

                signals.extend(pair_signals)

            except Exception as e:
                self.logger.error(f"Error generating signals for {pair}: {e}")

        return signals

    async def _execute_trades(self, signals):
        """Execute trades based on signals"""
        for signal in signals:
            try:
                # Check risk parameters
                risk_check, risk_metrics = self.risk_manager.check_trade_risk(
                    signal.pair,
                    signal.direction,
                    signal.position_sizes,
                    self.positions,
                    self.order_books,
                    self.pairs
                )

                if risk_check:
                    # Execute trade
                    success, orders = await self.trade_executor.execute_pairs_trade(
                        signal.pair,
                        signal.direction,
                        signal.position_sizes,
                        signal.prices,
                        self.order_books
                    )

                    if success:
                        self.positions[signal.pair] = {
                            'direction': signal.direction,
                            'entry_time': datetime.now(),
                            'entry_prices': signal.prices,
                            'position_sizes': signal.position_sizes
                        }

                    self.logger.info(
                        f"Executed trade for {signal.pair}: {success}")

            except Exception as e:
                self.logger.error(
                    f"Error executing trade for {signal.pair}: {e}")

    async def _manage_positions(self):
        """Manage existing positions"""
        for pair, position in list(self.positions.items()):
            try:
                # Check exit conditions
                if self._check_exit_conditions(pair, position):
                    # Close position
                    success, orders = await self.trade_executor.close_position(
                        position,
                        self.order_books
                    )

                    if success:
                        del self.positions[pair]

            except Exception as e:
                self.logger.error(f"Error managing position for {pair}: {e}")

    def _check_exit_conditions(self, pair: str, position: Dict) -> bool:
        """Check if position should be closed"""
        try:
            # Calculate current z-score
            zscore = self.cointegration_analyzer.calculate_zscore(
                self.pairs[pair]['asset1']['close'],
                self.pairs[pair]['asset2']['close'],
                self.pairs[pair]['hedge_ratio']
            )

            # Check stop loss and take profit
            return self.signal_generator._check_exit_conditions(
                zscore,
                position['direction'],
                0.8  # Default confidence
            )

        except Exception as e:
            self.logger.error(
                f"Error checking exit conditions for {pair}: {e}")
            return False


async def main():
    # Initialize and run trading system
    config_path = Path("config/config.yaml")
    trading_system = TradingSystem(config_path)

    try:
        # Initialize system
        cointegrated_pairs = await trading_system.initialize()

        if not cointegrated_pairs:
            trading_system.logger.error("No cointegrated pairs found")
            return

        # Start trading loop
        await trading_system.run_trading_loop()

    except Exception as e:
        trading_system.logger.error(f"Fatal error in trading system: {e}")

if __name__ == "__main__":
    asyncio.run(main())
