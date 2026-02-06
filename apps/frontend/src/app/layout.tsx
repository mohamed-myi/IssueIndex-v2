import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: {
    template: "%s | IssueIndex",
    default: "IssueIndex",
  },
  description: "Find high-quality open source issues to contribute to today.",
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: "IssueIndex",
    images: [
      {
        url: "/og-image.png", // I don't have this image yet but good practice to link
        width: 1200,
        height: 630,
        alt: "IssueIndex Platform",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "IssueIndex",
    description: "Find high-quality open source issues to contribute to today.",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

