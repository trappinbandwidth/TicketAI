// ticket icon
import Close from './assets/TicketIcon/close.svg';
import Assigned from './assets/TicketIcon/assigned.svg';
import Received from './assets/TicketIcon/received.svg';
import Processing from './assets/TicketIcon/processing.svg';
import Waiting from './assets/TicketIcon/waitingcourt.svg';

// Membership tiers
export const MEMBERSHIP_TIERS = {
  SILVER: 'silver',
  GOLD: 'gold',
  PLATINUM: 'platinum',
  NONE: 'none',
};

// Pricing structure
export const PRICING = {
  monthly: {
    silver: { price: 0, billing: '/month' },
    gold: { price: 44.99, billing: '/month' },
    platinum: { price: 68.99, billing: '/month' },
  },
  quarterly: {
    silver: { price: 0, billing: '/month', total: 0 },
    gold: { price: 38.09, billing: '/month', total: 114.27 },
    platinum: { price: 58.41, billing: '/month', total: 175.23 },
  },
  annually: {
    silver: { price: 0, billing: '/month', total: 0 },
    gold: { price: 37.49, billing: '/month', total: 449.90 },
    platinum: { price: 57.49, billing: '/month', total: 689.90 },
  },
};
export const TICKET_STATUSES_ICON = {
  'Ticket Received': Received,
  'Sent to Attorney': Assigned,
  "Driver Hasn't Paid": Processing,
  'Attny Assigned': Assigned,
  'Waiting on new Court Date': Waiting,
  'Agreement in Process': Processing,
  'Attorney Complete': Assigned,
  'Ticket Closed': Close,
};
// Features per tier
export const TIER_FEATURES = {
  silver: [
    'Basic Attorney Network',
    'Limited Coverage',
    'Standard Support',
  ],
  gold: [
    'Nationwide Attorney Network',
    '$0 Deductible for Tickets',
    '$500 Deductible for Trials',
    'DataQ Challenges Included',
    'Access to Thousands of Discounts',
    'Roadside Assistance Network',
    'Spouse covered',
  ],
  platinum: [
    'Nationwide Attorney Network',
    '$0 Deductible for Tickets',
    'Full Trial Coverage',
    'DataQ Challenges Included',
    'Access to Thousands of Discounts',
    'Roadside Assistance Network',
    'Spouse covered',
  ],
};

// UI styling per tier
export const TIER_STYLING = {
  silver: {
    gradient: 'linear-gradient(to bottom right, #a0a0a0, #4d4d4d)',
    boxShadow:'0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    icon: 'Star',
  },
  gold: {
    gradient: 'linear-gradient(to bottom right, #F2AE26, #d4951f)',
    boxShadow:'0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    icon: 'Award',
  },
  platinum: {
    gradient: 'linear-gradient(to bottom right, #1e3a5f, #0f1f3a)',
    boxShadow:'0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    icon: 'Crown',
  },
  none: {
    gradient: 'linear-gradient(180deg, #99a1af 0%, #99a1af 100%)',
    boxShadow:'0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    icon: 'X',
  },
};

// Membership names
export const TIER_NAMES = {
  silver: 'Silver Membership',
  gold: 'Gold Membership',
  platinum: 'Platinum Membership',
  none: 'No Membership',
};

// Upgrade paths (which tiers can upgrade to which)
export const UPGRADE_PATHS = {
  silver: [MEMBERSHIP_TIERS.GOLD, MEMBERSHIP_TIERS.PLATINUM],
  gold: [MEMBERSHIP_TIERS.PLATINUM],
  platinum: [],
  none: [MEMBERSHIP_TIERS.SILVER, MEMBERSHIP_TIERS.GOLD, MEMBERSHIP_TIERS.PLATINUM],
};

// Get upgrade message for a tier
export const getUpgradeMessage = (tier: string): string => {
  switch (tier) {
    case MEMBERSHIP_TIERS.SILVER:
      //return 'Want more benefits? Upgrade to Gold';
      return '';
    case MEMBERSHIP_TIERS.GOLD:
      //return 'Want complete coverage? Upgrade to Platinum';
      return '';
    case MEMBERSHIP_TIERS.PLATINUM:
      //return 'Complete coverage with premium benefits';
      return '';
    case MEMBERSHIP_TIERS.NONE:
      return 'You don\'t have an active membership.';
    default:
      return '';
  }
};
