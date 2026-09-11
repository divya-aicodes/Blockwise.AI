import { useNavigate } from "react-router-dom";
import { ChevronDown, ArrowUpRight, Check } from "lucide-react";
import { useAppStore } from "../store/useAppStore";
export default function DemoGuide() {
  const s = useAppStore(),
    navigate = useNavigate();
  return (
    <div className="demo-guide">
      <button className="text-button" onClick={() => s.setGuide(!s.guideOpen)}>
        Demo guide <ChevronDown size={14} />
      </button>
      {s.guideOpen && (
        <div className="guide-popover">
          <span className="eyebrow">GUIDED WORKFLOW</span>
          <p>Follow one asset from condition to a human decision.</p>
          <ol>
            {[
              "Select a high-risk asset",
              "Inspect condition and calculate risk",
              "Create a maintenance requirement",
              "Detect timetable conflicts",
              "Generate and compare alternatives",
              "Simulate a selected plan",
              "Explore digital-twin playback",
              "Approve, modify or reject",
              "Review simulation feedback",
            ].map((item, i) => (
              <li key={item}>
                <span>{i + 1}</span>
                {item}
              </li>
            ))}
          </ol>
          <button
            className="primary full"
            disabled={!s.assets.length}
            onClick={() => {
              s.startDemo();
              navigate("/map");
            }}
          >
            Start guided demo <ArrowUpRight size={16} />
          </button>
          {s.demo && (
            <small className="success inline">
              <Check size={13} /> High-risk asset selected. Inspect it to
              continue.
            </small>
          )}
        </div>
      )}
    </div>
  );
}
