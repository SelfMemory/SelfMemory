import { KratosFlow } from "@/components/KratosFlow";

export const metadata = { title: "Create account" };

export default async function Registration({ searchParams }: { searchParams: Promise<Record<string, string>> }) {
  return <KratosFlow type="registration" params={await searchParams} />;
}
