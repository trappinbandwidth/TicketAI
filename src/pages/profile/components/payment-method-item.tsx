import LucideIcon from 'src/components/lucide-icon';
import { Button } from 'src/components/ui';

interface PaymentMethodItemProps {
    method: any;
    onSetDefault: (id: string) => void;
    onRemove: (id: string) => void;
    isProcessing?: boolean;
}

export default function PaymentMethodItem({ method, onSetDefault, onRemove, isProcessing = false }: PaymentMethodItemProps) {
    const brand = method.brand || 'Visa';
    const isVisa = brand.toLowerCase() === 'visa';
    const isMastercard = brand.toLowerCase() === 'mastercard';
    const isAmex = brand.toLowerCase().includes('amex') || brand.toLowerCase().includes('american');
    const isDiscover = brand.toLowerCase() === 'discover';
    const isDefault = method.isDefault || method.status === 'Default';
    const cardLast4Digits = method.cardLast4Digits || method.last4 || '0000';
    const cardHolderName = method.cardHolderName || method.holderName || 'N/A';

    const expiryDate = method.expirationMonth && method.expirationYear
        ? `${method.expirationMonth}/${method.expirationYear.slice(-2)}`
        : method.expiry || 'MM/YY';

    const getCardGradientClassName = () => {
        if (isVisa) return 'from-blue-500 to-blue-700';
        if (isMastercard) return 'from-orange-500 to-red-600';
        if (isAmex) return 'from-blue-600 to-blue-800';
        if (isDiscover) return 'from-orange-600 to-orange-800';
        return 'from-gray-500 to-gray-700';
    };

    return (
        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-6">
            <div className={`mb-4 rounded-2xl bg-gradient-to-br ${getCardGradientClassName()} p-4 text-white`}>
                <div className="mb-8 flex items-center justify-between">
                    <div className="text-sm uppercase opacity-80">{brand}</div>
                    {isDefault && (
                        <div className="rounded-full bg-white/20 px-3 py-1 text-xs">Default</div>
                    )}
                </div>

                <div className="mb-4 text-xl tracking-wider">
                    •••• •••• •••• {cardLast4Digits}
                </div>

                <div className="flex items-center justify-between">
                    <div>
                        <div className="text-xs opacity-70">Cardholder</div>
                        <div className="text-sm">{cardHolderName}</div>
                    </div>
                    <div>
                        <div className="text-xs opacity-70">Expires</div>
                        <div className="text-sm">{expiryDate}</div>
                    </div>
                </div>
            </div>

            <div className="flex gap-3">
                {!isDefault && (
                    <Button
                        type="button"
                        fullWidth
                        onClick={() => onSetDefault(method.id)}
                        disabled={isProcessing}
                        variant="secondary"
                        className="flex-1 gap-2 rounded-xl border border-gray-300 bg-white py-2 text-sm text-[#1e3a5f] transition-colors hover:bg-gray-50"
                    >
                        <LucideIcon name="CheckCircle" size={16} />
                        Set as Default
                    </Button>
                )}
                <Button
                    type="button"
                    fullWidth
                    onClick={() => onRemove(method.id)}
                    disabled={isProcessing}
                    variant="secondary"
                    className="flex-1 gap-2 rounded-xl border border-red-300 bg-white py-2 text-sm text-[#dc2626] transition-colors hover:bg-red-50"
                >
                    <LucideIcon name="Trash2" size={16} />
                    Remove
                </Button>
            </div>
        </div>
    );
}
