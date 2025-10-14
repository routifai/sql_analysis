'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

export default function SuccessPage() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-gradient-to-b from-green-50 to-white flex items-center justify-center p-4">
      <div className="max-w-2xl w-full text-center">
        <div className="bg-white rounded-lg shadow-xl p-12">
          <div className="text-6xl mb-6">🎉</div>
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Onboarding Complete!
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Your database has been successfully connected and cataloged.
          </p>

          <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-8">
            <h2 className="font-semibold text-green-900 mb-3">What's Next?</h2>
            <div className="text-left text-green-800 space-y-3">
              <p className="flex items-start gap-2">
                <span className="font-bold">1.</span>
                <span>Use the MCP server to query your database with natural language</span>
              </p>
              <p className="flex items-start gap-2">
                <span className="font-bold">2.</span>
                <span>Make sure to include your email when making queries</span>
              </p>
              <p className="flex items-start gap-2">
                <span className="font-bold">3.</span>
                <span>The system will automatically route to your database and use your custom catalog</span>
              </p>
            </div>
          </div>

          <div className="bg-gray-50 rounded-lg p-6 mb-8">
            <h3 className="font-semibold text-gray-900 mb-3">Example MCP Query:</h3>
            <pre className="text-left bg-gray-900 text-green-400 p-4 rounded text-sm overflow-x-auto">
{`{
  "query": "Show me all users who joined last month",
  "user_email": "your@email.com"
}`}
            </pre>
          </div>

          <div className="flex gap-4 justify-center">
            <Link
              href="/"
              className="bg-blue-600 text-white px-8 py-3 rounded-md hover:bg-blue-700 transition-colors font-medium"
            >
              Back to Home
            </Link>
            <Link
              href="/onboard"
              className="border border-gray-300 px-8 py-3 rounded-md hover:bg-gray-50 transition-colors font-medium"
            >
              Onboard Another Database
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

