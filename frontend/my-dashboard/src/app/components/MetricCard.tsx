const toneMap: Record<string, string> = {
  green: "text-green-300",
  yellow: "text-yellow-300",
  blue: "text-blue-300",
  purple: "text-purple-300",
  pink: "text-pink-300",
};

export default function MetricCard({
  title, value, tone, span = 1, mono = false,
}: { title: string; value: string; tone: keyof typeof toneMap; span?: 1|2|3; mono?: boolean }) {
  return (
    <div className={`col-span-${span} bg-gray-900 p-4 rounded-2xl border border-gray-800`}>
      <h2 className={`text-lg font-semibold ${toneMap[tone]}`}>{title}</h2>
      <p className={`text-xl font-bold text-white mt-2 whitespace-pre-line ${mono ? "font-mono text-base" : ""}`}>
        {value}
      </p>
    </div>
  );
}
