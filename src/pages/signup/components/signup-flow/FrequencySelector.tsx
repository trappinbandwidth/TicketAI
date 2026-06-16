import { Button } from 'src/components/ui';

interface Frequency {
    savingsPercent: number | null;
    savingsBadge: string | null;
    label: string;
    key: string;
}

interface FrequencySelectorProps {
    frequencies: Frequency[];
    selectedFrequency: string;
    onFrequencyChange: (key: string) => void;
}

export default function FrequencySelector({
    frequencies,
    selectedFrequency,
    onFrequencyChange,
}: FrequencySelectorProps) {
    if (frequencies.length === 0) {
        return <p className="text-sm text-gray-500">Loading frequencies...</p>;
    }

    return (
        <div className="mb-3 flex gap-0.5 rounded-2xl bg-gray-100 p-1.5">
            {frequencies.map((freq) => (
                <Button
                    key={freq.key}
                    type="button"
                    size="sm"
                    onClick={() => onFrequencyChange(freq.key)}
                    className={`relative flex-1 py-2 text-[0.85rem] capitalize ${
                        selectedFrequency === freq.key
                            ? 'bg-white text-[#0D3E6B] shadow-[0_2px_8px_rgba(0,0,0,0.1)] hover:bg-white'
                            : 'bg-transparent text-slate-500 shadow-none hover:bg-slate-200 hover:text-slate-700'
                    }`}
                >
                    {freq.label}
                    {freq.savingsBadge && (
                        <span
                            className="absolute -top-2.5 whitespace-nowrap rounded-full bg-green-600 px-2 py-0.5 text-[0.65rem] font-semibold text-white"
                            style={{ right: freq.key === 'quarterly' ? -8 : -4 }}
                        >
                            {freq.savingsBadge}
                        </span>
                    )}
                </Button>
            ))}
        </div>
    );
}
