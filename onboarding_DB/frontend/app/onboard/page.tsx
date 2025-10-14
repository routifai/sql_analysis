'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function OnboardingPage() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    email: '',
    host: 'localhost',
    port: '5432',
    dbUser: '',
    dbPassword: '',
    dbName: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [availableTables, setAvailableTables] = useState<string[]>([]);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [loadingTables, setLoadingTables] = useState(false);
  const [showTableSelector, setShowTableSelector] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<{
    tested: boolean;
    success: boolean;
    message: string;
    dbVersion?: string;
  } | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
    // Reset connection status when user changes connection info
    if (['host', 'port', 'dbUser', 'dbPassword', 'dbName'].includes(e.target.name)) {
      setConnectionStatus(null);
    }
  };

  const handleTestConnection = async () => {
    if (!formData.host || !formData.dbName || !formData.dbUser || !formData.dbPassword) {
      setError('Please fill in all database connection fields first');
      return;
    }

    setTestingConnection(true);
    setError('');
    setConnectionStatus(null);

    try {
      const response = await fetch('http://localhost:8001/api/onboard/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_email: formData.email,
          db_type: 'postgres',
          host: formData.host,
          port: parseInt(formData.port),
          db_user: formData.dbUser,
          db_password: formData.dbPassword,
          db_name: formData.dbName,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to connect to database');
      }

      setConnectionStatus({
        tested: true,
        success: true,
        message: data.message,
        dbVersion: data.db_version,
      });
    } catch (err: any) {
      setConnectionStatus({
        tested: true,
        success: false,
        message: err.message,
      });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleListTables = async () => {
    if (!formData.host || !formData.dbName || !formData.dbUser || !formData.dbPassword) {
      setError('Please fill in all database connection fields first');
      return;
    }

    setLoadingTables(true);
    setError('');

    try {
      const response = await fetch('http://localhost:8001/api/onboard/list-tables', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_email: formData.email,
          db_type: 'postgres',
          host: formData.host,
          port: parseInt(formData.port),
          db_user: formData.dbUser,
          db_password: formData.dbPassword,
          db_name: formData.dbName,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to list tables');
      }

      const data = await response.json();
      setAvailableTables(data.tables);
      setShowTableSelector(true);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoadingTables(false);
    }
  };

  const handleTableToggle = (table: string) => {
    setSelectedTables((prev) =>
      prev.includes(table) ? prev.filter((t) => t !== table) : [...prev, table]
    );
  };

  const handleSelectAllTables = () => {
    setSelectedTables(availableTables);
  };

  const handleDeselectAllTables = () => {
    setSelectedTables([]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const requestBody: any = {
        user_email: formData.email,
        db_type: 'postgres',
        host: formData.host,
        port: parseInt(formData.port),
        db_user: formData.dbUser,
        db_password: formData.dbPassword,
        db_name: formData.dbName,
      };

      // Add selected tables if any
      if (selectedTables.length > 0) {
        requestBody.table_names = selectedTables;
      }

      const response = await fetch('http://localhost:8001/api/onboard/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to generate catalog');
      }

      const data = await response.json();
      
      // Navigate to review page with data
      const queryParams = new URLSearchParams({
        email: formData.email,
        host: formData.host,
        port: formData.port,
        dbUser: formData.dbUser,
        dbPassword: formData.dbPassword,
        dbName: formData.dbName,
        catalog: data.catalog,
      });
      
      router.push(`/review?${queryParams.toString()}`);
      
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-3xl mx-auto py-8">
        <div className="mb-6">
          <button
            onClick={() => router.push('/')}
            className="text-blue-600 hover:text-blue-800 flex items-center gap-2"
          >
            ← Back to Home
          </button>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Database Onboarding
          </h1>
          <p className="text-gray-600 mb-8">
            Connect your PostgreSQL database to get started
          </p>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
              <p className="text-red-800 font-medium">Error:</p>
              <p className="text-red-700 text-sm mt-1">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                Email Address *
              </label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="simonoulaidi@gmail.com"
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 placeholder:text-gray-500 bg-white"
              />
              <p className="mt-1 text-sm text-gray-700">
                Used to identify your queries in the MCP server
              </p>
            </div>

            {/* Database Type */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Database Type
              </label>
              <div className="px-4 py-2 bg-gray-100 border border-gray-300 rounded-md text-gray-900">
                PostgreSQL (only supported type currently)
              </div>
            </div>

            {/* Host */}
            <div className="grid md:grid-cols-3 gap-4">
              <div className="md:col-span-2">
                <label htmlFor="host" className="block text-sm font-medium text-gray-700 mb-2">
                  Host *
                </label>
                <input
                  type="text"
                  id="host"
                  name="host"
                  value={formData.host}
                  onChange={handleChange}
                  placeholder="localhost"
                  required
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 placeholder:text-gray-500 bg-white"
                />
              </div>
              <div>
                <label htmlFor="port" className="block text-sm font-medium text-gray-700 mb-2">
                  Port *
                </label>
                <input
                  type="number"
                  id="port"
                  name="port"
                  value={formData.port}
                  onChange={handleChange}
                  placeholder="5432"
                  required
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 placeholder:text-gray-500 bg-white"
                />
              </div>
            </div>

            {/* Database Name */}
            <div>
              <label htmlFor="dbName" className="block text-sm font-medium text-gray-700 mb-2">
                Database Name *
              </label>
              <input
                type="text"
                id="dbName"
                name="dbName"
                value={formData.dbName}
                onChange={handleChange}
                placeholder="mydb"
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 placeholder:text-gray-500 bg-white"
              />
            </div>

            {/* Username */}
            <div>
              <label htmlFor="dbUser" className="block text-sm font-medium text-gray-700 mb-2">
                Database Username *
              </label>
              <input
                type="text"
                id="dbUser"
                name="dbUser"
                value={formData.dbUser}
                onChange={handleChange}
                placeholder="postgres"
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 placeholder:text-gray-500 bg-white"
              />
            </div>

            {/* Password */}
            <div>
              <label htmlFor="dbPassword" className="block text-sm font-medium text-gray-700 mb-2">
                Database Password *
              </label>
              <input
                type="password"
                id="dbPassword"
                name="dbPassword"
                value={formData.dbPassword}
                onChange={handleChange}
                placeholder="••••••••"
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 placeholder:text-gray-500 bg-white"
              />
            </div>

            {/* Test Connection Button and Status */}
            <div className="pt-4 border-t border-gray-200">
              <div className="flex items-center gap-4">
                <button
                  type="button"
                  onClick={handleTestConnection}
                  disabled={testingConnection || !formData.host || !formData.dbName || !formData.dbUser || !formData.dbPassword}
                  className="bg-green-600 text-white py-2 px-6 rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium transition-colors flex items-center gap-2"
                >
                  {testingConnection ? (
                    <>
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Testing...
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Test Connection
                    </>
                  )}
                </button>

                {connectionStatus && (
                  <div className={`flex-1 p-3 rounded-md ${
                    connectionStatus.success 
                      ? 'bg-green-50 border border-green-200' 
                      : 'bg-red-50 border border-red-200'
                  }`}>
                    <div className="flex items-start gap-2">
                      {connectionStatus.success ? (
                        <svg className="w-5 h-5 text-green-600 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                      ) : (
                        <svg className="w-5 h-5 text-red-600 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                        </svg>
                      )}
                      <div className="flex-1">
                        <p className={`text-sm font-medium ${
                          connectionStatus.success ? 'text-green-800' : 'text-red-800'
                        }`}>
                          {connectionStatus.message}
                        </p>
                        {connectionStatus.success && connectionStatus.dbVersion && (
                          <p className="text-xs text-green-700 mt-1">
                            {connectionStatus.dbVersion}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
              {!connectionStatus && (
                <p className="mt-2 text-sm text-gray-700">
                  Test your database connection before proceeding
                </p>
              )}
            </div>

            {/* Table Selection Section */}
            <div className="pt-4 border-t border-gray-200">
              <div className="flex justify-between items-center mb-4">
                <div>
                  <h3 className="text-lg font-medium text-gray-900">Table Selection (Optional)</h3>
                  <p className="text-sm text-gray-700">Select specific tables or generate catalog for all tables</p>
                </div>
                <button
                  type="button"
                  onClick={handleListTables}
                  disabled={loadingTables || !formData.host || !formData.dbName || !formData.dbUser || !formData.dbPassword}
                  className="bg-gray-600 text-white py-2 px-4 rounded-md hover:bg-gray-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-sm font-medium transition-colors"
                >
                  {loadingTables ? (
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Loading...
                    </span>
                  ) : (
                    'List Tables'
                  )}
                </button>
              </div>

              {showTableSelector && availableTables.length > 0 && (
                <div className="bg-gray-50 rounded-md p-4 border border-gray-200">
                  <div className="flex justify-between items-center mb-3">
                    <p className="text-sm font-medium text-gray-700">
                      Found {availableTables.length} tables | Selected: {selectedTables.length}
                    </p>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={handleSelectAllTables}
                        className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                      >
                        Select All
                      </button>
                      <span className="text-gray-400">|</span>
                      <button
                        type="button"
                        onClick={handleDeselectAllTables}
                        className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                      >
                        Deselect All
                      </button>
                    </div>
                  </div>
                  
                  <div className="max-h-60 overflow-y-auto grid grid-cols-2 gap-2">
                    {availableTables.map((table) => (
                      <label
                        key={table}
                        className="flex items-center gap-2 p-2 bg-white rounded border border-gray-200 hover:bg-gray-50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedTables.includes(table)}
                          onChange={() => handleTableToggle(table)}
                          className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                        />
                        <span className="text-sm text-gray-700 font-mono">{table}</span>
                      </label>
                    ))}
                  </div>
                  
                  {selectedTables.length === 0 && (
                    <p className="mt-2 text-xs text-gray-700 italic">
                      No tables selected. Catalog will include all tables.
                    </p>
                  )}
                </div>
              )}
            </div>

            <div className="pt-4">
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 text-white py-3 px-6 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium transition-colors"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Generating Catalog...
                  </span>
                ) : (
                  'Generate Catalog'
                )}
              </button>
            </div>
          </form>

          <div className="mt-8 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
            <p className="text-sm text-yellow-900">
              <strong>⚠️ Security Note:</strong> Your credentials are used to connect to your database and extract the schema. 
              In production, all credentials should be encrypted before storage.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

