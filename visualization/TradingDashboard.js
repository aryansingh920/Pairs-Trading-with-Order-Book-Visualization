import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, BarChart, Bar, ReferenceLine } from 'recharts';
import { TrendingUp, TrendingDown, AlertCircle } from 'lucide-react';
import OrderBookViz from './OrderBookViz';

const TradingDashboard = ({ pairsData, tradingSignals, orderBookData, positions, performance }) => {
    const [selectedPair, setSelectedPair] = useState(null);
    const [alerts, setAlerts] = useState([]);

    useEffect(() => {
        // Process trading signals for alerts
        const newAlerts = tradingSignals
            .filter(signal => signal.confidence > 0.8)
            .map(signal => ({
                type: signal.signalType,
                pair: signal.pair,
                message: `High confidence ${signal.signalType} signal for ${signal.pair}`,
                timestamp: new Date()
            }));
        setAlerts(newAlerts);
    }, [tradingSignals]);

    const MetricCard = ({ title, value, isPercentage, isNegativeRed }) => (
        <Card>
            <CardContent className="p-6">
                <div className="space-y-2">
                    <p className="text-sm text-gray-500">{title}</p>
                    <p className={`text-2xl font-bold ${isNegativeRed && parseFloat(value) < 0 ? 'text-red-500' : ''}`}>
                        {isPercentage ? `${value}%` : value}
                    </p>
                </div>
            </CardContent>
        </Card>
    );

    const CustomTooltip = ({ active, payload, label }) => {
        if (!active || !payload?.length) return null;
        return (
            <div className="bg-white p-2 border rounded shadow-sm">
                <p className="font-medium">{label}</p>
                {payload.map((entry, index) => (
                    <p key={index} style={{ color: entry.color }}>
                        {entry.name}: {entry.value.toFixed(2)}
                    </p>
                ))}
            </div>
        );
    };

    return (
        <div className="space-y-6 p-6">
            {/* Performance Overview */}
            <div className="grid grid-cols-4 gap-4">
                <MetricCard
                    title="Total P&L"
                    value={`$${performance.totalPnl.toFixed(2)}`}
                    isNegativeRed={true}
                />
                <MetricCard
                    title="Sharpe Ratio"
                    value={performance.sharpeRatio.toFixed(2)}
                />
                <MetricCard
                    title="Win Rate"
                    value={(performance.winRate * 100).toFixed(1)}
                    isPercentage={true}
                />
                <MetricCard
                    title="Max Drawdown"
                    value={(performance.maxDrawdown * 100).toFixed(1)}
                    isPercentage={true}
                    isNegativeRed={true}
                />
            </div>

            {/* Main Content Grid */}
            <div className="grid grid-cols-12 gap-6">
                {/* Left Column - Pairs and Signals */}
                <div className="col-span-3 space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Trading Pairs</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-2">
                                {pairsData.map(pair => (
                                    <div
                                        key={pair.name}
                                        className={`p-3 rounded cursor-pointer hover:bg-gray-100 ${selectedPair === pair.name ? 'bg-gray-100' : ''
                                            }`}
                                        onClick={() => setSelectedPair(pair.name)}
                                    >
                                        <div className="flex justify-between items-center">
                                            <span className="font-medium">{pair.name}</span>
                                            <span className={pair.zscore > 0 ? 'text-green-500' : 'text-red-500'}>
                                                {pair.zscore.toFixed(2)}σ
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Alerts */}
                    <div className="space-y-2">
                        {alerts.map((alert, index) => (
                            <Alert key={index} variant={alert.type === 'entry' ? 'default' : 'destructive'}>
                                <AlertCircle className="h-4 w-4" />
                                <AlertDescription>{alert.message}</AlertDescription>
                            </Alert>
                        ))}
                    </div>
                </div>

                {/* Center Column - Charts */}
                <div className="col-span-6 space-y-6">
                    {selectedPair && (
                        <>
                            {/* Price Chart */}
                            <Card>
                                <CardHeader>
                                    <CardTitle>Price Movement - {selectedPair}</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="h-64">
                                        <LineChart
                                            data={pairsData.find(p => p.name === selectedPair)?.priceHistory}
                                            margin={{ top: 5, right: 20, bottom: 5, left: 20 }}
                                        >
                                            <XAxis dataKey="timestamp" />
                                            <YAxis />
                                            <Tooltip content={<CustomTooltip />} />
                                            <Legend />
                                            <Line type="monotone" dataKey="asset1Price" stroke="#8884d8" name="Asset 1" />
                                            <Line type="monotone" dataKey="asset2Price" stroke="#82ca9d" name="Asset 2" />
                                        </LineChart>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Spread Chart */}
                            <Card>
                                <CardHeader>
                                    <CardTitle>Spread Z-Score</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="h-48">
                                        <LineChart
                                            data={pairsData.find(p => p.name === selectedPair)?.spreadHistory}
                                            margin={{ top: 5, right: 20, bottom: 5, left: 20 }}
                                        >
                                            <XAxis dataKey="timestamp" />
                                            <YAxis />
                                            <Tooltip content={<CustomTooltip />} />
                                            <Line type="monotone" dataKey="zscore" stroke="#82ca9d" />
                                            <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
                                            <ReferenceLine y={2} stroke="#ff0000" strokeDasharray="3 3" />
                                            <ReferenceLine y={-2} stroke="#ff0000" strokeDasharray="3 3" />
                                        </LineChart>
                                    </div>
                                </CardContent>
                            </Card>
                        </>
                    )}
                </div>

                {/* Right Column - Order Book and Positions */}
                <div className="col-span-3 space-y-6">
                    {selectedPair && (
                        <>
                            <OrderBookViz
                                orderBookData={orderBookData[selectedPair]}
                                lastPrice={pairsData.find(p => p.name === selectedPair)?.lastPrice}
                                pairName={selectedPair}
                            />

                            {/* Open Positions */}
                            <Card>
                                <CardHeader>
                                    <CardTitle>Open Positions</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-2">
                                        {positions.map((position, index) => (
                                            <div key={index} className="p-3 border rounded">
                                                <div className="flex justify-between items-center">
                                                    <span className="font-medium">{position.pair}</span>
                                                    <span className={`flex items-center ${position.pnl >= 0 ? 'text-green-500' : 'text-red-500'
                                                        }`}>
                                                        {position.pnl >= 0 ? (
                                                            <TrendingUp className="w-4 h-4 mr-1" />
                                                        ) : (
                                                            <TrendingDown className="w-4 h-4 mr-1" />
                                                        )}
                                                        {position.pnl.toFixed(2)}%
                                                    </span>
                                                </div>
                                                <div className="text-sm text-gray-500 mt-1">
                                                    {position.direction} • Entry: ${position.entryPrice}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Trade History */}
                            <Card>
                                <CardHeader>
                                    <CardTitle>Recent Trades</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-2 max-h-64 overflow-y-auto">
                                        {performance.tradeHistory.map((trade, index) => (
                                            <div key={index} className="p-2 text-sm border-b last:border-b-0">
                                                <div className="flex justify-between items-center">
                                                    <span className="font-medium">{trade.pair}</span>
                                                    <span className={trade.pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                                                        ${trade.pnl.toFixed(2)}
                                                    </span>
                                                </div>
                                                <div className="text-gray-500 mt-1">
                                                    {new Date(trade.exitTime).toLocaleString()}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        </>
                    )}
                </div>
            </div>

            {/* Bottom Grid - Additional Metrics */}
            <div className="grid grid-cols-2 gap-6">
                {/* Trading Performance Chart */}
                <Card>
                    <CardHeader>
                        <CardTitle>Cumulative Returns</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="h-64">
                            <LineChart
                                data={performance.equityCurve}
                                margin={{ top: 5, right: 20, bottom: 5, left: 20 }}
                            >
                                <XAxis dataKey="timestamp" />
                                <YAxis />
                                <Tooltip content={<CustomTooltip />} />
                                <Line type="monotone" dataKey="value" stroke="#8884d8" dot={false} />
                            </LineChart>
                        </div>
                    </CardContent>
                </Card>

                {/* Trade Distribution */}
                <Card>
                    <CardHeader>
                        <CardTitle>Trade Distribution</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="h-64">
                            <BarChart
                                data={performance.tradeDistribution}
                                margin={{ top: 5, right: 20, bottom: 5, left: 20 }}
                            >
                                <XAxis dataKey="range" />
                                <YAxis />
                                <Tooltip content={<CustomTooltip />} />
                                <Bar dataKey="count" fill="#8884d8" />
                            </BarChart>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Risk Metrics */}
            <Card>
                <CardHeader>
                    <CardTitle>Risk Metrics</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-4 gap-4">
                        <div>
                            <p className="text-sm text-gray-500">Value at Risk (1d, 95%)</p>
                            <p className="text-xl font-bold">{performance.valueAtRisk.toFixed(2)}%</p>
                        </div>
                        <div>
                            <p className="text-sm text-gray-500">Beta</p>
                            <p className="text-xl font-bold">{performance.beta.toFixed(2)}</p>
                        </div>
                        <div>
                            <p className="text-sm text-gray-500">Correlation</p>
                            <p className="text-xl font-bold">{performance.correlation.toFixed(2)}</p>
                        </div>
                        <div>
                            <p className="text-sm text-gray-500">Information Ratio</p>
                            <p className="text-xl font-bold">{performance.informationRatio.toFixed(2)}</p>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Settings Panel */}
            <div className="fixed bottom-0 right-0 p-4">
                <Card className="w-64">
                    <CardHeader>
                        <CardTitle className="text-sm">Quick Settings</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-2">
                            <div className="flex justify-between items-center">
                                <span className="text-sm">Auto Trading</span>
                                <div className="relative inline-block w-10 mr-2 align-middle select-none">
                                    <input
                                        type="checkbox"
                                        className="toggle-checkbox absolute block w-6 h-6 rounded-full bg-white border-4 appearance-none cursor-pointer"
                                    />
                                    <label className="toggle-label block overflow-hidden h-6 rounded-full bg-gray-300 cursor-pointer" />
                                </div>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-sm">Risk Mode</span>
                                <select className="text-sm border rounded p-1">
                                    <option>Conservative</option>
                                    <option>Moderate</option>
                                    <option>Aggressive</option>
                                </select>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};

export default TradingDashboard;
