import React, { useEffect, useState } from 'react';
import { SecureAPI } from '../lib/secureApi';

interface RevenueData {
    property_id: string;
    revenue_by_currency: Record<string, string>;
    reservations_count: number;
}

interface RevenueSummaryProps {
    propertyId: string;
}

export const RevenueSummary: React.FC<RevenueSummaryProps> = ({ propertyId }) => {
    const [data, setData] = useState<RevenueData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        const fetchRevenue = async () => {
            setLoading(true);
            setError('');
            try {
                const response = await SecureAPI.getDashboardSummary(propertyId);
                setData(response);
            } catch (err) {
                setError('Failed to load revenue data');
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        fetchRevenue();
    }, [propertyId]);

    if (loading) {
        return (
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                <div className="animate-pulse space-y-4">
                    <div className="h-4 bg-gray-100 rounded w-1/4"></div>
                    <div className="h-8 bg-gray-100 rounded w-1/2"></div>
                    <div className="flex gap-4 pt-4">
                        <div className="h-12 bg-gray-100 rounded flex-1"></div>
                        <div className="h-12 bg-gray-100 rounded flex-1"></div>
                    </div>
                </div>
            </div>
        );
    }

    if (error) return <div className="p-4 text-red-500 bg-red-50 rounded-lg">{error}</div>;
    if (!data) return null;

    const revenueEntries = Object.entries(data.revenue_by_currency);

    return (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow duration-300">
            <div className="p-6">
                <div className="mb-6">
                    <div>
                        <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Total Revenue</h2>
                        <div className="flex flex-col gap-1 mt-1">
                            {revenueEntries.length ? revenueEntries.map(([currency, amount]) => (
                                <span key={currency} className="text-3xl font-bold text-gray-900 tracking-tight">
                                    {currency === 'UNKNOWN'
                                        ? `Unknown currency ${amount}`
                                        : new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(Number(amount))}
                                </span>
                            )) : <span className="text-3xl font-bold text-gray-900 tracking-tight">—</span>}
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-100">
                    <div>
                        <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">Property ID</p>
                        <p className="text-sm font-semibold text-gray-700 font-mono mt-1">{data.property_id}</p>
                    </div>
                    <div>
                        <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">Reservations</p>
                        <p className="text-sm font-semibold text-gray-700 mt-1">{data.reservations_count} <span className="font-normal text-gray-400">bookings</span></p>
                    </div>
                </div>

            </div>
        </div>
    );
};
