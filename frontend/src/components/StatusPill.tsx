export default function StatusPill({ value }: { value: string }) {
  return <span className={`status-pill status-${value.toLowerCase().replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>;
}
