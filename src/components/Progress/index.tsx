import { HTMLAttributes } from 'react';

interface ProgressProps extends HTMLAttributes<HTMLDivElement> {
    value: number;
    label: string;
    barColor: string;
}

const Progress = ({ value, label, barColor, ...rest }: ProgressProps) => {
    const safeValue = Math.max(0, Math.min(100, value));

    return (
        <div className="mb-2 flex items-center" {...rest}>
            <div className="min-w-[30%]">
                <p className="text-base font-semibold text-[#0D3E6B] transition-all duration-150">
                    {label}
                </p>
            </div>
            <div className="mr-1 w-full">
                <div className="h-[10px] w-[92%] max-w-full overflow-hidden rounded-[5px] bg-gray-200">
                    <div
                        className="h-full rounded-[5px] transition-[width] duration-300"
                        style={{ width: `${safeValue}%`, backgroundColor: barColor }}
                    />
                </div>
            </div>
            <div className="min-w-[35px]">
                <span className="text-sm font-semibold" style={{ color: barColor }}>{`${Math.round(safeValue)}%`}</span>
            </div>
        </div>
    );
};

export default Progress;
