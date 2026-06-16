import {
  ALargeSmall,
  ArrowLeft,
  ArrowRight,
  ArrowUpCircle,
  Award,
  Calendar,
  Camera,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Chrome,
  Circle,
  CircleAlert,
  CircleCheck,
  CircleCheckBig,
  CircleX,
  Clock,
  CloudUpload,
  CalendarDays,
  Copy,
  CreditCard,
  Crown,
  DollarSign,
  Download,
  Eye,
  Facebook,
  File,
  FileCheck,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  Gift,
  Hash,
  History,
  House,
  IdCard,
  Image,
  Info,
  Instagram,
  Linkedin,
  LoaderCircle,
  Lock,
  LockOpen,
  LogOut,
  LucideProps,
  Mail,
  MapPin,
  Medal,
  MessageSquare,
  MessageSquareText,
  Music,
  Pen,
  Phone,
  PhoneCall,
  Plus,
  QrCode,
  Receipt,
  RefreshCw,
  Search,
  Send,
  Settings,
  Share2,
  Shield,
  ShieldCheck,
  Star,
  Store,
  Tag,
  Trash2,
  TriangleAlert,
  Upload,
  User,
  UserCheck,
  UserPen,
  UserPlus,
  Users,
  Wallet,
  X,
  Building2,
} from 'lucide-react';

const iconMap = {
  ALargeSmall,
  ArrowLeft,
  ArrowRight,
  Award,
  Calendar,
  Camera,
  ArrowUpCircle,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Chrome,
  Circle,
  CircleAlert,
  Building2,
  CircleCheck,
  CircleCheckBig,
  CircleX,
  CalendarDays,
  Clock,
  CreditCard,
  Crown,
  DollarSign,
  Download,
  Eye,
  Facebook,
  File,
  FileCheck,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  Gift,
  Hash,
  History,
  House,
  IdCard,
  Image,
  Info,
  Instagram,
  Linkedin,
  LoaderCircle,
  Lock,
  LockOpen,
  CloudUpload,
  LogOut,
  Mail,
  MapPin,
  Medal,
  MessageSquare,
  MessageSquareText,
  Music,
  Pen,
  Phone,
  PhoneCall,
  Plus,
  QrCode,
  Copy,
  Receipt,
  Share2,
  RefreshCw,
  Search,
  Send,
  Settings,
  Shield,
  ShieldCheck,
  Star,
  Store,
  Tag,
  Trash2,
  TriangleAlert,
  Upload,
  User,
  UserCheck,
  UserPen,
  UserPlus,
  Users,
  Wallet,
  X,
};

export type LucideIconName = keyof typeof iconMap;

interface LucideIconProps extends Omit<LucideProps, 'ref'> {
  name: LucideIconName | string;
  size?: number;
  width?: number;
  height?: number;
  color?: string;
  strokeWidth?: number;
  className?: string;
}

/**
 * Reusable Lucide Icon Component
 * 
 * @param name - The name of the Lucide icon to render
 * @param size - Uniform size for both width and height (default: 24)
 * @param width - Custom width (overrides size)
 * @param height - Custom height (overrides size)
 * @param color - Icon color (default: 'currentColor')
 * @param strokeWidth - Stroke width of the icon (default: 2)
 * @param className - Additional CSS classes
 * @param props - Additional Lucide icon props
 */
export const LucideIcon = ({
  name,
  size = 24,
  width,
  height,
  color = 'currentColor',
  strokeWidth = 2,
  className = '',
  ...props
}: LucideIconProps) => {
  const IconComponent = iconMap[name as LucideIconName];

  if (!IconComponent) {
    console.warn(`Icon "${name}" not found in lucide-react`);
    return null;
  }

  return (
    <IconComponent
      width={width || size}
      height={height || size}
      color={color}
      strokeWidth={strokeWidth}
      className={className}
      {...props}
    />
  );
};

export default LucideIcon;
