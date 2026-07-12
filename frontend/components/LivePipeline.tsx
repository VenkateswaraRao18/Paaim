'use client';

import React, { useEffect, useState } from 'react';
import { usePipelineStream } from '@/lib/api-client';

interface LivePipelineProps {
  decisionId: string;
  autoScroll?: boolean;
}

const layerNames: Record<string, string> = {
  agents: 'Agents',
  policy: 'Policy',
  twin: 'Twin',
  red_team: 'Red-Team',
  approval: 'Approval',
  pipeline: 'Pipeline',
};

const eventIcons: Record<string, string> = {
  orchestration_started: '→',
  agents_routing: '→', agents_complete: '✓',
  policy_checking: '→', policy_complete: '✓',
  twin_simulating: '→', twin_complete: '✓',
  red_team_challenging: '→', red_team_complete: '✓',
  approval_routing: '→', approval_complete: '✓',
  orchestration_completed: '✓', orchestration_error: '✗',
};

export function LivePipeline({ decisionId, autoScroll = true }: LivePipelineProps) {
  const { events, isConnected, error } = usePipelineStream(decisionId);
  const [completedLayers, setCompletedLayers] = useState<Set<string>>(new Set());
  const endRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    const newCompleted = new Set(completedLayers);
    events.forEach((evt) => {
      if (evt.event_type.includes('complete') || evt.event_type === 'orchestration_completed') {
        newCompleted.add(evt.layer);
      }
    });
    setCompletedLayers(newCompleted);
  }, [events]);

  useEffect(() => {
    if (autoScroll) endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events, autoScroll]);

  if (error) {
    return (
      <div className="alert alert-bad bg-surface-bad border border-l-4 p-4">
        <p className="text-coral font-semibold text-[14px]">Connection error</p>
        <p className="text-ink/80 text-[13px] mt-0.5">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Connection status */}
      <div className="flex items-center gap-2 px-4 py-2 bg-surface-ok rounded-lg border border-moss">
        <span className="relative flex w-1.5 h-1.5">
          {isConnected && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-pine-2 opacity-50" />}
          <span className={`relative inline-flex rounded-full h-1.5 w-1.5 ${isConnected ? 'bg-pine-2' : 'bg-moss'}`} />
        </span>
        <span className="text-[13px] font-medium text-pine-2">
          {isConnected ? 'Live' : 'Connecting…'} · {events.length} events
        </span>
      </div>

      {/* Pipeline layers progress */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
        {Object.entries(layerNames).map(([layer, name]) => {
          const done = completedLayers.has(layer);
          return (
            <div
              key={layer}
              className={`p-2 rounded-lg text-center text-[12px] font-semibold transition-all border ${
                done ? 'bg-surface-ok text-pine-2 border-moss' : 'bg-paper text-dim border-line'
              }`}
            >
              {name}
              {done && <div className="text-[10px]">✓</div>}
            </div>
          );
        })}
      </div>

      {/* Event timeline */}
      <div className="bg-card border border-line rounded-lg p-4 max-h-96 overflow-y-auto font-mono text-[13px]">
        {events.length === 0 ? (
          <p className="text-dim italic">Waiting for events…</p>
        ) : (
          <div className="space-y-2">
            {events.map((event, idx) => (
              <div key={idx} className="flex gap-2 pb-2 border-b border-line last:border-0">
                <span className="text-pine-2 min-w-fit">{eventIcons[event.event_type] || '•'}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex gap-2 items-baseline">
                    <span className="font-bold text-pine-2">{event.event_type}</span>
                    <span className="text-dim">{layerNames[event.layer] || event.layer}</span>
                  </div>
                  {Object.keys(event.data).length > 0 && (
                    <div className="text-[11px] text-dim mt-1">
                      {JSON.stringify(event.data).substring(0, 60).replace(/[{}"]/, '')}
                      {JSON.stringify(event.data).length > 60 ? '…' : ''}
                    </div>
                  )}
                  <div className="text-[11px] text-dim/70 mt-1">{new Date(event.timestamp).toLocaleTimeString()}</div>
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
