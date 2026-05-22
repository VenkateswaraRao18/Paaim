'use client'

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-6xl mx-auto px-4 py-16">
        <div className="text-center">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">
            PAAIM Dashboard
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Policy-Aware Agentic Intelligence Manager
          </p>
          <p className="text-lg text-gray-500 mb-12">
            Manufacturing Decision Orchestration Layer
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-12">
            <div className="bg-white rounded-lg shadow-md p-8">
              <h2 className="text-2xl font-bold text-blue-600 mb-4">📊 Dashboard</h2>
              <p className="text-gray-600">
                Real-time incident tracking and decision monitoring
              </p>
            </div>

            <div className="bg-white rounded-lg shadow-md p-8">
              <h2 className="text-2xl font-bold text-purple-600 mb-4">⚙️ Agents</h2>
              <p className="text-gray-600">
                Built-in and custom agents for all manufacturing domains
              </p>
            </div>

            <div className="bg-white rounded-lg shadow-md p-8">
              <h2 className="text-2xl font-bold text-green-600 mb-4">📋 Audit Log</h2>
              <p className="text-gray-600">
                Complete evidence trail for compliance and transparency
              </p>
            </div>
          </div>

          <div className="mt-16">
            <p className="text-gray-600 mb-6">
              Status: <span className="inline-block px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-semibold">Ready</span>
            </p>
            <p className="text-sm text-gray-500">
              Phase 0: Foundation Setup — All services running ✅
            </p>
          </div>
        </div>
      </div>
    </main>
  )
}
