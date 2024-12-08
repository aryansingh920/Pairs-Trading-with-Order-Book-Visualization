# Configuration settings for the pairs trading system

TRADING_CONFIG = {
    'z_score_threshold': 2.0,  # Entry threshold for trades
    'stop_loss_multiplier': 2.5,  # Stop loss at 2.5 * z-score
    'take_profit_multiplier': 1.5,  # Take profit at 1.5 * z-score
    'max_position_size': 100000,  # Maximum position size in base currency
    'min_liquidity_ratio': 3.0,  # Minimum ratio of order book depth to trade size
}

# API Configuration
API_CONFIG = {
    'binance': {
        'api_key': 'your_api_key_here',
        'api_secret': 'your_api_secret_here',
    },
    'alpha_vantage': {
        'api_key': 'your_alpha_vantage_key_here',
    }
}

# Database Configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'pairs_trading',
    'user': 'user',
    'password': 'password'
}

# Visualization Configuration
VIZ_CONFIG = {
    'order_book_levels': 10,  # Number of levels to display in order book
    'update_interval': 1.0,  # Update interval in seconds
    'chart_height': 600,
    'chart_width': 1000,
}
