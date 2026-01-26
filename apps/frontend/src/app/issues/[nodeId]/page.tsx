import { Metadata } from "next";
import IssueDetailClient from "./client";
import { fetchIssue } from "@/lib/api/endpoints";

type PageProps = {
    params: Promise<{ nodeId: string }>;
};

export async function generateMetadata(props: PageProps): Promise<Metadata> {
    const params = await props.params;
    try {
        const issue = await fetchIssue(params.nodeId);

        // Truncate body for description if needed (approx 160 chars is standard optimization)
        // Using body_preview from endpoints if available? fetchIssue returns IssueDetailResponse which relies on `body`.
        // Let's use body but truncate.
        const description = issue.body.slice(0, 160).replace(/\n/g, " ") + "...";

        return {
            title: issue.title,
            description: description,
            openGraph: {
                title: issue.title,
                description: description,
                type: "article",
                publishedTime: issue.github_created_at,
                authors: [issue.repo_name],
            },
            twitter: {
                card: "summary",
                title: issue.title,
                description: description,
            },
        };
    } catch (e) {
        return {
            title: "Issue Not Found",
            description: "This issue could not be loaded.",
        };
    }
}

export default function IssueDetailPage() {
    return <IssueDetailClient />;
}
