import { fDate } from 'src/utils/format-time';
import LucideIcon from 'src/components/lucide-icon';
import { Button } from 'src/components/ui';

interface TransactionListItemProps {
    transaction: any;
    onViewReceipt: (transaction: any) => void;
    onDownload: (transaction: any) => void;
}

export default function TransactionListItem({ transaction, onViewReceipt, onDownload }: TransactionListItemProps) {
    const status = transaction.status || 'Completed';
    const isSuccess = status.toLowerCase() === 'completed';
    const isPending = status.toLowerCase() === 'pending';
    const title = transaction.opportunityName || transaction.name || transaction.reason || 'Transaction';

    const getTransactionIcon = (): string => {
        const type = transaction.transactionType?.toLowerCase() || 'normal';
        if (type === 'normal' || type.includes('subscription') || type.includes('membership')) {
            return 'CreditCard';
        }
        if (type === 'fee' || type === 'charge') {
            return 'DollarSign';
        }
        if (type === 'refund' || type === 'adjustment') {
            return 'Receipt';
        }
        return 'DollarSign';
    };

    const getIconColor = () => {
        const type = transaction.transactionType?.toLowerCase() || 'normal';
        if (type === 'normal' || type.includes('subscription') || type.includes('membership')) {
            return '#0D3E6B';
        }
        if (type === 'fee' || type === 'charge') {
            return '#F2AE26';
        }
        if (type === 'refund' || type === 'adjustment') {
            return '#16a34a';
        }
        return '#4b5563';
    };

    const iconColor = getIconColor();

    return (
        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-3 sm:p-4">
            <div className="mb-2 sm:mb-3 flex items-start gap-2 sm:gap-3">
                <div className="flex h-8 w-8 sm:h-10 sm:w-10 shrink-0 items-center justify-center rounded-xl border border-gray-200 bg-white">
                    <span style={{ color: iconColor }}>
                        <LucideIcon name={getTransactionIcon()} size={20} />
                    </span>
                </div>
                <div className="min-w-0 flex-1">
                    <div className="mb-1 break-words text-sm leading-tight text-[#1e3a5f] sm:text-base">
                        {title}
                    </div>
                    <div className="flex items-center gap-1.5 sm:gap-2 text-xs text-gray-500 sm:text-sm">
                        <LucideIcon name="Calendar" size={16} />
                        <span className="truncate">{fDate(transaction.dueDate || transaction.createdAt)}</span>
                    </div>
                </div>
                <div className="shrink-0 text-right">
                    <div className="mb-1 whitespace-nowrap text-sm text-[#1e3a5f] sm:text-base">
                        ${(transaction.amount || 0).toFixed(2)}
                    </div>
                    <span
                        className="whitespace-nowrap rounded-full px-1.5 py-0.5 text-xs sm:px-2 sm:py-1 sm:text-sm"
                        style={{
                            backgroundColor: isSuccess
                                ? 'rgb(220 252 231)'
                                : isPending
                                    ? 'rgb(254 243 199)'
                                    : 'rgb(254 226 226)',
                            color: isSuccess ? 'rgb(21 128 61)' : isPending ? 'rgb(180 83 9)' : 'rgb(185 28 28)',
                        }}
                    >
                        {status}
                    </span>
                </div>
            </div>

            <div className="flex gap-2 border-t border-gray-200 pt-2 sm:pt-3">
                <Button
                    type="button"
                    fullWidth
                    onClick={() => onViewReceipt(transaction)}
                    variant="secondary"
                    className="gap-1.5 rounded-xl border border-gray-300 bg-white px-2 text-xs text-gray-700 hover:bg-gray-50 sm:gap-2 sm:px-3 sm:text-sm"
                >
                    <LucideIcon name="Eye" size={16} />
                    <span className="truncate">View Receipt</span>
                </Button>
                <Button
                    type="button"
                    fullWidth
                    onClick={() => onDownload(transaction)}
                    className="gap-1.5 rounded-xl bg-[#1e3a5f] px-2 text-xs text-white hover:bg-[#152d47] sm:gap-2 sm:px-3 sm:text-sm"
                >
                    <LucideIcon name="Download" size={16} />
                    <span className="truncate">Download</span>
                </Button>
            </div>
        </div>
    );
}
