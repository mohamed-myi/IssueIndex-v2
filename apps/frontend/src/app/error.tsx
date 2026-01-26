"use client";

import { useEffect } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Error({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        // Log the error to an error reporting service
        console.error(error);
    }, [error]);

    return (
        <div className="min-h-screen flex flex-col items-center justify-center bg-[#0b0d12] text-[#e6e9f2] p-4">
            <div className="max-w-md w-full text-center space-y-6">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-red-500/10 border border-red-500/20">
                    <AlertCircle className="h-8 w-8 text-red-500" />
                </div>

                <div className="space-y-2">
                    <h2 className="text-2xl font-bold tracking-tight">Something went wrong!</h2>
                    <p className="text-white/50 text-sm">
                        We encountered an unexpected error. Our team has been notified.
                    </p>
                </div>

                <div className="p-4 rounded-lg bg-white/5 border border-white/10 text-left font-mono text-xs text-red-400 break-all">
                    {error.message || "Unknown error"}
                </div>

                <div className="flex justify-center gap-4">
                    <Button
                        onClick={() => window.location.href = "/"}
                        variant="outline"
                        className="border-white/10 hover:bg-white/5 hover:text-white"
                    >
                        Go Home
                    </Button>
                    <Button
                        onClick={() => reset()}
                        className="bg-[#6366f1] hover:bg-[#6366f1]/90 text-white"
                    >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Try again
                    </Button>
                </div>
            </div>
        </div>
    );
}
