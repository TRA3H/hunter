interface MatchScoreDotProps {
  score: number;
  size?: "sm" | "lg";
}

function scoreColor(score: number): string {
  if (score >= 85) return "#22c55e";
  if (score >= 70) return "#f59e0b";
  return "#6b7280";
}

export default function MatchScoreDot({ score, size = "sm" }: MatchScoreDotProps) {
  const px = size === "lg" ? 40 : 32;
  const innerPx = px - 6;
  const color = scoreColor(score);
  const pct = Math.min(100, Math.max(0, score));

  return (
    <div
      className="relative rounded-full flex items-center justify-center shrink-0"
      style={{
        width: px,
        height: px,
        background: `conic-gradient(${color} ${pct * 3.6}deg, hsl(240 14% 19%) 0deg)`,
      }}
    >
      <div
        className="rounded-full bg-card flex items-center justify-center"
        style={{ width: innerPx, height: innerPx }}
      >
        <span
          className="font-semibold tabular-nums"
          style={{ fontSize: size === "lg" ? 13 : 11, color }}
        >
          {score}
        </span>
      </div>
    </div>
  );
}
