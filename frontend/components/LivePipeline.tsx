'use client';

import React, { useEffect, useState } from 'react';
import { usePipelineStream, PipelineEvent, PipelineEventType } from '@/lib/api-client';

interface LivePipelineProps {
  decisionId: string;
  autoScroll?: boolean;
}

const layerNames: Record<string, string> = {
  'agents': '🤖 Agents',
  'policy': '⚖️ Policy',
  'twin': '🔮 Twin',
  'red_team': '🎯 Red-Team',
  'approval': '✅ Approval',
  'pipeline': '⚡ Pipeline',
};

const eventIcons: Record<string, string> = {
  'orchestration_started': '🚀',
  'agents_routing': '→',
  'agents_complete': '✓',
  'policy_checking': '→',
  'policy_complete': '✓',
  'twin_simulating': '→',
  'twin_complete': '✓',
  'red_team_challenging': '→',
  'red_team_complete': '✓',
  'approval_routing': '→',
  'approval_complete': '✓',
  'orchestration_completed': '✓',
  'orchestration_error': '✗',
};

export function LivePipeline({
  decisionId,
  autoScroll = true,
}: LivePipelineProps) {
  const { events, isConnected, error } = usePipelineStream(decisionId);
  const [completedLayers, setCompletedLayers] = useState<Set<string>>(new Set());
  const endRef = React.useRef<HTMLDivElement>(null);

  // Track completed layers
  useEffect(() => {
    const newCompleted = new Set(completedLayers);
    events.forEach((evt) => {
      if (
        evt.event_type.includes('complete') ||
        evt.event_type === 'orchestration_completed'
      ) {
        newCompleted.add(evt.layer);
      }
    });
    setCompletedLayers(newCompleted);
  }, [events]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll) {
      endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events, autoScroll]);

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800 font-semibold">Connection Error</p>
        <p className="text-red-600 text-sm">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Connection Status */}
      <div className="flex items-center gap-2 px-4 py-2 bg-blue-50 rounded-lg border border-blue-200">
        <div
          className={`w-2 h-2 rounded-full ${
            isConnected ? 'bg-green-500' : 'bg-gray-400'
          }`}
        />
        <span className="text-sm font-medium text-blue-900">
          {isConnected ? 'Live' : 'Connecting...'} ({events.length} events)
        </span>
      </div>

      {/* Pipeline Layers Progress */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
        {Object.entries(layerNames).map(([layer, name]) => (
          <div
            key={layer}
            className={`p-2 rounded text-center text-sm font-medium transition-all ${
              completedLayers.has(layer)
                ? 'bg-green-100 text-green-900 border border-green-300'
                : 'bg-gray-100 text-gray-700 border border-gray-300'
            }`}
          >
            {name}
            {completedLayers.has(layer) && (
              <div className="text-xs">✓</div>
            )}
          </div>
        ))}
      </div>

      {/* Event Timeline */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 max-h-96 overflow-y-auto font-mono text-sm">
        {events.length === 0 ? (
          <p className="text-gray-500 italic">Waiting for events...</p>
        ) : (
          <div className="space-y-2">
            {events.map((event, idx) => (
              <div
                key={idx}
                className="flex gap-2 pb-2 border-b border-gray-100 last:border-0"
              >
                <span className="text-lg min-w-fit">
                  {eventIcons[event.event_type] || '•'}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex gap-2 items-baseline">
                    <span className="font-bold text-blue-600">
                      {event.event_type}
                    </span>
                    <span className="text-gray-500">
                      {layerNames[event.layer] || event.layer}
                    </span>
                  </div>
                  {Object.keys(event.data).length > 0 && (
                    <div className="text-xs text-gray-600 mt-1">
                      {JSON.stringify(event.data)
                        .substring(0, 60)
                        .replace(/[{}"]/, '')}
                      {JSON.stringify(event.data).length > 60 ? '...' : ''}
                    </div>
                  )}
                  <div className="text-xs text-gray-400 mt-1">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))}
            <div ref={endRef} />
          </div>
        )}
      </div>
    </div>
  );
}
