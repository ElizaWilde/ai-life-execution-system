export const AVAILABLE_TIME_OPTIONS = [
  { value: "120", label: "<3h", hint: "Light window" },
  { value: "240", label: "3h-5h", hint: "Short day" },
  { value: "360", label: "5h-7h", hint: "Balanced day" },
  { value: "480", label: "7h-9h", hint: "Extended day" },
  { value: "600", label: ">9h", hint: "Maximum window" },
] as const;

export function availableTimeBucket(minutes: number) {
  if (minutes < 180) return "120";
  if (minutes <= 300) return "240";
  if (minutes <= 420) return "360";
  if (minutes <= 540) return "480";
  return "600";
}
