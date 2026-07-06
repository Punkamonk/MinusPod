import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { X } from 'lucide-react';
import LoadingSpinner from './LoadingSpinner';
import CueMarkModal from './CueMarkModal';
import { ghostBtn, primaryBtn, modalBackdrop, modalPanel, useEscape } from './cueScanStyles';
import { useScanQuery } from '../hooks/useScanQuery';
import {
  crossEpisodeScan,
  type CrossEpisodeCandidate,
  type CrossEpisodeScanResponse,
} from '../api/cueTemplates';
import { getEpisodes } from '../api/feeds';
import type { Episode } from '../api/types';
import { formatTimestamp } from '../utils/format';

const PICKER_PAGE_SIZE = 50;
// Maximum episodes a user may select for the cross-episode scan (server cap).
const CROSS_EPISODE_MAX = 5;
const CROSS_EPISODE_MIN = 2;

interface CueCrossEpisodeScanModalProps {
  slug: string;
  captureMinSeconds: number;
  captureMaxSeconds: number;
  captureMaxIntroSeconds: number;
  captureMaxOutroSeconds: number;
  onClose: () => void;
  onSaved: () => void;
}

export default function CueCrossEpisodeScanModal({
  slug,
  captureMinSeconds,
  captureMaxSeconds,
  captureMaxIntroSeconds,
  captureMaxOutroSeconds,
  onClose,
  onSaved,
}: CueCrossEpisodeScanModalProps) {
  useEscape(onClose);
  const [pickerPage, setPickerPage] = useState(0);
  // Selected episodes in click order (first = target). Full objects, not ids,
  // so title/duration survive paging away from the page they were picked on.
  const [selected, setSelected] = useState<Episode[]>([]);
  // Phase: picker -> results (scanning/ready/error handled in scanQuery state).
  const [phase, setPhase] = useState<'picker' | 'results'>('picker');
  // Seed for CueMarkModal when a candidate's "Make template" is clicked.
  const [seed, setSeed] = useState<CrossEpisodeCandidate | null>(null);

  const pickerQuery = useQuery({
    queryKey: ['cue-template-picker', slug, pickerPage],
    queryFn: () =>
      getEpisodes(slug, {
        limit: PICKER_PAGE_SIZE,
        offset: pickerPage * PICKER_PAGE_SIZE,
        status: 'completed',
        sortBy: 'published',
        sortDir: 'desc',
      }),
    enabled: !!slug,
  });

  const pickerEpisodes = (pickerQuery.data?.episodes ?? [])
    .filter((ep) => ep.hasOriginalAudio !== false);
  const pickerTotal = pickerQuery.data?.total ?? 0;
  const pickerTotalPages = Math.max(1, Math.ceil(pickerTotal / PICKER_PAGE_SIZE));

  const selectedIds = selected.map((ep) => ep.id);
  const targetEp = selected[0];

  // React Query scan: enabled once user advances to results phase.
  // Polling stops when status is no longer 'scanning'.
  const scanQueryKey = ['cue-cross-episode-scan', slug, selectedIds];
  const { data: scanData, scanning, scanError, rescan } =
    useScanQuery<CrossEpisodeScanResponse>({
      queryKey: scanQueryKey,
      queryFn: () => crossEpisodeScan(slug, selectedIds),
      rescanFn: () => crossEpisodeScan(slug, selectedIds, true),
      enabled: phase === 'results' && selected.length >= CROSS_EPISODE_MIN,
      savedErrorFallback: 'Scan failed.',
      thrownError: 'Scan failed. Try again.',
    });

  const candidates: CrossEpisodeCandidate[] = scanData?.candidates ?? [];

  const toggleEpisode = (ep: Episode) => {
    setSelected((prev) => {
      if (prev.some((p) => p.id === ep.id)) return prev.filter((p) => p.id !== ep.id);
      if (prev.length >= CROSS_EPISODE_MAX) return prev;
      return [...prev, ep];
    });
  };

  // Picker phase
  if (phase === 'picker') {
    return (
      <div className={modalBackdrop} onClick={onClose}>
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Find cues across episodes"
          className={`${modalPanel} w-full max-w-2xl p-5 max-h-[85vh] flex flex-col`}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-start justify-between mb-3">
            <div>
              <h3 className="text-base font-semibold">Find cues across episodes</h3>
              <p className="text-xs text-muted-foreground">
                Select {CROSS_EPISODE_MIN}-{CROSS_EPISODE_MAX} episodes. Results are shown in the first selected episode's time.
              </p>
            </div>
            <button type="button" className="text-muted-foreground hover:text-foreground" onClick={onClose} aria-label="Close">
              <X size={18} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto border border-border rounded">
            {pickerQuery.isLoading && <div className="p-4"><LoadingSpinner size="sm" /></div>}
            {pickerQuery.error && <p className="p-3 text-sm text-destructive">Could not load episodes.</p>}
            {!pickerQuery.isLoading && pickerEpisodes.length === 0 && (
              <p className="p-3 text-sm text-muted-foreground">No episodes with original audio found.</p>
            )}
            {pickerEpisodes.length > 0 && (
              <ul className="divide-y divide-border">
                {pickerEpisodes.map((ep) => {
                  const checked = selectedIds.includes(ep.id);
                  const atMax = !checked && selectedIds.length >= CROSS_EPISODE_MAX;
                  const rank = selectedIds.indexOf(ep.id);
                  return (
                    <li key={ep.id}>
                      <label
                        className={`flex items-start gap-3 px-3 py-2 cursor-pointer select-none ${atMax ? 'opacity-50 cursor-not-allowed' : 'hover:bg-muted/50'}`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={atMax}
                          onChange={() => toggleEpisode(ep)}
                          className="mt-0.5 shrink-0"
                          aria-label={`Select episode ${ep.title}`}
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">
                            {ep.title}
                            {rank === 0 && (
                              <span className="ml-2 px-1.5 py-0.5 text-xs rounded font-medium bg-primary/20 text-primary align-middle">
                                target
                              </span>
                            )}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {ep.published ? new Date(ep.published).toLocaleDateString() : 'unknown date'}
                            {typeof ep.duration === 'number' && ep.duration > 0
                              ? ` - ${Math.round(ep.duration / 60)} min` : ''}
                          </p>
                        </div>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {pickerTotalPages > 1 && (
            <div className="flex items-center justify-between mt-3 text-sm">
              <button
                type="button"
                className={`px-2 py-1 rounded ${ghostBtn} disabled:opacity-50`}
                onClick={() => setPickerPage((p) => Math.max(0, p - 1))}
                disabled={pickerPage === 0}
              >
                Prev
              </button>
              <span className="text-muted-foreground">
                Page {pickerPage + 1} / {pickerTotalPages}
              </span>
              <button
                type="button"
                className={`px-2 py-1 rounded ${ghostBtn} disabled:opacity-50`}
                onClick={() => setPickerPage((p) => Math.min(pickerTotalPages - 1, p + 1))}
                disabled={pickerPage + 1 >= pickerTotalPages}
              >
                Next
              </button>
            </div>
          )}

          <div className="mt-3 flex items-center justify-between gap-3">
            <div className="text-xs text-muted-foreground">
              {selected.length === 0 && 'Select at least 2 episodes.'}
              {selected.length === 1 && 'Select 1 more episode.'}
              {selected.length >= CROSS_EPISODE_MIN && (
                <>
                  {selected.length} selected{selected.length === CROSS_EPISODE_MAX ? ' (max)' : ''}
                  {targetEp && (
                    <> - results on: <span className="font-medium text-foreground truncate max-w-[180px] inline-block align-bottom">{targetEp.title}</span></>
                  )}
                </>
              )}
            </div>
            <button
              type="button"
              className={`px-3 py-1.5 rounded ${primaryBtn} text-sm disabled:opacity-50`}
              disabled={selected.length < CROSS_EPISODE_MIN}
              onClick={() => setPhase('results')}
            >
              Scan
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Results phase
  return (
    <>
      <div className={modalBackdrop} onClick={onClose}>
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Cross-episode scan results"
          className={`${modalPanel} w-full max-w-2xl p-5 max-h-[85vh] flex flex-col`}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-start justify-between mb-3">
            <div>
              <h3 className="text-base font-semibold">Cross-episode scan</h3>
              {targetEp && (
                <p className="text-xs text-muted-foreground truncate max-w-xl">
                  Results on: {targetEp.title}
                </p>
              )}
            </div>
            <button type="button" className="text-muted-foreground hover:text-foreground" onClick={onClose} aria-label="Close">
              <X size={18} />
            </button>
          </div>

          <div className="flex flex-wrap gap-2 mb-3">
            <button
              type="button"
              className={`px-3 py-1.5 rounded ${ghostBtn} text-sm`}
              onClick={() => setPhase('picker')}
            >
              Change episodes
            </button>
            {!scanning && (
              <button
                type="button"
                className={`px-3 py-1.5 rounded ${ghostBtn} text-sm`}
                onClick={() => rescan()}
              >
                Rescan
              </button>
            )}
          </div>

          {scanning && (
            <p className="text-sm text-muted-foreground flex items-center gap-2 mb-3">
              <LoadingSpinner size="sm" inline /> Scanning audio, this can take a minute...
            </p>
          )}
          {!scanning && scanError && (
            <p className="text-sm text-destructive mb-3">{scanError}</p>
          )}
          {!scanning && !scanError && scanData?.status === 'ready' && candidates.length === 0 && (
            <p className="text-sm text-muted-foreground">No recurring segments found.</p>
          )}

          {candidates.length > 0 && (
            <ul className="flex-1 overflow-y-auto divide-y divide-border border border-border rounded">
              {candidates.map((c) => (
                <li key={`${c.start}-${c.end}`} className="flex items-center gap-3 px-3 py-2 text-sm">
                  <div className="flex-1 min-w-0">
                    <span className="font-mono text-sm">
                      {formatTimestamp(c.start)} - {formatTimestamp(c.end)}
                    </span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      {(c.end - c.start).toFixed(2)}s
                    </span>
                    {c.episodeMatches != null && (
                      <span className="ml-2 px-1.5 py-0.5 text-xs rounded font-medium bg-blue-500/20 text-blue-600 dark:text-blue-400">
                        matched in {c.episodeMatches} ep{c.episodeMatches === 1 ? '' : 's'}
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    className={`shrink-0 px-3 py-1.5 rounded ${primaryBtn} text-xs`}
                    onClick={() => setSeed(c)}
                  >
                    Make template
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {seed && targetEp && (
        <CueMarkModal
          podcastSlug={slug}
          episodeId={targetEp.id}
          episodeTitle={targetEp.title}
          episodeDuration={targetEp.duration ?? 0}
          initialStart={seed.start}
          initialEnd={seed.end}
          captureMinSeconds={captureMinSeconds}
          captureMaxSeconds={captureMaxSeconds}
          captureMaxIntroSeconds={captureMaxIntroSeconds}
          captureMaxOutroSeconds={captureMaxOutroSeconds}
          onClose={() => setSeed(null)}
          onSaved={onSaved}
          onFinalSave={() => setSeed(null)}
        />
      )}
    </>
  );
}
