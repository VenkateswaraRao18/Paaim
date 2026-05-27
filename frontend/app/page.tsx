'use client'

import Link from 'next/link';
import { motion } from 'framer-motion';

export default function Home() {
  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  };

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 },
  };

  const features = [
    {
      icon: '🤖',
      title: 'Multi-Agent Orchestration',
      description: '5 specialist agents analyze decisions in parallel with AI-powered insights',
    },
    {
      icon: '⚡',
      title: 'Custom Agents',
      description: 'No-code builder to connect SCADA, CMS, IoT systems and define policies',
    },
    {
      icon: '🛡️',
      title: 'Policy Engine',
      description: 'Industrial Constitution enforcement with automatic constraint checking',
    },
    {
      icon: '📊',
      title: 'Decision Twin',
      description: 'Simulate impact of actions before execution - downtime, scrap, cost',
    },
    {
      icon: '🔍',
      title: 'Red-Team Challenge',
      description: 'AI questions assumptions and suggests safer alternatives automatically',
    },
    {
      icon: '👤',
      title: 'Human Approval',
      description: 'Right person approves right decision based on risk and role',
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900">
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-grid-pattern opacity-5" />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 sm:py-32">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center"
          >
            <div className="mb-8">
              <h1 className="text-5xl sm:text-7xl font-bold text-white mb-6">
                PAAIM
              </h1>
              <p className="text-xl sm:text-2xl text-blue-200 mb-2">
                Policy-Aware Agentic Intelligence Manager
              </p>
              <p className="text-lg text-gray-400">
                From Alert Overload to Coordinated, Governed Action
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="/dashboard"
                className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 px-8 rounded-lg text-lg transition-colors shadow-lg"
              >
                → Launch Dashboard
              </Link>
              <Link
                href="/custom-agents"
                className="inline-block bg-gray-700 hover:bg-gray-800 text-white font-bold py-4 px-8 rounded-lg text-lg transition-colors shadow-lg"
              >
                ⚡ Build Custom Agent
              </Link>
            </div>
          </motion.div>

          {/* Hero Stats */}
          <motion.div
            variants={container}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 sm:grid-cols-3 gap-8 mt-20"
          >
            {[
              { label: 'Specialist Agents', value: '5' },
              { label: 'Decision Layers', value: '7' },
              { label: 'Production Ready', value: '✓' },
            ].map((stat, i) => (
              <motion.div key={i} variants={item} className="text-center">
                <div className="text-4xl font-bold text-blue-400 mb-2">{stat.value}</div>
                <div className="text-gray-400">{stat.label}</div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section className="bg-gray-900 py-20 sm:py-32">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl font-bold text-white mb-4">Complete Pipeline</h2>
            <p className="text-xl text-gray-400">
              7-layer orchestration with policy enforcement, simulation, and human approval
            </p>
          </motion.div>

          <motion.div
            variants={container}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true }}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8"
          >
            {features.map((feature, i) => (
              <motion.div
                key={i}
                variants={item}
                className="bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-700 rounded-lg p-8 hover:border-blue-500 transition-colors"
              >
                <div className="text-4xl mb-4">{feature.icon}</div>
                <h3 className="text-xl font-bold text-white mb-2">{feature.title}</h3>
                <p className="text-gray-400">{feature.description}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Architecture Section */}
      <section className="bg-gradient-to-br from-blue-900 to-gray-900 py-20 sm:py-32">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl font-bold text-white mb-4">7-Layer Pipeline</h2>
            <p className="text-xl text-blue-200">
              Manufacturing event → intelligent decision in under 2 seconds
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="bg-gray-900 border border-blue-500 rounded-lg p-8 sm:p-12"
          >
            <div className="space-y-6 max-w-2xl mx-auto">
              {[
                { num: 1, title: 'Event Input', desc: 'Real MES/CMMS data or simulator' },
                { num: 2, title: 'Agent Analysis', desc: '5 specialists analyze simultaneously' },
                { num: 3, title: 'Policy Engine', desc: 'Check Industrial Constitution' },
                {
                  num: 4,
                  title: 'Decision Twin',
                  desc: 'Simulate downtime, scrap, cost',
                },
                { num: 5, title: 'Red-Team Challenge', desc: 'Claude API questions assumptions' },
                {
                  num: 6,
                  title: 'Approval Gate',
                  desc: 'Route to correct human',
                },
                {
                  num: 7,
                  title: 'Audit Trail',
                  desc: 'Record complete decision journey',
                },
              ].map((layer, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.05 }}
                  className="flex items-start gap-4"
                >
                  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center font-bold text-white">
                    {layer.num}
                  </div>
                  <div>
                    <h4 className="font-bold text-white">{layer.title}</h4>
                    <p className="text-gray-400 text-sm">{layer.desc}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="bg-gray-900 py-20 sm:py-32">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-4xl font-bold text-white mb-6">
              Ready to Take Control?
            </h2>
            <p className="text-xl text-gray-400 mb-8">
              Transform manufacturing decision-making from reactive alerts to proactive,
              governed intelligence.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="/dashboard"
                className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 px-8 rounded-lg text-lg transition-colors shadow-lg"
              >
                View Dashboard
              </Link>
              <Link
                href="/custom-agents"
                className="inline-block bg-gray-700 hover:bg-gray-800 text-white font-bold py-4 px-8 rounded-lg text-lg transition-colors shadow-lg"
              >
                Create Agent
              </Link>
            </div>

            <p className="text-gray-500 text-sm mt-8">
              Production-ready system • Real product, not a demo • Kubernetes deployment ready
            </p>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
