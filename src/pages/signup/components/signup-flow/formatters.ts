/**
 * Format phone number to (XXX) XXX-XXXX format
 */
export const formatPhoneNumber = (value: string): string => {
    const numbers = value.replace(/\D/g, '');
    if (numbers.length <= 3) return numbers;
    if (numbers.length <= 6) return `(${numbers.slice(0, 3)}) ${numbers.slice(3)}`;
    return `(${numbers.slice(0, 3)}) ${numbers.slice(3, 6)}-${numbers.slice(6, 10)}`;
};

/**
 * Format card number to XXXX XXXX XXXX XXXX format
 */
export const formatCardNumber = (value: string): string => {
    const numbers = value.replace(/\D/g, '');
    const groups = numbers.match(/.{1,4}/g);
    return groups ? groups.join(' ') : '';
};

/**
 * Format expiry date to MM/YY format
 */
export const formatExpiry = (value: string): string => {
    const numbers = value.replace(/\D/g, '');
    if (numbers.length <= 2) return numbers;
    return `${numbers.slice(0, 2)}/${numbers.slice(2, 4)}`;
};
