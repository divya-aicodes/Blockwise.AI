import { Play, Pause, RotateCcw, SkipBack, SkipForward } from "lucide-react";
import { clock } from "../lib";
export default function TwinPlaybackControls({
  playing,
  onToggle,
  onRestart,
  onStep,
  speed,
  setSpeed,
  now,
  bounds,
  onScrub,
}: {
  playing: boolean;
  onToggle: () => void;
  onRestart: () => void;
  onStep: (n: number) => void;
  speed: number;
  setSpeed: (s: number) => void;
  now: number;
  bounds: [number, number];
  onScrub: (n: number) => void;
}) {
  return (
    <div className="playback-controls">
      <div className="playback-buttons">
        <button
          className="icon-button"
          onClick={onRestart}
          aria-label="Restart playback"
        >
          <RotateCcw size={17} />
        </button>
        <button
          className="icon-button"
          onClick={() => onStep(-1)}
          aria-label="Step backward one minute"
        >
          <SkipBack size={17} />
        </button>
        <button
          className="play-button"
          onClick={onToggle}
          aria-label={playing ? "Pause playback" : "Play playback"}
        >
          {playing ? <Pause size={18} /> : <Play size={18} />}
        </button>
        <button
          className="icon-button"
          onClick={() => onStep(1)}
          aria-label="Step forward one minute"
        >
          <SkipForward size={17} />
        </button>
      </div>
      <strong className="playback-time mono">{clock(now)}</strong>
      <div className="scrubber">
        <input
          type="range"
          aria-label="Simulation time"
          min={bounds[0]}
          max={bounds[1]}
          step={1000}
          value={now}
          onChange={(e) => onScrub(Number(e.target.value))}
        />
        <span>
          <small>00:00 IST</small>
          <small>24:00 IST</small>
        </span>
      </div>
      <select
        aria-label="Playback speed"
        value={speed}
        onChange={(e) => setSpeed(Number(e.target.value))}
      >
        <option value={0.5}>0.5×</option>
        <option value={1}>1×</option>
        <option value={2}>2×</option>
      </select>
      <small className="playback-scale">1× = 10 min / sec</small>
    </div>
  );
}
