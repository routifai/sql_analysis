import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center p-4">
      <div className="max-w-4xl w-full">
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">
            Text2SQL Onboarding
          </h1>
          <p className="text-xl text-gray-600">
            Connect your database and start querying with natural language
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8 mb-12">
          <div className="bg-white p-8 rounded-lg shadow-lg">
            <div className="text-4xl mb-4">🔗</div>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">
              Connect Database
            </h2>
            <p className="text-gray-600 mb-6">
              Securely connect your PostgreSQL database and we'll automatically extract your schema
            </p>
            <Link
              href="/onboard"
              className="inline-block bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 transition-colors font-medium"
            >
              Start Onboarding →
            </Link>
          </div>

          <div className="bg-white p-8 rounded-lg shadow-lg">
            <div className="text-4xl mb-4">📊</div>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">
              AI-Powered Catalog
            </h2>
            <p className="text-gray-600 mb-6">
              Review and enhance the generated catalog with business context for better query accuracy
            </p>
          </div>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h3 className="font-semibold text-blue-900 mb-3">How it works:</h3>
          <ol className="space-y-2 text-blue-800">
            <li className="flex items-start">
              <span className="font-bold mr-2">1.</span>
              <span>Enter your email and PostgreSQL connection details</span>
            </li>
            <li className="flex items-start">
              <span className="font-bold mr-2">2.</span>
              <span>We generate an AI-optimized catalog of your database schema</span>
            </li>
            <li className="flex items-start">
              <span className="font-bold mr-2">3.</span>
              <span>Review and add custom descriptions to improve AI understanding</span>
            </li>
            <li className="flex items-start">
              <span className="font-bold mr-2">4.</span>
              <span>Start querying your database using natural language!</span>
            </li>
          </ol>
        </div>

        <div className="mt-8 text-center text-sm text-gray-500">
          <p>Currently supporting: PostgreSQL</p>
        </div>
      </div>
    </div>
  );
}
