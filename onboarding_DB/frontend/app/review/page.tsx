'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

function ReviewContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  const [email, setEmail] = useState('');
  const [dbInfo, setDbInfo] = useState({
    host: '',
    port: '',
    dbUser: '',
    dbPassword: '',
    dbName: '',
  });
  const [catalog, setCatalog] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    // Get parameters from URL
    const emailParam = searchParams.get('email');
    const catalogParam = searchParams.get('catalog');
    const hostParam = searchParams.get('host');
    const portParam = searchParams.get('port');
    const dbUserParam = searchParams.get('dbUser');
    const dbPasswordParam = searchParams.get('dbPassword');
    const dbNameParam = searchParams.get('dbName');
    
    if (emailParam) setEmail(emailParam);
    if (catalogParam) setCatalog(catalogParam);
    if (hostParam && portParam && dbUserParam && dbPasswordParam && dbNameParam) {
      setDbInfo({
        host: hostParam,
        port: portParam,
        dbUser: dbUserParam,
        dbPassword: dbPasswordParam,
        dbName: dbNameParam,
      });
    }
  }, [searchParams]);

  const handleSave = async () => {
    if (!email || !catalog || !dbInfo.host) {
      setError('Missing required information. Please go back and try again.');
      return;
    }

    setLoading(true);
    setError('');
    
    try {
      const response = await fetch('http://localhost:8001/api/onboard/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_email: email,
          catalog_markdown: catalog,
          db_info: {
            user_email: email,
            db_type: 'postgres',
            host: dbInfo.host,
            port: parseInt(dbInfo.port),
            db_user: dbInfo.dbUser,
            db_password: dbInfo.dbPassword,
            db_name: dbInfo.dbName,
          },
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to save');
      }

      setSuccess(true);
      
      // Redirect after 2 seconds
      setTimeout(() => {
        router.push('/success');
      }, 2000);
      
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const lineCount = catalog.split('\n').length;

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-6xl mx-auto py-8">
        <div className="mb-6">
          <button
            onClick={() => router.back()}
            className="text-blue-600 hover:text-blue-800 flex items-center gap-2"
          >
            ← Back
          </button>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Review Your Database Catalog
          </h1>
          <div className="flex items-center gap-4 mb-6">
            <p className="text-gray-600">
              Email: <span className="font-semibold text-gray-900">{email}</span>
            </p>
            <span className="text-gray-300">•</span>
            <p className="text-gray-600">
              Database: <span className="font-semibold text-gray-900">{dbInfo.dbName}</span>
            </p>
          </div>

          {success && (
            <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-md">
              <p className="text-green-800 font-medium flex items-center gap-2">
                <span className="text-xl">✅</span>
                Catalog saved successfully! Redirecting...
              </p>
            </div>
          )}

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
              <p className="text-red-800 font-medium">Error:</p>
              <p className="text-red-700 text-sm mt-1">{error}</p>
            </div>
          )}

          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <label className="block text-sm font-medium text-gray-700">
                Database Catalog (Markdown)
              </label>
              <span className="text-sm text-gray-500">
                {lineCount} lines • {catalog.length} characters
              </span>
            </div>
            <textarea
              value={catalog}
              onChange={(e) => setCatalog(e.target.value)}
              rows={30}
              className="w-full px-4 py-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
              placeholder="Catalog will appear here..."
            />
            <div className="mt-3 p-4 bg-blue-50 border border-blue-200 rounded-md">
              <p className="text-sm text-blue-900 font-medium mb-2">
                💡 Pro Tips for Better AI Query Results:
              </p>
              <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
                <li>Add business-friendly descriptions to tables and columns</li>
                <li>Include examples of common queries or patterns</li>
                <li>Document column meanings (e.g., "user_status: active, pending, or suspended")</li>
                <li>Note any important relationships or constraints</li>
              </ul>
            </div>
          </div>

          <div className="flex gap-4">
            <button
              onClick={handleSave}
              disabled={loading || success}
              className="flex-1 bg-blue-600 text-white py-3 px-6 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium transition-colors"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Saving...
                </span>
              ) : success ? (
                'Saved ✓'
              ) : (
                'Save & Complete Onboarding'
              )}
            </button>
            <button
              onClick={() => router.back()}
              disabled={loading}
              className="px-8 py-3 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              Back
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ReviewPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    }>
      <ReviewContent />
    </Suspense>
  );
}

