import { useUser, useAuth } from "@clerk/nextjs";
import { useEffect, useState, useCallback } from "react";
import { API_URL } from "../lib/config";
import Layout from "../components/Layout";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { Skeleton, SkeletonCard } from "../components/Skeleton";
import { showToast } from "../components/Toast";
import Head from "next/head";

interface UserData {
  clerk_user_id: string;
  display_name: string;
  years_until_retirement: number;
  target_retirement_income: number;
  asset_class_targets: Record<string, number>;
  region_targets: Record<string, number>;
}

interface Account {
  account_id: string;
  clerk_user_id: string;
  account_name: string;
  account_type: string;
  account_purpose: string;
  cash_balance: number;
  created_at: string;
  updated_at: string;
}

interface Position {
  position_id: string;
  account_id: string;
  symbol: string;
  quantity: number;
  created_at: string;
  updated_at: string;
}

interface Instrument {
  symbol: string;
  name: string;
  instrument_type: string;
  current_price?: number;
  asset_class_allocation?: Record<string, number>;
  region_allocation?: Record<string, number>;
  sector_allocation?: Record<string, number>;
}

export default function Dashboard() {
  const { user, isLoaded: userLoaded } = useUser();
  const { getToken } = useAuth();
  const [userData, setUserData] = useState<UserData | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [positions, setPositions] = useState<Record<string, Position[]>>({});
  const [instruments, setInstruments] = useState<Record<string, Instrument>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastAnalysisDate, setLastAnalysisDate] = useState<string | null>(null);

  // Form state for editable fields - start empty to avoid flicker
  const [displayName, setDisplayName] = useState("");
  const [yearsUntilRetirement, setYearsUntilRetirement] = useState(0);
  const [targetRetirementIncome, setTargetRetirementIncome] = useState(0);
  const [equityTarget, setEquityTarget] = useState(0);
  const [fixedIncomeTarget, setFixedIncomeTarget] = useState(0);
  const [northAmericaTarget, setNorthAmericaTarget] = useState(0);
  const [internationalTarget, setInternationalTarget] = useState(0);

  // Calculate portfolio summary
  const calculatePortfolioSummary = useCallback(() => {
    let totalValue = 0;
    const assetClassBreakdown: Record<string, number> = {
      equity: 0,
      fixed_income: 0,
      alternatives: 0,
      cash: 0
    };

    // Add cash balances
    accounts.forEach(account => {
      const cashBalance = Number(account.cash_balance);
      totalValue += cashBalance;
      assetClassBreakdown.cash += cashBalance;
    });

    // Add position values
    Object.entries(positions).forEach(([, accountPositions]) => {
      accountPositions.forEach(position => {
        const instrument = instruments[position.symbol];
        if (instrument?.current_price) {
          const positionValue = Number(position.quantity) * Number(instrument.current_price);
          totalValue += positionValue;

          // Add to asset class breakdown
          if (instrument.asset_class_allocation) {
            Object.entries(instrument.asset_class_allocation).forEach(([assetClass, percentage]) => {
              assetClassBreakdown[assetClass] = (assetClassBreakdown[assetClass] || 0) + (positionValue * percentage / 100);
            });
          }
        }
      });
    });

    return { totalValue, assetClassBreakdown };
  }, [accounts, positions, instruments]);

  // Load user data and accounts
  useEffect(() => {
    async function loadData() {
      if (!userLoaded || !user) return;

      try {
        const token = await getToken();
        if (!token) {
          setError("Not authenticated");
          setLoading(false);
          return;
        }

        // Get/create user
        const userResponse = await fetch(`${API_URL}/api/user`, {
          headers: {
            "Authorization": `Bearer ${token}`,
          },
        });

        if (!userResponse.ok) {
          throw new Error(`Failed to sync user: ${userResponse.status}`);
        }

        const response = await userResponse.json();
        const userData = response.user; // Extract user from response
        setUserData(userData);
        setDisplayName(userData.display_name || "");
        setYearsUntilRetirement(userData.years_until_retirement || 0);
        // Ensure target_retirement_income is a number
        const income = userData.target_retirement_income
          ? (typeof userData.target_retirement_income === 'string'
            ? parseFloat(userData.target_retirement_income)
            : userData.target_retirement_income)
          : 0;
        setTargetRetirementIncome(income);
        setEquityTarget(userData.asset_class_targets?.equity || 0);
        setFixedIncomeTarget(userData.asset_class_targets?.fixed_income || 0);
        setNorthAmericaTarget(userData.region_targets?.north_america || 0);
        setInternationalTarget(userData.region_targets?.international || 0);

        // Get accounts
        const accountsResponse = await fetch(`${API_URL}/api/accounts`, {
          headers: {
            "Authorization": `Bearer ${token}`,
          },
        });

        if (accountsResponse.ok) {
          const accountsData = await accountsResponse.json();
          setAccounts(accountsData);

          // Get positions for each account
          const positionsMap: Record<string, Position[]> = {};
          const instrumentsMap: Record<string, Instrument> = {};

          for (const account of accountsData) {
            // Skip if account has no ID
            if (!account.id) {
              console.warn('Account missing ID in dashboard:', account);
              continue;
            }

            const positionsResponse = await fetch(`${API_URL}/api/accounts/${account.id}/positions`, {
              headers: {
                "Authorization": `Bearer ${token}`,
              },
            });

            if (positionsResponse.ok) {
              const positionsData = await positionsResponse.json();
              // API returns positions in a positions key
              positionsMap[account.id] = positionsData.positions || [];

              // Store instrument data from each position
              for (const position of positionsData.positions || []) {
                if (position.instrument) {
                  instrumentsMap[position.symbol] = position.instrument as Instrument;
                }
              }
            }
          }

          setPositions(positionsMap);
          setInstruments(instrumentsMap);
        }

        // Get last analysis date
        // This would come from the jobs endpoint in a real implementation
        setLastAnalysisDate(null);

      } catch (err) {
        console.error("Error loading data:", err);
        setError(err instanceof Error ? err.message : "Failed to load data");
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [userLoaded, user, getToken]);

  // Listen for analysis completion events to refresh data
  useEffect(() => {
    if (!userLoaded || !user) return;

    const handleAnalysisCompleted = async () => {
      try {
        const token = await getToken();
        if (!token) return;

        console.log('Analysis completed - refreshing dashboard data...');

        // Refresh accounts to get latest prices
        const accountsResponse = await fetch(`${API_URL}/api/accounts`, {
          headers: {
            "Authorization": `Bearer ${token}`,
          },
        });

        if (accountsResponse.ok) {
          const accountsData = await accountsResponse.json();
          setAccounts(accountsData.accounts || []);

          // Load positions for each account
          const positionsData: Record<string, Position[]> = {};
          const instrumentsData: Record<string, Instrument> = {};

          for (const account of accountsData.accounts || []) {
            const positionsResponse = await fetch(
              `${API_URL}/api/accounts/${account.id}/positions`,
              {
                headers: {
                  "Authorization": `Bearer ${token}`,
                },
              }
            );

            if (positionsResponse.ok) {
              const data = await positionsResponse.json();
              positionsData[account.id] = data.positions || [];

              // Extract instruments from positions
              for (const position of data.positions || []) {
                if (position.instrument) {
                  instrumentsData[position.symbol] = position.instrument;
                }
              }
            }
          }

          setPositions(positionsData);
          setInstruments(instrumentsData);

          // Portfolio will be recalculated on render
        }
      } catch (err) {
        console.error("Error refreshing dashboard data:", err);
      }
    };

    // Listen for the completion event
    window.addEventListener('analysis:completed', handleAnalysisCompleted);

    return () => {
      window.removeEventListener('analysis:completed', handleAnalysisCompleted);
    };
  }, [userLoaded, user, getToken, calculatePortfolioSummary]);

  // Save user settings
  const handleSaveSettings = async () => {
    if (!userData) return;

    // Input validation
    if (!displayName || displayName.trim().length === 0) {
      showToast('error', 'Display name is required');
      return;
    }

    if (yearsUntilRetirement < 0 || yearsUntilRetirement > 50) {
      showToast('error', 'Years until retirement must be between 0 and 50');
      return;
    }

    if (targetRetirementIncome < 0) {
      showToast('error', 'Target retirement income must be positive');
      return;
    }

    // Validate allocation percentages
    const equityFixed = equityTarget + fixedIncomeTarget;
    if (Math.abs(equityFixed - 100) > 0.01) {
      showToast('error', 'Equity and Fixed Income must sum to 100%');
      return;
    }

    const regionTotal = northAmericaTarget + internationalTarget;
    if (Math.abs(regionTotal - 100) > 0.01) {
      showToast('error', 'North America and International must sum to 100%');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");

      const updateData = {
        display_name: displayName.trim(),
        years_until_retirement: yearsUntilRetirement,
        target_retirement_income: targetRetirementIncome,
        asset_class_targets: {
          equity: equityTarget,
          fixed_income: fixedIncomeTarget
        },
        region_targets: {
          north_america: northAmericaTarget,
          international: internationalTarget
        }
      };

      const response = await fetch(`${API_URL}/api/user`, {
        method: "PUT",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(updateData),
      });

      if (!response.ok) {
        throw new Error(`Failed to save settings: ${response.status}`);
      }

      const updatedUser = await response.json();
      setUserData(updatedUser);

      // Show success toast
      showToast('success', 'Settings saved successfully!');

    } catch (err) {
      console.error("Error saving settings:", err);
      showToast('error', err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const { totalValue, assetClassBreakdown } = calculatePortfolioSummary();

  // Prepare data for pie chart
  const pieChartData = Object.entries(assetClassBreakdown)
    .filter(([, value]) => value > 0)
    .map(([key, value]) => ({
      name: key.charAt(0).toUpperCase() + key.slice(1).replace('_', ' '),
      value: Math.round(value),
      percentage: totalValue > 0 ? Math.round(value / totalValue * 100) : 0
    }));

  const COLORS = ['#209DD7', '#753991', '#FFB707', '#062147', '#10B981'];

  return (
    <>
      <Head>
        <title>Dashboard - Alex AI Financial Advisor</title>
      </Head>
      <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-3xl font-bold text-dark mb-8">Dashboard</h1>

        {loading ? (
          // Loading skeleton
          <div className="space-y-8">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="bg-white rounded-lg shadow p-6">
                  <Skeleton className="h-4 w-3/4 mx-auto mb-3" />
                  <Skeleton className="h-8 w-1/2 mx-auto" />
                </div>
              ))}
            </div>
            <SkeletonCard />
            <SkeletonCard />
          </div>
        ) : (
          <>
            {/* Portfolio Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <h3 className="text-sm font-medium text-gray-500 mb-3">Total Portfolio Value</h3>
            <p className="text-3xl font-bold text-primary">
              ${totalValue % 1 === 0
                ? totalValue.toLocaleString('en-US')
                : totalValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-6 text-center">
            <h3 className="text-sm font-medium text-gray-500 mb-3">Number of Accounts</h3>
            <p className="text-3xl font-bold text-dark">{accounts.length}</p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-2 text-center">Asset Allocation</h3>
            {pieChartData.length > 0 ? (
              <div className="h-24">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieChartData}
                      cx="50%"
                      cy="50%"
                      innerRadius={20}
                      outerRadius={40}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {pieChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value: number) => `$${value.toLocaleString()}`} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-gray-500">No positions yet</p>
            )}
          </div>

          <div className="bg-white rounded-lg shadow p-6 text-center">
            <h3 className="text-sm font-medium text-gray-500 mb-3">Last Analysis</h3>
            <p className="text-3xl font-bold text-dark">
              {lastAnalysisDate ? new Date(lastAnalysisDate).toLocaleDateString() : "Never"}
            </p>
          </div>
        </div>

        {/* User Settings Section */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-xl font-semibold text-dark mb-6">User Settings</h2>

          {loading ? (
            <p className="text-gray-500">Loading...</p>
          ) : error && !error.includes("success") ? (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
              <p className="text-red-600">{error}</p>
            </div>
          ) : error && error.includes("success") ? (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
              <p className="text-green-600">✅ {error}</p>
            </div>
          ) : null}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Basic Info */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Display Name
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Target Retirement Income (Annual)
              </label>
              <input
                type="text"
                value={targetRetirementIncome ? targetRetirementIncome.toLocaleString('en-US') : ''}
                onChange={(e) => {
                  // Remove commas and parse as number
                  const value = e.target.value.replace(/,/g, '');
                  const num = parseInt(value) || 0;
                  if (!isNaN(num)) {
                    setTargetRetirementIncome(num);
                  }
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            {/* Retirement Slider */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Years Until Retirement: {yearsUntilRetirement}
              </label>
              <input
                type="range"
                min="0"
                max="50"
                value={yearsUntilRetirement}
                onChange={(e) => setYearsUntilRetirement(Number(e.target.value))}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-500">
                <span>0</span>
                <span>10</span>
                <span>20</span>
                <span>30</span>
                <span>40</span>
                <span>50</span>
              </div>
            </div>

            {/* Target Allocations */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-3">Target Asset Class Allocation</h3>
              <div className="space-y-3">
                <div>
                  <label className="text-sm text-gray-600">Equity: {equityTarget}%</label>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={equityTarget}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setEquityTarget(val);
                      setFixedIncomeTarget(100 - val);
                    }}
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="text-sm text-gray-600">Fixed Income: {fixedIncomeTarget}%</label>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={fixedIncomeTarget}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setFixedIncomeTarget(val);
                      setEquityTarget(100 - val);
                    }}
                    className="w-full"
                  />
                </div>
              </div>

              {/* Mini pie chart for asset allocation */}
              <div className="mt-4 h-32">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={[
                        { name: 'Equity', value: equityTarget },
                        { name: 'Fixed Income', value: fixedIncomeTarget }
                      ]}
                      cx="50%"
                      cy="50%"
                      outerRadius={40}
                      dataKey="value"
                    >
                      <Cell fill="#209DD7" />
                      <Cell fill="#753991" />
                    </Pie>
                    <Tooltip formatter={(value) => `${value}%`} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-3">Target Regional Allocation</h3>
              <div className="space-y-3">
                <div>
                  <label className="text-sm text-gray-600">North America: {northAmericaTarget}%</label>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={northAmericaTarget}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setNorthAmericaTarget(val);
                      setInternationalTarget(100 - val);
                    }}
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="text-sm text-gray-600">International: {internationalTarget}%</label>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={internationalTarget}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setInternationalTarget(val);
                      setNorthAmericaTarget(100 - val);
                    }}
                    className="w-full"
                  />
                </div>
              </div>

              {/* Mini pie chart for regional allocation */}
              <div className="mt-4 h-32">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={[
                        { name: 'North America', value: northAmericaTarget },
                        { name: 'International', value: internationalTarget }
                      ]}
                      cx="50%"
                      cy="50%"
                      outerRadius={40}
                      dataKey="value"
                    >
                      <Cell fill="#FFB707" />
                      <Cell fill="#062147" />
                    </Pie>
                    <Tooltip formatter={(value) => `${value}%`} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="mt-6">
            <button
              onClick={handleSaveSettings}
              disabled={saving || loading}
              className={`px-6 py-2 rounded-lg font-medium transition-colors ${
                saving || loading
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-primary text-white hover:bg-blue-600'
              }`}
            >
              {saving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </div>
          </>
        )}
      </div>
      </Layout>
    </>
  );
}