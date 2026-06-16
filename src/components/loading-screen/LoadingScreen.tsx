/**
 * LoadingScreen - Modern loading component
 * Optimized for mobile devices (iOS & Android)
 * Provides smooth, engaging loading experience during Suspense fallback
 */
export default function LoadingScreen() {
    return (
        <div
            className="fixed inset-0 z-[9999] flex items-center justify-center bg-white px-2 text-center"
            style={{
                paddingTop: 'env(safe-area-inset-top, 0px)',
                paddingBottom: 'env(safe-area-inset-bottom, 0px)',
                animation: 'fadeInLoading 0.5s ease-out',
            }}
        >
            <style>{`@keyframes fadeInLoading { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } } @keyframes shimmerLoading { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }`}</style>
            <div className="flex flex-col items-center gap-3 sm:gap-4">
                {/* Animated Logo Circle */}
                <div className="relative flex items-center justify-center">
                    {/* Spinning outer ring */}
                    <div className="absolute h-[100px] w-[100px] animate-spin rounded-full border-[3px] border-transparent border-r-[#0D3E6B] border-t-[#0D3E6B] sm:h-[120px] sm:w-[120px]" />

                    {/* Inner pulsing background */}
                    <div className="flex h-20 w-20 animate-pulse items-center justify-center rounded-full bg-[#EAF1F8] shadow-[0_8px_24px_rgba(13,62,107,0.15)] sm:h-24 sm:w-24">
                        {/* CDL Text */}
                        <span
                            className="text-[1.75rem] font-extrabold tracking-[0.5px] sm:text-[2.125rem]"
                            style={{
                                background: 'linear-gradient(135deg, #0D3E6B 0%, #1e3a5f 100%)',
                                backgroundClip: 'text',
                                WebkitBackgroundClip: 'text',
                                WebkitTextFillColor: 'transparent',
                            }}
                        >
                            CDL
                        </span>
                    </div>
                </div>

                {/* Loading Text and Progress */}
                <div className="flex flex-col items-center gap-2">
                    <h2 className="text-base font-semibold text-gray-900 sm:text-lg">
                        Loading...
                    </h2>

                    {/* Progress Bar with Shimmer */}
                    <div className="relative h-1 w-[180px] overflow-hidden rounded bg-gray-200 sm:w-[220px]">
                        <div
                            className="absolute left-0 top-0 h-full w-1/2"
                            style={{
                                background: 'linear-gradient(90deg, transparent, rgba(13, 62, 107, 0.6), transparent)',
                                animation: 'shimmerLoading 1.5s ease-in-out infinite',
                            }}
                        />
                    </div>

                    {/* Animated Dots */}
                    <div className="flex gap-1 pt-1">
                        {[0, 1, 2].map((index) => (
                            <div
                                key={index}
                                className="h-2 w-2 animate-pulse rounded-full bg-[#0D3E6B]"
                                style={{ animationDelay: `${index * 0.2}s` }}
                            />
                        ))}
                    </div>

                    {/* Caption */}
                    <p className="mt-0.5 text-xs text-gray-500 sm:text-[0.8125rem]">
                        Please wait while we load your content
                    </p>
                </div>
            </div>
        </div>
    );
}
