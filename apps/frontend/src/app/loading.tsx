import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
    return (
        <div className="min-h-screen bg-[#0b0d12] text-white/50">
            {/* Fake TopNav */}
            <div className="fixed top-0 left-0 right-0 h-[var(--topnav-height)] border-b border-white/5 bg-[#0b0d12]" />

            <div className="flex pt-[var(--topnav-height)]">
                {/* Fake Sidebar */}
                <div className="hidden md:block w-[var(--sidebar-width)] h-[calc(100vh-var(--topnav-height))] border-r border-white/5 p-6 space-y-6">
                    <Skeleton className="h-4 w-24 bg-white/5" />
                    <Skeleton className="h-4 w-32 bg-white/5" />
                    <Skeleton className="h-4 w-20 bg-white/5" />
                </div>

                {/* Content area */}
                <main className="flex-1 p-8 space-y-6">
                    <div className="flex items-center justify-between">
                        <Skeleton className="h-8 w-48 bg-white/5" />
                        <Skeleton className="h-8 w-24 bg-white/5" />
                    </div>

                    <div className="space-y-4">
                        {Array.from({ length: 5 }).map((_, i) => (
                            <div key={i} className="flex gap-4 p-4 rounded-xl border border-white/5 bg-[#111420]/50">
                                <Skeleton className="h-12 w-12 rounded-full bg-white/5" />
                                <div className="space-y-2 flex-1">
                                    <Skeleton className="h-4 w-3/4 bg-white/5" />
                                    <Skeleton className="h-3 w-1/2 bg-white/5" />
                                </div>
                            </div>
                        ))}
                    </div>
                </main>
            </div>
        </div>
    );
}
