# Create root directory
mkdir -p pairs_trading

# Create subdirectories
mkdir -p pairs_trading/{config,data,analysis,backtesting,execution,visualization,utils}

# Create Python files
touch pairs_trading/config/config.py

touch pairs_trading/data/__init__.py
touch pairs_trading/data/data_fetcher.py
touch pairs_trading/data/order_book.py

touch pairs_trading/analysis/__init__.py
touch pairs_trading/analysis/cointegration.py
touch pairs_trading/analysis/signals.py

touch pairs_trading/backtesting/__init__.py
touch pairs_trading/backtesting/backtest.py

touch pairs_trading/execution/__init__.py
touch pairs_trading/execution/risk_manager.py
touch pairs_trading/execution/trade_executor.py

touch pairs_trading/visualization/__init__.py
touch pairs_trading/visualization/order_book_viz.py
touch pairs_trading/visualization/dashboard.py

touch pairs_trading/utils/__init__.py
touch pairs_trading/utils/helpers.py

# Create project-level files
touch pairs_trading/requirements.txt
touch pairs_trading/main.py

