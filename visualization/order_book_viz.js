import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine } from 'recharts';

const OrderBookViz = ({ orderBookData, lastPrice, pairName }) => {
    const [combinedData, setCombinedData] = useState([]);
    const [maxVolume, setMaxVolume] = useState(0);

    useEffect(() => {
        if (!orderBookData) return;

        // Process order book data for visualization
        const processedData = [];
        let maxVol = 0;

        // Process bids (buy orders)
        orderBookData.bids.forEach(level => {
            const volume = parseFloat(level.quantity);
            maxVol = Math.max(maxVol, volume);
            processedData.push({
                price: parseFloat(level.price),
                volume,
                type: 'bid',
                total: parseFloat(level.price) * volume
            });
        });

        // Process asks (sell orders)
        orderBookData.asks.forEach(level => {
            const volume = parseFloat(level.quantity);
            maxVol = Math.max(maxVol, volume);
            processedData.push({
                price: parseFloat(level.price),
                volume,
                type: 'ask',
                total: parseFloat(level.price) * volume
            });
        });

        setCombinedData(processedData);
        setMaxVolume(maxVol);
    }, [orderBookData]);

    const CustomTooltip = ({ active, payload }) => {
        if (!active || !payload?.length) return null;

        const data = payload[0].payload;
        return (
            <div className="bg-white p-2 border rounded shadow-sm">
                <p>Price: {data.price.toFixed(2)}</p>
                <p>Volume: {data.volume.toFixed(2)}</p>
                <p>Total: {data.total.toFixed(2)}</p>
                <p>Type: {data.type}</p>
            </div>
        );
    };

    return (
        <Card className="w-full">
            <CardHeader>
                <CardTitle className="flex justify-between items-center">
                    <span>Order Book - {pairName}</span>
                    <span className="text-lg font-normal">
                        Last Price: {lastPrice?.toFixed(2)}
                    </span>
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-6">
                    {/* Depth Chart */}
                    <div className="h-64">
                        <LineChart
                            data={combinedData}
                            margin={{ top: 5, right: 20, bottom: 5, left: 20 }}
                        >
                            <XAxis
                                dataKey="price"
                                type="number"
                                domain={['dataMin', 'dataMax']}
                                tickFormatter={val => val.toFixed(2)}
                            />
                            <YAxis
                                dataKey="volume"
                                domain={[0, maxVolume]}
                                tickFormatter={val => val.toFixed(1)}
                            />
                            <Tooltip content={<CustomTooltip />} />
                            <ReferenceLine x={lastPrice} stroke="#666" strokeDasharray="3 3" />
                            <Line
                                type="stepAfter"
                                dataKey="volume"
                                stroke="#ef4444"
                                dot={false}
                                data={combinedData.filter(d => d.type === 'ask')}
                            />
                            <Line
                                type="stepAfter"
                                dataKey="volume"
                                stroke="#22c55e"
                                dot={false}
                                data={combinedData.filter(d => d.type === 'bid')}
                            />
                        </LineChart>
                    </div>

                    {/* Order Book Tables */}
                    <div className="grid grid-cols-2 gap-4">
                        {/* Asks Table */}
                        <div>
                            <h3 className="text-lg font-semibold mb-2 text-red-500">
                                Asks (Sells)
                            </h3>
                            <div className="overflow-y-auto max-h-48">
                                <table className="w-full">
                                    <thead>
                                        <tr>
                                            <th className="text-left">Price</th>
                                            <th className="text-right">Size</th>
                                            <th className="text-right">Total</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {orderBookData?.asks.map((level, i) => (
                                            <tr key={`ask-${i}`} className="hover:bg-gray-50">
                                                <td className="text-left text-red-500">
                                                    {parseFloat(level.price).toFixed(2)}
                                                </td>
                                                <td className="text-right">
                                                    {parseFloat(level.quantity).toFixed(4)}
                                                </td>
                                                <td className="text-right">
                                                    {(parseFloat(level.price) *
                                                        parseFloat(level.quantity)).toFixed(2)}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Bids Table */}
                        <div>
                            <h3 className="text-lg font-semibold mb-2 text-green-500">
                                Bids (Buys)
                            </h3>
                            <div className="overflow-y-auto max-h-48">
                                <table className="w-full">
                                    <thead>
                                        <tr>
                                            <th className="text-left">Price</th>
                                            <th className="text-right">Size</th>
                                            <th className="text-right">Total</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {orderBookData?.bids.map((level, i) => (
                                            <tr key={`bid-${i}`} className="hover:bg-gray-50">
                                                <td className="text-left text-green-500">
                                                    {parseFloat(level.price).toFixed(2)}
                                                </td>
                                                <td className="text-right">
                                                    {parseFloat(level.quantity).toFixed(4)}
                                                </td>
                                                <td className="text-right">
                                                    {(parseFloat(level.price) *
                                                        parseFloat(level.quantity)).toFixed(2)}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

export default OrderBookViz;
