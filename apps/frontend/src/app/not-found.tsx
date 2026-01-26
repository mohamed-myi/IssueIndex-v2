import Link from "next/link";
import { FileQuestion } from "lucide-react";

export default function NotFound() {
    return (
        <div className="min-h-screen flex flex-col items-center justify-center bg-[#0b0d12] text-[#e6e9f2] p-4">
            <div className="text-center space-y-6">
                <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-2xl bg-[#6366f1]/10 border border-[#6366f1]/20">
                    <FileQuestion className="h-10 w-10 text-[#6366f1]" />
                </div>

                <div className="space-y-2">
                    <h1 className="text-4xl font-bold tracking-tight">404</h1>
                    <p className="text-lg font-medium text-white/80">Page not found</p>
                    <p className="text-white/50 max-w-[400px]">
                        The page you are looking for might have been removed, had its name changed, or is temporarily unavailable.
                    </p>
                </div>

                <div className="pt-4">
                    <Link
                        href="/"
                        className="inline-flex h-10 items-center justify-center rounded-xl bg-[#6366f1] px-8 text-sm font-medium text-white transition-colors hover:bg-[#6366f1]/90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
                    >
                        Back to Home
                    </Link>
                </div>
            </div>
        </div>
    );
}
