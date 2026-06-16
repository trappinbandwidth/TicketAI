import { useNavigate } from 'react-router-dom';
import { DashboardContent } from 'src/layouts/dashboard';
import LucideIcon from 'src/components/lucide-icon';
import { Button } from 'src/components/ui';

export default function PrivacySecurityPage() {
    const navigate = useNavigate();

    return (
        <DashboardContent>
            <div className="mb-3 flex items-center">
                <Button
                    type="button"
                    onClick={() => navigate('/profile')}
                    variant="secondary"
                    size="icon"
                    className="mr-2 rounded-full border border-slate-200 bg-white text-[#1a365d] shadow-sm"
                >
                    <LucideIcon name="ChevronLeft" size={24} />
                </Button>
                <div>
                    <h1 className="text-2xl font-extrabold text-[#1a365d]">
                        Privacy & Security
                    </h1>
                    <p className="text-sm text-gray-500">
                        Control your data
                    </p>
                </div>
            </div>

            <div className="mb-3 rounded-lg bg-white p-1 shadow-sm">
                <div className="flex items-center gap-1.5 p-2">
                    <LucideIcon name="ShieldCheck" size={24} color="#1a365d" />
                    <p className="text-base font-bold text-[#1a365d]">
                        Privacy Controls
                    </p>
                </div>

                <div className="space-y-2 p-2">
                    <Button
                        variant="secondary"
                        fullWidth
                        size="lg"
                        onClick={() => window.open('https://rigresolve.com/privacy', '_blank')}
                        className="justify-start gap-2 border border-slate-200 bg-white px-4 text-[#1a365d]"
                    >
                        <LucideIcon name="FileText" size={20} />
                        View Privacy Policy
                    </Button>

                    <Button
                        variant="secondary"
                        fullWidth
                        size="lg"
                        className="justify-start gap-2 border border-slate-200 bg-white px-4 text-[#1a365d]"
                    >
                        <LucideIcon name="Download" size={20} />
                        Download My Data
                    </Button>

                    <Button
                        variant="danger"
                        fullWidth
                        size="lg"
                        className="justify-start gap-2 px-4"
                    >
                        <LucideIcon name="Trash2" size={20} />
                        Delete Account
                    </Button>
                </div>
            </div>
        </DashboardContent>
    );
}
