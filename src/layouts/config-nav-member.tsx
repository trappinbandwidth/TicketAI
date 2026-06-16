import LucideIcon from 'src/components/lucide-icon';

export const LucideNavIcon = (name: string) => <LucideIcon name={name} style={{ width: '100%', height: '100%' }} />;

export const memberNavData = [
    {
        title: 'Home',
        path: '/member-dashboard',
        icon: LucideNavIcon('House'),
    },
    {
        title: 'Tickets',
        path: '/member-tickets',
        icon: LucideNavIcon('FileText'),
    },
    {
        title: 'Referral',
        path: '/member-referral',
        icon: LucideNavIcon('UserPlus'),
    },
    {
        title: 'Rewards',
        path: '/member-rewards',
        icon: LucideNavIcon('Gift'),
    },
    {
        title: 'Support',
        path: '/member-support',
        icon: LucideNavIcon('MessageSquare'),
    },
];
