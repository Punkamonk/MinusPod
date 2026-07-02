import type { ReactNode } from 'react';
import { Play, Pause, SkipBack, SkipForward, Rewind, FastForward, Square } from 'lucide-react';
import { formatTime } from '../../utils/adReviewHelpers';
import { PLAYBACK_RATES, ghostBtn, primaryBtn, selectionBtn } from './controlStyles';

// Shared playback transport bar for the audio-editor modals (AdReviewModal and
// CueMarkModal). Purely presentational: the host owns the <audio> element, the
// playhead loop, and all handlers. Rendering from one component keeps the two
// modals' controls identical. All controls (transport, the optional amber
// "play selection" icon, and the speed selector) sit on one centered row that
// wraps as a unit on narrow screens; the selection readout is centered below.
interface TransportBarProps {
  isPlaying: boolean;
  onTogglePlay: () => void;
  onSeekToStart: () => void;
  onSeekToEnd: () => void;
  onSeekRelative: (delta: number) => void;
  onStop: () => void;
  playbackRate: number;
  onPlaybackRateChange: (rate: number) => void;
  currentTime: number;
  selectionDuration: number;
  inSelection: boolean;
  selectionLabel?: string;
  onPlaySelection?: () => void;
  // Optional override for the selection-length readout (e.g. the cue modal
  // shows a precise "1.00s" + validation instead of the default mm:ss).
  selectionInfo?: ReactNode;
}

function TransportBar({
  isPlaying,
  onTogglePlay,
  onSeekToStart,
  onSeekToEnd,
  onSeekRelative,
  onStop,
  playbackRate,
  onPlaybackRateChange,
  currentTime,
  selectionDuration,
  inSelection,
  selectionLabel = 'in selection',
  onPlaySelection,
  selectionInfo,
}: TransportBarProps) {
  return (
    <div className="mt-3 px-3 py-2 rounded-lg bg-secondary/50 border border-border">
      {/* Primary controls -- the transport cluster is centered as the focal
          element; the speed selector is pinned to the right of the SAME row
          (absolute, so it never wraps to its own line on a narrow modal). */}
      <div className="relative flex items-center justify-center gap-0.5">
        <button type="button" onClick={onSeekToStart} className={`p-1.5 rounded ${ghostBtn}`} title="Jump to START pin">
          <SkipBack className="w-4 h-4" />
        </button>
        <button type="button" onClick={() => onSeekRelative(-10)} className={`p-1.5 rounded ${ghostBtn}`} title="Back 10s">
          <Rewind className="w-4 h-4" />
        </button>
        <button type="button" onClick={onTogglePlay} className={`p-1.5 rounded-full ${primaryBtn}`} title="Play / pause (Space)">
          {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
        </button>
        {onPlaySelection && (
          <button
            type="button"
            onClick={onPlaySelection}
            className={`ml-0.5 ${selectionBtn}`}
            title="Play the selection only"
            aria-label="Play selection"
          >
            <Play className="w-4 h-4" />
          </button>
        )}
        <button type="button" onClick={() => onSeekRelative(10)} className={`p-1.5 rounded ${ghostBtn}`} title="Forward 10s">
          <FastForward className="w-4 h-4" />
        </button>
        <button type="button" onClick={onSeekToEnd} className={`p-1.5 rounded ${ghostBtn}`} title="Jump to END pin">
          <SkipForward className="w-4 h-4" />
        </button>
        <button type="button" onClick={onStop} className={`p-1.5 rounded ${ghostBtn}`} title="Stop (pause + return to START)">
          <Square className="w-4 h-4" />
        </button>
        <label className="absolute right-1 top-1/2 -translate-y-1/2 inline-flex items-center" title="Playback speed">
          <span className="sr-only">Playback speed</span>
          <select
            value={playbackRate}
            onChange={(e) => onPlaybackRateChange(Number(e.target.value))}
            aria-label="Playback speed"
            className={`appearance-none h-7 pl-1.5 pr-4 rounded text-xs font-semibold tabular-nums cursor-pointer ${ghostBtn} ${playbackRate !== 1 ? 'text-foreground' : ''} focus:outline-hidden focus:ring-2 focus:ring-ring`}
          >
            {PLAYBACK_RATES.map((r) => (
              <option key={r} value={r}>{r}&times;</option>
            ))}
          </select>
          <svg
            className="pointer-events-none absolute right-1 top-1/2 -translate-y-1/2 w-3 h-3 opacity-60"
            viewBox="0 0 12 12"
            fill="none"
            aria-hidden="true"
          >
            <path d="M3 5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </label>
      </div>
      {/* Secondary row: selection readout, centered under the controls. */}
      <div className="mt-2 flex items-center justify-center gap-2 flex-wrap text-xs tabular-nums text-muted-foreground">
        <span className="text-foreground">{formatTime(currentTime)}</span>
        <span>/</span>
        {selectionInfo ?? <span>{formatTime(selectionDuration)} selection</span>}
        {inSelection && (
          <span className="ml-1 px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-500 text-[10px] font-semibold uppercase tracking-wider">
            {selectionLabel}
          </span>
        )}
      </div>
    </div>
  );
}

export default TransportBar;
